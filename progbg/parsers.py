import re
from typing import List, Dict

from .globals import _sb_executions


class MatchParser:
    """MatchParser class takes regex matches and on success run a given function"""

    def __init__(self, match_rules: Dict):
        """Match parser init
        Arguments:
            match_rules: Dictionary of regex to a tuple of a list output names
            and a function that will return values to bind to those names
        Example:
            parse = sb.MatchParser(
                {
                    "^Latency": (
                        ["avg", "max", "min"], func
                    )
                },
            )

            In the above example we take data from the out directory, take the line
            that matches on ^Latency and outputs the avg, max and min. func
            is a function that will output values which bind to these names.
            This means func must output a list of 3 values for this above example.
        """
        self.match_rules = match_rules
        self.execution = None

    def _match(self, line: str, obj: Dict):
        for cand, tup in self.match_rules.items():
            if re.search(cand, line):
                output = tup[1](line)
                if len(output) != len(tup[0]):
                    raise Exception(
                        "Function provided outputed {} values, expected {}".format(
                            len(output), len(tup[0])
                        )
                    )
                for match in zip(tup[0], output):
                    obj[match[0]] = match[1]

    def param_exists(self, name: str) -> bool:
        """Check if a param exists as an output of the parser"""
        return any([name in varfunc[0] for varfunc in self.match_rules.values()])

    def fields(self) -> List[str]:
        """ Retrieve all named fields within the parser"""
        return [item for sublist in self.match_rules.values() for item in sublist[0]]

    def parse(self, path, bench_args, backend_args) -> List:
        """Parse the execution"""
        obj = {}
        with open(path, "r") as file:
            for line in file:
                self._match(line, obj)
            # Make sure to put constants in the data as well
            for key, val in bench_args.items():
                obj[key] = val

            if backend_args:
                for key, val in backend_args.items():
                    obj[key] = val

            # We hold field names within our filename as well, things like iteration number
            # and var variable value
            obj["_execution_name"] = path.split("/")[-1].split("_")[0]
            execution = _sb_executions[obj["_execution_name"]]
            obj.update(execution.reverse_file_out(path))

        return obj


class FileParser:
    """FileParser class parses an entire file pointed to by the path variable using a user
    defined function

    Arguments:
    names: Name bindings for the expected output from func.
    func: A function of the form `def func(path): ...` where path is the name
    of the file to be parsed.   Func should return a list that is the same
    length as names.
    """

    def __init__(self, names: List[str], func):
        self.func = func
        self.names = names

    def param_exists(self, name: str) -> bool:
        """Check if a param exists as an output of the parser"""
        return name in self.names

    def fields(self) -> List[str]:
        """ Retrieve all named fields within the parser"""
        return self.names

    def parse(self, path, bench_args, backend_args) -> List:
        """Parse the whole file at path"""
        vals = self.func(path)
        if vals == None:
            return None

        if len(vals) != len(self.names):
            raise Exception(
                "Issue with provided function, returned {} vals, expected {}".format(
                    str(len(vals)), str(len(self.names))
                )
            )

        obj = {}
        for val in zip(self.names, vals):
            obj[val[0]] = val[1]

        if backend_args:
            for key, val in backend_args.items():
                obj[key] = val

        obj["_execution_name"] = path.split("/")[-1].split("_")[0]
        execution = _sb_executions[obj["_execution_name"]]
        obj.update(execution.reverse_file_out(path))

        return obj
