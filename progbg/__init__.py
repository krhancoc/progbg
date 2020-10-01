"""
Simple bench module
"""

from .core import plan_execution, plan_graph, plan_figure
from .core import registerbackend, registerbenchmark
from .core import Variables, DefBenchmark

from .globals import _sb_executions, _sb_registered_benchmarks
from .globals import _sb_registered_backend, _sb_graphs, _sb_figures

from .graphing import LineGraph, BarGraph, GroupBy

from .parsers import MatchParser, FileParser
