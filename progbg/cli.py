"""CLI Module

This module processes and handles all command line interface input
and dispatches commands to the proper area
"""
# pylint: disable-msg=E0611,E0401

import os
from argparse import ArgumentParser

from .core import execute_plan
from .serve import create_server


def cli_entry():
    """Main entry point for the command line interface"""

    parser = ArgumentParser(
        description="A simple programmable benchmarking and graphing tool"
    )
    parser.add_argument("plan", help="Location of the plan.py file")
    parser.add_argument(
        "-p",
        type=int,
        help="Creates a server to serve the generated graphs at the port provided",
    )
    parser.add_argument(
        "--no-exec",
        action="store_true",
        help="Do not re-run any executions \
            (Note: This assume all output defined in graphs are already progbg format)",
    )
    parser.add_argument(
        "--no-reinit",
        action="store_true",
        help="Do not re-initialize backends during each iteration when running benchmarks",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Turns on printing within the run, init, and uninit methods provided by user",
    )

    args = parser.parse_args()
    if not os.path.isfile(args.plan):
        print("Issue finding the plan.py file/")
        return

    globs = execute_plan(args.plan, args)

    if args.p:
        create_server(
            globs["_sb_executions"],
            globs["_sb_graphs"],
            globs["_sb_figures"],
            os.path.abspath("graphs"),
        ).run(port=args.p)
