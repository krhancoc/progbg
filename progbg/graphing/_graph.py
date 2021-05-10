from abc import ABC, abstractmethod
import pandas as pd

from cycler import Cycler
from ..style import get_style, set_style

class GraphObject(ABC):

    @abstractmethod
    def get_data(self):
        pass

class Graph(ABC):
    def get_data(self, restrict_on, opts):
        return [ y.get_data(restrict_on, opts) for y in self.workloads ]
    
    def graph(self, fig, ax):

        before = get_style()

        if self.style:
            set_style(self.style)

        data = self.get_data(self._restrict_on, self._opts)
        self._graph(ax, data)
        self.format(fig, ax)

        set_style(before)

    def format(self, fig, ax):
        for x in self.formatters:
            x(fig, ax)

    @abstractmethod
    def _graph(self, ax, data):
        pass

