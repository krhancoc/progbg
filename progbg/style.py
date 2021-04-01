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
from cycler import cycler

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
)

_hatch_styles = dict(
    a=["**", "++", "//", "xx", "oo"],
)

_line_styles = dict(a=["-", "-.", "--", "x", "s", "<", ",", "d"])


def get_style(style_name: str):
    """Get a style cycler

    Retrieve an iterable (cycler) object allowing to iterate over colors or hatches. Used by graphs

    Args:
        style_name (str): String in form "T_C" where T = color, hatch or line, and C = character (a-z)

    Return
        Cycler object with either hatch or color set
    """

    vals = style_name.split("_")
    if vals[0] == "hatch":
        style_list = _hatch_styles[vals[1]]
        return cycler(hatch=style_list)
    elif vals[0] == "line":
        style_list = _line_styles[vals[1]]
        return cycler(
            color=["#000000"] * len(style_list),
            linestyle=style_list,
            linewidth=[1] * len(style_list),
        )
    else:
        return cycler(color=_color_styles[vals[1]])


progbg_default_style = {
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 10,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 10,
    "pgf.texsystem": "pdflatex",
    "pgf.rcfonts": False,
    "axes.prop_cycle": get_style("color_a"),
}

mpl.rcParams.update(progbg_default_style)
