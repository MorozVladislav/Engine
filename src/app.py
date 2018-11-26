#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements GUI of the game."""
import tkFileDialog
import tkSimpleDialog
from Tkinter import Frame, StringVar, IntVar, Menu, Label, Canvas, Scrollbar, Checkbutton, Entry
from Tkinter import HORIZONTAL, VERTICAL, BOTTOM, RIGHT, LEFT, BOTH, END, X, Y
from functools import wraps
from json import loads
from os.path import join
from socket import error, herror, gaierror, timeout

from attrdict import AttrDict
from PIL.ImageTk import PhotoImage

from client import Client, ClientException
from graph import Graph


def prepare_coordinates(func):
    """Calculates scales and coordinates for drawing in case they were not calculated previously.

    :param func: function - function that requires coordinates and scales
    :return: wrapped function
    """
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        if self.scale_x is None or self.scale_y is None:
            indent_x = max([icon.width() for icon in self.icons.values()]) / 2 + 5
            indent_y = max([icon.height() for icon in self.icons.values()]) / 2 + self.font_size + 5
            self.scale_x = int((self.x0 - indent_x) / max([abs(point[1]['x']) for point in self.points]))
            self.scale_y = int((self.y0 - indent_y) / max([abs(point[1]['y']) for point in self.points]))
        if not self.coordinates:
            for point in self.points:
                x, y = int(point[1]['x'] * self.scale_x + self.x0), int(point[1]['y'] * self.scale_y + self.y0)
                self.coordinates[point[0]] = (x, y)
        return func(self, *args, **kwargs)

    return wrapped


def client_exceptions(func):
    """Catches exceptions that can be thrown by Client and displays them in status bar.
    :param func: function - function that uses Client methods
    :return: wrapped function
    """
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except (ClientException, error, herror, gaierror, timeout) as exc:
            self.status_bar.set('Error: {}'.format(exc.message))

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

    def __init__(self, master=None):
        """Creates application main window with sizes self.WIDTH and self.HEIGHT.

        :param master: instance - Tkinter.Tk instance
        """
        super(Application, self).__init__(master)
        self.master.title('Engine Game')
        self.master.geometry('{}x{}'.format(self.WIDTH, self.HEIGHT))

        self.source, self._map, self.points, self.lines, self.captured_point = None, None, None, None, None
        self.x0, self.y0, self.scale_x, self.scale_y, self.font_size = None, None, None, None, None
        self.coordinates, self.captured_lines = {}, {}
        self.canvas_obj = AttrDict()
        
        self.zoom_rect_id = None
        self.ctrl_l_pressed = False
        self.start_zoom_x, self.start_zoom_y = -1, -1
        self.zoom_state_stack = [{'zoom_offset': (0.0, 0.0), 'zoom_coef': 1.0}]

        self.settings_window = None
        self.client = Client()
        self._server_settings = [self.client.host, self.client.port, self.client.username, self.client.password]
        self.idx, self.ratings, self.posts, self.trains = None, {}, {}, {}
        self.icons = {
            1: PhotoImage(file=join('icons', 'city.png')),
            2: PhotoImage(file=join('icons', 'market.png')),
            3: PhotoImage(file=join('icons', 'store.png')),
            4: PhotoImage(file=join('icons', 'point.png'))
        }

        self.menu = Menu(self)
        filemenu = Menu(self.menu)
        filemenu.add_command(label='Open file', command=self.file_open)
        filemenu.add_command(label='Server settings', command=self.open_server_settings)
        filemenu.add_command(label='Exit', command=self.exit)
        self.menu.add_cascade(label='File', menu=filemenu)
        self.menu.add_command(label='Play', command=self.bot)
        master.config(menu=self.menu)

        self.status_bar = StringVar()
        self.status_bar.set('Ready')
        self.label = Label(master, textvariable=self.status_bar).pack()

        self.frame = Frame(self)
        self.frame.bind('<Configure>', self.resize_frame)
        self.canvas = Canvas(self.frame, bg=self.BG, scrollregion=(0, 0, self.winfo_width(), self.winfo_height())) 
        self.canvas.bind('<Button-1>', self.l_button_pressed)
        self.canvas.bind('<Motion>', self.mouse_move)
        self.canvas.bind('<B1-ButtonRelease>', self.l_button_release)
        self.canvas.bind('<Configure>', self.resize_canvas)
        self.frame.bind('<KeyPress>', self.key_down)
        self.frame.bind('<KeyRelease>', self.key_up)
        self.frame.pack()
        
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
        self.weighted_check = Checkbutton(self, text='Proportionally to weight', variable=self.weighted,
                                          command=self.build_map)
        self.weighted_check.pack(side=LEFT)

        self.show_weight = IntVar()
        self.show_weight_check = Checkbutton(self, text='Show weight', variable=self.show_weight,
                                             command=self.show_weights)
        self.show_weight_check.pack(side=LEFT)

        self.pack(fill=BOTH, expand=True)

        self.login()

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

    @property
    def server_settings(self):
        """Returns a list of actual server settings."""
        return self._server_settings

    @server_settings.setter
    def server_settings(self, value):
        """Logs in and receives map each time a list of server settings was assigned."""
        self._server_settings = value
        self.login()
        self.get_map()

    def resize_frame(self, event):
        """Calculates new font size each time frame size changes.

        :param event: Tkinter.Event - Tkinter.Event instance for Configure event
        :return: None
        """
        self.font_size = int(0.0125 * min(event.width, event.height))

    def resize_canvas(self, event):
        """Redraws map each time Canvas size changes. Scales map each time visible part of Canvas is enlarged.

        :param event: Tkinter.Event - Tkinter.Event instance for Configure event
        :return: None
        """
        self.apply_zoom(event.x, event.y)
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
            
    def apply_zoom(self, x, y):
        """Applies the lates zoom parameters to x, y"""        
        for zoom_params in self.zoom_state_stack:
            x = (x-zoom_params['zoom_offset'][0]) * zoom_params['zoom_coef'] + zoom_params['zoom_offset'][0]
            y = (y-zoom_params['zoom_offset'][1]) * zoom_params['zoom_coef'] + zoom_params['zoom_offset'][1]
        return x, y

#     def undo_zoom(self, x, y):
#         """Applies the lates zoom parameters to x, y"""        
#         for zoom_params in self.zoom_state_stack:
#             x = (x-zoom_params['zoom_offset'][0]) / zoom_params['zoom_coef'] + zoom_params['zoom_offset'][0]
#             y = (y-zoom_params['zoom_offset'][1]) / zoom_params['zoom_coef'] + zoom_params['zoom_offset'][1]
#         return x, y


    def file_open(self):
        """Implements file dialog and builds and draws a map once a file is chosen."""
        try:
            self.source = tkFileDialog.askopenfile(parent=self.master, **self.FILE_OPEN_OPTIONS).name
        except AttributeError:
            return
        self.idx, self.ratings, self.posts, self.trains = None, {}, {}, {}
        self.build_map()

    def open_server_settings(self):
        """Open server settings window."""
        ServerSettings(self, title='Server settings')
        self.frame.focus_set()

    def exit(self):
        """Closes application and sends logout request."""
        self.logout()
        self.master.destroy()

    def build_map(self):
        """Builds and draws new map."""
        if self.source is not None:
            self.map = Graph(self.source, weighted=self.weighted.get())
            self.status_bar.set('Map title: '+self.map.name)
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
        if self.map is not None:
            self.canvas.delete('all')
            self.draw_map()

    @prepare_coordinates
    def draw_points(self):
        """Draws map points by prepared coordinates."""
        point_objs = {}
        objs_point = {}
        for point in self.points:
            x, y = self.coordinates[point[0]]
            if self.posts and point[0] in self.posts.keys():
                icon_id = self.posts[point[0]]['type']
                text = self.posts[point[0]]['name'].upper()
                point_id = self.canvas.create_image(x, y, image=self.icons[icon_id])
                y -= (self.icons[icon_id].height() / 2) + self.font_size
                text_id = self.canvas.create_text(x, y, text=text, font="{} {}".format(self.FONT, self.font_size))
            else:
                icon_id = 4
                point_id = self.canvas.create_image(x, y, image=self.icons[icon_id])
                text_id = None
            point_objs[point_id] = {'idx': point[0], 'text_obj': text_id, 'icon': icon_id}
            objs_point[point[0]] = point_id
        self.canvas_obj['point'] = point_objs
        self.canvas_obj['canvas_point'] = objs_point

    @prepare_coordinates
    def draw_lines(self):
        """Draws map lines by prepared coordinates and shows their weights if self.show_weight is set to 1."""
        line_objs = {}
        for line in self.lines:
            x_start, y_start = self.coordinates[line[0]]
            x_stop, y_stop = self.coordinates[line[1]]
            line_id = self.canvas.create_line(x_start, y_start, x_stop, y_stop)
            x_canvas_start, y_canvas_start, x_canvas_stop, y_canvas_stop = self.canvas.coords(line_id)
            self.canvas.tag_lower(line_id)
            line_objs[line_id] = {'idx': line[2]['idx'], 'weight': line[2]['weight'], 'start_point': line[0],
                                  'end_point': line[1], 'weight_obj': ()}
        self.canvas_obj['line'] = line_objs
        self.show_weights()

    def show_weights(self):
        """Shows line weights when self.show_weight is set to 1 and hides them when it is set to 0."""
        if len(self.canvas_obj) > 0:
            if self.show_weight.get():
                for line in self.canvas_obj.line.values():
                    if line['weight_obj']:
                        for obj in line['weight_obj']:
                            self.canvas.itemconfigure(obj, state='normal')
                    else:
                        pointId = self.canvas_obj.canvas_point[line['start_point']]
                        #x_start, y_start, x_end, y_end  = line['canvas_coords'] 
                        x_start, y_start = self.canvas.coords(pointId)
                        pointId = self.canvas_obj.canvas_point[line['end_point']]
                        x_end, y_end = self.canvas.coords(pointId)
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
            self.canvas.coords(self.captured_point, new_x, new_y)
            indent_y = self.icons[self.canvas_obj.point[self.captured_point]['icon']].height() / 2 + self.font_size
            if self.canvas_obj.point[self.captured_point]['text_obj'] is not None:
                self.canvas.coords(self.canvas_obj.point[self.captured_point]['text_obj'], new_x, new_y - indent_y)
            
            for key, value in self.captured_lines.items():
                line_attrs = self.canvas_obj.line[key]
                if value == 'start_point':
                    pointId = self.canvas_obj.canvas_point[line_attrs['end_point']]
                    x, y = self.canvas.coords(pointId)
                    self.canvas.coords(key, new_x, new_y, x, y)
                else:
                    pointId = self.canvas_obj.canvas_point[line_attrs['start_point']]
                    x, y = self.canvas.coords(pointId)
                    self.canvas.coords(key, x, y, new_x, new_y)
                if self.show_weight.get():
                    mid_x, mid_y = self.midpoint(new_x, new_y, x, y)
                    self.canvas.coords(line_attrs['weight_obj'][1], mid_x, mid_y)
                    r = self.font_size * len(str(line_attrs['weight']))
                    self.canvas.coords(line_attrs['weight_obj'][0], mid_x - r, mid_y - r, mid_x + r, mid_y + r)
                    
            
            self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def key_up(self, event):
        # <Ctrl_L> released
        self.ctrl_l_pressed = ((event.state & 0x0004) != 0)

        if event.keysym == 'Escape':
            self.reset_zoom()
    
    def key_down(self, event):
        # <Ctrl_L> pressed
        self.ctrl_l_pressed = ((event.state & 0x0004) != 0)
        
    def l_button_pressed(self, event):
        if self.ctrl_l_pressed:
            self.start_zoom(event)
        else:
            self.capture_point(event)
    
    def l_button_release(self, event):
        if self.ctrl_l_pressed and self.zoom_rect_id != None:
            self.canvas.delete(self.zoom_rect_id)
            self.zoom(event)
            self.start_zoom_x, self.start_zoom_y = -1, -1
        else:
            self.release_point(event)

    def mouse_move(self, event):
        #process zoom rectangle
        if self.zoom_rect_id:
            self.canvas.delete(self.zoom_rect_id)
        if self.ctrl_l_pressed and self.start_zoom_x >= 0:
            self.zoom_rect_id = self.canvas.create_rectangle(self.start_zoom_x, self.start_zoom_y,
                                                             event.x, event.y)
        else:
            self.move_point(event)
            
    def start_zoom(self, event):
        self.start_zoom_x, self.start_zoom_y = event.x, event.y 
    

    def zoom(self, event):
        x_coef = float(self.winfo_width())/abs(event.x-self.start_zoom_x)
        y_coef = float(self.winfo_height())/abs(event.y-self.start_zoom_y)
        
        zoom_coef = min(x_coef, y_coef)
        
        #let's predict the center of our new visable area
        x0, y0 = (event.x+self.start_zoom_x)/2, (event.y+self.start_zoom_y)/2
        
        #move zoom left corner to the canvas if it appears to be outside Canvas
        x0_new = max(0, x0-(self.winfo_width()/zoom_coef)/2)
        y0_new = max(0, y0-(self.winfo_height()/zoom_coef)/2)

        zoom_offset = (x0_new, y0_new)
               
        #get all chosen area
        #Ok Let's finally zoom it!
        self.zoom_state_stack.append({'zoom_offset': zoom_offset, 'zoom_coef': zoom_coef})
        self.canvas.scale('all', zoom_offset[0], zoom_offset[1], zoom_coef, zoom_coef)
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        
    #restore graph and canvas to default parameters
    def reset_zoom(self):
        if (len(self.zoom_state_stack) > 1):
            zoom_params = self.zoom_state_stack.pop()
        else:
            zoom_params = self.zoom_state_stack[0]
        self.canvas.scale('all', zoom_params['zoom_offset'][0], zoom_params['zoom_offset'][1], 
                                1.0 / zoom_params['zoom_coef'], 1.0 / zoom_params['zoom_coef'])        
    
    @client_exceptions
    def login(self):
        """Sends log in request and displays username and rating in status bar."""
        self.idx, self.ratings, self.posts, self.trains = None, {}, {}, {}
        self.client.host, self.client.port = self.server_settings[:2]
        response = loads(self.client.login(name=self.server_settings[2], password=self.server_settings[3]).data)
        self.status_bar.set('{}: {}'.format(response['name'], response['rating']))

    @client_exceptions
    def logout(self):
        """Sends log out request."""
        self.client.logout()

    @client_exceptions
    def get_map(self):
        """Requests static and dynamic objects and draws map."""
        self.source = self.client.get_static_objects().data
        dynamic_objects = loads(self.client.get_dynamic_objects().data)
        self.idx = dynamic_objects['idx']
        for key, value in dynamic_objects['ratings'].items():
            self.ratings[key] = value
        for item in dynamic_objects['posts']:
            self.posts[item['point_idx']] = item
        for item in dynamic_objects['trains']:
            self.trains[item['line_idx']] = item
        self.build_map()

    def bot(self):
        """Calls bot for playing the game."""
        pass



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
        Label(master, text="Host:").grid(row=0, sticky='W')
        Label(master, text="Port:").grid(row=1, sticky='W')
        Label(master, text="Player name:").grid(row=2, sticky='W')
        Label(master, text="Password:").grid(row=3, sticky='W')
        for i in xrange(4):
            self.entries.append(Entry(master))
            setting = self.parent.server_settings[i]
            self.entries[i].insert(END, setting if setting is not None else '')
            self.entries[i].grid(row=i, column=1)
        return self.entries[0]

    def apply(self):
        """Assigns entered value to parent host, port username and password attributes."""
        settings = []
        for entry in self.entries:
            settings.append(str(entry.get()) if entry.get() != '' else None)
        self.parent.server_settings = settings
        