import progbg as sb
import time
from random import randint

@sb.registerbackend
class FFS:
    @staticmethod
    def init(myvar = 10, pass_me_in = 5):
        print("FFS Backend initing {} {}".format(myvar, pass_me_in))

    @staticmethod
    def uninit():
        pass

@sb.registerbackend
class BCK:
    @staticmethod
    def init(another_var = 2):
        print("BCK Backend initing {}".format(another_var))

    @staticmethod
    def uninit():
        pass

@sb.registerbackend
class Tomcat:
    @staticmethod
    def init(tom_var = 2):
        print("TOM Backend initing {}".format(tom_var))

    @staticmethod
    def uninit():
        pass


@sb.registerbenchmark
class WRK:
    @staticmethod
    def run(backend, outfile, test = 5, x = 10):
        # DO STUFF
        avg = str(randint(1, 1000))
        max = str(randint(500, 1000))
        min = str(randint(1, 499))
        vals="{} {}\n".format(test, x)
        strn="Latency  {}  {}  {}".format(avg, max, min)
        with open(outfile, 'w') as out:
            out.write(vals)
            out.write(strn)

def func(line):
    return [x.strip() for x in line.split()[1:]]


# Test file output without backend
sb.plan_execution("wrk1",
    sb.DefBenchmark("wrk",
        sb.Variables(
            consts = {},
            var = [("x" ,range(0, 3, 1)), ("test", range(0, 5, 2))]
        ),
        iterations = 5,
        parse = sb.MatchParser(
            {
                "^Latency": (
                    ["avg", "max", "min"], func
                )
            },
        )
    ),
    out = "out",
)

# Test sqlite output with backend
sb.plan_execution("wrk2",
    sb.DefBenchmark("wrk",
        sb.Variables(
            consts = {
                "test" : 2
            },
            var = [("x" ,range(0, 3, 1))]
        ),
        iterations = 5,
        parse = sb.MatchParser(
            {
                "^Latency": (
                    ["avg", "max", "min"], func
                )
            },
        )
    ),
    {
        'ffs/tomcat': sb.Variables(
            consts = {
                "myvar": 5
            },
            var = [("pass_me_in", range(0, 10, 2))]
        ),
        'bck': sb.Variables(
            consts = {},
            var = [("another_var", [1, 5 ,7])]
        )
    },
    out = "out.db",
)

# Test benchmark with backend and directory output
sb.plan_execution("wrk3",
    sb.DefBenchmark("wrk",
        sb.Variables(
            consts = {
                "test" : 2
            },
            var = [("x" ,range(0, 3, 1))]
        ),
        iterations = 5,
        parse = sb.MatchParser(
            {
                "^Latency": (
                    ["avg", "max", "min"], func
                )
            },
        )
    ),
    {
        'ffs/tomcat': sb.Variables(
            consts = {
                "myvar": 5
            },
            var = [("pass_me_in", range(0, 10, 2))]
        ),
        'bck': sb.Variables(
            consts = {},
            var = [("another_var", [1, 5 ,7])]
        )
    },
    out = "out",
)

# Test sql output without backend
sb.plan_execution("wrk4",
    sb.DefBenchmark("wrk",
        sb.Variables(
            consts = {},
            var = [("x" ,range(0, 3, 1)), ("test", range(0, 5, 2))]
        ),
        iterations = 5,
        parse = sb.MatchParser(
            {
                "^Latency": (
                    ["avg", "max", "min"], func
                )
            },
        )
    ),
    out = "out.db",
)

sb.plan_graph("graph-1",
    sb.LineGraph(
        "x",
        "avg",
        ["wrk2:ffs/tomcat", "wrk2:bck","wrk1"],
        {
            "pass_me_in": 4,
            "another_var": 5,
            "test" : 2,
        },
        out = "avg.svg"
    ),
)

sb.plan_graph("graph-2",
    sb.LineGraph(
        'x',
        "min",
        ["wrk2:ffs/tomcat", "wrk1"],
        {
            'pass_me_in': 4,
            "test" : 2
        },
        out = "min.svg"
    ),
)
sb.plan_graph("graph-3",
    sb.BarGraph(
            ["min", "avg", "max"],
            ["wrk2:ffs/tomcat", "wrk2:bck", "wrk3:bck"],
            {
                'pass_me_in': 4,
                'test': 2,
                'x': 0,
                "another_var": 5,
            },
            group_by=sb.GroupBy.EXECUTION,
            out = "samplebar.svg"
    ),
)

sb.plan_graph("graph-4",
    sb.BarGraph(
            ["min", "avg", "max"],
            ["wrk2:ffs/tomcat", "wrk2:bck"],
            {
                'pass_me_in': 4,
                'test': 2,
                'x': 0,
                "another_var": 5,
            },
            group_by=sb.GroupBy.OUTPUT,
            out = "samplebar_output.svg"
    ),
)


sb.plan_figure("fig-1",
        [["graph-1", "graph-4"],
         ["graph-2", "graph-3"]],
        {
            "height": 6,
            "width": 6,
        },
        out  = "samplefig.svg"
)

def myformatter(figure, axes):
    figure.set_figwidth(10)
    figure.suptitle("Title for this figure")
    figure.tight_layout()

sb.plan_figure("fig-2",
        [["graph-1", "graph-2"]],
        myformatter,
        out  = "samplefigform.svg"
)
