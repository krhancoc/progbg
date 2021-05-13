import progbg as sb
import progbg.graphing as graph

import time
from random import randint
from cycler import cycler


@sb.registerbackend
class FFS:
    @staticmethod
    def start(myvar=10, pass_me_in=5):
        print("FFS Backend initing {} {}".format(myvar, pass_me_in))

    @staticmethod
    def uninit():
        pass


@sb.registerbackend
class BCK:
    @staticmethod
    def start(another_var=2):
        print("BCK Backend initing {}".format(another_var))

    @staticmethod
    def uninit():
        pass


@sb.registerbackend
class Tomcat:
    @staticmethod
    def start(tom_var=2):
        print("TOM Backend initing {}".format(tom_var))

    @staticmethod
    def uninit():
        pass


@sb.registerbenchmark
class Wrk:
    @staticmethod
    def run(backend, outfile, test=5, x=10):
        # DO STUFF
        min = str(randint(1, 100))
        mid = str(randint(400, 600))
        max = str(randint(700, 1000))
        vals = "{} {}\n".format(test, x)
        strn = "Latency  {}  {}  {}".format(min, mid, max)
        with open(outfile, "w") as out:
            out.write(vals)
            out.write(strn)


def func(line):
    return [x.strip() for x in line.split()[1:]]


def file_func(metrics, path):
    with open(path, "r") as file:
        for line in file.readlines():
            if "Latency" in line:
                vals = [int(x.strip()) for x in line.split()[1:]]
                metrics.add_metric("low", vals[0])
                metrics.add_metric("mid", vals[1])
                metrics.add_metric("high", vals[2])


def text_parser(metrics, path):
    metrics.add_metric("low", 100)


composed_backend = sb.compose_backends(Tomcat, FFS)
# Test file output without backend
exec = sb.plan_execution(
    Wrk({}, [("x", range(0, 5))], iterations=5),
    out="out",
    backends=[composed_backend({}, [("pass_me_in", range(0, 10, 2))])],
    parser=file_func,
)

exec2 = sb.plan_parse("exec1_parsed", "tests/test.txt", text_parser)

bf = graph.BarFactory(exec)


graph1 = sb.plan_graph(
    graph.BarGraph(
        [bf(["low"]), bf(["low", "mid", "high"])],
        restrict_on={
            "pass_me_in": 0,
            "x": 0,
        },
        width=0.5,
        out="test.svg",
        style="hatch_a",
    )
)

line1 = graph.Line(exec, "low", x="x", label="Low Label")
line2 = graph.Line(exec, "mid", x="x", label="Mid Label")
line3 = graph.Line(exec, "high", x="x", label="High Label")

graph2 = sb.plan_graph(
    graph.LineGraph(
        [line1, line2, line3],
        restrict_on={
            "pass_me_in": 0,
        },
        out="line.svg",
        style="color_b",
    )
)

line1 = graph.Line(exec, "low", x="x", style="--")
line2 = graph.Line(exec, "mid", x="x", label="Mid Label")
line3 = graph.Line(exec, "high", x="x", label="High Label")

cdf_graph = sb.plan_graph(
    graph.LineGraph(
        [line1, line2, line3],
        restrict_on={
            "pass_me_in": 0,
        },
        type="cdf",
        style="line_a",
        out="cdf.svg",
    )
)

custom_graph = sb.plan_graph(
    graph.LineGraph(
        [line1, line2],
        restrict_on={
            "pass_me_in": 0,
        },
        type="cdf",
        out="custom_style.svg",
        title="Custom Style Graph",
        style=cycler(color=["blue", "green"]),
    )
)

b1 = graph.Bar([(10, 0)], ["data1"], label="Bar Const 1")
b2 = graph.Bar([(20, 0)], ["data2"])
b3 = graph.Bar([(30, 0)], ["data3"])
const = sb.plan_graph(
    graph.BarGraph(
        [b1, b2, b3],
        width=0.5,
        out="consttest.svg",
        style="hatch_a",
    )
)

b1 = graph.BarGroup([(10, 0), (20, 0), (30, 0)], "data1", label=["G1", "G2", "G3"])
b2 = graph.BarGroup([(30, 0), (15, 0), (10, 0)], "data2", label=["G1", "G2", "G3"])
const = sb.plan_graph(
    graph.BarGraph(
        [b1, b2],
        width=0.5,
        out="constgrouptest.svg",
        style="hatch_a",
    )
)

b1 = graph.BarGroup([(10, 0), (20, 0)], "data1", label=["G1", "G2"])
b2 = graph.BarGroup([(30, 0), (15, 0)], "data2", label=["G1", "G2"])
const = sb.plan_graph(
    graph.BarGraph(
        [b1, b2],
        width=0.5,
        out="constgrouptest-even.svg",
        style="hatch_a",
    )
)

b1 = graph.BarGroup(
    [(10, 0), (20, 0), (30, 0), (44, 0), (30, 0), (44, 0)],
    "data1",
    label=["G1", "G2", "G3", "G4", "G5", "G6"],
)
const = sb.plan_graph(
    graph.BarGraph(
        [b1],
        width=0.5,
        out="constgrouptest-even2.svg",
        style="hatch_a",
    )
)


b1 = graph.BarGroup(
    [(10, 0), (20, 0), (30, 0), (40, 0), (22, 0)],
    "data1",
    label=["G1", "G2", "G3", "G4", "G5"],
)
b2 = graph.BarGroup(
    [(10, 0), (20, 0), (30, 0), (40, 0), (22, 0)],
    "data2",
    label=["G1", "G2", "G3", "G4", "G5"],
)
const = sb.plan_graph(
    graph.BarGraph(
        [b1, b2],
        width=0.5,
        out="constgrouptest-odd2.svg",
        style="hatch_a",
    )
)


line1 = graph.Line(200, "low")
line2 = graph.Line(exec, "mid", x="x", label="Mid Label")
line3 = graph.Line(exec, "high", x="x", label="High Label")

cdf_graph = sb.plan_graph(
    graph.LineGraph(
        [line1, line2, line3],
        restrict_on={
            "pass_me_in": 0,
        },
        type="cdf",
        style="line_a",
        out="constline.svg",
    )
)


sb.plan_figure(
    "figure.pgf",
    [
        [graph1, graph1, graph1],
        [cdf_graph, custom_graph, custom_graph],
        [cdf_graph, custom_graph, custom_graph],
    ],
)
