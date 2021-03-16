# pylint: disable-msg=E0611,E0401,C0103,W0703,R0903

"""Core API calls and classes for ProgBG

This module contains all the related API calls for creating and managing
t.format(str(bench_args[val]))ihe plan.py files, graphing is handled within graphing.py.

sA special case we have to handling is the handling of global variables
within ProgBG. Since we dynamically pull in a users file, their module
has a different set of globals then ours, so upon importing their
python file we must edit our globals to be equivalent to theirs.
This can be seen in the function import_plan.

"""

import os
import sys
import importlib
import inspect
import sqlite3
import shutil

import types
import subprocess
from typing import List, Dict
from pprint import pformat
from pprint import pprint

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .format import format_fig, check_formatter
from .util import Backend, Variables, dump_obj, error
from .util import silence_print, restore_print

from .globals import _sb_registered_benchmarks, _sb_registered_backend
from .globals import _sb_executions, _sb_graphs, _sb_rnames
from .globals import _sb_figures, GRAPHS_DIR
from .globals import _EDIT_GLOBAL_TABLE


class Metrics:
    def __init__(self):
        self._vars = dict()
        self._consts = dict()

    def add_metric(self, key, val):
        if key not in self._vars:
            self._vars[key] = [val]
        else:
            self._vars[key].append(val)

    def __getitem__(self, key):
        if key in self._vars:
            return self._vars[key]

        return self._consts[key]

    def add_constant(self, key, val):
        self._consts[key] = val

    def combinate(self, other: Dict):
        for key, val in other._vars.items():
            if key in self._vars:
                self._vars[key].append(val)
            else:
                self._vars[key] = val

    def get_stats(self):
        obj = dict()
        for key, val in self._vars.items():
            obj[key] = np.mean(val)
            obj[key + "_std"] = np.std(val)
        for key, val in self._consts.items():
            obj[key] = val

        return obj

    def __repr__(self):
        obj = self.get_stats()
        return pformat(obj)


def _retrieve_named_backends(back_obj):
    named = []
    for backend in back_obj.backends:
        cls = _sb_registered_backend[backend]
        required_init = inspect.getfullargspec(cls.init).args
        required_uninit = inspect.getfullargspec(cls.uninit).args
        named.extend(required_init + required_uninit)

    return named


def _retrieve_named_benchmarks(name):
    cls = _sb_registered_benchmarks[name]
    required_run = inspect.getfullargspec(cls.run).args[2:]

    return required_run


def _retrieve_backends(back_obj):
    return [_sb_registered_backend[back] for back in back_obj.backends]


def check_file_backend(file_name):
    """Checks what the backend of a given filename is
    Files are orgnized into WORKLOAD_backend_BACKEND_...
    For workloads that don't used a backend the _backend is
    not there
    """
    chunks = file_name.split('_')
    if chunks[1] != '_backend':
        return None

    return chunks[2]


def registerbenchmark_sh(name: str, file_path: str):
    custom_backend = type(name, (object, ), {})

    @staticmethod
    def run(backend, out_file):
        out = open(out_file, 'w')
        shell = subprocess.Popen("sh", stdin=subprocess.PIPE, stdout=out)
        script = open(file_path, "r").read()
        script += "\n"
        shell.stdin.write(str.encode(script))
        script = open(file_path, "r").read()
        run_str = "run\n".format(i)
        shell.stdin.write(str.encode(run_str))
        shell.stdin.close()
        shell.wait()

    custom_backend.run = run
    registerbenchmark(custom_backend)


def registerbackend_sh(name: str, file_path: str):
    custom_backend = type(name, (object, ), {})

    @staticmethod
    def init():
        shell = subprocess.Popen(
            "sh", stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        script = open(file_path, "r").read()
        script += "\n"
        shell.stdin.write(str.encode(script))
        shell.stdin.write(str.encode("init > /dev/null\n"))
        shell.stdin.write(str.encode("env\n"))
        shell.stdin.close()
        environment = dict()
        for line in shell.stdout:
            name, value = line.decode('ascii').strip().split('=', 1)
            environment[name] = value
        uniq = {k: environment[k] for k in set(environment) - set(os.environ)}
        custom_backend.env = uniq
        shell.wait()

    custom_backend.init = init

    @staticmethod
    def uninit():
        shell = subprocess.Popen(
            "sh", stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=custom_backend.env)
        script = open(file_path, "r").read()
        script += "\n"
        shell.stdin.write(str.encode(script))
        shell.stdin.write(str.encode("uninit\n"))
        shell.stdin.close()
        shell.wait()

    custom_backend.uninit = uninit

    registerbackend(custom_backend)


class NullBackend:
    def __init__(self, consts={}, var=[]):
        self.var = Variables(consts, var)

    @staticmethod
    def init():
        pass

    @staticmethod
    def uninit():
        pass


class Execution:
    """Execution class, see plan_execution documentation"""

    def __init__(self, benchmark, backends: List, parser, out: str):
        self.bench = benchmark

        if backends:
            self.backends = backends
        else:
            self.backends = [NullBackend()]

        self.run_benchmarks = None
        self.out = out
        self.parser = parser
        self._cached = None
        self.name = ",".join(
            [back.name for back in self.backends]) + "-" + self.bench.name

    def print(self, string):
        """Pretty printer for execution"""
        print("\033[1;31m[{} - {}]:\033[0m {}".format(self.name,
                                                      self.bench.name, string))

    def tables(self):
        """
        Generates the tables needed for the sqlite backend

        Table names are in the form EXECNAME__BENCHNAME__BACKENDS
        Composed backends are seperated by "_b_".  This is because characters
        like "/" and "-" and ":" are not accepted by sqlite.
        """
        tables = {}
        if self.backends:
            for back_obj in self.backends:
                fields_backends = _retrieve_named_backends(back_obj)
                fields_benchmark = _retrieve_named_benchmarks(self.bench.name)
                fields_parser = self.bench.parser.fields()
                tablename = "{}__{}__{}".format(self.name,
                                                self.bench.name, back_obj.path_sql)
                fields = fields_backends + fields_benchmark + fields_parser + _sb_rnames
                tables[tablename] = sorted(fields)
        else:
            fields_benchmark = _retrieve_named_benchmarks(self.bench.name)
            fields_parser = self.bench.parser.fields()
            tablename = "{}__{}".format(self.name,
                                        self.bench.name)
            fields = fields_benchmark + fields_parser + _sb_rnames
            tables[tablename] = sorted(fields)

        return tables

    def _setup_tables(self):
        conn = sqlite3.connect(self.out)
        for name, vals in self.tables.items():
            c = conn.cursor()
            quotes = ['"{}"'.format(val) for val in vals]
            exec_str = "CREATE TABLE {} ({});".format(name, ",".join(quotes))
            try:
                c.execute(exec_str)
            except sqlite3.OperationalError:
                exec_str = "DELETE FROM {}".format(name)
                c.execute(exec_str)
            conn.commit()
            c.close()
        conn.close()

    # Constantly creating the connection is not so nice.
    def _add_sql_row(self, obj, bench_args, full_backend_args):
        conn = sqlite3.connect(self.out)
        c = conn.cursor()
        inserted = False
        for name_full, fields in self.tables.items():
            name = name_full.split('__')
            if obj["_execution_name"] != name[0]:
                continue

            if obj["_workload"] != name[1]:
                continue

            if len(name) == 3:
                sql_friendly = Backend.out_to_sql(obj["_backend"])
                if sql_friendly != name[2]:
                    continue

                obj["_backend"] = sql_friendly

            vals = []
            for val in fields:
                # We have to eliminate the first and last char as they are quotes
                if val in obj:
                    # If we do typing for object we would have to do it here?
                    # When we get the fields we would also ask for typing
                    # Its a feature that will probably need to be added sooner
                    # over later
                    vals.append('"{}"'.format(str(obj[val])))
                else:
                    if full_backend_args and val in full_backend_args:
                        vals.append('"{}"'.format(str(full_backend_args[val])))
                    elif val in bench_args:
                        vals.append('"{}"'.format(str(bench_args[val])))
                    else:
                        vals.append('""')

            quotes = ['"{}"'.format(val.strip()) for val in fields]
            exec_str = "INSERT INTO {} ({})\nVALUES ({});".format(name_full,
                                                                  ",".join(quotes), ",".join(vals))

            c.execute(exec_str)
            conn.commit()
            c.close()
            inserted = True
            break

        conn.close()
        if not inserted:
            raise Exception("Object was not/could not be added to any table")

    def clean(self):
        """Cleans output directories"""
        if self.is_sql_backed():
            self._setup_tables()
        else:
            try:
                os.mkdir(self.out)
            except Exception as e:
                if len(os.listdir(self.out)) > 0:
                    self.print(e)
                    self.print(
                        "Problem creating out directory {}, test data already there".format(self.out))
                    exit(0)

    def _merged_args(self, back_vars):
        benchmark = self.bench.variables.produce_args()
        backend = back_vars.produce_args()
        args = []
        for back in backend:
            arg = dict(
                benchmark=benchmark,
                backend=back
            )
            args.append(arg)

        return args

    def parse(self):
        # Pretty messy having to do this twice but need to retrieve proper data
        if self._cached:
            self.print("Using cached parsed output")
            return

        combined = []
        for back in self.backends:
            args = self._merged_args(back.variables)
            for arg_set in args:
                bench_args = arg_set["benchmark"]
                back_args = arg_set["backend"]
                for ba in bench_args:
                    metrics = Metrics()
                    for k, v in ba.items():
                        metrics.add_constant(k, v)
                    for k, v in back_args.items():
                        metrics.add_constant(k, v)
                    for iteration in range(0,  self.bench.iterations):
                        out_file = os.path.abspath(self.out_file(back,
                                                                 back_args, ba, iteration))
                        self.parser(metrics, out_file)
                    combined.append(metrics)

        self._cached = combined

    def out_file(self, back_obj, backend_args, bench_args, iteration):
        """Determine output filename given a some backend and bench arguments

        output is {Execution_name}_b_{BCK1-BCK2}_{BCKVARS}_{WRKVARS}
        """
        file = self.bench.__class__.__name__
        file += "_b_{}".format(back_obj.name)
        for name in back_obj.variables.y_names():
            file += "_{}".format(backend_args[name])

        for name in self.bench.variables.y_names():
            file += "_{}".format(bench_args[name])
        file += "_{}".format(iteration)

        if self.is_sql_backed():
            return "{}".format(file)

        return "{}/{}".format(self.out, file)

    def is_sql_backed(self):
        """Checks if execution storage backend is sqlite3"""
        return self.out.endswith('.db')

    def execute(self):
        """Execute the execution defined

        Argument:
            args: Arguments namespace from the cli
        """
        # Go through every registered backend
        for back in self.backends:
            args = self._merged_args(back.variables)

            # Go through every argument possibility given consts
            # and variables
            for arg_set in args:
                bench_args = arg_set["benchmark"]
                back_args = arg_set["backend"]
                back.__class__.start(**back_args)
                # Go through every benchmark argument listing
                for ba in bench_args:
                    for iteration in range(0,  self.bench.iterations):
                        out_file = os.path.abspath(self.out_file(back,
                                                                 back_args, ba, iteration))
                        self.bench.__class__.run(back.name, out_file, **ba)
                back.__class__.uninit()

    def param_exists(self, name: str) -> bool:
        """Checks if a param exists within either the benchmark or the parser"""
        bench_has = self.bench.param_exists(name)
        if self.backends:
            backend_has = any([back_obj.runtime_variables.param_exists(name)
                               for back_obj in self.backends])
        else:
            backend_has = False

        return bench_has or backend_has

    def __str__(self):
        title = self.bench.name + "("
        for back in self.backends:
            title += "{}".format(back.name)
        title += ")"
        return "{}".format(title)


class NoBenchmark:
    def __init__(self, parser):
        self.parser = parser


class ParseExecution:
    def __init__(self, data: str, out_dir: str, func):
        self._data = data
        self.out = out_dir
        self._func = func
        self.bench = NoBenchmark(self)
        self._cached = None

    def fields(self):
        return self._obj.keys()

    def is_sql_backed(self):
        return False

    def param_exists(self, param):
        return True

    def _parse_file(self, metrics, path: str, iter):
        self._func(metrics, path)

    def parse(self):
        if self._cached:
            return

        metrics = Metrics()
        if os.path.isdir(self._data):
            i = 0
            for file in os.listdir(self._data):
                path = os.path.join(self._data, file)
                self._parse_file(metrics, path, i)
                i += 1
        else:
            self._parse_file(metrics, self._data, 0)

        self._cached = [metrics]

    def execute(self):
        pass

    def clean(self):
        pass


def plan_parse(file, parse_file_func, out_dir: str = None):
    _sb_executions.append(ParseExecution(file, out_dir, parse_file_func))
    return _sb_executions[-1]


def compose_backends(*backends):

    def construct(self, consts={}, vars=[]):
        self.variables = Variables(consts, vars)
        self.name = "-".join([b.__name__ for b in backends])

    def start(**kwargs):
        for backend in backends:
            backend.start(**kwargs)

    def uninit():
        for backend in reversed(backends):
            backend.uninit()

    composition = type("", (), {
        "__init__": construct,
        "start": start,
        "uninit": uninit
    })

    return composition


def plan_execution(runner,
                   backends: Dict = None,
                   parser=None,
                   out: str = None) -> None:
    """Plan an execution

    Definition of an execution of a workload/benchmark and backends you wish to run the workload
    on.

    Arguments:
        name: Name of the execution, to be used by graph objects to plot data
        run: Running object (DefBenchmark, or Command line benchmark)
        backend: Backends are a dictionary object that tie a backend you wish to run
        (this must be a lowercase name of a registered backend) to a Variables
        object.  This Variables objects holds how you want the backend to change
        for an execution.  See Variables documentation for more info
        parse: A parse object that defines how to take output from a workload,
        and retrieve data.
    """

    # We have to fix up the variables, we do this so the user doesnt
    # have to re-input variables twice. Parser also needs to know
    # variable names to create the object
    _sb_executions.append(Execution(runner, backends, parser, out))
    return _sb_executions[-1]


def plan_graph(name: str, graphobj):
    """Plan a graph object
    Takes a graph object (LineGraph, etc) and ties the a name to it to be
    used by figures

    Argument:
        name: Name of the graph object - must be unique among all graphs
        graphobj: Graph object to tie to the name
    """
    if name in _sb_graphs:
        error("Graph already defined: {}".format(name))

    _sb_graphs[name] = graphobj


def _is_static(func):
    return isinstance(func, types.FunctionType)


def _has_required_args(func):
    return len(inspect.getfullargspec(func).args) >= 2


_names_used = []


def _check_names(cls, func, is_run=False):
    if is_run:
        args = inspect.getfullargspec(func).args[2:]
    else:
        args = inspect.getfullargspec(func).args
    for name in args:
        # if name in _names_used:
        # error("Class '{}'-> function '{}' uses already defined argument name: {}".format(
        # cls.__name__, func.__name__, name))

        _names_used.append(name)


def registerbenchmark(cls):
    """Register for benchmark

    cls: Class definition to wrap and register
    """
    if not hasattr(cls, "run"):
        error("Benchmark requires the run function: {}".format(cls.__name__))

    if not _has_required_args(cls.run):
        error("Benchmark run needs 2 argument for output path: {}".format(cls.__name__))

    _check_names(cls, cls.run, is_run=True)

    def construct(self, consts={}, vars=[], iterations=1):
        self.variables = Variables(consts, vars)
        self.iterations = iterations
        self.name = cls.__name__

    cls.__init__ = construct

    _sb_registered_benchmarks[cls.__name__.lower()] = cls

    return cls


def get_args(spec, **kwargs):
    args = dict()
    for i, k in enumerate(spec.args):
        if k in kwargs:
            args[k] = kwargs[k]
    return args


def registerbackend(cls):
    """Regististration of a backend class

    Argument:
    cls: Class definition to wrap and register
    """
    if not hasattr(cls, "start"):
        error("Backend requires the init function: {}".format(cls.__name__))

    if not hasattr(cls, "uninit"):
        error("Backend requires the uninit function: {}".format(cls.__name__))

    _check_names(cls, cls.start)
    _check_names(cls, cls.uninit)

    def construct(self, consts={}, vars=[]):
        self.vars = Variables(consts, vars)
        self.name = cls.__name__

    spec = inspect.getfullargspec(cls.start)
    old = cls.start

    def wrapped_start(**kwargs):
        args = get_args(spec, **kwargs)
        return old(**args)

    cls.__init__ = construct
    cls.start = wrapped_start

    _sb_registered_backend[cls.__name__.lower()] = cls

    return cls


def import_plan(filepath: str, mod_globals):
    """Import a .py file to be used by the progbg system
    When the plan is imported, the script is run (all the plan_* function calls)
    this creates and fills global variables within that module. Since modules do
    not share global objects we must edit progbg global table (_EDIT_GLOBAL_TABLE)
    to have these objects as well (figures, graphs, executions)

    Arguments:
        filepath: Path to the .py plan file
        mod_globals: Globals dictionary object (globals())
    """
    spec = importlib.util.spec_from_file_location('_plan',
                                                  filepath)
    plan_mod = importlib.util.module_from_spec(spec)
    # Different module so different global
    sys.modules["_plan"] = plan_mod
    spec.loader.exec_module(plan_mod)
    members = inspect.getmembers(plan_mod)
    # We must find the module that was imported in the user given file. This
    # file imports from us, so we must grab that module they imported and
    # set our globals to it.  This is because globals across modules
    # are not unique, meaning each individual module has its own global
    # so to make our 'globals' truly global we have to set our
    # globals to theirs
    imported_name = ""
    for name, mod in members:
        if hasattr(mod, '_sb_executions'):
            imported_name = name

    if not imported_name:
        error("Plan does import progbg: Fix by adding import progbg")

    # Fix globals in our namespace
    for name in _EDIT_GLOBAL_TABLE:
        mod_globals[name] = getattr(getattr(plan_mod, imported_name), name)


class Figure:
    """Create figure given a set of graphs, for more information see plan_figure documentation"""

    def __init__(self,
                 name: str,
                 graphs: List[List[str]],
                 formatter,
                 out: str):
        check_formatter(formatter)

        self.name = name
        self.graphs = graphs
        self.formatter = formatter
        self.out = out

    def print(self, strn: str) -> None:
        """Pretty print function"""
        print("\033[1;35m[{}]:\033[0m {}".format(self.out, strn))

    def create(self):
        """Create the figure"""
        self.print("Creating Figure")
        h = len(self.graphs)
        w = len(self.graphs[0])
        fig, axes = plt.subplots(ncols=w, nrows=h, squeeze=False)
        for y in range(0, h):
            for x in range(0, w):
                graph = _sb_graphs[self.graphs[y][x]]
                try:
                    graph.graph(axes[y][x], silent=True)
                except Exception as err:
                    error("Problem with graph {}: {}".format(self.name, err))

        format_fig(fig, axes, self.formatter)

        out = os.path.join(GRAPHS_DIR, self.out)
        plt.savefig(out, bbox_inches="tight", pad_inches=0)
        if not out.endswith(".svg"):
            out = ".".join(out.split(".")[:-1]) + ".svg"
            plt.savefig(out, bbox_inches="tight", pad_inches=0)


def plan_figure(name: str, graph_layout: List[List[str]], formatter, out: str):
    """Plan a figure given a set of graphs
    Arguments:
        name: Unique name for the figure (unique among figures)
        graph_layout: An m x n matrix that defines how you want you
        figure to hold graph objects
        formatter: Formatter object that tells you how to format the
        object this can be either a Dict or a function that takes the figure,
        and axes as an argument (as defined by matplotlib)
        out: output name for the figure.
    Examples:
            sb.plan_figure("fig-1",
                    [["graph-1"],
                    ["graph-2"]],
                    {
                        "height": 6,
                        "width": 3,
                    },
                    out  = "samplefig.svg"
            )

            We See here this will create a 1 by 2 matrix where the first row will contain graph-1
            and the second will contain graph 2

            The figure will be modified to have a figure height of 6, and width of 3 and saved to
            sampelefig.svg
    """
    if name in _sb_figures:
        error("Figure already defined: {}".format(name))

    _sb_figures[name] = Figure(name, graph_layout, formatter, out)


def execute_plan(plan: str, args):
    """Entry point to start executing progbg
    Argument:
        plan: Path to plan .py file
        no_exec: When true, will not execute any planned execution but rather will only
        take re-parse and re-make graphs
    """
    import_plan(plan, globals())

    if not args.no_exec:
        for execution in _sb_executions:
            execution.clean()

    if not args.no_exec:
        for execution in _sb_executions:
            execution.execute()

    for execution in _sb_executions:
        execution.parse()

    try:
        os.mkdir(GRAPHS_DIR)
    except FileExistsError:
        pass

    for graph in _sb_graphs.values():
        if len(graph.out):
            fig, axes = plt.subplots()
            fig.set_size_inches(3.25, 3.25)
            graph.graph(axes)
            format_fig(fig, axes, graph.formatter)
            for curout in graph.out:
                out = os.path.join(GRAPHS_DIR, curout)
                try:
                    plt.savefig(out)
                except:
                    print("Problem with output {}".format(out))

    for fig in _sb_figures.values():
        fig.create()

    return globals()
