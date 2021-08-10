from typing import List, Dict
from pprint import pformat
from enum import Enum
import pandas as pd
import os

import matplotlib as mpl
import numpy as np

from cycler import cycler, Cycler

from ._util import filter, axis_kwargs
from ._graph import Graph, GraphObject

from ..globals import _sb_executions
from ..util import Backend, retrieve_obj, error
from ..util import ExecutionStub
from ..style import get_style, set_style


class Bar(GraphObject):
    """Bar object used within `BarGraph`

    This represent a bar within a bar graph.  Its construction used an execution object.
    Once an execution is done, metrics objects are pulled and summarized into means and standard
    deviations.

    The keys within the `core.Metrics` are used to compose bars.  You may select just one.
    But optionally you may compose bars of many metrics (See matplotlibs stacked bar).

    Arguments:
        wl (Execution, List):  Execution object or list for constant values
        composed_of (List): A key for the data to use, or optionally a list of keys
        label (str): Label of the bar

    Example:
        >>> e1 = plan_execution(...)
        >>> e2 = plan_execution(...)
        >>> e3 = plan_execution(...)
        >>>
        >>> b1 = Bar(e1, ["data1", "data2"])
        >>>
        >>> # Below Bar: data1 = 10, data2 = 22
        >>> b1 = Bar([10, 22], ["data1", "data2"])
    """

    def __init__(self, wl, composed_of, label=None):

        self.composed = composed_of
        if isinstance(wl, list):
            d = dict()
            for i, x in enumerate(self.composed):
                d[x] = wl[i]
            wl = ExecutionStub(**d)
        self.workload = wl
        self.label = label
        if isinstance(label, str):
            self.label = [label]
        if label is None:
            self.label = [""]

    def get_data(self, restrict_on):
        d = filter(self.workload._cached, restrict_on)[0].get_stats()
        composed = []
        for c in self.composed:
            composed.append(c)
            composed.append(c + "_std")
        label = self.label
        return pd.DataFrame({c: d[c] for c in composed}, index=self.label).T


class BarGroup(GraphObject):
    """Groups Data as bars on single value

    Arguments:
        executions (List): List of executions to include in group
        cat (str): category to compare the workloads
        label (List[str]): Labels for the elements in the group

    Examples:
        >>> e1 = plan_execution(...)
        >>> e2 = plan_execution(...)
        >>> e3 = plan_execution(...)
        >>>
        >>> b1 = BarGroup([e1, e2, e3], "data1", ["exec1", "exec2", "exec3"])
        >>> b2 = BarGroup([e1, 20, e3], "data1", ["exec1", "normal", "exec3"])
    """

    def __init__(self, executions, cat, label):
        self.wls = executions
        self.cat = cat
        self.label = label

    def get_data(self, restrict_on):
        bars = []
        for i, w in enumerate(self.wls):
            bars.append(Bar(w, [self.cat], [self.label[i]]))
        dfs = [b.get_data(restrict_on).T for b in bars]
        return dfs

    def bars(self):
        bars = []
        half = (len(self.wls) - 1 / 2) - 1
        for i, w in enumerate(self.wls):
            if i == half:
                bars.append(Bar(w, self.cat, self.label[i]))
            else:
                bars.append(Bar(w, self.cat, None))
        return bars


class BarFactory:
    """Ease of use Factory Class

    Used to quickly be able to make many bars from one Execution object
    """

    def __init__(self, wl):
        self.workload = wl

    def __call__(self, composed_of, label=None):
        if not label:
            label = self.workload.name
        return Bar(self.workload, composed_of, label)


class BarGraph(Graph):
    """Bar Graph

    Args:
        workloads (List): A list of list of bars.  Each list is a grouping of bars to be graphs.
        group_labels (List): Labels associated to each grouped list in workloads.
        formatter (Function, optional): Function object for post customization of graphs.
        width (float): Width of each bar
        out (Path): Output file for this single graph to be saved to
        style (str): Style of the graph (default: color_a)
        kwargs (optional): Passed to matplotlib `Axes.plot` function or optional named params below.

    Progbg optional kwargs:
        title (str): Title of the graph or figure

    Examples:
        Suppose we have some previously defined execution called `exec`.

        >>> exec = plan_execution(...)
        >>> bar1 = Bar(exec, "stat-one", label="Custom Stat")
        >>> bar2 = Bar(exec, "stat-two", label="Custom Stat Two")
        >>> plan_graph(
        >>>     BarGraph([[bar1, bar2]],
        >>>         group_labels=["These a grouped!"],
        >>>         out="custom.svg"
        >>>     )

        The above example would create a graph grouping both bar1, and bar2 next to each other. The below example
        would seperate bar1 and bar2. "stat-one", and "stat-two", are both values that would have been added to the
        associated `core.Metrics` object which is passed through the parser functions provided by the user.

        >>> plan_graph(
        >>>     BarGraph([[bar1], [bar2]],
        >>>         group_labels=["Group 1!", "Group 2!"],
        >>>         out="custom.svg"
        >>>     )
    """

    def __init__(self, workloads: List, **kwargs):
        super().__init__(**kwargs)

        default_options = dict(
            std=True,
            group_labels=[],
            log=False,
            width=0.5,
        )

        for prop, default in default_options.items():
            setattr(self, prop, kwargs.get(prop, default))

        self.workloads = workloads
        self.html_out = ".".join(self.out.split(".")[:-1]) + ".svg"

    def _graph(self, ax, data):
        if isinstance(self.workloads[0], BarGroup):
            # Retrieve top level labels
            data = [pd.concat(x) for x in data]
            data = pd.concat(data, axis=1)
            cols = [c for c in data.columns if c[-4:] != "_std"]
            cols_std = [c for c in data.columns if len(c) > 4 and c[-4:] == "_std"]
            cols = list(set(cols))
            cols_std = list(set(cols_std))
            df = data[cols].T
            std = data[cols_std]
            std.columns = [x[:-4] for x in std.columns]
            std = std.T
            df.plot.bar(rot=-90, ax=ax, yerr=std, capsize=4, width=self.width)
            if self.log:
                ax.set_yscale("log")
        else:
            data = pd.concat(data, axis=1).T
            cols = [c for c in data.columns if c[-4:] != "_std"]
            cols_std = [c for c in data.columns if len(c) > 4 and c[-4:] == "_std"]
            df = data[cols]
            std = data[cols_std].T
            df.plot(rot=-90, kind="bar", stacked=True, ax=ax)
