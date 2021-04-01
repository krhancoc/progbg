import os

from typing import Dict
from flask import Flask, render_template, send_from_directory, abort
from progbg import BarGraph, LineGraph
from pprint import pformat


def create_server(executions: Dict, graphs: Dict, figures: Dict, graphs_dir: str):
    app = Flask(__name__, instance_relative_config=True)
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route("/")
    def home():
        return render_template("index.html", graphs=graphs, figures=figures)

    @app.route("/data/<graph_index>")
    def data(graph_index=None):
        graph = graphs[int(graph_index)]
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
