from ._graph import Graph

class CustomGraph(Graph):
    def __init__(self, workloads, func, out, formatter=[], style="color_a"):
        self.workloads = workloads
        self.formatter = formatter
        self.formatters = formatter
        self.style = style
        self.out = out
        self._opts = dict(
            std = True,
        )
        self.html_out = ".".join(out.split(".")[:-1]) + ".svg"
        self._restrict_on = {}
        self.func = func

    def _graph(self, ax, data):
        self.func(ax, data)
