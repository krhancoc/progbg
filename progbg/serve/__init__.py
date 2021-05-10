import os

from typing import Dict
from flask import Flask, render_template, send_from_directory, abort
from progbg import Execution
from progbg.graphing import *
from pprint import pformat


def create_server(executions, graphs, figures, graphs_dir: str):
    app = Flask(__name__, instance_relative_config=True)
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route("/create_graph")
    def create_graph():
        for e in executions:
            if isinstance(e, Execution):
                print(e.varying())
        return render_template("create_graph.html", graphs=graphs, 
                figures=figures)

    @app.route("/")
    def home():
        for e in executions:
            if isinstance(e, Execution):
                print(e.get_varying())
        return render_template("index.html", graphs=graphs, figures=figures)

    @app.route("/data/<graph_index>")
    def data(graph_index=None):
        graph = graphs[int(graph_index)]
        print(graph)
        if isinstance(graph, BarGraph):
            # Its a bar graph
            return render_template("bar_data.html", name=graph_index, graph=graph)
        elif isinstance(graph, LineGraph):
            return render_template("line_data.html", name=graph_index, graph=graph)

        abort(404, description="Not implemented Graph")

    @app.route("/graphs/<path:filename>")
    def graphs_static(filename):
        return send_from_directory(graphs_dir, filename)

    return app
