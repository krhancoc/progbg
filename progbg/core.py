# pylint: disable-msg=E0611,E0401,C0103,W0703,R0903

"""Core API calls and classes for ProgBG

This module contains all the related API calls for creating and managing
the plan.py files, graphing is handled within graphing.py.

A special case we have to handling is the handling of global variables
within ProgBG. Since we dynamically pull in a users file, their module
has a different set of globals then ours, so upon importing their
python file we must edit our globals to be equivalent to theirs.
This can be seen in the function import_plan.

"""

import os
import re
import importlib
import sys
import inspect
import itertools
from typing import List, Dict, Tuple
from pprint import pformat

import matplotlib.pyplot as plt

from .format import format_fig, check_formatter

_sb_registered_benchmarks = {}
_sb_registered_backend = {}
_sb_executions = {}
_sb_graphs = {}
_sb_figures = {}
"""Registration globals

These globals are used by the plan_* functions, as well as the
register_* decoraters to keep track of what has been planned
by the user
"""

GRAPHS_DIR = "graphs"
"""str: default graphs directory"""
PROGBG_EXTENSION = ".progbg"
"""str: Extension used for file already parsed by parsers"""


# String versions of the dictionaries
_EDIT_GLOBAL_TABLE = {
    "_sb_registered_benchmarks": _sb_registered_benchmarks,
    "_sb_registered_backend": _sb_registered_backend,
    "_sb_executions": _sb_executions,
    "_sb_graphs": _sb_graphs,
    "_sb_figures": _sb_figures,
}
"""Globals Table

Table to allow us to quickly access applicable global variables within 
the globals() table
"""

_sb_rnames = ["_backend", "_execution_name", "_iter"]

def _retrieve_backends(path):
    backends = path.split('/')
    return [ _sb_registered_backend[back] for back in backends ]

def _backend_format_to_file(path):
    return "-".join(path.split("/"))

def _backend_format_reverse(path):
    return "/".join(path.split("-"))

class Variables:
    """
    Variables is a container class for variables for a given execution

    This will define the permutations that can occur for those that utilize the
    class (see Variables.produce_args documentation)
    Attributes:
        const: A dictionary of argument names to values that will be passed
        var: A tuple of an argument name and some iterable object
    """

    def __init__(self, consts: Dict = None,
                 var: List[Tuple[str, List]] = None) -> None:
        if any([i in consts for i in _sb_rnames]) or (var[0] in _sb_rnames):
            raise Exception(
                "Cannot use a reserved name for a variable {}".format(
                    pformat(_sb_rnames)))
        for x in var:
            if x[0] in consts:
                raise Exception("Name defined as constant and varying: {}".format(
                    x[0]))

        self.consts = consts
        self.var = var

    def produce_args(self) -> List[Dict]:
        """Produces a list of arguments given the consts and vars
        Example:
            Variables(
                sb.Variables(
                    consts = {
                        "other" : 1
                    },
                    var = [("x" ,range(0, 3, 1)), ("test", range(0, 5, 2))]
                ),

            In this example this would produce args as follows:
                { other = 1, x = 0, test = 0},
                { other = 1, x = 0, test = 2},
                { other = 1, x = 0, test = 4},
                { other = 1, x = 1, test = 0},
                ...
                { other = 1, x = 2, test = 4},
        """
        key_names, ranges = zip(*self.var)
        args = []
        for perm in itertools.product(*ranges):
            run_vars = dict(self.consts)
            for i, k in enumerate(key_names):
                run_vars[k] = perm[i]
            args.append(run_vars)

        return args


    def param_exists(self, name: str) -> bool:
        """Checks if a variable is defined either as a constant or a varrying variable"""
        return (name in self.consts) or any([ name == x[0] for x in self.var])

    def y_names(self) -> List[str]:
        """Returns the names of varrying or responding variables"""
        return [ x[0] for x in self.var ]

    def const_names(self) -> List[str]:
        """Returns names of constants"""
        return self.consts.keys()

    def __repr__(self) -> str:
        return pformat(vars(self), width=30)

def dump_obj(file: str, obj: Dict):
    """Dump dictionary to file key=val"""
    with open(file, 'w') as f:
        for key, val in obj.items():
            line = "{}={}\n".format(key, val)
            f.write(line)

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


class MatchParser:
    """MatchParser class takes regex matches and on success run a given function"""
    def __init__(self, retrieve_dir: str, match_rules: Dict, save: str = None):
        """Match parser init
        Arguments:
            retrieve_dir: directory to retrieve output from a benchmark
            match_rules: Dictionary of regex to a tuple of a list output names
            and a function that will return values to bind to those names
            save: Directory in which to save parsed results
        Example:
            parse = sb.MatchParser("out",
                {
                    "^Latency": (
                        ["avg", "max", "min"], func
                    )
                },
                save = "out"
            )

            In the above example we take data from the out directory, take the line
            that matches on ^Latency and outputs the avg, max and min. func
            is a function that will output values which bind to these names.
            This means func must output a list of 3 values for this above example.
        """
        if not os.path.isdir(retrieve_dir):
            raise Exception(
                "Retrieving from not a directory: {}".format(retrieve_dir))

        self.retrieve_dir = retrieve_dir
        self.match_rules = match_rules
        if save:
            try:
                os.mkdir(save)
            except FileExistsError:
                pass
        self.save_to = save
        self.execution = None

    def _match(self, line: str, obj: Dict):
        for cand, tup in self.match_rules.items():
            if re.search(cand, line):
                output = tup[1](line)
                if len(output) != len(tup[0]):
                    raise Exception("Function provided outputed {} values, expected {}"
                            .format(len(output), len(tup[0])))
                for e in zip(tup[0], output):
                    obj[e[0]] = e[1]


    def param_exists(self, name: str) -> bool:
        """Check if a param exists as an output of the parser"""
        return any([name in varfunc[0]
                    for varfunc in self.match_rules.values()])


    def parse(self):
        """Parse the execution"""
        files = [
            os.path.join(self.retrieve_dir, p) for p in os.listdir(
                self.retrieve_dir) if p.startswith(self.execution.name)
                and not p.endswith(PROGBG_EXTENSION)
        ]
        benchs = []
        for file in files:
            obj = {}
            with open(file, 'r') as f:
                for line in f:
                    self._match(line, obj)
                # Make sure to put constants in the data as well
                for key, val in self.execution.bench.variables.consts.items():
                    obj[key] = val
                backend = check_file_backend(file)
                if backend != None:
                    for key, val in self.execution.backends[backend].consts.items():
                        obj[key] = val
            obj['_execution_name'] = self.execution.name

            # We hold field names within our filename as well, things like iteration number
            # and var variable value
            obj.update(self.execution.reverse_file_out(file))
            if (self.save_to):
                save_file = os.path.join(self.save_to, os.path.basename(file))
                save_file += PROGBG_EXTENSION
                dump_obj(save_file, obj)

            benchs.append(obj)
        return benchs


class Execution:
    """Execution class, see plan_execution documentation"""
    def __init__(self, name: str, benchmark, parser, backends: List[str]):
        self.name = name
        self.bench = benchmark
        self.parser = parser
        self.backends = backends
        self.run_benchmarks = None

    def print(self, string):
        """Pretty printer for execution"""
        print("[{} - {}]: {}".format(self.name, self.bench.name, string))

    def clean(self):
        """Cleans output directories"""
        self.bench.clear_out()

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

    def out_file(self, path, backend_args, bench_args, iteration):
        """Determine output filename given a some backend and bench arguments

        output is {Execution_name}_b_{BCK1-BCK2}_{BCKVARS}_{WRKVARS}
        """
        file = self.name
        if path:
            bench_name = _backend_format_to_file(path)
            file += "_b_{}".format(bench_name)
            for name in self.backends[path].y_names():
                file += "_{}".format(backend_args[name])
        for name in self.bench.variables.y_names():
            file += "_{}".format(bench_args[name])
        file += "_{}".format(iteration)
        return "{}/{}".format(self.bench.out_dir, file)

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
            pathname = _backend_format_reverse(values['_backend'])
            for name in self.backends[pathname].y_names():
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

    def _execute(self, path, args, iteration):
        benchmarker = _sb_registered_benchmarks[self.bench.name]

        full_backend_args = args['backend']
        backends = _retrieve_backends(path)
        for backend in backends:
            required = inspect.getfullargspec(backend.init)
            backend_args = { k:v for k,v in full_backend_args.items() if k in required }
            backend.init(**backend_args)

        self.print("Executing backend with args: {}".format(pformat(full_backend_args)))
        for bench_arg in args['benchmark']:
            out_file = self.out_file(path, full_backend_args, bench_arg, iteration)
            benchmarker.run(out_file, **bench_arg)

        for backend in reversed(backends):
            backend.uninit()

    def _execute_no_backend(self):
        benchmarker = _sb_registered_benchmarks[self.bench.name]
        benchmark_args = self.bench.variables.produce_args()
        total_steps = len(benchmark_args) * self.bench.iterations
        i = 0
        for args in benchmark_args:
            for iteration in range(0, self.bench.iterations):
                out_file = self.out_file(None, None, args, iteration)
                benchmarker.run(out_file, **args)
                i += 1
                self.print("[{}/{}]".format(i, total_steps))

    def _execute_with_backends(self):
        for path, back_vars in self.backends.items():
            args = self._merged_args(back_vars)
            total_steps = len(args) * self.bench.iterations
            i = 0
            for arg in args:
                for iteration in range(0, self.bench.iterations):
                    self._execute(path, arg, iteration)
                    i += 1
                    self.print("[{}/{}]".format(i, total_steps))

    def execute(self, no_exec):
        """Execute the execution defined

        Argument:
            no_exec: Do not run the benchmarks, rather only run attached
            parser (if there is any defined)
        """

        if not no_exec:
            self.print("Starting execution")
            if self.backends is None:
                self._execute_no_backend()
            else:
                self._execute_with_backends()
            self.print("Done execution")

        if self.parser:
            self.print("Starting Parsing")
            self.run_benchmarks = self.parser.parse()
            self.print("Done parsing")

    def param_exists(self, name: str) -> bool:
        """Checks if a param exists within either the benchmark or the parser"""
        bench_has = self.bench.param_exists(name)
        if self.parser:
            parse_has = self.parser.param_exists(name)
        else:
            parse_has = False

        if (self.backends):
            backend_has = any([variable.param_exists(name) 
                for variable in self.backends.values()])
        else:
            backend_has = False

        return bench_has or parse_has or backend_has

    def __str__(self):
        title = "Execution " + self.name

        return "{}\n{}\n{}".format(title, '=' * len(title), str(self.bench))


class DefBenchmark:
    """Defined Benchmark - A Class that represents an execution of a registered benchmark class

    These are used in pair with @registerbenchmark, where the name given to init must match
    the class name (all class names are converted to all lower case versions)
    """

    def __init__(self, name: str, var: Variables, out_dir: str = None,
                 iterations: int = 1):
        """Instantiation of a Defined Benchmark

        Arguments:
            name: name of the associated registeredbenchmark class (lower case)
            var: Variable object to define how you want the benchmark to change during
            and execution (See Variables documentation)
            out_dir: Directory you wish raw data to output to, this is taken by parser objects
            iterations: Number of iterations you wish this benchmark to run given the variable
            object
        """
        if name not in _sb_registered_benchmarks:
            raise Exception(
                "Attempting to used undefined benchmark: {}".format(name))

        self.name = name
        self.variables = var
        self.iterations = iterations
        if out_dir:
            self.out_dir = out_dir
        else:
            self.out_dir = name + "-out"

        try:
            os.mkdir(self.out_dir)
        except FileExistsError:
            pass

    def clear_out(self):
        """Clears output directory of all files"""
        for path in os.listdir(self.out_dir):
            os.remove(os.path.join(self.out_dir, path))

    def param_exists(self, param):
        """Checks if param exists

        This will check the variables defined by benchmark
        """
        return self.variables.param_exists(param)

    def __str__(self):
        return pformat(vars(self), width=30)


def plan_execution(
        name: str,
        run,
        backends: Dict = None,
        parse=None,
        ) -> None:
    """Plan an execution

    Definition of an execution of a workload and possible backends

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
    if name in _sb_executions:
        raise Exception("Workload already define: {}".format(name))

    # We have to fix up the variables, we do this so the user doesnt
    # have to re-input variables twice. Parser also needs to know
    # variable names to create the object
    _sb_executions[name] = Execution(name, run, parse, backends)
    if _sb_executions[name].parser:
        _sb_executions[name].parser.execution = _sb_executions[name]


def plan_graph(name: str, graphobj):
    """Plan a graph object
    Takes a graph object (LineGraph, etc) and ties the a name to it to be
    used by figures

    Argument:
        name: Name of the graph object - must be unique among all graphs
        graphobj: Graph object to tie to the name
    """
    if name in _sb_graphs:
        raise Exception("Graph already defined: {}".format(name))

    _sb_graphs[name] = graphobj


def registerbenchmark(cls):
    """Register for benchmark

    cls: Class definition to wrap and register
    """
    _sb_registered_benchmarks[cls.__name__.lower()] = cls


def registerbackend(cls):
    """Regististration of a backend class

    Argument:
    cls: Class definition to wrap and register
    """
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
        print("plan.py does not import from simplebench")
        return

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

    def create(self):
        """Create the figure"""
        h = len(self.graphs)
        w = len(self.graphs[0])
        fig, axes = plt.subplots(ncols=w, nrows=h, squeeze=False)
        for y in range(0, h):
            for x in range(0, w):
                graph = _sb_graphs[self.graphs[y][x]]
                try:
                    graph.graph(axes[y][x])
                except Exception as err:
                    print("Problem with graph {}: {}".format(self.name, err))
                    sys.exit(1)


        format_fig(fig, axes, self.formatter)

        out = os.path.join(GRAPHS_DIR, self.out)
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
        raise Exception("Figure already defined: {}".format(name))

    _sb_figures[name] = Figure(name, graph_layout, formatter, out)


def execute_plan(plan: str, no_exec=False):
    """Entry point to start executing progbg
    Argument:
        plan: Path to plan .py file
        no_exec: When true, will not execute any planned execution but rather will only
        take re-parse and re-make graphs
    """
    import_plan(plan, globals())

    if not no_exec:
        for execution in _sb_executions.values():
            execution.clean()

    for execution in _sb_executions.values():
        execution.execute(no_exec)

    try:
        os.mkdir(GRAPHS_DIR)
    except FileExistsError:
        pass

    for name, graph in _sb_graphs.items():
        if graph.out:
            fig, axes = plt.subplots()
            #try:
            graph.graph(axes)
            # except Exception as e:
                # print("Problem with graph {}: {}".format(name, e))
                # sys.exit(1)
            format_fig(fig, axes, graph.formatter)
            out = os.path.join(GRAPHS_DIR, graph.out)
            plt.savefig(out, bbox_inches="tight", pad_inches=0)

    for fig in _sb_figures.values():
        fig.create()

    return globals()
