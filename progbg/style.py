"""
Styles chosen from  https://colorbrewer2.org/#type=diverging&scheme=PRGn&n=6ef _reset_default

Colors are chosen as they are printer and/or colorblind friendly

Currently users can choose between two generals styles: hatch, line, or color

They then enumerate styles in each by select a character. Graphs support the style named paramater, which allow
to change the style to the selected style. 

For example a BarGraph could be given the style "hatch_a", or "color_b". Currently I do
not support hatches and colors cause I find this distracts readers of the data, but open to discussion.
"""
import matplotlib as mpl
from cycler import cycler, Cycler

mpl.use("pgf")

_color_styles = dict(
    a=[
        "#762a83",
        "#af8dc3",
        "#e7d4e8",
        "#d9f0d3",
        "#7fbf7b",
        "#1b7837",
    ],  # Colorblind + Printer Friendly
    b=[
        "#a6cee3",
        "#1f78b4",
        "#b2df8a",
        "#33a02c",
        "#fb9a99",
        "#e31a1c",
    ],  # Printer Friendly
    c=[
        "#1b9e77",
        "#d95f02",
        "#7570b3",
        "#e7298a",
        "#66a61e",
        "#e6ab02",
    ],  # Printer Friendly
    bw=[
        "#AAAAAA",
        "#000000",
    ],
)

_hatch_styles = dict(
    a=["**", "++", "//", "xx", "oo", "O", "\\", "*", "o"],
)

_line_styles = dict(a=["-", "-.", "--", ":"])

progbg_default_style = {
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8,
    "figure.titlesize": 10,
    "pgf.texsystem": "pdflatex",
    "pgf.rcfonts": False,
    "text.usetex": True,
    "errorbar.capsize": 1,
}

_current_style = "color_a"


def get_style():
    return _current_style


def get_style_cycler():
    return progbg_default_style["axes.prop_cycle"]


def set_style(style_name):
    """Get a style cycler

    Retrieve an iterable (cycler) object allowing to iterate over colors or hatches. Used by graphs

    Args:
        style_name (str): String in form "T_C" where T = color, hatch or line, and C = character (a-z)

    Return
        Cycler object with either hatch or color set
    """
    _current_style = style_name
    if not isinstance(style_name, Cycler):
        vals = style_name.split("_")
        if vals[0] == "hatch":
            style_list = _hatch_styles[vals[1]]
            c = cycler(
                hatch=style_list,
                color=["#FFFFFF"] * len(style_list),
                edgecolor=["#000000"] * len(style_list),
            )
        elif vals[0] == "line":
            style_list = _line_styles[vals[1]]
            c = cycler(
                color=["#000000"] * len(style_list),
                linestyle=style_list,
                linewidth=[1] * len(style_list),
            )
        else:
            c = cycler(color=_color_styles[vals[1]])
    else:
        c = style_name

    progbg_default_style["axes.prop_cycle"] = c
    mpl.rcParams.update(progbg_default_style)
