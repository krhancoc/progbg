"""Common utility formatters used by Graphs"""

from matplotlib.ticker import FuncFormatter


def set_yrange(min=None, max=None):
    def tmp(fig, axes):
        x, y = axes.get_ylim()
        if min is None:
            min = x

        if max is None:
            max = y

        axes.set_ylim(min, max)

    return tmp


def set_size(w, h):
    def format(fig, axes):
        fig.set_figheight(h)
        fig.set_figwidth(w)
        fig.tight_layout()

    return format


def _axis_formatter(type, label="", tf=None):
    units = dict(
        p=1e-12,
        n=1e-9,
        u=1e-6,
        m=1e-3,
        c=0.01,
        d=0.1,
        S=1.0,
        da=10.0,
        h=100.0,
        k=float(10e3),
        M=float(10e6),
        G=float(10e9),
        T=float(10e12),
    )

    def tmp_num(tf):
        def number_formatter(number, pos=0):
            if tf:
                to_from = units[tf[0]] / units[tf[1]]
                number = to_from * number
            magnitude = 0
            while abs(number) >= 1000:
                magnitude += 1
                number /= 1000
            return "%d%s" % (number, ["", "k", "M", "B", "T", "Q"][magnitude])

        return number_formatter

    def format(fig, axes):
        getattr(axes, type).set_major_formatter(FuncFormatter(tmp_num(tf)))
        axes.set_ylabel(label)

    return format


def yaxis_formatter(label="", tf=None):
    return _axis_formatter("yaxis", label, tf)


def xaxis_formatter(label="", tf=None):
    return _axis_formatter("xaxis", label, tf)


def legend_remap(d):
    def tmp(fig, axes):
        h, labels = ax.get_legend_handles_labels()
        l = [d[l] for l in labels]
        ax.legend(h, l)

    return tmp
