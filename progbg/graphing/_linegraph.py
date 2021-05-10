from typing import List, Dict
from pprint import pformat
from enum import Enum
import pandas as pd
import os

import matplotlib as mpl
import numpy as np

from cycler import cycler, Cycler

from ._graph import Graph, GraphObject

from ..globals import _sb_executions
from ..subr import retrieve_axes, check_one_varying
from ..subr import aggregate_bench, aggregate_list
from ..util import Backend, retrieve_obj, error
from ..util import ExecutionStub
from ..style import get_style, set_style

class ConstLine(GraphObject):
    def __init__(self, value, label, index, style=":"):
        self.label = label
        self.value = value
        self.index = index
        self.style = style

    def get_data(self, restrict_on, opts):
        val = self.value._cached[0].get_stats()[self.index]
        return (self.label,  val )

class Line(GraphObject):
    def __init__(self, workload, value: str, y, label: str = None, style="--"):
        if label:
            self.label = label
        else:
            self.label = value
        self.value = value
        self.workload = workload
        self.y = y
        self.style = style


    def get_data(self, restrict_on, opts):
        d = {
                self.label: [],
                self.label + "_std":  []
            }
        for x in self.workload:
            d[self.label].append(x._cached[0].get_stats()[self.value])
            d[self.label + "_std"].append(x._cached[0].get_stats()[self.value + "_std"])
        return pd.DataFrame(d, index=self.y)

class LineGraph(Graph):
    """progbg Line Graph

    Args:
        lines (List[Line]): Workloads that the line graph will use in the WRK:BCK1/BCK2 format
        x (str): This is the variable you will be tracking.
        type (str) (Function, optional): Type of line graph (default, cdf)
        style (str, cycler): Style string for progbg styles or a cycler object to dictate custom style of lines
        formatter (Function, optional): Formatter to be used on the graph once the graph is complete
        out (str, optional): Optional name for file the user wishes to save the graph too.
        kwargs (optional): Passed to matplotlib `Axes.plot` function or optional named params below.

    Progbg optional kwargs:
        title (str): Title of the graph or figure

    Types of Line Graphs:
        default: This is just the standard line graph
        cdf: Creates a CDF line graph

    Examples:
        Suppose we have some previously defined backend `composed_backend` and workloads `Wrk`:

        >>> exec = sb.plan_execution(
        >>>     Wrk({}, [("x", range(0, 5))], iterations = 5),
        >>>     out = "out",
        >>>     backends = [composed_backend({},
        >>>         [("pass_me_in", range(0, 10, 2))])],
        >>>     parser = file_func,
        >>> )

        Note: We are executing the benchmark over a ranging value called "x". Say we want to see how
        our stat changes over this value using a line graph. The following would be done:

        >>> line1 = Line(exec, "stat-one", label="Custom Stat")
        >>> line2 = Line(exec, "stat-two", label="Custom Stat Two")
        >>> plan_graph(
        >>>     LineGraph([line1, line2],
        >>>         "x",
        >>>         restrict_on = {
        >>>             "pass_me_in", 0,
        >>>         },
        >>>         out="custom.svg"
        >>>         title="My Line Graph"
        >>>     )

        We restrict on `pass_me_in = 0` as in the above execution we are executing over this as well so
        we need to isolate on one changing value for the line graph.
    """


    def __init__(self, lines, out, formatters=[], style="color_a"):
        self.workloads = []
        self.consts = []
        for c in lines:
            if isinstance(c, ConstLine):
                self.consts.append(c)
            else:
                self.workloads.append(c)
        self._restrict_on = {}
        self._opts = {}
        self.html_out = ".".join(out.split(".")[:-1]) + ".svg"
        self.formatter = formatters
        self.formatters = formatters
        self.style = style
        self.out = out

    def _graph(self, ax, data):
        consts = [ x.get_data(self._restrict_on, self._opts) for x in 
                self.consts ]
        vals = [ x for x in data[0].T.columns]
        styles = [ x.style for x in self.workloads ]
        styles_consts = [ x.style for x in self.consts ]

        data = pd.concat(data, axis = 1)
        consts = [ pd.DataFrame({ c[0] : [c[1]] * len(vals) }, index=vals) for c in consts ]
        if len(consts):
            consts = pd.concat(consts, axis = 1)

        cols = [ c for c in data.columns if c[-4:] != "_std"]
        cols_std = [ c for c in data.columns if len(c) > 4 and c[-4:] == "_std"]
        d = data[cols]
        std = data[cols_std]
        std.columns = [ x[:-4] for x in std.columns ]
        y = [ x for x in d.T.columns ]

        tmp = iter(self.style)
        for i, x in enumerate(d.columns):
            vl = next(tmp)
            ax.errorbar(y, d[x].tolist(), fmt=styles[i], yerr=std[x], linewidth=1, **vl)
        if len(consts):
            for i, x in enumerate(consts.columns):
                vl = next(tmp)
                ax.plot(y, consts[x].tolist(), styles_consts[i], markersize=6, 
                        **vl)

        ylim = ax.get_ylim()
        ylim = (0, ylim[1])
        ax.set_ylim(ylim)
