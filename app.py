#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import tkFileDialog
from Tkinter import HORIZONTAL, VERTICAL, BOTTOM, RIGHT, LEFT, BOTH, X, Y
from Tkinter import Tk, StringVar, IntVar, Frame, Menu, Label, Canvas, Scrollbar, Checkbutton

from graph import Graph


def prepare_coordinates(func):
    def wrapped(self, *args, **kwargs):
        if self.SCALE_X is None or self.SCALE_Y is None:
            self.SCALE_X = int((self.X0 - self.R - 5) / max([abs(point[1]['x']) for point in self.points]))
            self.SCALE_Y = int((self.Y0 - self.R - 5) / max([abs(point[1]['y']) for point in self.points]))
        if len(self.coordinates) == 0:
            for point in self.points:
                x, y = int(point[1]['x'] * self.SCALE_X + self.X0), int(point[1]['y'] * self.SCALE_Y + self.Y0)
                self.coordinates[point[0]] = (x, y)
        return func(self, *args, **kwargs)
    return wrapped


class Application(Frame, object):

    FILE_OPEN_OPTIONS = {
        'mode': 'rb',
        'title': 'Choose *.json file',
        'defaultextension': '.json',
        'filetypes': [('JSON file', '*.json')]
    }
    WIDTH, HEIGHT = 1280, 720
    X0, Y0, SCALE_X, SCALE_Y = WIDTH / 2, HEIGHT / 2, None, None
    R = int(0.05 * min(X0, Y0))

    def __init__(self, master=None):
        super(Application, self).__init__(master)
        self.master.title('Graph')

        self._graph, self.points, self.lines = None, None, None
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
        self.canvas = Canvas(self.frame, bg="lightblue", scrollregion=(0, 0, self.WIDTH, self.HEIGHT))
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

        self.show_weight = IntVar()
        self.check_button = Checkbutton(self, text='Show weight', variable=self.show_weight, command=self.show_weights)
        self.check_button.pack(side=LEFT)

        self.pack()

    @property
    def graph(self):
        return self._graph

    @graph.setter
    def graph(self, value):
        self.canvas.delete('all')
        self.SCALE_X, self.SCALE_Y = None, None
        self.coordinates = {}
        self.weights = []
        self._graph = value

    def file_open(self):
        try:
            self.path.set(tkFileDialog.askopenfile(parent=root, **self.FILE_OPEN_OPTIONS).name)
        except AttributeError:
            return
        self.graph = Graph(self.path.get())
        self.points, self.lines = self.graph.get_coordinates()
        self.create_lines(self.lines)
        self.create_points(self.points)

    def exit(self):
        self.master.destroy()

    @prepare_coordinates
    def create_points(self, points):
        for point in points:
            x, y = self.coordinates[point[0]]
            self.canvas.create_oval(x - self.R, y - self.R, x + self.R, y + self.R, fill='lightgreen')
            self.canvas.create_text(x, y, text=point[0], font="Verdana " + str(int(self.R / 2)))

    @prepare_coordinates
    def create_lines(self, lines):
        for line in lines:
            x_start, y_start = self.coordinates[line[0]]
            x_stop, y_stop = self.coordinates[line[1]]
            self.canvas.create_line(x_start, y_start, x_stop, y_stop)
            self.weights.append(((x_start + x_stop) / 2, (y_start + y_stop) / 2, line[2]['weight']))
        self.show_weights()

    def show_weights(self):
        if len(self.weights) == 0:
            return
        if self.show_weight.get():
            for weight in self.weights:
                x, y, value = weight
                r = int(self.R / 2) * len(str(value))
                self.ids.append(self.canvas.create_oval(x - r, y - r, x + r, y + r, fill='lightblue', width=0))
                self.ids.append(self.canvas.create_text(x, y, text=value, font="Verdana " + str(r)))
        else:
            for element_id in self.ids:
                self.canvas.delete(element_id)


if __name__ == '__main__':
    root = Tk()
    app = Application(master=root)
    app.mainloop()
