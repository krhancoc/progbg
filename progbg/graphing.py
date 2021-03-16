# pylint: disable-msg=E0611,E0401,C0103,W0703,R0903,R0913,R0914
"""
Graphing Module

Holds all related code around the different graphs the progbg supports
"""
from typing import List, Dict
from pprint import pformat
from enum import Enum
import pandas as pd
import os
#import sqlite3

import matplotlib as mpl
import numpy as np

from .globals import _sb_executions
from .subr import retrieve_axes, check_one_varying
from .subr import aggregate_bench, aggregate_list
from .format import check_formatter
from .util import Backend, retrieve_obj, error

mpl.use("pgf")

TYPES = ['r--', 'bs', 'g^', 'p*']
COLORS = ['teal', 'limegreen', 'mediumorchid',
          'crimson', 'peru', 'tomato', 'silver', 'lightsalmon']
PATTERNS = ["**", "++", "//", "xx", "oo"]
PATTERNS = ["\\\\", "..", "//", "++", "OO"]
ALTERNATE = [
    {
        "hatch": "//",
        "color": "white",
    },
    {"color": "grey"},
    {
        "color": "white",
        #            "hatch": "..",
        #            "edgecolor": "teal"
    },
    {"color": "darkgrey"}]

pgf_with_pdflatex = {
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 10,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 10,
    "pgf.texsystem": "pdflatex",
    "pgf.rcfonts": False
}

mpl.rcParams.update(pgf_with_pdflatex)


def reformat_large(tick_val):
    if tick_val >= 1000000000:
        val = round(tick_val / 1000000000, 1)
        new_tick_format = '{:}B'.format(val)
    elif tick_val >= 1000000:
        val = round(tick_val / 1000000, 1)
        new_tick_format = '{:}M'.format(val)
    elif tick_val >= 1000:
        val = round(tick_val / 1000, 1)
        new_tick_format = '{:}K'.format(val)
    else:
        new_tick_format = tick_val

    new_tick_format = str(new_tick_format)

    index_of_decimal = new_tick_format.find(".")
    if index_of_decimal != -1:
        value_after_decimal = new_tick_format[index_of_decimal + 1]
        if value_after_decimal == "0":
            new_tick_format = new_tick_format[0:index_of_decimal] + \
                new_tick_format[index_of_decimal + 2:]

    return new_tick_format


def normalize(group_list, index_to):
    normal = group_list[index_to]
    final_list = []
    for group in group_list:
        stddev = group[1] / group[0]
        newval = group[0] / normal[0]
        final_list.append((newval, stddev * newval))
    return final_list


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
        output = any([_sb_executions[work.split(":")[0]].param_exists(key)
                      for work in workloads])
        if not output:
            print(output)
            error("Unrecognized key for retrict constraint: {}".format(key))


def _retrieve_data_files(execution, restriction):
    files = [os.path.join(execution.out, path)
             for path in os.listdir(execution.out)]
    benchmarks = []
    for file in files:
        try:
            obj = retrieve_obj(file)
            if _is_good(obj, restriction):
                benchmarks.append(obj)
        except:
            continue
    if len(benchmarks) == 0:
        error("No output after restriction are not filtering everything out? {} - {}"
              .format(pformat(restriction), execution.name))

    return benchmarks


def _retrieve_data_db(execution, restriction):
    conn = sqlite3.connect(execution.out)
    if execution.backends:
        sq_friendly = Backend.out_to_sql(restriction['_backend'])
        tablename = "{}__{}__{}".format(
            execution.name, execution.bench.name, sq_friendly)
        if tablename not in execution.tables:
            raise Exception("Table not present, this should not occur")
    else:
        tablename = "{}__{}".format(execution.name, execution.bench.name)

    new_restrict = {k: restriction[k]
                    for k in execution.tables[tablename] if k in restriction}
    c = conn.cursor()
    # Eliminate quotes.  Deciding whether to default include them for better SQL or default remove
    # for readability
    new_restrict = {k: restriction[k]
                    for k in execution.tables[tablename] if k in restriction}

    # This feels not good to use -- have to find a nice abstraction for converting between
    # SQL Friendly names and names that feel good for the user, should not be hard coded
    if execution.backends:
        new_restrict["_backend"] = sq_friendly

    clauses = ["({}='{}')".format(k, v) for k, v in new_restrict.items()]
    full = " AND ".join(clauses)
    quotes = ['{}'.format(val) for val in execution.tables[tablename]]
    exec_str = "SELECT {} FROM {} WHERE ({})".format(
        ",".join(quotes), tablename, full)
    c.execute(exec_str)
    data = c.fetchall()
    if not len(data):
        raise Exception("Restriction too fine - no data found")

    if len(data[0]) != len(execution.tables[tablename]):
        raise Exception("Data types not matching with sqldb")

    benchmarks = [dict(zip(execution.tables[tablename], vals))
                  for vals in data]
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


def filter(metrics, restrict_dict):
    final_metric = []
    for metric in metrics:
        if all(item in metric.get_stats().items() for item in restrict_dict.items()):
            final_metric.append(metric)
    return final_metric


class BarGraph:
    """progbg Bar Graph"""

    def __init__(
            self,
            workloads: List,
            inner_labels,
            group_labels,
            formatter=None,
            restrict_on=None,
            width=0.3,
            out: str = None):

        self.workloads = workloads
        self.out = out
        self.aggregation = None
        self.restrict_on = restrict_on
        self.width = width
        self.gl = group_labels
        self.il = inner_labels
        self.formatter = formatter

    def graph(self, ax, silent=False):

        flatten = [x for sub in self.workloads for x in sub]
        # We create a matrix that is the number of bars wide, and the number
        # of categories that the bars are broken down tall. Certain bars may not
        # be broken down at all and so those categories are zero filled
        column_space = dict()
        for wl in flatten:
            for k in wl.composed:
                column_space[k] = True

        # Each unique breakdown label gets its own dimension in the column space
        column_space = list(column_space.keys())
        # Create each column as a row, we will just rotate matrix
        matrix = []
        for wl in flatten:
            arr = np.zeros(len(column_space))
            metrics = filter(wl.workload._cached, self.restrict_on)
            if (len(metrics) > 1):
                self.print(
                    "Warning: Restriction not fine grained enough, multiple selections are available", silent)
            metrics = metrics[0].get_stats()
            for x in wl.composed:
                arr[column_space.index(x)] = metrics[x]
            matrix.append(arr)
        matrix = np.array(matrix)
        df = pd.DataFrame(matrix, columns=column_space, index=[
                          b.workload.name for b in flatten])

        width = self.width
        df.plot(kind="bar", stacked=True, width=width, ax=ax)

        h, _ = ax.get_legend_handles_labels()
        x_ticks = []
        children = h[0].get_children()
        x_tick_at = children[0].get_x()
        x_tick_at_last = children[-1].get_x() + width
        distance = x_tick_at_last - x_tick_at
        inter_bar = 0.01
        inter_space = (distance - ((width + inter_bar) *
                                   len(flatten))) / (len(self.workloads) + 1)
        # For some reason the first bar starts at a negative X co-ordinate, so dont really
        # know how the coordinate system in matplot lib currently works and docs say otherwise.  So
        # for now just adding to adjust for this
        x_tick_at = inter_space + x_tick_at

        for group in self.workloads:
            x_ticks.append(x_tick_at)
            for wl in group[1:]:
                x_ticks.append(x_tick_at + width + inter_bar)
                x_tick_at += width + inter_bar
            x_tick_at += width + inter_space

        if (x_ticks[-1] + width / 2) > x_tick_at_last:
            self.print("Width param is too large, please reduce")
            return

        for x in range(0, len(column_space)):
            for i, child in enumerate(h[x].get_children()):
                child.set_x(x_ticks[i])
        ax.set_xticks([x + (width / 2) for x in x_ticks])
        ax.set_xticklabels([b.label for b in flatten])

    def print(self, strn: str, silent) -> None:
        """Pretty printer for BarGraph"""
        if silent:
            return

        print("\033[1;34m[{}]:\033[0m {}".format(self.out, strn))


class Bar:
    def __init__(self, wl, composed_of, label):
        if isinstance(composed_of, str, ):
            self.composed = [composed_of]
        else:
            self.composed = composed_of
        self.workload = wl
        self.label = label


class BarFactory:
    def __init__(self, wl):
        self.workload = wl

    def __call__(self, composed_of, label=None):
        if not label:
            label = self.workload.name
        return Bar(self.workload, composed_of, label)


class Histogram:
    """ ProgBG Histogram plots a specific label over its common entries.
    """

    def __init__(
            self,
            label,
            workload: str,
            out: str = None,
            filter_func=None,
            kwargs=None,
            formatter=None):

        self.workload = workload
        self.label = label
        self.filter_func = filter_func
        self.kwargs = kwargs
        self.formatter = formatter
        self.out = out

    def graph(self, ax, silent=False):
        self.print("Graphing", silent)
        benchmarks = retrieve_relavent_data([self.workload], [])[self.workload]
        aggregate = aggregate_list(benchmarks, self.filter_func)

        default_kwargs = {
            'edgecolor': 'black',
            "density": True,
            "bins": 10,
            "color": "lightgrey"
        }

        if (self.kwargs):
            default_kwargs.update(self.kwargs)

        ax.hist(aggregate[self.label], **default_kwargs)

    def print(self, strn: str, silent) -> None:
        """Pretty printer for LineGraph"""
        if silent:
            return

        print("\033[1;34m[{}]:\033[0m {}".format(self.out, strn))


class CustomGraph:
    def __init__(
            self,
            workloads: List[str],
            graph_func,
            out: str = None,
            filter=None,
            restrict: Dict = None,
            formatter=None):

        self.workloads = workloads
        self.graph_func = graph_func
        self.filter = filter
        self.formatter = formatter
        if restrict:
            self.restrict = restrict
        else:
            self.restrict = dict()
        self.out = out

    def graph(self, ax, silent=False):
        self.aggregation = dict()
        for work, benchmark in retrieve_relavent_data(self.workloads, self.restrict).items():
            self.aggregation[work] = aggregate_bench(benchmark, self.filter)
        self.graph_func(ax, self.aggregation)


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

    def print(self, strn: str, silent) -> None:
        """Pretty printer for LineGraph"""
        if silent:
            return

        print("\033[1;34m[{}]:\033[0m {}".format(self.out, strn))

    def graph(self, ax, silent=False):
        """ Create the line graph
        Arguments:
            ax: Axes object to attach data too
        """
        self.print("Graphing", silent)
        self.aggregation = dict()
        for work, benchmark in retrieve_relavent_data(self.workloads, self.restrict).items():
            check_one_varying(benchmark, extras=[self.x_name])
            x, y, ystd, self.aggregation[work] = retrieve_axes(
                benchmark, self.x_name, self.y_name)
            vals = sorted(list(zip(x, y)), key=lambda x: x[0])
            x, y = zip(*vals)
            ax.plot(x, y, linestyle='-', linewidth=1, label=work)

        ax.legend()
