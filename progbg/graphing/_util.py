from typing import List, Dict
from pprint import pformat
from enum import Enum
import pandas as pd
import os

# import sqlite3

import matplotlib as mpl
import numpy as np

from cycler import cycler, Cycler

from ..globals import _sb_executions
from ..subr import retrieve_axes, check_one_varying
from ..subr import aggregate_bench, aggregate_list
from ..util import Backend, retrieve_obj, error
from ..util import ExecutionStub
from ..style import get_style, set_style

def _is_good(benchmark, restriction):
    for key, val in restriction.items():
        if key not in benchmark:
            continue
        if str(benchmark[key]) != str(val):
            return False

    return True


def _retrieve_data_files(execution, restriction):
    files = [os.path.join(execution.out, path) for path in os.listdir(execution.out)]
    benchmarks = []
    for file in files:
        try:
            obj = retrieve_obj(file)
            if _is_good(obj, restriction):
                benchmarks.append(obj)
        except:
            continue
    if len(benchmarks) == 0:
        error(
            "No output after restriction are not filtering everything out? {} - {}".format(
                pformat(restriction), execution.name
            )
        )

    return benchmarks


def _retrieve_data_db(execution, restriction):
    conn = sqlite3.connect(execution.out)
    if execution.backends:
        sq_friendly = Backend.out_to_sql(restriction["_backend"])
        tablename = "{}__{}__{}".format(
            execution.name, execution.bench.name, sq_friendly
        )
        if tablename not in execution.tables:
            raise Exception("Table not present, this should not occur")
    else:
        tablename = "{}__{}".format(execution.name, execution.bench.name)

    new_restrict = {
        k: restriction[k] for k in execution.tables[tablename] if k in restriction
    }
    c = conn.cursor()
    # Eliminate quotes.  Deciding whether to default include them for better SQL or default remove
    # for readability
    new_restrict = {
        k: restriction[k] for k in execution.tables[tablename] if k in restriction
    }

    # This feels not good to use -- have to find a nice abstraction for converting between
    # SQL Friendly names and names that feel good for the user, should not be hard coded
    if execution.backends:
        new_restrict["_backend"] = sq_friendly

    clauses = ["({}='{}')".format(k, v) for k, v in new_restrict.items()]
    full = " AND ".join(clauses)
    quotes = ["{}".format(val) for val in execution.tables[tablename]]
    exec_str = "SELECT {} FROM {} WHERE ({})".format(",".join(quotes), tablename, full)
    c.execute(exec_str)
    data = c.fetchall()
    if not len(data):
        raise Exception("Restriction too fine - no data found")

    if len(data[0]) != len(execution.tables[tablename]):
        raise Exception("Data types not matching with sqldb")

    benchmarks = [dict(zip(execution.tables[tablename], vals)) for vals in data]
    c.close()
    conn.close()

    return benchmarks


def _retrieve_relavent_data(workloads: str, restriction: Dict):
    """
    Grab the workloads string, and retrictions and filter out the data within the specified out
    backend, this can either be a file or an sqllite3 db.
    """
    final_args = dict()
    for work in workloads:
        restrict = dict(restriction)
        path = work.split(":")
        restrict["_execution_name"] = path[0]
        if len(path) == 2:
            restrict["_backend"] = Backend.user_to_out(path[1])
        execution = _sb_executions[path[0]]
        if execution.is_sql_backed():
            benchmark = _retrieve_data_db(execution, restrict)
        else:
            benchmark = _retrieve_data_files(execution, restrict)

        final_args[work] = benchmark

    return final_args


def _calculate_ticks(group_len: int, width: float):
    """Given some group size, and width calculate
    where ticks would occur.

    Meant for bar graphs
    """
    if group_len % 2 == 0:
        start = ((int(group_len / 2) - 1) * width * -1) - (width / 2.0)
    else:
        start = int((group_len / 2)) * width * -1

    temp = []
    offset = start
    for _ in range(0, group_len):
        temp.append(offset)
        offset += width
    return temp


def axis_kwargs(ax, kwargs):
    if "title" in kwargs:
        ax.set_title(kwargs.get("title"))


def filter(metrics: List, restrict_dict: Dict):
    """Filter a list of metrics given a restriction dict"""
    final_metric = []
    for metric in metrics:
        if all(item in metric.get_stats().items() for item in restrict_dict.items()):
            final_metric.append(metric)
    return final_metric


