#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements application for visualisation of graphs described by *.json files."""

import tkFileDialog
from Tkinter import HORIZONTAL, VERTICAL, BOTTOM, RIGHT, LEFT, BOTH, X, Y
from Tkinter import Tk, StringVar, IntVar, Frame, Menu, Label, Canvas, Scrollbar, Checkbutton

from utils.graph import Graph


def prepare_coordinates(func):
    """Calculates scales and prepares coordinates for drawing in Canvas in case the actions were not
    performed previously."""

    def wrapped(self, *args, **kwargs):
        if self.scale_x is None or self.scale_y is None:
            self.scale_x = int((self.x0 - self.r - 5) / max([abs(point[1]['x']) for point in self.points]))
            self.scale_y = int((self.y0 - self.r - 5) / max([abs(point[1]['y']) for point in self.points]))
        if len(self.coordinates) == 0:
            for point in self.points:
                x, y = int(point[1]['x'] * self.scale_x + self.x0), int(point[1]['y'] * self.scale_y + self.y0)
                self.coordinates[point[0]] = (x, y)
        return func(self, *args, **kwargs)
    return wrapped


class Application(Frame, object):
    """The application main class."""

    FILE_OPEN_OPTIONS = {
        'mode': 'rb',
        'title': 'Choose *.json file',
        'defaultextension': '.json',
        'filetypes': [('JSON file', '*.json')]
    }
    WIDTH, HEIGHT = 1280, 720
    BG = "lightblue"
    POINT_COLOR = 'lightgreen'
    FONT = 'Verdana'

    def __init__(self, master=None):
        """Creates application main window with Canvas sizes self.WIDTH and self.HEIGHT."""

        super(Application, self).__init__(master)
        self.master.title('Graph Visualisation App')

        self._graph, self.points, self.lines = None, None, None
        self.x0, self.y0, self.scale_x, self.scale_y = self.WIDTH / 2, self.HEIGHT / 2, None, None
        self.r = int(0.05 * min(self.x0, self.y0))
        self.font_size = self.r / 2
        self.coordinates, self.weights, self.ids = {}, [], []

        self.menu = Menu(self)
        filemenu = Menu(self.menu)
        filemenu.add_command(label='Open', command=self.file_open)
        filemenu.add_command(label='Exit', command=self.exit)
        self.menu.add_cascade(label='File', menu=filemenu)
        master.config(menu=self.menu)

        self.path = StringVar()
        self.path.set('No file chosen')
        self.label = Label(master, textvariable=self.path).pack()

        self.frame = Frame(self)
        self.canvas = Canvas(self.frame, bg=self.BG, scrollregion=(0, 0, self.WIDTH, self.HEIGHT))
        self.canvas.config(width=self.WIDTH, height=self.HEIGHT)
        hbar = Scrollbar(self.frame, orient=HORIZONTAL)
        hbar.pack(side=BOTTOM, fill=X)
        hbar.config(command=self.canvas.xview)
        vbar = Scrollbar(self.frame, orient=VERTICAL)
        vbar.pack(side=RIGHT, fill=Y)
        vbar.config(command=self.canvas.yview)
        self.canvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.pack(fill=BOTH, expand=True)
        self.frame.pack()

        self.weighted = IntVar()
        self.weighted_check = Checkbutton(self, text='Weighted graph', variable=self.weighted,
                                          command=self.build_graph)
        self.weighted_check.pack(side=LEFT)

        self.show_weight = IntVar()
        self.show_weight_check = Checkbutton(self, text='Show weight', variable=self.show_weight,
                                             command=self.show_weights)
        self.show_weight_check.pack(side=LEFT)

        self.pack()

    @property
    def graph(self):
        """Returns the actual graph."""

        return self._graph

    @graph.setter
    def graph(self, value):
        """Clears Canvas and resets internally used variables each time a new graph is assigned."""

        self.canvas.delete('all')
        self.scale_x, self.scale_y = None, None
        self.coordinates, self.weights, self.ids = {}, [], []
        self._graph = value

    def file_open(self):
        """Implements file dialog and when a file is chosen builds and draws the graph."""

        try:
            self.path.set(tkFileDialog.askopenfile(parent=root, **self.FILE_OPEN_OPTIONS).name)
        except AttributeError:
            return
        self.build_graph()

    def build_graph(self):
        """Builds and draws graph."""

        self.graph = Graph(self.path.get(), weighted=self.weighted.get())
        self.points, self.lines = self.graph.get_coordinates()
        self.create_lines(self.lines)
        self.create_points(self.points)

    def exit(self):
        """Closes application."""

        self.master.destroy()

    @prepare_coordinates
    def create_points(self, points):
        """Draws points in Canvas.

        Args:
            points: List of tuples where each tuple denotes separate point. Each point is represented by two value
            which are point idx and a dict of point attributes including point coordinates with keys 'x' and 'y'.

        Returns:
            None.

        """

        for point in points:
            x, y = self.coordinates[point[0]]
            self.canvas.create_oval(x - self.r, y - self.r, x + self.r, y + self.r, fill=self.POINT_COLOR)
            self.canvas.create_text(x, y, text=point[0], font="{} {}".format(self.FONT, self.font_size))

    @prepare_coordinates
    def create_lines(self, lines):
        """Draws lines in Canvas and fills list of weights with their coordinates to draw by.

        Shows line weights if self.show_weight is set to 1.

                Args:
                    lines: List of tuples where each tuple denotes separate line. Each line is represented by three
                    values which are two idxs of points which are connected with the line and a dict of line attributes
                    including line weight with the key 'weight'.

                Returns:
                    None.

        """

        for line in lines:
            x_start, y_start = self.coordinates[line[0]]
            x_stop, y_stop = self.coordinates[line[1]]
            self.canvas.create_line(x_start, y_start, x_stop, y_stop)
            self.weights.append(((x_start + x_stop) / 2, (y_start + y_stop) / 2, line[2]['weight']))
        self.show_weights()

    def show_weights(self):
        """Shows line weights when set to 1 and hides them whe set to 0. Returns None if self.weights is empty."""

        if len(self.weights) == 0:
            return
        if self.show_weight.get():
            for weight in self.weights:
                x, y, value = weight
                r = int(self.r / 2) * len(str(value))
                self.ids.append(self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=self.BG, width=0))
                self.ids.append(self.canvas.create_text(x, y, text=value, font="{} {}".format(self.FONT, str(r))))
        else:
            for element_id in self.ids:
                self.canvas.delete(element_id)


if __name__ == '__main__':
    root = Tk()
    app = Application(master=root)
    app.mainloop()
