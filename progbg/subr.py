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


def check_one_varying(benchmarks: List[Dict], extras: List[str] = []):
    """Check whether a given benchmark has only one varrying variable
    Arguments:
        benchmarks: List of parsed benchmark objects
        extras: List of variable names that are allowed to vary
    """
    execution = _sb_executions[benchmarks[0]["_execution_name"]]
    varying = []
    for rule in execution.bench.parser.fields():
        varying.append(rule)

    varying.extend(extras)
    varying.append("_iter")

    consts = {k: v for k, v in benchmarks[0].items() if k not in varying}
    for bench in benchmarks[1:]:
        for key, val in bench.items():
            if key in varying:
                continue

            if key not in consts:
                consts[key] = val
            else:
                if str(consts[key]) != str(val):
                    print(
                        "Only one variable should be changing in the graph: {}".format(
                            key
                        )
                    )
                    exit(0)


def aggregate_list(group, filter_func=None):
    init_size = len(group)
    size = init_size
    while len(group):
        if filter_func and (not filter_func(group[0])):
            size -= 1
            group.pop(0)
            continue
        first = dict(group[0])
        break

    group.pop(0)
    for k, val in first.items():
        if not val:
            first[k] = []
            continue

        try:
            first[k] = [float(val)]
        except ValueError:
            first[k] = [val]

    for i in range(0, len(group)):
        if filter_func and (not filter_func(group[i])):
            size -= 1
            continue

        for k in first.keys():

            try:
                if not group[i][k]:
                    continue
            except:
                print(
                    "Problem with Benchmark {}: Iteration {}".format(
                        group[i]["_execution_name"], group[i]["_iter"]
                    )
                )
                print(group[i])
                continue

            try:
                val = float(group[i][k])
                first[k].append(val)
            except ValueError:
                first[k].append(group[i][k])
    # TODO: Better way of showing this to the user
    # print("Filter has eliminated {}/{} data points".format(init_size - size, init_size))
    return first


def aggregate_bench(group: List[Dict], filter_func=None) -> Dict:
    """Aggregation helper function"""
    first = aggregate_list(group, filter_func)
    for k in first.keys():
        if not len(first[k]):
            continue

        if not isinstance(first[k][0], str):
            if k + "_std" in first:
                assert len(first[k]) == 1
                first[k] = (first[k][0], first[k + "_std"])
            else:
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
        try:
            y_values.append(benchmark[y_name][0])
            y_std.append(benchmark[y_name][1])
        except:
            print("Problem in benchmark {}".format(benchmark))
            exit(0)

    return (x_values, y_values, y_std, combined)
