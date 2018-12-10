#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements GUI of the game."""
import tkFileDialog
import tkSimpleDialog
from Tkinter import Frame, StringVar, IntVar, Menu, Label, Canvas, Scrollbar, Checkbutton, Entry, Button
from Tkinter import HORIZONTAL, VERTICAL, BOTTOM, RIGHT, LEFT, BOTH, END, NORMAL, X, Y
from functools import wraps
from os.path import expanduser, exists
from os.path import join
from threading import Thread

from PIL.ImageTk import PhotoImage
from attrdict import AttrDict
from lya import AttrDict as DefaultsDict

from bot import Bot
from graph import Graph


def prepare_coordinates(func):
    """Calculates scales and coordinates for drawing in case they were not calculated previously.

    :param func: function - function that requires coordinates and scales
    :return: wrapped function
    """
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        if not self.scale_x or not self.scale_y:
            indent_x = max([icon.width() for icon in self.icons.values()]) + 5
            indent_y = max([icon.height() for icon in self.icons.values()]) + self.font_size + 5
            self.scale_x = int((self.x0 - indent_x) / max([abs(point['x']) for point in self.points.values()]))
            self.scale_y = int((self.y0 - indent_y) / max([abs(point['y']) for point in self.points.values()]))
        if not self.coordinates:
            for idx, attrs in self.points.items():
                x, y = int(attrs['x'] * self.scale_x + self.x0), int(attrs['y'] * self.scale_y + self.y0)
                self.coordinates[idx] = (x, y)
        return func(self, *args, **kwargs)

    return wrapped


class Application(Frame, object):
    """The application main class."""
    WIDTH, HEIGHT = 1280, 720
    BG = 'white'
    FONT = 'Verdana'
    FILE_OPEN_OPTIONS = {
        'mode': 'rb',
        'title': 'Choose *.json file',
        'defaultextension': '.json',
        'filetypes': [('JSON file', '*.json')]
    }
    DEFAULTS = 'default_settings.yaml'

    def __init__(self, master=None):
        """Creates application main window with sizes self.WIDTH and self.HEIGHT.

        :param master: instance - Tkinter.Tk instance
        """
        super(Application, self).__init__(master)
        self.master.title('Engine Game')
        self.master.geometry('{}x{}'.format(self.WIDTH, self.HEIGHT))
        self.master.protocol('WM_DELETE_WINDOW', self.exit)

        self.source = None
        self._map = None
        self.points = None
        self.lines = None
        self.captured_point = None
        self.x0 = None
        self.y0 = None
        self.scale_x = None
        self.scale_y = None
        self.font_size = None
        self.coordinates = {}
        self.captured_lines = {}
        self.canvas_obj = AttrDict()
        self.icons = {
            0: PhotoImage(file=join('icons', 'player_city.png')),
            1: PhotoImage(file=join('icons', 'city.png')),
            2: PhotoImage(file=join('icons', 'market.png')),
            3: PhotoImage(file=join('icons', 'store.png')),
            4: PhotoImage(file=join('icons', 'point.png')),
            5: PhotoImage(file=join('icons', 'player_train.png')),
            6: PhotoImage(file=join('icons', 'train.png')),
            7: PhotoImage(file=join('icons', 'crashed_train.png')),
            8: PhotoImage(file=join('icons', 'play.png')),
            9: PhotoImage(file=join('icons', 'stop.png')),
            10: PhotoImage(file=join('icons', 'big_play.png'))
        }
        self.queue_requests = {
            0: self.set_status_bar,
            1: self.set_player_idx,
            2: self.build_map,
            3: self.refresh_map,
            98: self.start_bot,
            99: self.stop_bot
        }

        self.settings_window = None
        self.defaults = None
        if exists(expanduser(self.DEFAULTS)):
            with open(expanduser(self.DEFAULTS), 'r') as cfg:
                self.defaults = DefaultsDict.from_yaml(cfg)

        self.user_info = [None]*5
        if self.defaults:
            self.user_info = {
                'host': None if not self.defaults.host else str(self.defaults.host),
                'port': None if not self.defaults.port else int(self.defaults.port),
                'username': None if not self.defaults.username else str(self.defaults.username),
                'password': None if not self.defaults.password else str(self.defaults.password),
                'timeout': None if not self.defaults.timeout else int(self.defaults.timeout)
            }

        self.player_idx = None
        self.posts = {}
        self.trains = {}
        self.bot = Bot()
        self.bot_thread = None

        self.menu = Menu(self)
        filemenu = Menu(self.menu)
        filemenu.add_command(label='Open file', command=self.file_open)
        filemenu.add_command(label='Server settings', command=self.open_server_settings)
        filemenu.add_command(label='Exit', command=self.exit)
        self.menu.add_cascade(label='Menu', menu=filemenu)
        master.config(menu=self.menu)

        self._status_bar = StringVar()
        self.label = Label(master, textvariable=self._status_bar)
        self.label.pack()

        self.frame = Frame(self)
        self.frame.bind('<Configure>', self._resize_frame)
        self.canvas = Canvas(self.frame, bg=self.BG, scrollregion=(0, 0, self.winfo_width(), self.winfo_height()))
        self.canvas.bind('<Button-1>', self._capture_point)
        self.canvas.bind('<Motion>', self._move_point)
        self.canvas.bind('<B1-ButtonRelease>', self._release_point)
        self.canvas.bind('<Configure>', self._resize_canvas)
        hbar = Scrollbar(self.frame, orient=HORIZONTAL)
        hbar.pack(side=BOTTOM, fill=X)
        hbar.config(command=self.canvas.xview)
        vbar = Scrollbar(self.frame, orient=VERTICAL)
        vbar.pack(side=RIGHT, fill=Y)
        vbar.config(command=self.canvas.yview)
        self.canvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.pack(fill=BOTH, expand=True)
        self.frame.pack(fill=BOTH, expand=True)

        self.weighted = IntVar(value=1)
        self.weighted_check = Checkbutton(self, text='Proportionally to length', variable=self.weighted,
                                          command=self._proportionally)
        self.weighted_check.pack(side=RIGHT, in_=self.frame)

        self.show_weight = IntVar()
        self.show_weight_check = Checkbutton(self, text='Show length', variable=self.show_weight,
                                             command=self.show_weights)
        self.show_weight_check.pack(side=RIGHT, in_=self.frame)

        self.start_button = Button(self, image=self.icons[10], highlightbackground="white", command=self.start_game)
        self.start_button.pack(expand=1, in_=self.canvas)
        self.button = Button(self, image=self.icons[9], highlightbackground="white", command=self.bot_control)
        self.button.pack(side=LEFT, in_=self.frame)
        self.button.lower(self.frame)

        self.pack(fill=BOTH, expand=True)
        self.requests_executor()
        self.set_status_bar('Click Play to start the game')

    @property
    def map(self):
        """Returns the actual map."""
        return self._map

    @map.setter
    def map(self, value):
        """Clears previously drawn map and assigns a new map to self._map."""
        self.clear_map()
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), self.canvas.winfo_height()))
        self.x0, self.y0 = self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2
        self._map = value

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

    def _resize_frame(self, event):
        """Calculates new font size each time frame size changes.

        :param event: Tkinter.Event - Tkinter.Event instance for Configure event
        :return: None
        """
        self.font_size = int(0.0125 * min(event.width, event.height))

    def _resize_canvas(self, event):
        """Redraws map each time Canvas size changes. Scales map each time visible part of Canvas is enlarged.

        :param event: Tkinter.Event - Tkinter.Event instance for Configure event
        :return: None
        """
        if self.map:
            k = min(float(event.width) / float(self.x0 * 2), float(event.height) / float(self.y0 * 2))
            self.scale_x, self.scale_y = self.scale_x * k, self.scale_y * k
            self.x0, self.y0 = self.x0 * k, self.y0 * k
            self.redraw_map()
            self.redraw_trains()
            x_start, y_start, x_end, y_end = self.canvas.bbox('all')
            x_start = 0 if x_start > 0 else x_start
            y_start = 0 if y_start > 0 else y_start
            self.canvas.configure(scrollregion=(x_start, y_start, x_end, y_end))

    def _proportionally(self):
        """Rebuilds map and redraws trains."""
        self.build_map()
        self.redraw_trains()

    def _capture_point(self, event):
        """Stores captured point and it's lines.

        :param event: Tkinter.Event - Tkinter.Event instance for ButtonPress event
        :return: None
        """
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        obj_ids = self.canvas.find_overlapping(x - 5, y - 5, x + 5, y + 5)
        if not obj_ids:
            return
        for obj_id in obj_ids:
            if obj_id in self.canvas_obj.point.keys():
                self.captured_point = obj_id
                point_idx = self.canvas_obj.point[obj_id]['idx']
                self.captured_lines = {}
                for line_id, attr in self.canvas_obj.line.items():
                    if attr['start_point'] == point_idx:
                        self.captured_lines[line_id] = 'start_point'
                    if attr['end_point'] == point_idx:
                        self.captured_lines[line_id] = 'end_point'
        if self.weighted.get():
            self.weighted.set(0)

    def _release_point(self, event):
        """Writes new coordinates for a moved point and resets self.captured_point and self.captured_lines.

        :param event: Tkinter.Event - Tkinter.Event instance for ButtonRelease event
        :return: None
        """
        if self.captured_point:
            idx = self.canvas_obj.point[self.captured_point]['idx']
            x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            self.coordinates[idx] = (x, y)
            self.points[idx]['x'], self.points[idx]['y'] = (x - self.x0) / self.scale_x, (y - self.y0) / self.scale_y
            self.captured_point = None
            self.captured_lines = {}

    def _move_point(self, event):
        """Moves point and its lines. Moves weights if self.show_weight is set to 1.

        In case some point is moved beyond Canvas border Canvas scrollregion is resized correspondingly.
        :param event: Tkinter.Event - Tkinter.Event instance for Motion event
        :return: None
        """
        if self.captured_point:
            new_x, new_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            self.canvas.coords(self.captured_point, new_x, new_y)
            indent_y = self.icons[self.canvas_obj.point[self.captured_point]['icon']].height() / 2 + self.font_size
            if self.canvas_obj.point[self.captured_point]['text_obj']:
                self.canvas.coords(self.canvas_obj.point[self.captured_point]['text_obj'], new_x, new_y - indent_y)
            self.coordinates[self.canvas_obj.point[self.captured_point]['idx']] = (new_x, new_y)
            self.canvas.configure(scrollregion=self.canvas.bbox('all'))

            for line_id, attr in self.captured_lines.items():
                line_attrs = self.canvas_obj.line[line_id]
                if attr == 'start_point':
                    x, y = self.coordinates[line_attrs['end_point']]
                    self.canvas.coords(line_id, new_x, new_y, x, y)
                else:
                    x, y = self.coordinates[line_attrs['start_point']]
                    self.canvas.coords(line_id, x, y, new_x, new_y)
                if self.show_weight.get():
                    mid_x, mid_y = self.midpoint(new_x, new_y, x, y)
                    self.canvas.coords(line_attrs['weight_obj'][1], mid_x, mid_y)
                    r = self.font_size * len(str(line_attrs['weight']))
                    self.canvas.coords(line_attrs['weight_obj'][0], mid_x - r, mid_y - r, mid_x + r, mid_y + r)

            self.redraw_trains()

    def set_player_idx(self, value):
        """Sets a player idx value."""
        self.player_idx = value

    def file_open(self):
        """Opens file dialog and builds and draws a map once a file is chosen. Stops bot if its started."""
        path = tkFileDialog.askopenfile(parent=self.master, **self.FILE_OPEN_OPTIONS)
        if path:
            if self.bot_thread:
                self.stop_bot()
            self.posts, self.trains = {}, {}
            self.source = path.name
            self.weighted_check.configure(state=NORMAL)
            self.build_map()

    def open_server_settings(self):
        """Opens server settings window."""
        self.set_status_bar('Server settings')
        ServerSettings(self, title='Server settings')

    def exit(self):
        """Closes application and stops bot if its started."""
        if self.bot_thread:
            self.stop_bot()
        self.master.destroy()

    def start_game(self):
        """Starts bot or opens server settings if settings are invalid."""
        self.start_button.destroy()
        if None in self.user_info.values():
            self.open_server_settings()
        self.set_status_bar('Click play to start the game')
        self.button.lift(self.frame)
        self.button.configure(image=self.icons[8])

    def start_bot(self):
        """Starts bot"""
        self.bot_thread = Thread(target=self.bot.start, kwargs={
                                'host': self.user_info['host'],
                                'port': self.user_info['port'],
                                'time_out': self.user_info['timeout'],
                                'username': self.user_info['username'],
                                'password': self.user_info['password']})
        self.bot_thread.start()

    def stop_bot(self):
        """Stops bot"""
        self.bot.stop()
        self.bot_thread.join()
        self.bot_thread = None

    def bot_control(self):
        """Starts bot for playing the game or stops it if it is started."""
        if self.bot_thread:
            self.stop_bot()
        else:
            self.start_bot()

    def set_status_bar(self, value):
        """Assigns new status bar value and updates it.

        :param value: string - status bar string value
        :return: None
        """
        self._status_bar.set(value)
        self.label.update()

    def build_map(self, source=None):
        """Builds and draws new map.

        :param source: string - source string; could be JSON string or path to *.json file.
        :return: None
        """
        if source:
            self.source = source
        if self.source:
            self.map = Graph(self.source, weighted=self.weighted.get())
            self.set_status_bar('Map title: {}'.format(self.map.name))
            self.points, self.lines = self.map.get_coordinates()
            self.draw_map()

    def draw_map(self):
        """Draws map by prepared coordinates."""
        self.draw_lines()
        self.draw_points()

    def clear_map(self):
        """Clears previously drawn map and resets coordinates and scales."""
        self.canvas.delete('all')
        self.scale_x, self.scale_y = None, None
        self.coordinates = {}

    def redraw_map(self):
        """Redraws existing map by existing coordinates."""
        if self.map:
            self.coordinates = {}
            for obj_id in self.canvas_obj.line:
                self.canvas.delete(obj_id)
            self.draw_lines()
        self.redraw_points()

    def redraw_points(self):
        """Redraws map points by existing coordinates."""
        if self.map:
            for obj_id, attrs in self.canvas_obj.point.items():
                if attrs['text_obj']:
                    self.canvas.delete(attrs['text_obj'])
                self.canvas.delete(obj_id)
            self.draw_points()

    def redraw_trains(self):
        """Redraws existing trains."""
        if self.trains and hasattr(self.canvas_obj, 'train'):
            for obj_id, attrs in self.canvas_obj.train.items():
                self.canvas.delete(attrs['text_obj'])
                self.canvas.delete(obj_id)
        self.draw_trains()

    @prepare_coordinates
    def draw_points(self):
        """Draws map points by prepared coordinates."""
        point_objs = {}
        captured_point_idx = self.canvas_obj.point[self.captured_point]['idx'] if self.captured_point else None
        for idx in self.points.keys():
            x, y = self.coordinates[idx]
            if self.posts and idx in self.posts.keys():
                post_type = self.posts[idx]['type']
                if post_type == 1:
                    status = '{}/{} {}/{} {}/{}'.format(self.posts[idx]['population'],
                                                        self.posts[idx]['population_capacity'],
                                                        self.posts[idx]['product'],
                                                        self.posts[idx]['product_capacity'],
                                                        self.posts[idx]['armor'],
                                                        self.posts[idx]['armor_capacity'])
                elif post_type == 2:
                    status = '{}/{}'.format(self.posts[idx]['product'], self.posts[idx]['product_capacity'])
                else:
                    status = '{}/{}'.format(self.posts[idx]['armor'], self.posts[idx]['armor_capacity'])
                image_id = 0 if post_type == 1 and self.posts[idx]['player_idx'] == self.player_idx else post_type
                point_id = self.canvas.create_image(x, y, image=self.icons[image_id])
                y -= (self.icons[post_type].height() / 2) + self.font_size
                text_id = self.canvas.create_text(x, y, text=status, font="{} {}".format(self.FONT, self.font_size))
            else:
                post_type = 4
                point_id = self.canvas.create_image(x, y, image=self.icons[post_type])
                text_id = None
            point_objs[point_id] = {'idx': idx, 'text_obj': text_id, 'icon': post_type}
            self.captured_point = point_id if idx == captured_point_idx else self.captured_point
        self.canvas_obj['point'] = point_objs

    @prepare_coordinates
    def draw_lines(self):
        """Draws map lines by prepared coordinates and shows their weights if self.show_weight is set to 1."""
        line_objs, captured_lines_idx = {}, {}
        if self.captured_lines:
            for line_id in self.captured_lines.keys():
                captured_lines_idx[self.canvas_obj.line[line_id]['idx']] = line_id
        for idx, attrs in self.lines.items():
            x_start, y_start = self.coordinates[attrs['start_point']]
            x_stop, y_stop = self.coordinates[attrs['end_point']]
            line_id = self.canvas.create_line(x_start, y_start, x_stop, y_stop)
            line_objs[line_id] = {'idx': idx, 'weight': attrs['weight'], 'start_point': attrs['start_point'],
                                  'end_point': attrs['end_point'], 'weight_obj': ()}
            if idx in captured_lines_idx.keys():
                self.captured_lines[line_id] = self.captured_lines.pop(captured_lines_idx[idx])
        self.canvas_obj['line'] = line_objs
        self.show_weights()

    @prepare_coordinates
    def draw_trains(self):
        """Draws trains by prepared coordinates"""
        trains = {}
        for train in self.trains.values():
            start_point = self.lines[train['line_idx']]['start_point']
            end_point = self.lines[train['line_idx']]['end_point']
            weight = self.lines[train['line_idx']]['weight']
            position = train['position']
            x_start, y_start = self.coordinates[start_point]
            x_end, y_end = self.coordinates[end_point]
            delta_x, delta_y = int((x_start - x_end) / weight) * position, int((y_start - y_end) / weight) * position
            x, y = x_start - delta_x, y_start - delta_y
            image = self.icons[5] if train['player_idx'] == self.player_idx else self.icons[6]
            indent_y = image.height() / 2
            train_id = self.canvas.create_image(x, y - indent_y, image=image)
            status = '{}/{}'.format(train['goods'], train['goods_capacity'])
            text_id = self.canvas.create_text(x, y - (2 * indent_y + self.font_size), text=status,
                                              font="{} {}".format(self.FONT, self.font_size))
            trains[train_id] = {'icon': 4, 'text_obj': text_id}
        self.canvas_obj['train'] = trains

    def show_weights(self):
        """Shows line weights when self.show_weight is set to 1 and hides them when it is set to 0."""
        if not self.canvas_obj:
            return
        if self.show_weight.get():
            for line in self.canvas_obj.line.values():
                if line['weight_obj']:
                    for obj in line['weight_obj']:
                        self.canvas.itemconfigure(obj, state='normal')
                else:
                    x_start, y_start = self.coordinates[line['start_point']]
                    x_end, y_end = self.coordinates[line['end_point']]
                    x, y = self.midpoint(x_start, y_start, x_end, y_end)
                    value = line['weight']
                    size = self.font_size
                    r = int(size) * len(str(value))
                    oval_id = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=self.BG, width=0)
                    text_id = self.canvas.create_text(x, y, text=value, font="{} {}".format(self.FONT, str(size)))
                    line['weight_obj'] = (oval_id, text_id)
        else:
            for line in self.canvas_obj.line.values():
                if line['weight_obj']:
                    for obj in line['weight_obj']:
                        self.canvas.itemconfigure(obj, state='hidden')

    def requests_executor(self):
        """Dequeues and executes requests. Assigns corresponding label to bot control button."""
        if self.bot_thread:
            if not self.bot.queue.empty():
                request_type, request_body = self.bot.queue.get_nowait()
                if request_body:
                    self.queue_requests[request_type](request_body)
                    if 'Error' in request_body:
                        self.set_status_bar('Check your internet connection: ')
                        self.stop_bot()
                else:
                    self.queue_requests[request_type]()
        if self.bot_thread and self.bot_thread.is_alive():
            self.button.configure(image=self.icons[9])
        else:
            self.button.configure(image=self.icons[8])
        self.after(50, self.requests_executor)

    def refresh_map(self, dynamic_objects):
        """Refreshes map with passed dynamic objects.

        :param dynamic_objects: dict - dict of dynamic objects
        :return: None
        """
        for post in dynamic_objects['posts']:
            self.posts[post['point_idx']] = post
        for train in dynamic_objects['trains']:
            self.trains[train['idx']] = train
        self.redraw_points()
        self.redraw_trains()


class ServerSettings(tkSimpleDialog.Dialog, object):
    """Server settings window class"""

    def __init__(self, *args, **kwargs):
        """Initiates ServerSettings instance with additional attribute.

        :param args: positional arguments - positional arguments passed to parent __init__ method
        :param kwargs: keyword arguments - keyword arguments passed to parent __init__ method
        """
        self.entries = []
        super(ServerSettings, self).__init__(*args, **kwargs)

    def body(self, master):
        """Creates server settings window.

        :param master: instance - master widget instance
        :return: Entry instance
        """
        self.resizable(False, False)
        settings = [self.parent.user_info['host'], self.parent.user_info['port'], 
                    self.parent.user_info['username'], self.parent.user_info['password']]
        Label(master, text="Host:").grid(row=0, sticky='W')
        Label(master, text="Port:").grid(row=1, sticky='W')
        Label(master, text="Player name:").grid(row=2, sticky='W')
        Label(master, text="Password:").grid(row=3, sticky='W')
        for i in xrange(4):
            self.entries.append(Entry(master))
            setting = settings[i]
            self.entries[i].insert(END, setting if setting else '')
            self.entries[i].grid(row=i, column=1)
        return self.entries[0]

    def apply(self):
        """Assigns entered value to parent host, port username and password attributes."""
        settings = []
        for entry in self.entries:
            settings.append(str(entry.get()) if entry.get() != '' else None)
        self.parent.user_info['host'] = settings[0]
        self.parent.user_info['port'] = settings[1]
        self.parent.user_info['username'] = settings[2]
        self.parent.user_info['password'] = settings[3]
