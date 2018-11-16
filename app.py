#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements application for visualisation of graphs described by *.json files."""

import tkFileDialog, tkMessageBox, socket
from Tkinter import HORIZONTAL, VERTICAL, BOTTOM, RIGHT, LEFT, BOTH, X, Y
from Tkinter import Tk, StringVar, IntVar, Frame, Menu, Label, Canvas, Scrollbar, Checkbutton, Toplevel, Button, Entry

from attrdict import AttrDict

from utils.graph import Graph

from utils.client import Client, UsernameMissing


def prepare_coordinates(func):
    """Calculates scales and coordinates for drawing in case they were not calculated previously.

    :param func: function - function that requires coordinates and scales
    :return: wrapped function
    """

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
    BG = "white"
    POINT_COLOR = 'orange'
    FONT = 'Verdana'

    def __init__(self, master=None):
        """Creates application main window with sizes self.WIDTH and self.HEIGHT.

        :param master: instance - Tkinter.Tk instance
        """
        super(Application, self).__init__(master)
        self.master.title('Graph Visualisation App')
        self.master.geometry('{}x{}'.format(self.WIDTH, self.HEIGHT))

        self._graph, self.points, self.lines = None, None, None
        self.coordinates, self.captured_lines = {}, {}
        self.x0, self.y0, self.scale_x, self.scale_y, self.r, self.font_size = None, None, None, None, None, None
        self.canvas_obj = AttrDict()
        self.captured_point = None
        self.top, self.server_data = None, None
        self.client = Client()

        self.menu = Menu(self)
        filemenu = Menu(self.menu)
        filemenu.add_command(label='Open file', command=self.file_open)
        filemenu.add_command(label='Server settings', command=self.server_settings)
        filemenu.add_command(label='Exit', command=self.exit)
        self.menu.add_cascade(label='File', menu=filemenu)
        master.config(menu=self.menu)

        self.path = StringVar()
        self.path.set('No file chosen')
        self.label = Label(master, textvariable=self.path).pack()

        self.frame = Frame(self)
        self.frame.bind('<Configure>', self.resize_frame)
        self.canvas = Canvas(self.frame, bg=self.BG, scrollregion=(0, 0, self.winfo_width(), self.winfo_height()))
        self.canvas.bind('<Button-1>', self.capture_point)
        self.canvas.bind('<Motion>', self.move_point)
        self.canvas.bind('<B1-ButtonRelease>', self.release_point)
        self.canvas.bind('<Configure>', self.resize_canvas)
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

        self.host = StringVar()
        self.port = StringVar()
        self.player_name = StringVar()
        self.password = StringVar()

    @property
    def graph(self):
        """Returns the actual graph."""

        return self._graph

    @graph.setter
    def graph(self, value):
        """Clears previously drawn graph and assigns a new graph to self._graph."""

        self.clear_graph()
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), self.canvas.winfo_height()))
        self.x0, self.y0 = self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2
        self._graph = value

    def resize_frame(self, event):
        """Calculates new sizes of point and font each time frame size changes.

        :param event: Tkinter.Event - Tkinter.Event instance for Configure event
        :return: None
        """
        self.r = int(0.05 * min(event.width / 2, event.height / 2))
        self.font_size = self.r / 2

    def resize_canvas(self, event):
        """Redraws graph each time Canvas size changes. Scales graph each time visible part of Canvas is enlarged.

        :param event: Tkinter.Event - Tkinter.Event instance for Configure event
        :return: None
        """
        if self.graph is not None:
            if event.width > self.canvas.bbox('all')[2] and event.height > self.canvas.bbox('all')[3]:
                self.x0, self.y0 = int(event.width / 2), int(event.height / 2)
                self.clear_graph()
                self.draw_graph()
            else:
                self.redraw_graph()
            self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def file_open(self):
        """Implements file dialog and builds and draws a graph once a file is chosen.

        :return: None
        """
        try:
            self.path.set(tkFileDialog.askopenfile(parent=root, **self.FILE_OPEN_OPTIONS).name)
        except AttributeError:
            return
        self.build_graph()

    def build_graph(self):
        """Builds and draws new graph.

        :return: None
        """
        if self.path.get() != 'No file chosen' or self.server_data is not None:
            if self.path.get() != 'No file chosen':
                self.graph = Graph(self.path.get(), weighted=self.weighted.get())
            elif self.server_data is not None:
                self.graph = Graph(self.server_data, weighted=self.weighted.get())
            self.points, self.lines = self.graph.get_coordinates()
            self.draw_graph()

    def draw_graph(self):
        """Draws graph by prepared coordinates.

        :return: None
        """
        self.draw_lines()
        self.draw_points()

    def clear_graph(self):
        """Clears previously drawn graph and resets coordinates and scales.

        :return: None
        """
        self.canvas.delete('all')
        self.scale_x, self.scale_y = None, None
        self.coordinates = {}

    def redraw_graph(self):
        """Redraws existing graph by existing coordinates.

        :return: None
        """
        if self.graph is not None:
            self.canvas.delete('all')
            self.draw_graph()

    @prepare_coordinates
    def draw_points(self):
        """Draws graph points by prepared coordinates.

        :return: None
        """
        point_objs = {}
        for point in self.points:
            x, y = self.coordinates[point[0]]
            point_id = self.canvas.create_oval(x - self.r, y - self.r, x + self.r, y + self.r, fill=self.POINT_COLOR)
            text_id = self.canvas.create_text(x, y, text=point[0], font="{} {}".format(self.FONT, self.font_size))
            point_objs[point_id] = {'idx': point[0], 'text_obj': text_id}
        self.canvas_obj['point'] = point_objs

    @prepare_coordinates
    def draw_lines(self):
        """Draws graph lines by prepared coordinates and shows their weights if self.show_weight is set to 1.

        :return: None
        """
        line_objs = {}
        for line in self.lines:
            x_start, y_start = self.coordinates[line[0]]
            x_stop, y_stop = self.coordinates[line[1]]
            line_id = self.canvas.create_line(x_start, y_start, x_stop, y_stop)
            self.canvas.tag_lower(line_id)
            line_objs[line_id] = {'idx': line[2]['idx'], 'weight': line[2]['weight'], 'start_point': line[0],
                                  'end_point': line[1], 'weight_obj': ()}
        self.canvas_obj['line'] = line_objs
        self.show_weights()

    def show_weights(self):
        """Shows line weights when self.show_weight is set to 1 and hides them when it is set to 0.

        :return: None
        """
        if len(self.canvas_obj) > 0:
            if self.show_weight.get():
                for line in self.canvas_obj.line.values():
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
                for line in self.canvas_obj.line.values():
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
        """Stores captured point and it's lines.

        :param event: Tkinter.Event - Tkinter.Event instance for ButtonPress event
        :return: None
        """
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        obj_ids = self.canvas.find_overlapping(x - 5, y - 5, x + 5, y + 5)
        if obj_ids:
            for obj_id in obj_ids:
                if obj_id in self.canvas_obj.point.keys():
                    self.captured_point = obj_id
                    point = self.canvas_obj.point[obj_id]['idx']
                    self.captured_lines = {}
                    for key, value in self.canvas_obj.line.items():
                        if value['start_point'] == point:
                            self.captured_lines[key] = 'start_point'
                        if value['end_point'] == point:
                            self.captured_lines[key] = 'end_point'
            if self.weighted.get():
                self.weighted.set(0)

    def release_point(self, event):
        """Writes new coordinates for a moved point and resets self.captured_point and self.captured_lines.

        :param event: Tkinter.Event - Tkinter.Event instance for ButtonRelease event
        :return: None
        """
        if self.captured_point:
            point_idx = self.canvas_obj.point[self.captured_point]['idx']
            x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            self.coordinates[point_idx] = (x, y)
            for point in self.points:
                if point[0] == point_idx:
                    point[1]['x'], point[1]['y'] = (x - self.x0) / self.scale_x, (y - self.y0) / self.scale_y
            self.captured_point = None
            self.captured_lines = {}

    def move_point(self, event):
        """Moves point and its lines. Moves weights if self.show_weight is set to 1.

        In case some point is moved beyond Canvas border Canvas scrollregion is resized correspondingly.
        :param event: Tkinter.Event - Tkinter.Event instance for Motion event
        :return: None
        """
        if self.captured_point:
            new_x, new_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            self.canvas.coords(self.captured_point, new_x - self.r, new_y - self.r, new_x + self.r, new_y + self.r)
            self.canvas.coords(self.canvas_obj.point[self.captured_point]['text_obj'], new_x, new_y)
            self.canvas.configure(scrollregion=self.canvas.bbox('all'))

            for key, value in self.captured_lines.items():
                line_attrs = self.canvas_obj.line[key]
                if value == 'start_point':
                    x, y = self.coordinates[line_attrs['end_point']]
                    self.canvas.coords(key, new_x, new_y, x, y)
                else:
                    x, y = self.coordinates[line_attrs['start_point']]
                    self.canvas.coords(key, x, y, new_x, new_y)
                if self.show_weight.get():
                    mid_x, mid_y = self.midpoint(new_x, new_y, x, y)
                    self.canvas.coords(line_attrs['weight_obj'][1], mid_x, mid_y)
                    r = int(self.r / 2) * len(str(line_attrs['weight']))
                    self.canvas.coords(line_attrs['weight_obj'][0], mid_x - r, mid_y - r, mid_x + r, mid_y + r)

    def exit(self):
        """Closes application.

        :return: None
        """
        self.master.destroy()

    def server_settings(self):
        """Open server settings window.

        :return: None
        """
        self.top = Toplevel()

        self.host.set(self.client.address[0])
        self.port.set(self.client.address[1])

        Label(self.top, text="Host:").grid(row=0, column=0, sticky="w")
        Label(self.top, text="Port:").grid(row=1, column=0, sticky="w")
        Label(self.top, text="Player name:").grid(row=2, column=0, sticky="w")
        Label(self.top, text="Password:").grid(row=3, column=0, sticky="w")

        Entry(self.top, textvariable=self.host).grid(row=0, column=1, padx=5, pady=5)
        Entry(self.top, textvariable=self.port).grid(row=1, column=1, padx=5, pady=5)
        Entry(self.top, textvariable=self.player_name).grid(row=2, column=1, padx=5, pady=5)
        Entry(self.top, textvariable=self.password).grid(row=3, column=1, padx=5, pady=5)

        Button(self.top, text='Apply', command=self.apply_server_settings).grid(row=4, column=0, padx=5, pady=5,
                                                                                sticky="w")
        Button(self.top, text='Cancel', command=self.cancel_server_settings).grid(row=4, column=1, padx=5, pady=5,
                                                                                  sticky="e")
        self.top.grab_set()
        self.top.focus_set()
        self.top.wait_window()

    def apply_server_settings(self):
        """Apply server settings and connection to host.

        :return: None
        """
        try:
            self.client = Client(self.validate_entry(self.host.get()), self.validate_entry(self.port.get()))
            self.client.login(self.validate_entry(self.player_name.get()), self.validate_entry(self.password.get()))
            self.server_data = self.client.get_static_objects().data
            self.path.set('No file chosen')
            self.build_graph()
        except UsernameMissing as e:
            tkMessageBox.showwarning('Warning', str(e).capitalize())
        except socket.error as e:
            tkMessageBox.showerror('Error', str(e).capitalize())

    @staticmethod
    def validate_entry(text_variable):
        """Validate string length.

        :param text_variable: string - string to check
        :return: None if the string length is 0 else the string
        """
        if len(text_variable.strip()) == 0:
            return None
        else:
            return text_variable

    def cancel_server_settings(self):
        """Closes server settings.

        :return: None
        """
        self.top.destroy()


if __name__ == '__main__':
    root = Tk()
    app = Application(master=root)
    app.mainloop()
