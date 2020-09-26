import os

from typing import Dict
from flask import Flask, render_template, send_from_directory
from pprint import pformat


def create_server(
        executions: Dict,
        graphs: Dict,
        figures: Dict,
        graphs_dir: str):
    app = Flask(__name__, instance_relative_config=True)
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route('/')
    def home():
        return render_template('index.html', graphs=graphs, figures=figures)

    @app.route('/data/<graph_name>')
    def data(graph_name=None):
        graph = graphs[graph_name]
        if hasattr(graph, "responding"):
            # Its a bar graph
            return render_template('bar_data.html', name=graph_name, graph=graph)
        else:
            return render_template('line_data.html', name=graph_name, graph=graph)

    @app.route('/graphs/<path:filename>')
    def graphs_static(filename):
        return send_from_directory(graphs_dir, filename)

    return app
