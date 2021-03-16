"""
Simple bench module
"""

from .core import plan_execution, plan_graph, plan_figure, plan_parse
from .core import registerbackend, registerbenchmark, registerbackend_sh
from .core import registerbenchmark_sh
from .core import compose_backends

from .globals import _sb_executions, _sb_registered_benchmarks
from .globals import _sb_registered_backend, _sb_graphs, _sb_figures

from .graphing import LineGraph, BarGraph, Bar, BarFactory
