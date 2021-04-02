"""
**ProgBG**: Programmable Benchmarking and Graphing Tool

progbg takes a user provided plan file (.py) to help with the running of benchmarks,
parsing of data, and the production of graphs and composing graphs into figures. ProgBG
provides a simple API and only requires user provide small code snippets to run entire automated
executions of their benchmarks.

Associated high level functions of progbg are:
    `core.plan_execution`, `core.plan_parse`, `core.plan_graph`, `core.plan_figure`
"""

from .core import plan_execution, plan_graph, plan_figure, plan_parse
from .core import registerbackend, registerbenchmark, registerbackend_sh
from .core import registerbenchmark_sh
from .core import compose_backends

from .globals import _sb_executions, _sb_registered_benchmarks
from .globals import _sb_registered_backend, _sb_graphs, _sb_figures

from .graphing import LineGraph, Line
from .graphing import BarGraph, Bar, BarFactory

from .style import get_style
