# pylint: disable-msg=W0102
"""Subroutines Module

Useful helper functions
"""
import itertools
from pprint import pformat
from typing import List, Dict, Tuple

import numpy as np

from .globals import _sb_executions

Axes = Tuple[List[float], List[float], List[float]]
def check_one_varying(benchmarks: List[Dict], extras: List[str]=[]):
    """Check whether a given benchmark has only one varrying variable
    Arguments:
        benchmarks: List of parsed benchmark objects
        extras: List of variable names that are allowed to vary
    """
    execution = _sb_executions[benchmarks[0]['_execution_name']]
    varying = []
    for rule in execution.bench.parser.match_rules.values():
        varying.extend(rule[0])

    varying.extend(extras)
    varying.append('_iter')

    consts = { k:v for k, v in benchmarks[0].items() if k not in varying }
    for bench in benchmarks[1:]:
        for key, val in bench.items():
            if key in varying:
                continue

            if key not in consts:
                consts[key] = val
            else:
                if str(consts[key]) != str(val):
                    raise Exception("Only one variable should be changing in a graph:{}"
                            .format(key))


def aggregate_bench(group: List[Dict]) -> Dict:
    """Aggregation helper function"""
    first = dict(group[0])
    for k, val in first.items():
        if not val:
            first[k] = []
            continue

        try:
            first[k] = [float(val)]
        except ValueError:
            first[k] = [val]

    for i in range(1, len(group)):
        for k in first.keys():

            if not group[i][k]:
                continue

            try:
                val = float(group[i][k])
                first[k].append(val)
            except ValueError:
                first[k].append(group[i][k])

    for k in first.keys():
        if not len(first[k]):
            continue

        if not isinstance(first[k][0], str):
            first[k] = (np.mean(first[k]), np.std(first[k]))

    return first


def retrieve_axes(benchmarks: List[Dict], x_name: str, y_name: str) -> Axes:
    """
    Retrieve associated axes for a given benchmark
    """
    combined = dict()
    grouped = dict()
    for benchmark in benchmarks:
        if benchmark[x_name] in grouped:
            grouped[benchmark[x_name]].append(benchmark)
        else:
            grouped[benchmark[x_name]] = [benchmark]

    for key, group in grouped.items():
        combined[float(key)] = aggregate_bench(list(group))

    x_values = []
    y_values = []
    y_std = []
    for key, benchmark in combined.items():
        x_values.append(key)
        y_values.append(benchmark[y_name][0])
        y_std.append(benchmark[y_name][1])

    return (x_values, y_values, y_std, combined)
