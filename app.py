#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements application for visualisation of graphs described by *.json files."""

import tkFileDialog
from Tkinter import HORIZONTAL, VERTICAL, BOTTOM, RIGHT, LEFT, BOTH, X, Y
from Tkinter import Tk, StringVar, IntVar, Frame, Menu, Label, Canvas, Scrollbar, Checkbutton

from attrdict import AttrDict

from utils.graph import Graph


def prepare_coordinates(func):
    """Calculates scales and coordinates for drawing in case they were not calculated previously."""

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
        'LINE': 'line'
    })
    FILE_OPEN_OPTIONS = {
        'mode': 'rb',
        'title': 'Choose *.json file',
        'defaultextension': '.json',
        'filetypes': [('JSON file', '*.json')]
    }
    WIDTH, HEIGHT = 1280, 720
    BG = "white"
    POINT_COLOR = 'orange'
    FONT = 'Verdana'

    def __init__(self, master=None):
        """Creates application main window with sizes self.WIDTH and self.HEIGHT."""

        super(Application, self).__init__(master)
        self.master.title('Graph Visualisation App')
        self.master.geometry('{}x{}'.format(self.WIDTH, self.HEIGHT))

        self._graph, self.points, self.lines = None, None, None
        self.coordinates, self.canvas_obj, self.captured_lines = {}, {}, {}
        self.x0, self.y0, self.scale_x, self.scale_y, self.r, self.font_size = None, None, None, None, None, None
        self.captured_point = None

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
        self.canvas = Canvas(self.frame, bg=self.BG, scrollregion=(0, 0, self.winfo_width(), self.winfo_height()))
        self.canvas.bind('<Button-1>', self.capture_point)
        self.canvas.bind('<Motion>', self.move_point)
        self.canvas.bind('<B1-ButtonRelease>', self.release_point)
        self.canvas.bind('<Configure>', self.resize_window)
        hbar = Scrollbar(self.frame, orient=HORIZONTAL)
        hbar.pack(side=BOTTOM, fill=X)
        hbar.config(command=self.canvas.xview)
        vbar = Scrollbar(self.frame, orient=VERTICAL)
        vbar.pack(side=RIGHT, fill=Y)
        vbar.config(command=self.canvas.yview)
        self.canvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.pack(fill=BOTH, expand=True)
        self.frame.pack(fill=BOTH, expand=True)

        self.weighted = IntVar()
        self.weighted_check = Checkbutton(self, text='Weighted graph', variable=self.weighted,
                                          command=self.build_graph)
        self.weighted_check.pack(side=LEFT)

        self.show_weight = IntVar()
        self.show_weight_check = Checkbutton(self, text='Show weight', variable=self.show_weight,
                                             command=self.show_weights)
        self.show_weight_check.pack(side=LEFT)

        self.pack(fill=BOTH, expand=True)

    @property
    def graph(self):
        """Returns the actual graph."""

        return self._graph

    @graph.setter
    def graph(self, value):
        """Clears previously drawn graph and assigns a new graph to self._graph."""

        self.clear_graph()
        self._graph = value

    def file_open(self):
        """Implements file dialog and builds and draws a graph once a file is chosen."""

        try:
            self.path.set(tkFileDialog.askopenfile(parent=root, **self.FILE_OPEN_OPTIONS).name)
        except AttributeError:
            return
        self.build_graph()

    def build_graph(self):
        """Builds and draws new graph."""

        if self.path.get() != 'No file chosen':
            self.graph = Graph(self.path.get(), weighted=self.weighted.get())
            self.points, self.lines = self.graph.get_coordinates()
            self.draw_graph()

    def draw_graph(self):
        """Draws graph by prepared coordinates."""

        self.draw_lines()
        self.draw_points()

    def clear_graph(self):
        """Clears previously drawn graph and resets coordinates and scales."""

        self.canvas.delete('all')
        self.scale_x, self.scale_y = None, None
        self.coordinates = {}

    def resize_window(self, event):
        """Redraws graph each time main window size changes.

        :param event: Tkinter.Event - Tkinter.Event instance for Configure event
        :return: None
        """

        self.x0, self.y0 = int(event.width / 2), int(event.height / 2)
        self.r = int(0.05 * min(self.x0, self.y0))
        self.font_size = self.r / 2
        if self.graph is not None:
            self.clear_graph()
            self.draw_graph()

    @prepare_coordinates
    def draw_points(self):
        """Draws graph points by prepared coordinates."""

        self.canvas_obj[self.TYPES.POINT] = {}
        for point in self.points:
            x, y = self.coordinates[point[0]]
            point_id = self.canvas.create_oval(x - self.r, y - self.r, x + self.r, y + self.r, fill=self.POINT_COLOR)
            text_id = self.canvas.create_text(x, y, text=point[0], font="{} {}".format(self.FONT, self.font_size))
            self.canvas_obj[self.TYPES.POINT][point_id] = {'idx': point[0], 'text_obj': text_id}

    @prepare_coordinates
    def draw_lines(self):
        """Draws graph lines by prepared coordinates and shows their weights if self.show_weight is set to 1."""

        self.canvas_obj[self.TYPES.LINE] = {}
        for line in self.lines:
            x_start, y_start = self.coordinates[line[0]]
            x_stop, y_stop = self.coordinates[line[1]]
            line_id = self.canvas.create_line(x_start, y_start, x_stop, y_stop)
            self.canvas.tag_lower(line_id)
            self.canvas_obj[self.TYPES.LINE][line_id] = {'idx': line[2]['idx'], 'weight': line[2]['weight'],
                                                         'start_point': line[0], 'end_point': line[1], 'weight_obj': ()}
        self.show_weights()

    def show_weights(self):
        """Shows line weights when self.show_weight is set to 1 and hides them when it is set to 0."""

        if self.canvas_obj:
            if self.show_weight.get():
                for line in self.canvas_obj[self.TYPES.LINE].values():
                    if line['weight_obj']:
                        self.canvas.itemconfigure(line['weight_obj'][0], state='normal')
                        self.canvas.itemconfigure(line['weight_obj'][1], state='normal')
                    else:
                        x_start, y_start = self.coordinates[line['start_point']]
                        x_end, y_end = self.coordinates[line['end_point']]
                        x, y = self.midpoint(x_start, y_start, x_end, y_end)
                        value = line['weight']
                        r = int(self.r / 2) * len(str(value))
                        oval_id = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=self.BG, width=0)
                        text_id = self.canvas.create_text(x, y, text=value, font="{} {}".format(self.FONT, str(r)))
                        line['weight_obj'] = (oval_id, text_id)
            else:
                for line in self.canvas_obj[self.TYPES.LINE].values():
                    if line['weight_obj']:
                        self.canvas.itemconfigure(line['weight_obj'][0], state='hidden')
                        self.canvas.itemconfigure(line['weight_obj'][1], state='hidden')

    @staticmethod
    def midpoint(x_start, y_start, x_end, y_end):
        """Calculates a midpoint coordinates between two points.

        :param x_start: int - x coordinate of the start point
        :param y_start: int - y coordinate of the start point
        :param x_end: int - x coordinate of the end point
        :param y_end: int - y coordinate of the end point
        :return: 2-tuple of a midpoint coordinates
        """

        return (x_start + x_end) / 2, (y_start + y_end) / 2

    def capture_point(self, event):
        """Captures point and it's lines when mouse button is pressed.

        :param event: Tkinter.Event - Tkinter.Event instance for ButtonPress event
        :return: None
        """

        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        obj_ids = self.canvas.find_overlapping(x - 5, y - 5, x + 5, y + 5)
        if obj_ids:
            for obj_id in obj_ids:
                if obj_id in self.canvas_obj[self.TYPES.POINT].keys():
                    self.captured_point = obj_id
                    point = self.canvas_obj[self.TYPES.POINT][obj_id]['idx']
                    self.captured_lines = {}
                    for key, value in self.canvas_obj[self.TYPES.LINE].items():
                        if value['start_point'] == point:
                            self.captured_lines[key] = 'start_point'
                        if value['end_point'] == point:
                            self.captured_lines[key] = 'end_point'
            if self.weighted.get():
                self.weighted.set(0)

    def release_point(self, event):
        """Releases point and its lines on Canvas. Writes new coordinates for a moved point.

        :param event: Tkinter.Event - Tkinter.Event instance for ButtonRelease event
        :return: None
        """

        point_idx = self.canvas_obj[self.TYPES.POINT][self.captured_point]['idx']
        x, y = self.coordinates[point_idx]
        for point in self.points:
            if point[0] == point_idx:
                point[1]['x'], point[1]['y'] = (x - self.x0) / self.scale_x, (y - self.y0) / self.scale_y
        self.captured_point = None
        self.captured_lines = {}

    def move_point(self, event):
        """Moves point and its lines on Canvas If self.show_weight is set to 1 moves weights.

        :param event: Tkinter.Event - Tkinter.Event instance for Motion event
        :return: None
        """
        if self.captured_point:
            new_x, new_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            self.canvas.coords(self.captured_point, event.x - self.r, event.y - self.r, event.x + self.r,
                               event.y + self.r)
            self.canvas.coords(self.canvas_obj[self.TYPES.POINT][self.captured_point]['text_obj'], event.x, event.y)

            for key, value in self.captured_lines.items():
                line_attrs = self.canvas_obj[self.TYPES.LINE][key]
                if value == 'start_point':
                    x, y = self.coordinates[line_attrs['end_point']]
                    self.canvas.coords(key, new_x, new_y, x, y)
                    self.coordinates[line_attrs['start_point']] = (new_x, new_y)
                else:
                    x, y = self.coordinates[line_attrs['start_point']]
                    self.canvas.coords(key, x, y, new_x, new_y)
                    self.coordinates[line_attrs['end_point']] = (new_x, new_y)
                if self.show_weight.get():
                    mid_x, mid_y = self.midpoint(new_x, new_y, x, y)
                    self.canvas.coords(line_attrs['weight_obj'][1], mid_x, mid_y)
                    r = int(self.r / 2) * len(str(line_attrs['weight']))
                    self.canvas.coords(line_attrs['weight_obj'][0], mid_x - r, mid_y - r, mid_x + r, mid_y + r)

    def exit(self):
        """Closes application."""

        self.master.destroy()


if __name__ == '__main__':
    root = Tk()
    app = Application(master=root)
    app.mainloop()
