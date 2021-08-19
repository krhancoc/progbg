# pylint: disable-msg=E0611,E0401,C0103,W0703,R0903

"""Core API calls and classes for ProgBG

This module contains all related API calls for creating and managing
plan.py files. Special global variables are used to keep track
of registered backends and benchmarks.
"""

import os
import sys
import importlib
import inspect
import sqlite3

import types
import subprocess
from typing import List, Dict
from pprint import pformat

import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

import numpy as np
import pandas as pd

from .util import Backend, Variables, error, Metrics

from .style import get_style, set_style

from .globals import _sb_registered_benchmarks, _sb_registered_backend
from .globals import _sb_executions, _sb_graphs, _sb_rnames
from .globals import _sb_figures, GRAPHS_DIR
from .globals import _EDIT_GLOBAL_TABLE

from .globals import DEFAULT_SIZE

__pdoc__ = {}


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


def registerbenchmark_sh(name: str, file_path: str):
    custom_backend = type(name, (object,), {})

    @staticmethod
    def run(backend, out_file):
        out = open(out_file, "w")
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
    custom_backend = type(name, (object,), {})

    @staticmethod
    def init():
        shell = subprocess.Popen("sh", stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        script = open(file_path, "r").read()
        script += "\n"
        shell.stdin.write(str.encode(script))
        shell.stdin.write(str.encode("init > /dev/null\n"))
        shell.stdin.write(str.encode("env\n"))
        shell.stdin.close()
        environment = dict()
        for line in shell.stdout:
            name, value = line.decode("ascii").strip().split("=", 1)
            environment[name] = value
        uniq = {k: environment[k] for k in set(environment) - set(os.environ)}
        custom_backend.env = uniq
        shell.wait()

    custom_backend.init = init

    @staticmethod
    def uninit():
        shell = subprocess.Popen(
            "sh", stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=custom_backend.env
        )
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


__pdoc__["NullBackend"] = False


class Execution:
    """Execution class, see plan_execution documentation"""

    def __init__(self, benchmark, backends: List, parser, out: str):
        self.bench = benchmark

        if backends:
            self.backends = backends
        else:
            self.backends = [NullBackend()]

        self.out = out
        self.parser = parser
        self._cached = None
        self.name = (
            ",".join([back.name for back in self.backends]) + "-" + self.bench.name
        )

    def varying(self):
        return [x[0] for x in self.bench.variables.var] + [
            x[0] for back in self.backends for x in back.variables.var
        ]

    def print(self, string):
        """Pretty printer for execution"""
        print(
            "\033[1;31m[{} - {}]:\033[0m {}".format(self.name, self.bench.name, string)
        )

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
                tablename = "{}__{}__{}".format(
                    self.name, self.bench.name, back_obj.path_sql
                )
                fields = fields_backends + fields_benchmark + fields_parser + _sb_rnames
                tables[tablename] = sorted(fields)
        else:
            fields_benchmark = _retrieve_named_benchmarks(self.bench.name)
            fields_parser = self.bench.parser.fields()
            tablename = "{}__{}".format(self.name, self.bench.name)
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
            name = name_full.split("__")
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
            exec_str = "INSERT INTO {} ({})\nVALUES ({});".format(
                name_full, ",".join(quotes), ",".join(vals)
            )

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
                        "Problem creating out directory {}, test data already there".format(
                            self.out
                        )
                    )
                    exit(0)

    def _merged_args(self, back_vars):
        benchmark = self.bench.variables.produce_args()
        backend = back_vars.produce_args()
        args = []
        for back in backend:
            arg = dict(benchmark=benchmark, backend=back)
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
                    for iteration in range(0, self.bench.iterations):
                        out_file = os.path.abspath(
                            self.out_file(back, back_args, ba, iteration)
                        )
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
        return self.out.endswith(".db")

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
                    for iteration in range(0, self.bench.iterations):
                        out_file = os.path.abspath(
                            self.out_file(back, back_args, ba, iteration)
                        )
                        self.bench.__class__.run(back.name, out_file, **ba)
                back.__class__.uninit()

    def param_exists(self, name: str) -> bool:
        """Checks if a param exists within either the benchmark or the parser"""
        bench_has = self.bench.param_exists(name)
        if self.backends:
            backend_has = any(
                [
                    back_obj.runtime_variables.param_exists(name)
                    for back_obj in self.backends
                ]
            )
        else:
            backend_has = False

        return bench_has or backend_has

    def __str__(self):
        title = self.bench.name + "("
        for back in self.backends:
            title += "{}".format(back.name)
        title += ")"
        return "{}".format(title)


__pdoc__["Execution"] = False


class NoBenchmark:
    def __init__(self, parser):
        self.parser = parser


__pdoc__["NoBenchmark"] = False


class ParseExecution:
    def __init__(self, name, data: str, out_dir: str, func):
        self._data = data
        self.out = out_dir
        self._func = func
        self.bench = NoBenchmark(self)
        self._cached = None
        self.name = name

    def fields(self):
        return self._obj.keys()

    def is_sql_backed(self):
        return False

    def param_exists(self, param):
        return True

    def _parse_file(self, metrics, path: str, iter):
        self._func(metrics, path)
        if self.out is not None:
            metrics.to_file(self.out + "/" + self.name)

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


__pdoc__["ParseExecution"] = False


def plan_parse(name: str, file: str, parse_file_func, out_dir: str = None):
    """Plan a parsing Execution

    Sometimes its not required to have progbg run actual benchmarks, and you may
    wish to compare to other frameworks which have auto runners. The plan_parse
    function allows for the ability to capture data output from a text file and
    integrate it into graphs.

    Args:
        name (str): Unique Name for the planned parsing execution.
        file (str): File to be parsed and sent to the parse_file_func argument
        parse_file_func (Function): Function to parse the data of the file argument
        out_dir (str, optional): Directory to place parsed data

    Returns:
        Execution object

    Example:
        >>> def my_text_parser(metrics: Metrics, out_file: str):
        >>>     ...
        >>> exec = plan_parse("exec_name", "my_data.txt", my_text_parser)
    """
    _sb_executions.append(ParseExecution(name, file, out_dir, parse_file_func))
    return _sb_executions[-1]


def compose_backends(*backends):
    """Composes registered backend classes into anonymous class

    This function is used to compose one or more backends into an anonymous class
    which can be used when defining executions in `plan_execution`.

    Args:
        *backends (class): Class objects to compose together

    Examples:
        >>>
        >>> @registerbackend
        >>> class Backend1
        >>>     ...
        >>>
        >>> @registerbackend
        >>> class Backend2
        >>>     ...
        >>>
        >>> composition = compose_backends(Backend1, Backend2)
    """

    def construct(self, consts={}, vars=[]):
        self.variables = Variables(consts, vars)
        self.name = "-".join([b.__name__ for b in backends])

    def start(**kwargs):
        for backend in backends:
            backend.start(**kwargs)

    def uninit():
        for backend in reversed(backends):
            backend.uninit()

    composition = type(
        "", (), {"__init__": construct, "start": start, "uninit": uninit}
    )

    return composition


def plan_execution(runner, backends: List = None, parser=None, out: str = None) -> None:
    """Plan an execution

    Definition of an execution of a workload/benchmark and backends you wish to run the workload
    on.

    Args:
        runner (Benchmark): Constructed Benchmark object
        backends (List): List of Constructed backends to run on
        parser (Function): Parsing function which takes a metrics, and out_file as args.
        out (str): Directory in which to place parsed output.

    Returns:
        Execution object

    Examples:

        >>> @registerbenchmark
        >>> class benchmark:
        >>>     def run(x = 10):
        >>>         ...
        >>>
        >>> @registerbackend:
        >>> class myback:
        >>>     ...
        >>>
        >>> def my_parser(metrics: Metrics, out_file: str):
        >>>     ...
        >>>
        >>> execution = plan_execution(
        >>>                 benchmark({}, [("x", range(0, 10))]),
        >>>                 out = "out",
        >>>                 backends = [myback()],
        >>>                 parser = my_parser
        >>>             )

        Basic example, notice that when binding arguments to a workload (through construction). In the
        above example:
        >>> benchmark({}, [("x", range(0, 10))])

        You bind variables to the named arguments of the run function (or init function for backends).
        In this example is the `x` variable, which we have chosen to vary from 0 to 10. If for example
        we wished for `x` to remain constant we would place it within the first argument of the
        constructor. Like so:

        >>> execution = plan_execution(
        >>>                 benchmark(dict(
        >>>                     x = 5
        >>>                 ), []),
        >>>                 out = "out",
        >>>                 backends = [myback()],
        >>>                 parser = my_parser
        >>>             )


    """

    # We have to fix up the variables, we do this so the user doesnt
    # have to re-input variables twice. Parser also needs to know
    # variable names to create the object
    _sb_executions.append(Execution(runner, backends, parser, out))
    return _sb_executions[-1]


def plan_graph(graphobj):
    """Plan a graph object
    Takes a graph object (LineGraph, etc) and ties the a name to it to be
    used by figures

    Args:
        graphobj (obj): Specified graph to use

    Example:
        >>> exec1 = plan_execution(...)
        >>> exec2 = plan_execution(...)
        >>> bf = BarFactory(exec1)
        >>> bf_two = BarFactory(exec2)
        >>> graph = plan_graph(
        >>>             BarGraph(
        >>>                 [
        >>>                     [bf("data-one"), bf_two("data-one")],
        >>>                     [bf("data-two"), bf_two("data-two")],
        >>>                 ],
        >>>             ...
        >>> )

        Above is an example of using plan graph.  Arguments are mostly dependent on each implementation
        of the Graph. See `graphing.BarGraph`, `graphing.LineGraph`,
        `graphing.CustomGraph`, `graphing.Histogram` etc.
    """
    _sb_graphs.append(graphobj)
    return _sb_graphs[-1]


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
    """Register a benchmark with ProgBG

    Args:
        cls (class): Class to wrap and register

    Returns:
        Wrapped class object
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


def _get_args(spec, **kwargs):
    args = dict()
    for i, k in enumerate(spec.args):
        if k in kwargs:
            args[k] = kwargs[k]
    return args


def registerbackend(cls):
    """Register a class with ProgBG

    Args:
    cls (class): Class object to wrap and register

    Returns:
        Wrapped class object
    """
    if not hasattr(cls, "start"):
        error(
            "The following Backend is missing the 'start' function: {}".format(
                cls.__name__
            )
        )

    if not hasattr(cls, "uninit"):
        error(
            "The following Backend is missing the 'uninit' function: {}".format(
                cls.__name__
            )
        )

    _check_names(cls, cls.start)
    _check_names(cls, cls.uninit)

    def construct(self, consts={}, vars=[]):
        self.vars = Variables(consts, vars)
        self.name = cls.__name__

    spec = inspect.getfullargspec(cls.start)
    old = cls.start

    def wrapped_start(**kwargs):
        args = _get_args(spec, **kwargs)
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
    spec = importlib.util.spec_from_file_location("_plan", filepath)
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
        if hasattr(mod, "_sb_executions"):
            imported_name = name

    if not imported_name:
        error("Plan does import progbg: Fix by adding import progbg")

    # Fix globals in our namespace
    for name in _EDIT_GLOBAL_TABLE:
        mod_globals[name] = getattr(getattr(plan_mod, imported_name), name)


__pdoc__["import_plan"] = False


def default_formatter(fig, axes):
    """Default formatter placeholder

    Override this to apply a default format function to all graphs and figures
    """


def _format_fig(fig, axes, formatter):
    if not formatter:
        formatter = [default_formatter]
    for x in formatter:
        x(fig, axes)


class Figure:
    """Create figure given a set of graphs, for more information see plan_figure documentation"""

    def __init__(self, out: str, graphs: List):

        self.graphs = graphs
        self.out = out
        self.html_out = ".".join(out.split(".")[:-1]) + ".svg"
        self.h = len(self.graphs)
        self.w = len(self.graphs[0])

    def print(self, strn: str) -> None:
        """Pretty print function"""
        print("\033[1;35m[{}]:\033[0m {}".format(self.out, strn))

    def _find_stretch(self, graph, x_start, y_start):
        cur_x = x_start
        cur_y = y_start
        # Find x streth
        while (cur_x < self.w) and self.graphs[y_start][cur_x] is graph:
            cur_x += 1

        while (cur_y < self.h) and self.graphs[cur_y][x_start] is graph:
            cur_y += 1

        return (cur_x - 1, cur_y - 1)

    def create(self):
        """Create the figure"""
        self.print("Creating Figure")
        fig = plt.figure()
        gs = GridSpec(self.h, self.w, figure=fig)
        found = dict()
        # Span the graphs Matrix. Assumptions made:
        # 1. No duplicate graphs within a figure.
        # 2. Graphs are always rectangles
        # With this we can start in the top left and scan the NxM graph matrix
        # When we find a new graph we know this is a corner of the new graph as we
        # always start from the left most edge, and top most edge. We then check the bounds
        # and push these bounds into a dictionary
        for r in range(0, self.h):
            for c in range(0, self.w):
                if self.graphs[r][c] not in found.keys():
                    g = self.graphs[r][c]
                    x, y = self._find_stretch(g, c, r)
                    found[g] = (c, x, r, y)

        for k, v in found.items():
            ax = fig.add_subplot(gs[v[2] : v[3] + 1, v[0] : v[1] + 1])
            k.graph(fig, ax)

        #fig.tight_layout()

        out = os.path.join(GRAPHS_DIR, self.out)
        plt.savefig(out)
        if not out.endswith(".svg"):
            out = ".".join(out.split(".")[:-1]) + ".svg"
            plt.savefig(out)


__pdoc__["Figure"] = False


def plan_figure(out, graph_layout: List[List[str]]):
    """Plan a figure given a set of graphs
    Arguments:
        out (str): output name for the figure - used as an ID.
        graph_layout (List[List]): An M by N matrix that defines figure layout.
    Examples:
        >>> graph1 = plan_graph(...)
        >>> graph2 = plan_graph(...)
        >>> graph3 = plan_graph(...)
        >>> graph4 = plan_graph(...)
        >>>
        >>> def myformatter(fig, axes):
        >>>     # Axes here will be a list over a single object in the same layout
        >>>     # as the provided graph_layout argument.
        >>>     ...
        >>>
        >>> plan_figure("graph-fig.pgf",
        >>>             [
        >>>                 [graph1, graph2],
        >>>                 [graph3, graph4]],
        >>> )

        The above example will create a figure that is layed out like the following:

         Graph1  Graph2

         Graph3  Graph4

        Graph variables can be used as a way to identify size of figures in relation to each other
        for example:

        >>> plan_figure(
        >>>     "figure.pgf",
        >>>     [
        >>>         [graph1,     graph1,       graph1],
        >>>         [cdf_graph,  custom_graph, custom_graph],
        >>>         [cdf_graph,  custom_graph, custom_graph]
        >>>     ]
        >>> )

        Produces a figure in which graph1 spans the top (3 units wide) of the figure, with cdf_graph and
        custom_graph below it. cdf_graph is a 2 units tall graph sitting to the left of custom_graph
        which is 2 units wide and 2 units tall graph within the figure
    """
    _sb_figures.append(Figure(out, graph_layout))
    return _sb_figures[-1]


def execute_plan(plan: str, args):
    """Entry point to start executing progbg

    Args:
        plan (str): Path to plan .py file
        args (Namespace): Namespace of arguments (no_exec (bool))
    """
    import_plan(plan, globals())

    set_style(get_style())

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

    for graph in _sb_graphs:
        fig, axes = plt.subplots(figsize=DEFAULT_SIZE)
        graph.graph(fig, axes)
        out = os.path.join(GRAPHS_DIR, graph.out)
        #fig.tight_layout()
        fig.legend()
        fig.subplots_adjust(left=0.35, right=0.95)
        plt.savefig(out)
        out = os.path.join(GRAPHS_DIR, graph.html_out)
        plt.savefig(out)

    for fig in _sb_figures:
        fig.create()

    return globals()
