# pylint: disable-msg=E0611,E0401,C0103,W0703,R0903,R0913
"""
Graphing Module

Holds all related code around the different graphs the progbg supports
"""
from typing import List, Dict
from pprint import pformat
from enum import Enum

import matplotlib as mpl
import numpy as np

from .core import _sb_executions
from .subr import retrieve_axes, check_one_varying
from .subr import aggregate_bench
from .subr import backend_format_reverse
from .format import check_formatter

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
    EXECUTION = 1
    OUTPUT = 2

def filter_on_consts(benchmark, variables, backend):
    if backend: 
        path_name = backend_format_reverse(benchmark['_backend'])
        if path_name != backend:
            return False

    for key, val in variables.items():
        if key not in benchmark:
            continue
        if str(benchmark[key]) != str(val):
            return False

    return True

def check_workloads_and_restrictions(workloads, restrict, params):
    for workload_path in workloads:
        path = workload_path.split(":")
        workload = path[0]
        if workload not in _sb_executions:
            raise Exception(
                "Undefined workload in for graph: {}".format(workload))
        for param in params:
            if not _sb_executions[workload].param_exists(param):
                raise Exception(
                    "Workload {} has {} undefined".format(
                        workload, param))

        if len(path) == 2:
            if not _sb_executions[workload].backends:
                raise Exception("Workload does not define a backend to run on: {}"
                        .format(workload_path))

            if path[1] not in _sb_executions[workload].backends:
                raise Exception("Graph wishes to graph non-existent backend in workload: {}"
                        .format(path[1]))

        if len(path) > 2:
            raise Exception("Undefined workload/backend pair: {}".format(workload_path))

    for key in restrict.keys():
        output = any([_sb_executions[work.split(":")[0]].param_exists(key) for work in workloads])
        if not output:
            print(output)
            raise Exception("Unrecognized key for retrict constraint: {}".format(key))

def retrieve_relavent_data(workloads, restriction):
    final_args = dict()
    for work in workloads:
        path = work.split(':')
        benchmark = _sb_executions[path[0]].run_benchmarks
        if len(path) > 1:
            reduce_on_consts = lambda x: filter_on_consts(x, restriction, path[1])
        else:
            reduce_on_consts = lambda x: filter_on_consts(x, restriction, None)

        benchmark = list(filter(reduce_on_consts, benchmark))

        if len(benchmark) == 0:
            raise Exception("No output after restriction are not filtering everything out? {} - {}"
                    .format(pformat(restriction), work))

        final_args[work] = benchmark

    return final_args

def calculate_ticks(group_len, width):
    if group_len % 2 == 0:
        start = ((int(group_len / 2) - 1) * width * -1) - (width / 2.0)
    else:
        start = (int((group_len / 2)) * width * -1)

    temp = []
    offset = start
    for x in range(0, group_len):
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
    """progbg Line Graph"""
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
        print("[Line - ({}, {})]: {}".format(self.x_name, self.y_name, strn))

    def graph(self, ax):
        """ Create the line graph
        Arguments:
            ax: Axes object to attach data too
        """
        self.aggregation = dict()
        for work, benchmark in retrieve_relavent_data(self.workloads, self.restrict).items():
            check_one_varying(benchmark, extras=[self.x_name])
            x, y, ystd, self.aggregation[work] = retrieve_axes(
                benchmark, self.x_name, self.y_name)
            ax.errorbar(x, y, yerr=ystd, linestyle='-', fmt='o',
                        capsize=1, elinewidth=1, markersize=2, linewidth=1)
