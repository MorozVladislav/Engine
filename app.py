#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements application for visualisation of graphs described by *.json files."""

import tkFileDialog
from Tkinter import HORIZONTAL, VERTICAL, BOTTOM, RIGHT, LEFT, BOTH, X, Y
from Tkinter import Tk, StringVar, IntVar, Frame, Menu, Label, Canvas, Scrollbar, Checkbutton

from attrdict import AttrDict

from utils.graph import Graph


def prepare_coordinates(func):
    """Calculates scales and coordinates for drawing in Canvas in case they were not calculated previously."""

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

    TYPES = AttrDict({
        'POINT': 'point',
        'LINE': 'line',
        'WEIGHT': 'weight',
        'TEXT': 'text'
    })
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
        self.coordinates = {}
        self.canvas_obj = {}

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
        self.canvas.bind('<B1-Motion>', self.move_points)
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
        self.coordinates = {}
        self.canvas_obj = {}
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

        if self.path.get() != 'No file chosen':
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

        :param points: list - list of tuples where each tuple denotes separate point. Each point is represented by two
        value which are point idx and a dict of point attributes including point coordinates with keys 'x' and 'y'
        :return: None
        """

        self.canvas_obj[self.TYPES.POINT] = {}
        for point in points:
            x, y = self.coordinates[point[0]]
            point_id = self.canvas.create_oval(x - self.r, y - self.r, x + self.r, y + self.r, fill=self.POINT_COLOR)
            text_id = self.canvas.create_text(x, y, text=point[0], font="{} {}".format(self.FONT, self.font_size))
            self.canvas_obj[self.TYPES.POINT][point_id] = {'idx': point[0], 'text_id': text_id}

    @prepare_coordinates
    def create_lines(self, lines):
        """Draws lines in Canvas and fills list of weights with their coordinates to draw by.

        Shows line weights if self.show_weight is set to 1.
        :param lines: list - list of tuples where each tuple denotes separate line. Each line is represented by three
        values which are two idxs of points which are connected with the line and a dict of line attributes including
        line weight with the key 'weight'
        :return: None
        """

        self.canvas_obj[self.TYPES.LINE] = {}
        for line in lines:
            x_start, y_start = self.coordinates[line[0]]
            x_stop, y_stop = self.coordinates[line[1]]
            line_id = self.canvas.create_line(x_start, y_start, x_stop, y_stop)
            self.canvas_obj[self.TYPES.LINE][line_id] = {'idx': line[2]['idx'], 'weight': line[2]['weight'],
                                                         'point_start': line[0], 'point_end': line[1], 'weight_obj': ()}

        self.show_weights()

    def show_weights(self):
        """Shows line weights when set to 1 and hides them whe set to 0. Returns None if self.weights is empty."""

        if self.show_weight.get():
            for line in self.canvas_obj[self.TYPES.LINE].values():
                x_start, y_start = self.coordinates[line['point_start']]
                x_end, y_end = self.coordinates[line['point_end']]
                x, y = self.medium_coordinates(x_start, y_start, x_end, y_end)
                value = line['weight']
                r = int(self.r / 2) * len(str(value))
                oval_id = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=self.BG, width=0)
                text_id = self.canvas.create_text(x, y, text=value, font="{} {}".format(self.FONT, str(r)))
                line['weight_obj'] = (oval_id, text_id)
        else:
            for values in self.canvas_obj[self.TYPES.LINE].values():
                if len(values['weight_obj']) != 0:
                    self.canvas.delete(values['weight_obj'][0])
                    self.canvas.delete(values['weight_obj'][1])

    @staticmethod
    def medium_coordinates(x_start, y_start, x_end, y_end):
        """Calculation the midpoint between two points

        :param: x_start: x coordinate of the start point,
        y_start: y coordinate of the start point
        x_end: y coordinate of the end point
        y_end: y coordinate of the end point
        :return: the midpoint coordinates
        """

        return (x_start + x_end) / 2, (y_start + y_end) / 2

    def move_points(self, event):
        """Move the point and edges."""

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        obj_id = self.canvas.find_overlapping(x - 5, y - 5, x + 5, y + 5)
        for obj in obj_id:
            if obj in self.canvas_obj[self.TYPES.POINT].keys():
                obj_number = self.canvas_obj[self.TYPES.POINT][obj]['idx']
                self.canvas.coords(obj, event.x - self.r, event.y - self.r, event.x + self.r, event.y + self.r)
                self.canvas.coords(self.canvas_obj[self.TYPES.POINT][obj]['text_id'], event.x, event.y)

                for key, values in self.canvas_obj[self.TYPES.LINE].iteritems():
                    if obj_number in (values['point_start'], values['point_end']):
                        if obj_number == values['point_start']:
                            new_point_x, new_point_y = self.coordinates[values['point_end']]
                            self.canvas.coords(key, x, y, new_point_x, new_point_y)
                        else:
                            new_point_x, new_point_y = self.coordinates[values['point_start']]
                            self.canvas.coords(key, new_point_x, new_point_y, x, y)

                        self.coordinates[obj_number] = (x, y)

                        if self.show_weight.get():
                            x_medium, y_medium = self.medium_coordinates(new_point_x, new_point_y, x, y)
                            self.canvas.coords(values['weight_obj'][1], x_medium, y_medium)
                            r = int(self.r / 2) * len(str(values['weight']))
                            self.canvas.coords(values['weight_obj'][0], x_medium - r, y_medium - r, x_medium + r,
                                               y_medium + r)


if __name__ == '__main__':
    root = Tk()
    app = Application(master=root)
    app.mainloop()
