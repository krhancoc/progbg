"""Module to hold all the globals used within progbg"""

_sb_registered_benchmarks = {}
_sb_registered_backend = {}
_sb_executions = {}
_sb_graphs = {}
_sb_figures = {}
"""Registration globals

These globals are used by the plan_* functions, as well as the
register_* decoraters to keep track of what has been planned
by the user
"""

GRAPHS_DIR = "graphs"
"""str: default graphs directory"""
PROGBG_EXTENSION = ".progbg"
"""str: Extension used for file already parsed by parsers"""


# String versions of the dictionaries
_EDIT_GLOBAL_TABLE = {
    "_sb_registered_benchmarks": _sb_registered_benchmarks,
    "_sb_registered_backend": _sb_registered_backend,
    "_sb_executions": _sb_executions,
    "_sb_graphs": _sb_graphs,
    "_sb_figures": _sb_figures,
}
"""Globals Table

Table to allow us to quickly access applicable global variables within
the globals() table
"""

_sb_rnames = ["_backend", "_execution_name", "_iter", "_workload"]
