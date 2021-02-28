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
import importlib
import inspect
import sqlite3
import shutil
import types
from typing import List, Dict
from pprint import pformat

import matplotlib.pyplot as plt

from .format import format_fig, check_formatter
from .util import Backend, Variables, dump_obj, error
from .util import silence_print, restore_print

from .globals import _sb_registered_benchmarks, _sb_registered_backend
from .globals import _sb_executions, _sb_graphs, _sb_rnames
from .globals import _sb_figures, GRAPHS_DIR
from .globals import _EDIT_GLOBAL_TABLE

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
    return [ _sb_registered_backend[back] for back in back_obj.backends ]


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


class Execution:
    """Execution class, see plan_execution documentation"""
    def __init__(self, name: str, benchmark, backends: Dict, out: str):
        self.name = name
        self.bench = benchmark

        if backends:
            self.backends = [ Backend(k, v) for k, v in backends.items() ]
        else:
            self.backends = None

        self.run_benchmarks = None
        self.out = out
        self.cli_args = None

    def print(self, string):
        """Pretty printer for execution"""
        print("\033[1;31m[{} - {}]:\033[0m {}".format(self.name, self.bench.name, string))

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
            quotes = [ '"{}"'.format(val) for val in vals ]
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

            quotes = [ '"{}"'.format(val.strip()) for val in fields ]
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
                    self.print("Problem creating out directory {}, test data already there".format(self.out))
                    exit(0)

    def _merged_args(self, back_vars):
        benchmark = self.bench.variables.produce_args()
        backend = back_vars.produce_args()
        args = []
        for back in backend:
            arg = dict(
                benchmark = benchmark,
                backend = back
            )
            args.append(arg)

        return args

    def out_file(self, back_obj, backend_args, bench_args, iteration):
        """Determine output filename given a some backend and bench arguments

        output is {Execution_name}_b_{BCK1-BCK2}_{BCKVARS}_{WRKVARS}
        """
        file = self.name
        if back_obj:
            bench_name = back_obj.path_out
            file += "_b_{}".format(bench_name)
            for name in back_obj.runtime_variables.y_names():
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

    def _get_back_obj(self, path):
        for back_obj in self.backends:
            if path == back_obj.path_user:
                return back_obj

        return None

    def reverse_file_out(self, file: str) -> Dict:
        """Take a given file, and extracts variable information from it
        Arguments:
            file: file name
        Returns:
            Dictionary of values with associated key headers (defined by variables)
        """
        values = dict()
        parts = file.split('_')[1:]
        i = 0
        if parts[i] == "b":
            i += 1
            values['_backend'] = parts[i]
            i += 1
            back_obj = self._get_back_obj(Backend.out_to_user(values['_backend']))
            for name in back_obj.runtime_variables.y_names():
                values[name] = parts[i]
                i += 1

        for name in self.bench.variables.y_names():
            values[name] = parts[i]
            i += 1

        values['_iter'] = int(parts[i])
        i += 1
        if len(parts) !=  i:
            raise Exception("Improper number of arguments in file")

        return values

    def _execute(self, back_obj, args, iteration, init = True):
        if not self.cli_args.debug:
            silence_print()

        if back_obj:
            full_backend_args = args['backend']
            backends = _retrieve_backends(back_obj)
            for backend in backends:
                required = inspect.getfullargspec(backend.init)
                # Set defaults for full_backend args
                for index, k in enumerate(required.args):
                    if k not in full_backend_args:
                        full_backend_args[k] = required.defaults[index]
                # Seperate out only the args needed for this backend
                backend_args = { k:v for k,v in full_backend_args.items() if k in required.args }
                if init:
                    backend.init(**backend_args)
        else:
            full_backend_args = None

        # We have to capture the output from this benchmark. I'm unsure whether to use
        # a FIFO here.  Its a nice abstraction to use but I'm unsure the memory that
        # this would hold. Worth testing another time.
        for bench_arg in args['benchmark']:
            out_file = self.out_file(back_obj, full_backend_args, bench_arg, iteration)
            backend_str = ""
            if back_obj:
                backend_str = back_obj.path_user
            obj = self.bench.run(backend_str, out_file, bench_arg, full_backend_args)
            if obj:
                if self.is_sql_backed():
                    self._add_sql_row(obj, bench_arg, full_backend_args)
                    os.remove(out_file)
                else:
                    dump_obj(out_file, obj)

        if back_obj and init:
            for backend in reversed(backends):
                backend.uninit()

        if not self.cli_args.debug:
            restore_print()

    def _execute_no_backend(self):
        benchmark_args = self.bench.variables.produce_args()
        self.print("No backend provided - running iterations")
        for args in benchmark_args:
            for iteration in range(0, self.bench.iterations):
                self._execute(None, dict( benchmark = [args] ), iteration)

    def _execute_with_backends(self):
        for back_obj in self.backends:
            arguments = self._merged_args(back_obj.runtime_variables)
            self.print("Backend: {} {}".format(back_obj.path_user, arguments))
            for arg in arguments:
                self._execute(back_obj, arg, 0, init = True)
                for iteration in range(1, self.bench.iterations):
                    if self.cli_args.no_reinit:
                        self._execute(back_obj, arg, iteration, init = False)
                    else:
                        self._execute(back_obj, arg, iteration, init = True)
                if self.cli_args.no_reinit and back_obj:
                    backends = _retrieve_backends(back_obj)
                    for backend in reversed(backends):
                        backend.uninit()


    def execute(self, args):
        """Execute the execution defined

        Argument:
            args: Arguments namespace from the cli
        """
        self.cli_args = args

        if not args.no_exec:
            self.print("Starting execution")
            if self.backends is None:
                self._execute_no_backend()
            else:
                self._execute_with_backends()
            self.print("Done execution")

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
        title = "Execution " + self.name
        return "{}\n{}\n{}".format(title, '=' * len(title), str(self.bench))


class DefBenchmark:
    """Defined Benchmark - A Class that represents an execution of a registered benchmark class

    These are used in pair with @registerbenchmark, where the name given to init must match
    the class name (all class names are converted to all lower case versions)
    """

    def __init__(self, name: str, var: Variables,
                    iterations: int = 1,
                    parse = None):
        """Instantiation of a Defined Benchmark

        Arguments:
            name: name of the associated registeredbenchmark class (lower case)
            var: Variable object to define how you want the benchmark to change during
            and execution (See Variables documentation)
            iterations: Number of iterations you wish this benchmark to run given the variable
            object
            parse: Parser object to convert raw data to usable objects and output
        """
        if name not in _sb_registered_benchmarks:
            error(
                "Attempting to used undefined benchmark: {}".format(name))

        self.name = name
        self.variables = var
        self.iterations = iterations
        self.parser = parse

    def run(self, backend: str, out_file: str, bench_args: Dict, backend_args: Dict):
        """Run the given benchmark

        This expects backends to be setup if any are required.

        Arguments:
        out_file: File to send output to.  We hand this to the run function
        of the benchmark so users can have something to write to or pass to their process
        backend:  String in path format of backend its being ran on
        bench_args:  Named arguments for the benchmark
        backend_args: Named arguments for the backends, this is used to help
        the parser with context on what was passed.

        Return:
            Dictionary of parsed output from the file. None is returned if no parser
            was given
        """
        if not self.iterations:
            return None

        benchmarker = _sb_registered_benchmarks[self.name]
        benchmarker.run(backend, out_file, **bench_args)
        if self.parser:
            obj = self.parser.parse(out_file, bench_args, backend_args)
            if obj == None:
                return None
            obj["_workload"] = self.name

            return obj

        return None


    def param_exists(self,  param):
        """Checks if param exists

        This will check the variables defined by benchmark
        """
        parse_has = False
        if self.parser:
            parse_has = self.parser.param_exists(param)

        return self.variables.param_exists(param) or parse_has

    def __str__(self):
        return pformat(vars(self), width=30)


def plan_execution(
        name: str,
        run,
        backends: Dict = None,
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

    if any(ch in name for ch in ['-', '/']):
        error("Names cannot contain '-' or '/'")

    if name in _sb_executions:
        error("Workload already define: {}".format(name))

    # We have to fix up the variables, we do this so the user doesnt
    # have to re-input variables twice. Parser also needs to know
    # variable names to create the object
    _sb_executions[name] = Execution(name, run, backends, out)

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

def _check_names(cls, func, is_run = False):
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

    if not _is_static(cls.run):
        error("Benchmark requires the run function be static: {}".format(cls.__name__))

    if not _has_required_args(cls.run):
        error("Benchmark run needs 1 argument for output path: {}".format(cls.__name__))

    _check_names(cls, cls.run, is_run = True)

    _sb_registered_benchmarks[cls.__name__.lower()] = cls


def registerbackend(cls):
    """Regististration of a backend class

    Argument:
    cls: Class definition to wrap and register
    """
    if not hasattr(cls, "init"):
        error("Backend requires the init function: {}".format(cls.__name__))

    if not hasattr(cls, "uninit"):
        error("Backend requires the uninit function: {}".format(cls.__name__))

    if not _is_static(cls.init):
        error("Backend requires the init function be static: {}".format(cls.__name__))

    if not _is_static(cls.uninit):
        error("Backend requires the init function be static: {}".format(cls.__name__))

    _check_names(cls, cls.init)
    _check_names(cls, cls.uninit)

    _sb_registered_backend[cls.__name__.lower()] = cls


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
    spec = importlib.util.spec_from_file_location('_plan', filepath)
    plan_mod = importlib.util.module_from_spec(spec)
    # Different module so different global
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
        error("plan.py does not import from simplebench")

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
                    graph.graph(axes[y][x], silent = True)
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
        for execution in _sb_executions.values():
            execution.clean()

    for execution in _sb_executions.values():
        execution.execute(args)

    try:
        os.mkdir(GRAPHS_DIR)
    except FileExistsError:
        pass

    for graph in _sb_graphs.values():
        if len(graph.out):
            fig, axes = plt.subplots()
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
