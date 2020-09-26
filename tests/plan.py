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
    def run(outfile, test = 5, x = 10):
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

sb.plan_execution("wrk-2",
        sb.DefBenchmark("wrk",
            sb.Variables(
                consts = {
                    "test" : 2
                },
                var = [("x" ,range(0, 3, 1))]
            ),
            iterations = 5,
            out_dir = "out",
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
        parse = sb.MatchParser("out",
            {
                "^Latency": (
                    ["avg", "max", "min"], func
                )
            },
            save = "out"
        )
)

sb.plan_execution("wrk-1",
        sb.DefBenchmark("wrk",
            sb.Variables(
                consts = {},
                var = [("x" ,range(0, 3, 1)), ("test", range(0, 5, 2))]
            ),
            iterations = 5,
            out_dir = "out",
        ),
        parse = sb.MatchParser("out",
            {
                "^Latency": (
                    ["avg", "max", "min"], func
                )
            },
            save = "out"
        )
)

sb.plan_graph("graph-1",
    sb.LineGraph(
        "x",
        "avg",
        ["wrk-2:ffs/tomcat", "wrk-2:bck","wrk-1"],
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
        ["wrk-2:ffs/tomcat", "wrk-1"],
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
            ["wrk-2:ffs/tomcat", "wrk-2:bck"],
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
            ["wrk-2:ffs/tomcat", "wrk-2:bck"],
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
        [["graph-1"],
         ["graph-2"]],
        {
            "height": 6,
            "width": 3,
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
