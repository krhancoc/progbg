"""Utility function and classes used throughout progbg"""

import itertools
import sys
import os
from pprint import pformat
from typing import List, Dict, Tuple

from matplotlib.ticker import FuncFormatter

import numpy as np
import pandas as pd

from .globals import _sb_rnames

REQUIRED = object()


class Metrics:
    """Metrics collection object

    This object is given to executions to allow for users to specify what data
    must be kept. The main functio that should be used by users is the add_metric
    function, which simply appends data points to a list to be used to calculate
    means and standard deviation later
    """

    def __init__(self):
        self._vars = dict()
        self._consts = dict()

    def add_metric(self, key, val):
        """Add a data point to a metric key

        Args:
            key (str): Key to add value to
            val (int, float): value to append to a list

        Example:
            Suppose we have a parser we wish to use. This parser takes
            both a metrics object and a file path.

            >>> def my_parser(metrics: Metrics, out: str):
            >>>     with open(out, 'r') as f:
            >>>         mydata = f.read()
            >>>         val = find_specific_value(mydata)
            >>>         metrics.add_metric('my-stored-val', val)
        """
        if key not in self._vars:
            self._vars[key] = [val]
        else:
            self._vars[key].append(val)

    def to_file(self, path):
        stats = self.get_stats()
        with open(path, "w") as f:
            for k, val in stats.items():
                f.write("{}={}\n".format(k, val))

    def add_metrics(self, key, vals):
        for v in vals:
            self.add_metric(key, v)

    def stat(self, key):
        obj = self.get_stats()
        return obj[key]

    def __getitem__(self, key):
        obj = self.get_stats()
        if key in self._vars:
            return self._vars[key]

        return self._consts[key]

    def __contains__(self, key):
        return (key in self._vars) or (key in self._consts)

    def add_constant(self, key, val):
        """Add a constant to a metric object

        Args:
            key (str): Key for constant
            val (obj): Value of this constant
        """
        self._consts[key] = val

    def _combine(self, other: Dict):
        for key, val in other._vars.items():
            if key in self._vars:
                self._vars[key].append(val)
            else:
                self._vars[key] = val

    def get_stats(self):
        """Returns the metrics object

        Will return the current metrics of this object. Each associated
        key will have its mean and standard deviation calculated.  Standard deviation
        is stored within a "_std" key.

        For example. If I had some metrics with associated key "my-metric". The returned
        dictionary would store the mean at key "my-metrics", and store standard deviation
        at key "my-metrics_std".  This allows users to also manually set standard deviation
        of objects if needed. For example when using then `plan_parse` style executions.

        Returns:
            dict
        """
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


def normalize(group_list, index_to):
    normal = group_list[index_to]
    final_list = []
    for group in group_list:
        stddev = group[1] / group[0]
        newval = group[0] / normal[0]
        final_list.append((newval, stddev * newval))
    return final_list


def silence_print():
    sys.stdout = open(os.devnull, "w")


def restore_print():
    sys.stdout.close()
    sys.stdout = sys.__stdout__


def error(strn: str):
    print("\033[0;31m[Error]:\033[0m {}".format(strn))
    sys.exit(-1)


def dump_obj(file: str, obj: Dict):
    """Dump dictionary to file key=val"""
    with open(file, "w") as ofile:
        for key, val in obj.items():
            line = "{}={}\n".format(key, val)
            ofile.write(line)


def retrieve_obj(file: str) -> Dict:
    """Retrieve dictionary from file key=val"""
    obj = {}
    with open(file, "r") as ofile:
        for line in ofile.readlines():
            vals = line.strip().split("=")
            try:
                obj[vals[0]] = vals[1]
            except:
                print("Issue with file: {}".format(file))
                exit(0)
    return obj


class Variables:
    """
    Variables is a container class for variables for a given execution

    This will define the permutations that can occur for those that utilize the
    class (see Variables.produce_args documentation)

    Attributes:
        const: A dictionary of argument names to values that will be passed
        var: A tuple of an argument name and some iterable object
    """

    def __init__(self, consts: Dict = None, var: List[Tuple[str, List]] = None) -> None:
        if len(var):
            if any([i in consts for i in _sb_rnames]) or (var[0] in _sb_rnames):
                raise Exception(
                    "Cannot use a reserved name for a variable {}".format(
                        pformat(_sb_rnames)
                    )
                )
            for vals in var:
                if vals[0] in consts:
                    raise Exception(
                        "Name defined as constant and varying: {}".format(vals[0])
                    )

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
        if not len(self.var):
            return [dict(self.consts)]

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
        return (name in self.consts) or any([name == x[0] for x in self.var])

    def y_names(self) -> List[str]:
        """Returns the names of varrying or responding variables"""
        return [x[0] for x in self.var]

    def const_names(self) -> List[str]:
        """Returns names of constants"""
        return self.consts.keys()

    def __repr__(self) -> str:
        return pformat(vars(self), width=30)


class Backend:
    def __init__(self, path, variables):
        self.backends = path.split("/")
        self.runtime_variables = variables

    @staticmethod
    def user_to_sql(path):
        return "_b_".join(path.split("/"))

    @staticmethod
    def user_to_out(path):
        return "-".join(path.split("/"))

    @staticmethod
    def out_to_user(path):
        return "/".join(path.split("-"))

    @staticmethod
    def out_to_sql(path):
        return "_b_".join(path.split("-"))

    @property
    def path_sql(self):
        return "_b_".join(self.backends)

    @property
    def path_user(self):
        return "/".join(self.backends)

    @property
    def path_out(self):
        return "-".join(self.backends)

    def __eq__(self, path):
        return (
            (self.path_sql == path)
            or (self.path_out == path)
            or (self.path_user == path)
        )


class ExecutionStub:
    def __init__(self, **kwargs):
        metric = Metrics()
        for k, v in kwargs.items():
            metric.add_constant(k, v)
        self._cached = [metric]


def set_size(w, h):
    def format(fig, axes):
        fig.set_figheight(h)
        fig.set_figwidth(w)
        fig.tight_layout()

    return format


def _axis_formatter(type, label="", tf=None):
    units = dict(
        p=1e-12,
        n=1e-9,
        u=1e-6,
        m=1e-3,
        c=0.01,
        d=0.1,
        S=1.0,
        da=10.0,
        h=100.0,
        k=float(10e3),
        M=float(10e6),
        G=float(10e9),
        T=float(10e12),
    )

    def tmp_num(tf):
        def number_formatter(number, pos=0):
            if tf:
                to_from = units[tf[0]] / units[tf[1]]
                number = to_from * number
            magnitude = 0
            while abs(number) >= 1000:
                magnitude += 1
                number /= 1000
            return "%d%s" % (number, ["", "k", "M", "B", "T", "Q"][magnitude])

        return number_formatter

    def format(fig, axes):
        getattr(axes, type).set_major_formatter(FuncFormatter(tmp_num(tf)))
        axes.set_ylabel(label)

    return format


def yaxis_formatter(label="", tf=None):
    return _axis_formatter("yaxis", label, tf)


def xaxis_formatter(label="", tf=None):
    return _axis_formatter("xaxis", label, tf)


def legend_remap(d):
    def tmp(fig, axes):
        h, labels = ax.get_legend_handles_labels()
        l = [d[l] for l in labels]
        ax.legend(h, l)

    return tmp
