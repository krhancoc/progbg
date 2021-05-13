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
        >>> l3 = Line([e1, (20, 2), e3], "data1", x=[0, 1, 2])
        >>> # Using a single integer or flat specifies a constant line on the graph
        >>> l4_constant = Line(100, "data1")
    """

    def __init__(self, execution, value: str, 
            x=None, label: str = None, 
            style="--", color=None):
        if label:
            self.label = label
        else:
            self.label = value
        self.value = value
        self.color = color

        self.workload = execution
        self.x = x
        self.style = style
        if isinstance(x, str):
            assert not isinstance(
                x, list
            ), "When x is data ID, only one execution can be specified"

        if isinstance(x, list):
            assert len(x) == len(
               execution 
            ), "When x is a list, execution list length must equal x list length"

    def get_data(self, restrict_on, iter=None):
        # Check is list of elements
        d = {self.label: [], self.label + "_std": []}
        if isinstance(self.workload, list):
            for x in self.workload:
                if isinstance(x, tuple):
                    d[self.label].append(x[0])
                    d[self.label + "_std"].append(x[1])
                else:
                    d[self.label].append(x._cached[0].get_stats()[self.value])
                    d[self.label + "_std"].append(
                        x._cached[0].get_stats()[self.value + "_std"]
                    )

            return pd.DataFrame(d, index=self.x)
        else:
            if isinstance(self.workload, int):
                d[self.label] = self.workload
                d[self.label + "_std"] = 0

                return pd.DataFrame(d, index=["CONSTANT"])
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

        self.workloads = lines
        self.html_out = ".".join(self.out.split(".")[:-1]) + ".svg"

    def _graph(self, ax, data):
        # It seems like styles is not respected setting them so we will manually do them
        style = iter(get_style_cycler())
        for d in data:
            tmp = next(style)
            # Filter out std and regular data columns
            cols = [c for c in d.columns if c[-4:] != "_std"]
            cols_std = [c for c in d.columns if c[-4:] == "_std"]
            x = d[cols]
            x_std = d[cols_std]

            # Since we are lines should only have one value in each column
            lab = [ c for c in x.columns ][0]
            lab_std = [ c for c in x_std.columns ][0]

            # Check for constant label
            if "CONSTANT" in d.index:
                val = x.iloc[0][lab]
                ax.axhline(y=val, **tmp)
            else:
                y = [x for x in d.T.columns]
                # Extract lists from the dataframe
                x_list = [x.loc[v][lab] for v in y ]
                x_std_list = [x_std.loc[v][lab_std] for v in y ]
                if self.std:
                    ax.errorbar(y, x_list, yerr=x_std_list, **tmp)
                else:
                    ax.plot(y, x_list, **tmp)
