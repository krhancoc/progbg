from typing import List, Dict
from pprint import pformat
from enum import Enum
import pandas as pd
import os

import matplotlib as mpl
import numpy as np

from cycler import cycler, Cycler

from ._graph import Graph, GraphObject
from ._util import filter

from ..globals import _sb_executions
from ..util import Backend, retrieve_obj, error
from ..util import ExecutionStub
from ..style import get_style, set_style, get_style_cycler


class ConstLine(GraphObject):
    """Const Line Object
    Will plot a horizontal line

    Arguments:
        value: Value for constant line, either a workload or straight number
        label (str): Label for the line
        index: Label used for the value's index. Used when comparing against other lines
    """

    def __init__(self, value, label, index, style=":"):
        self.label = label
        self.value = value
        self.index = index
        self.style = style

    def get_data(self, restrict_on):
        val = self.value._cached[0].get_stats()[self.index]
        return (self.label, val)


class Line(GraphObject):
    """Line Object
    Used to specify a line within a graph.

    Arguments:
        workload (Execution, list[Execution]): Specifies an Execution or list to produce a series.
        value (str): Data label to capture in the series
        x (str, list): When one execution is specified, represent string label to specify x axis.

    Optional:
        label (str): Label for the line
        style (str): Style for the line

    Examples:
        >>> e1 = plan_execution(...)
        >>> e2 = plan_execution(...)
        >>> e3 = plan_execution(...)
        >>>
        >>> l1 = Line(e1, "data1", x="x_axis_data")
        >>> # In below line object, line at point 0 will specify e1["data1"],
        >>> # 1 will specify e2["data1"], and 2 will specify e3["data1"]
        >>> l2 = Line([e1, e2, e3], "data1", x=[0, 1, 2])
    """

    def __init__(self, execution, value: str, x=None, label: str = None, style="--"):
        if label:
            self.label = label
        else:
            self.label = value
        self.value = value
        self.workload = execution
        self.x = x
        self.style = style
        assert x is not None, "x must be specified"

        if isinstance(x, str):
            assert not isinstance(
                x, list
            ), "When x is data ID, only one execution can be specified"

        if isinstance(x, list):
            assert len(x) == len(
                self.workload
            ), "When x is a list, workload list length must equal x list length"

    def get_data(self, restrict_on, iter=None):
        d = {self.label: [], self.label + "_std": []}
        if isinstance(self.workload, list):
            for x in self.workload:
                d[self.label].append(x._cached[0].get_stats()[self.value])
                d[self.label + "_std"].append(
                    x._cached[0].get_stats()[self.value + "_std"]
                )

            return pd.DataFrame(d, index=self.x)
        else:
            metrics = filter(self.workload._cached, restrict_on)
            dicts = [d.get_stats() for d in metrics]
            df = pd.DataFrame(dicts)
            df = df.groupby([self.x])

            return pd.DataFrame(df.mean()[[self.value, self.value + "_std"]])


class LineGraph(Graph):
    """progbg Line Graph

    Args:
        lines (List[Line]): Workloads that the line graph will use in the WRK:BCK1/BCK2 format
        type (str) (Function, optional): Type of line graph (default, cdf)
        style (str, cycler): Style string for progbg styles or a cycler object to dictate custom style of lines
        formatter (Function, optional): Formatter to be used on the graph once the graph is complete
        out (str, optional): Optional name for file the user wishes to save the graph too.
        kwargs (optional): Passed to matplotlib `Axes.plot` function or optional named params below.

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

        >>> line1 = Line(exec, "stat-one", x="x", label="Custom Stat")
        >>> line2 = Line(exec, "stat-two", x="x", label="Custom Stat Two")
        >>> plan_graph(
        >>>     LineGraph([line1, line2],
        >>>         restrict_on = {
        >>>             "pass_me_in", 0,
        >>>         },
        >>>         out="custom.svg"
        >>>     )

        We restrict on `pass_me_in = 0` as in the above execution we are executing over this as well so
        we need to isolate on one changing value for the line graph.
    """

    def __init__(self, lines, **kwargs):
        super().__init__(**kwargs)

        default_options = dict(
            std=False,
            group_labels=[],
            type="default",
            log=False,
            width=0.5,
        )

        for prop, default in default_options.items():
            setattr(self, prop, kwargs.get(prop, default))

        self.consts = []
        self.workloads = []
        for c in lines:
            if isinstance(c, ConstLine):
                self.consts.append(c)
            else:
                self.workloads.append(c)

        self.html_out = ".".join(self.out.split(".")[:-1]) + ".svg"

    def _graph(self, ax, data):
        # Hack for dealing with const lines.
        consts = [x.get_data(self._restrict_on) for x in self.consts]
        vals = [x for x in data[0].T.columns]
        styles = [x.style for x in self.workloads]
        styles_consts = [x.style for x in self.consts]

        # Combine data
        data = pd.concat(data, axis=1)
        consts = [pd.DataFrame({c[0]: [c[1]] * len(vals)}, index=vals) for c in consts]
        if len(consts):
            consts = pd.concat(consts, axis=1)

        # Pull out the standard deviation and such
        cols = [c for c in data.columns if c[-4:] != "_std"]
        cols_std = [c for c in data.columns if len(c) > 4 and c[-4:] == "_std"]
        d = data[cols]
        std = data[cols_std]
        std.columns = [x[:-4] for x in std.columns]
        y = [x for x in d.T.columns]

        # It seems like styles is not respected setting them so we will manually do them
        style = iter(get_style_cycler())
        for i, x in enumerate(d.columns):
            tmp = next(style)
            if self.std:
                ax.errorbar(y, d[x].tolist(), yerr=std[x], **tmp, label=x)
            else:
                ax.plot(y, d[x].tolist(), styles[i], **tmp, label=x)
        if len(consts):
            for i, x in enumerate(consts.columns):
                tmp = next(style)
                ax.plot(y, consts[x].tolist(), **tmp, label=x)
