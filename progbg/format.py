from typing import Dict, Union

import matplotlib as mpl

SimpleType = Union[int, str, float]


def change_height(fig: mpl.figure.Figure, axes: mpl.axes.Axes, arg: float):
    fig.set_figheight(arg)


def change_width(fig: mpl.figure.Figure, axes: mpl.axes.Axes, arg: float):
    fig.set_figwidth(arg)


supported_options = {
    "height": change_height,
    "width": change_width
}

default_formatter = {}


def check_formatter(formatter: Dict[str, SimpleType]):
    """
    """
    if not formatter:
        return

    if callable(formatter):
        return

    for option in formatter.keys():
        if option not in supported_options:
            raise Exception("Unknown format option: {}".format(option))


def format_fig(fig, axes, formatter):
    if not formatter:
        formatter = default_formatter

    if callable(formatter):
        formatter(fig, axes)
        return

    for option, arg in formatter.items():
        supported_options[option](fig, axes, arg)

    fig.tight_layout()
