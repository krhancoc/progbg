import progbg as sb
import time
import os
from random import randint

@sb.registerbackend
class FFS:
    @staticmethod
    def start(myvar = 10, pass_me_in = 5):
        print("FFS Backend initing {} {}".format(myvar, pass_me_in))

    @staticmethod
    def uninit():
        pass

@sb.registerbackend
class BCK:
    @staticmethod
    def start(another_var = 2):
        print("BCK Backend initing {}".format(another_var))

    @staticmethod
    def uninit():
        pass

@sb.registerbackend
class Tomcat:
    @staticmethod
    def start(tom_var = 2):
        print("TOM Backend initing {}".format(tom_var))

    @staticmethod
    def uninit():
        pass


@sb.registerbenchmark
class Wrk:
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

def file_func(metrics, path):
    with open(path, 'r') as file:
        for line in file.readlines():
            if "Latency" in line:
                vals = [int(x.strip()) for x in line.split()[1:]]
                metrics.add_metric("low" , vals[0])
                metrics.add_metric("mid", vals[1])
                metrics.add_metric("high",  vals[2])


def text_parser(metrics, path):
    metrics.add_metric("low", 100)

composed_backend = sb.compose_backends(Tomcat, FFS)
#Test file output without backend
exec = sb.plan_execution(
    Wrk({}, [("x", range(0, 5))], iterations = 5),
    out = "out",
    backends = [composed_backend({}, 
        [("pass_me_in", range(0, 10, 2))])],
    parser = file_func,
)

exec2 = sb.plan_parse("tests/test.txt", text_parser)

bf = sb.BarFactory(exec)
graph1 = sb.plan_graph(
        sb.BarGraph(
            [
                [bf("low", "custom-label1"), bf(["low", "mid"]), bf("low")], 
                [bf("low"), bf("low")],
                [bf("low"), bf(["low", "mid", "high"], "otherlabel")]
            ],
            group_labels = ["yolo-1", "yolo-2", "yolo-3"],
            restrict_on = {
                "pass_me_in": 0,
                "x": 0,
            },
            width = 0.5,
            out = "test.svg",
            title = "My Custom Graph"
        )
)

line1 = sb.Line(exec, "low", 
        label="Low Label",
        linestyle='dashdot')
line2 = sb.Line(exec, "mid", label="Mid Label")
line3 = sb.Line(exec, "high", label="High Label")

graph2 = sb.plan_graph(
        sb.LineGraph(
            [line1, line2, line3],
            "x",
            restrict_on = {
                "pass_me_in": 0,
            },
            out = "line.svg",
            title = "My Lines"
        )
)

sb.plan_figure("Final Figure",
        [[graph1], [graph2]],
        None,
        "final.svg"
)






