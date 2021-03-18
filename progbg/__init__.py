"""
Programmable Benchmarking and Graphing Tool

progbg takes a user provided plan file (.py) to help with the running of benchmarks,
parsing of data, and the production of graphs and composing graphs into figures. ProgBG
provides a simple API and only requires user provide code snippets to run.  For example
providing just a function on how to parse a file.

Associated high level functions of progbg are:
    plan_execution, plan_graph, plan_figure
"""

from .core import plan_execution, plan_graph, plan_figure, plan_parse
from .core import registerbackend, registerbenchmark, registerbackend_sh
from .core import registerbenchmark_sh
from .core import compose_backends

from .globals import _sb_executions, _sb_registered_benchmarks
from .globals import _sb_registered_backend, _sb_graphs, _sb_figures

from .graphing import LineGraph, BarGraph, Bar, BarFactory

from .graphing import Histogram, CustomGraph
