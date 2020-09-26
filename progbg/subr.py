"""Subroutines Module

Useful helper functions
"""
from typing import List, Dict, Tuple
import itertools

import numpy as np

from .core import _sb_executions

Axes = Tuple[List[float], List[float], List[float]]
def check_one_varying(benchmarks: List[Dict], extras: List[str]=[]):
    """Check whether a given benchmark has only one varrying variable
    Arguments:
        benchmarks: List of parsed benchmark objects
        extras: List of variable names that are allowed to vary
    """
    execution = _sb_executions[benchmarks[0]['_execution_name']]
    varying = []
    for rule in execution.parser.match_rules.values():
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
    first = dict(group[0])
    for k, v in first.items():
        try:
            first[k] = [float(v)]
        except ValueError:
            first[k] = [v]

    for i in range(1, len(group)):
        for k, v in first.items():
            if isinstance(first[k][0], str):
                first[k].append(group[i][k])
            else:
                first[k].append(float(group[i][k]))

    for k, v in first.items():
        if not isinstance(first[k][0], str):
            first[k] = (np.mean(first[k]), np.std(first[k]))

    return first


def retrieve_axes(benchmarks: List[Dict], x_name: str, y_name: str) -> Axes:
    grouped = itertools.groupby(benchmarks, lambda x: x[x_name])
    combined = dict()
    for key, group in grouped:
        combined[float(key)] = aggregate_bench(list(group))

    x_values = []
    y_values = []
    y_std = []
    for key, benchmark in combined.items():
        x_values.append(key)
        y_values.append(benchmark[y_name][0])
        y_std.append(benchmark[y_name][1])

    return (x_values, y_values, y_std, combined)

def backend_format_to_file(path):
    return "-".join(path.split("/"))

def backend_format_reverse(path):
    return "/".join(path.split("-"))


