"""Utility function and classes used throughout progbg"""

import itertools
import sys
import os
from pprint import pformat
from typing import List, Dict, Tuple

from .globals import _sb_rnames


def reformat_large(tick_val):
    if tick_val >= 1000000000:
        val = round(tick_val / 1000000000, 1)
        new_tick_format = "{:}B".format(val)
    elif tick_val >= 1000000:
        val = round(tick_val / 1000000, 1)
        new_tick_format = "{:}M".format(val)
    elif tick_val >= 1000:
        val = round(tick_val / 1000, 1)
        new_tick_format = "{:}K".format(val)
    else:
        new_tick_format = tick_val

    new_tick_format = str(new_tick_format)

    index_of_decimal = new_tick_format.find(".")
    if index_of_decimal != -1:
        value_after_decimal = new_tick_format[index_of_decimal + 1]
        if value_after_decimal == "0":
            new_tick_format = (
                new_tick_format[0:index_of_decimal]
                + new_tick_format[index_of_decimal + 2 :]
            )

    return new_tick_format


def normalize(group_list, index_to):
    normal = group_list[index_to]
    final_list = []
    for group in group_list:
        stddev = group[1] / group[0]
        newval = group[0] / normal[0]
        final_list.append((newval, stddev * newval))
    return final_list


def silence_print():
    sys.stdout = open(os.devnull, "w")


def restore_print():
    sys.stdout.close()
    sys.stdout = sys.__stdout__


def error(strn: str):
    print("\033[0;31m[Error]:\033[0m {}".format(strn))
    sys.exit(-1)


def dump_obj(file: str, obj: Dict):
    """Dump dictionary to file key=val"""
    with open(file, "w") as ofile:
        for key, val in obj.items():
            line = "{}={}\n".format(key, val)
            ofile.write(line)


def retrieve_obj(file: str) -> Dict:
    """Retrieve dictionary from file key=val"""
    obj = {}
    with open(file, "r") as ofile:
        for line in ofile.readlines():
            vals = line.strip().split("=")
            try:
                obj[vals[0]] = vals[1]
            except:
                print("Issue with file: {}".format(file))
                exit(0)
    return obj


class Variables:
    """
    Variables is a container class for variables for a given execution

    This will define the permutations that can occur for those that utilize the
    class (see Variables.produce_args documentation)

    Attributes:
        const: A dictionary of argument names to values that will be passed
        var: A tuple of an argument name and some iterable object
    """

    def __init__(self, consts: Dict = None, var: List[Tuple[str, List]] = None) -> None:
        if len(var):
            if any([i in consts for i in _sb_rnames]) or (var[0] in _sb_rnames):
                raise Exception(
                    "Cannot use a reserved name for a variable {}".format(
                        pformat(_sb_rnames)
                    )
                )
            for vals in var:
                if vals[0] in consts:
                    raise Exception(
                        "Name defined as constant and varying: {}".format(vals[0])
                    )

        self.consts = consts
        self.var = var

    def produce_args(self) -> List[Dict]:
        """Produces a list of arguments given the consts and vars
        Example:
            Variables(
                sb.Variables(
                    consts = {
                        "other" : 1
                    },
                    var = [("x" ,range(0, 3, 1)), ("test", range(0, 5, 2))]
                ),

            In this example this would produce args as follows:
                { other = 1, x = 0, test = 0},
                { other = 1, x = 0, test = 2},
                { other = 1, x = 0, test = 4},
                { other = 1, x = 1, test = 0},
                ...
                { other = 1, x = 2, test = 4},
        """
        if not len(self.var):
            return [dict(self.consts)]

        key_names, ranges = zip(*self.var)
        args = []
        for perm in itertools.product(*ranges):
            run_vars = dict(self.consts)
            for i, k in enumerate(key_names):
                run_vars[k] = perm[i]
            args.append(run_vars)

        return args

    def param_exists(self, name: str) -> bool:
        """Checks if a variable is defined either as a constant or a varrying variable"""
        return (name in self.consts) or any([name == x[0] for x in self.var])

    def y_names(self) -> List[str]:
        """Returns the names of varrying or responding variables"""
        return [x[0] for x in self.var]

    def const_names(self) -> List[str]:
        """Returns names of constants"""
        return self.consts.keys()

    def __repr__(self) -> str:
        return pformat(vars(self), width=30)


class Backend:
    def __init__(self, path, variables):
        self.backends = path.split("/")
        self.runtime_variables = variables

    @staticmethod
    def user_to_sql(path):
        return "_b_".join(path.split("/"))

    @staticmethod
    def user_to_out(path):
        return "-".join(path.split("/"))

    @staticmethod
    def out_to_user(path):
        return "/".join(path.split("-"))

    @staticmethod
    def out_to_sql(path):
        return "_b_".join(path.split("-"))

    @property
    def path_sql(self):
        return "_b_".join(self.backends)

    @property
    def path_user(self):
        return "/".join(self.backends)

    @property
    def path_out(self):
        return "-".join(self.backends)

    def __eq__(self, path):
        return (
            (self.path_sql == path)
            or (self.path_out == path)
            or (self.path_user == path)
        )
