# pylint: disable-msg=E0611,E0401,C0103,W0703,R0903,R0913,R0914
"""
Graphing Module

Holds all related code around the different graphs the progbg supports
"""
from typing import List, Dict
from pprint import pformat
from enum import Enum
import os
import sqlite3

import matplotlib as mpl
import numpy as np

from .globals import _sb_executions
from .subr import retrieve_axes, check_one_varying
from .subr import aggregate_bench
from .format import check_formatter
from .util import Backend, retrieve_obj, error

mpl.use("pgf")

TYPES = ['r--', 'bs', 'g^', 'p*']
COLORS = ['c', 'm', 'r', 'g']
PATTERNS = ["**", "++", "//", "xx", "oo"]

pgf_with_pdflatex = {
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 9,
    "pgf.texsystem": "pdflatex",
    "pgf.rcfonts": False
}

mpl.rcParams.update(pgf_with_pdflatex)


class GroupBy(Enum):
    """BarGraph grouping options"""
    EXECUTION = 1
    OUTPUT = 2

def _is_good(benchmark, restriction):
    for key, val in restriction.items():
        if key not in benchmark:
            continue
        if str(benchmark[key]) != str(val):
            return False

    return True

def check_workloads_and_restrictions(workloads, restrict, params):
    """
    Checks workload, given the restriction and parameters given
    is correct
    """
    for workload_path in workloads:
        path = workload_path.split(":")
        workload = path[0]
        if workload not in _sb_executions:
                error("Undefined workload in for graph: {}".format(workload))
        for param in params:
            if not _sb_executions[workload].param_exists(param):
                    error("Workload {} has {} undefined".format(
                        workload, param))

        if len(path) == 2:
            if not _sb_executions[workload].backends:
                error("Workload does not define a backend to run on: {}"
                        .format(workload_path))

            if path[1] not in _sb_executions[workload].backends:
                error("Graph wishes to graph non-existent backend in workload: {}"
                        .format(path[1]))

        if len(path) > 2:
            error("Undefined workload/backend pair: {}".format(workload_path))

    for key in restrict.keys():
        output = any([_sb_executions[work.split(":")[0]].param_exists(key) for work in workloads])
        if not output:
            print(output)
            error("Unrecognized key for retrict constraint: {}".format(key))

def _retrieve_data_files(execution, restriction):
    files = [ os.path.join(execution.out, path) for path in os.listdir(execution.out) ]
    benchmarks = []
    for file in files:
        obj = retrieve_obj(file)
        if _is_good(obj, restriction):
            benchmarks.append(obj)
    if len(benchmarks) == 0:
        error("No output after restriction are not filtering everything out? {} - {}"
                .format(pformat(restriction), execution.name))

    return benchmarks

def _retrieve_data_db(execution, restriction):
    conn = sqlite3.connect(execution.out)
    if execution.backends:
        sq_friendly = Backend.out_to_sql(restriction['_backend'])
        tablename = "{}__{}__{}".format(execution.name, execution.bench.name, sq_friendly)
        if tablename not in execution.tables:
            raise Exception("Table not present, this should not occur")
    else:
        tablename = "{}__{}".format(execution.name, execution.bench.name)

    new_restrict = {k: restriction[k] for k in execution.tables[tablename] if k in restriction}
    c = conn.cursor()
    # Eliminate quotes.  Deciding whether to default include them for better SQL or default remove
    # for readability
    new_restrict = {k: restriction[k] for k in execution.tables[tablename] if k in restriction}

    # This feels not good to use -- have to find a nice abstraction for converting between
    # SQL Friendly names and names that feel good for the user, should not be hard coded
    if execution.backends:
        new_restrict["_backend"] = sq_friendly

    clauses = ["({}='{}')".format(k, v) for k, v in new_restrict.items()]
    full = " AND ".join(clauses)
    quotes = [ '{}'.format(val) for val in execution.tables[tablename] ]
    exec_str = "SELECT {} FROM {} WHERE ({})".format(",".join(quotes), tablename, full)
    c.execute(exec_str)
    data = c.fetchall()

    if len(data[0]) != len(execution.tables[tablename]):
        raise Exception("Data types not matching with sqldb")

    benchmarks = [dict(zip(execution.tables[tablename], vals)) for vals in data]
    c.close()
    conn.close()

    return benchmarks


def retrieve_relavent_data(workloads: str, restriction: Dict):
    """
    Grab the workloads string, and retrictions and filter out the data within the specified out
    backend, this can either be a file or an sqllite3 db.
    """
    final_args = dict()
    for work in workloads:
        restrict = dict(restriction)
        path = work.split(':')
        restrict["_execution_name"] = path[0]
        if len(path) == 2:
            restrict["_backend"] = Backend.user_to_out(path[1])
        execution = _sb_executions[path[0]]
        if execution.is_sql_backed():
            benchmark = _retrieve_data_db(execution, restrict)
        else:
            benchmark = _retrieve_data_files(execution, restrict)

        final_args[work] = benchmark

    return final_args

def calculate_ticks(group_len: int, width: float):
    """Given some group size, and width calculate
    where ticks would occur.

    Meant for bar graphs
    """
    if group_len % 2 == 0:
        start = ((int(group_len / 2) - 1) * width * -1) - (width / 2.0)
    else:
        start = (int((group_len / 2)) * width * -1)

    temp = []
    offset = start
    for _ in range(0, group_len):
        temp.append(offset)
        offset += width
    return temp

class BarGraph:
    """progbg Bar Graph"""
    def __init__(
            self,
            responding: List[str],
            workloads: List[str],
            restrict: Dict,
            group_by: GroupBy = GroupBy.OUTPUT,
            formatter: Dict = None,
            out: str = None):

        check_workloads_and_restrictions(workloads, restrict, responding)
        check_formatter(formatter)

        self.formatter = None
        self.responding = responding
        self.workloads = workloads
        self.out = out
        self.restrict = restrict
        self.aggregation = None
        self.group_by = group_by

    def graph(self, ax):
        """Graph the bar graph one the given axes object"""
        width = 0.30
        self.aggregation = dict()
        for work, benchmark in retrieve_relavent_data(self.workloads, self.restrict).items():
            check_one_varying(benchmark, extras=self.responding)
            self.aggregation[work] = aggregate_bench(benchmark)

        groups = []
        group_labels = []
        inner_labels = []
        if self.group_by == GroupBy.EXECUTION:
            for key in self.workloads:
                group = []
                for val in self.responding:
                    group.append(self.aggregation[key][val])
                groups.append(group)
            group_labels = self.workloads
            inner_labels = self.responding
        elif self.group_by == GroupBy.OUTPUT:
            for val in self.responding:
                group = []
                for key in self.workloads:
                    group.append(self.aggregation[key][val])
                groups.append(group)
            group_labels = self.responding
            inner_labels = self.workloads
        else:
            raise Exception("Unrecognized GroupBy Variable")

        ticks = calculate_ticks(len(groups[0]), width)

        x_ticks = np.arange(len(groups))
        ax.set_xticks(x_ticks)
        ax.set_xticklabels(group_labels)

        # We now want each bar with a specific label
        for i in range(0, len(groups[0])):
            at_index_val = [ g[i][0] for g in groups ]
            at_index_std = [ g[i][1] for g in groups ]
            ax.bar(x_ticks + ticks[i], at_index_val, width, yerr=at_index_std,
                    ecolor='black',
                    capsize=10,
                    label=inner_labels[i])

        ax.legend()

class LineGraph:
    """progbg Line Graph

    Arguments:
        x: attribute you wish to plot its change
        y: attribute you wish to see respond to the change in x
        workloads: Workloads that the line graph will use in the WRK:BCK1/BCK2 format
        formatter: Optional formatter to be used on the graph once the graph is complete
        out: Optional name for file the user wishes to save the graph too.  We automatically always produce
        a .svg file.  Current supported extensions are: .svg, .pgf, .png. 
    """
    def __init__(
            self,
            x: str,
            y: str,
            workloads: List[str],
            restrict: Dict,
            formatter: Dict = None,
            out: str = None):

        check_workloads_and_restrictions(workloads, restrict, [x, y])
        check_formatter(formatter)

        self.formatter = None
        self.x_name = x
        self.y_name = y
        self.workloads = workloads
        self.out = out
        self.restrict = restrict
        self.aggregation = None

    def print(self, strn: str) -> None:
        """Pretty printer for LineGraph"""
        print("\033[1;34m[{}]:\033[0m {}".format(self.out, strn))

    def graph(self, ax):
        """ Create the line graph
        Arguments:
            ax: Axes object to attach data too
        """
        self.print("Graphing")
        self.aggregation = dict()
        for work, benchmark in retrieve_relavent_data(self.workloads, self.restrict).items():
            check_one_varying(benchmark, extras=[self.x_name])
            x, y, ystd, self.aggregation[work] = retrieve_axes(
                benchmark, self.x_name, self.y_name)
            ax.errorbar(x, y, yerr=ystd, linestyle='-', fmt='o',
                        capsize=1, elinewidth=1, markersize=2, linewidth=1)
