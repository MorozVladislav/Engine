#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements bot for playing the game."""
from functools import wraps
from json import loads
from socket import error, herror, gaierror, timeout

from client import Client, ClientException


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
            if isinstance(exc, ClientException) or isinstance(exc, timeout):
                message = exc.message
            else:
                message = exc.strerror
            self.refresh_status_bar('Error: {}'.format(message))
            raise exc

    return wrapped


class Bot(object):
    """The bot main class."""

    def __init__(self, app):
        """Initiates bot.

        :param app: instance - Application instance
        """
        self.app = app
        self.client = None
        self.started = False
        self.player_idx, self.idx, self.ratings, self.posts, self.trains = None, None, {}, {}, {}
        self.adjacencies = {}

    def refresh_status_bar(self, value):
        """Enqueues application status bar refresh request.

        :param value: string - status string
        :return: None
        """
        self.app.bot_queue.put((0, value))

    @client_exceptions
    def build_map(self):
        """Requests static objects and enqueues draw map request."""
        self.app.bot_queue.put((1, self.client.get_static_objects().data))

    @client_exceptions
    def refresh_map(self):
        """Requests dynamic objects and enqueues refresh map request."""
        dynamic_objects = loads(self.client.get_dynamic_objects().data)
        self.idx = dynamic_objects['idx']
        self.ratings = dynamic_objects['ratings']
        for post in dynamic_objects['posts']:
            self.posts[post['point_idx']] = post
        for train in dynamic_objects['trains']:
            self.trains[train['idx']] = train
        rating = '{}: {}'.format(self.ratings[self.player_idx]['name'], self.ratings[self.player_idx]['rating'])
        self.refresh_status_bar(rating)
        self.app.bot_queue.put((2, dynamic_objects))

    @client_exceptions
    def login(self):
        """Creates Client, sends log in request and displays username and rating in status bar."""
        self.refresh_status_bar('Connecting...')
        self.client = Client(host=self.app.host,
                             port=self.app.port,
                             timeout=self.app.timeout,
                             username=self.app.username,
                             password=self.app.password)
        response = loads(self.client.login().data)
        self.player_idx = response['idx']
        self.refresh_status_bar('{}: {}'.format(response['name'], response['rating']))

    @client_exceptions
    def logout(self):
        """Sends log out request and resets internally used variables."""
        self.client.logout()
        self.player_idx, self.idx, self.ratings, self.posts, self.trains = None, None, {}, {}, {}

    @client_exceptions
    def tick(self):
        """Sends turn request and refreshes map."""
        self.client.turn()
        self.refresh_map()

    def start(self):
        """Logs in and starts bot."""
        self.login()
        self.build_map()
        self.refresh_map()
        self.create_adjacency_list()
        self.started = True
        while self.started:
            self.move_train(1, 19)
            self.move_train(1, 16)
            self.move_train(1, 13)
        self.logout()

    def stop(self):
        """Stops bot."""
        self.started = False

    def create_adjacency_list(self):
        """Creates new dict of adjacencies."""
        self.adjacencies = {}
        for idx, attrs in self.app.lines.items():
            start_point = attrs['start_point']
            end_point = attrs['end_point']
            if start_point not in self.adjacencies.keys():
                self.adjacencies[start_point] = {}
            if end_point not in self.adjacencies.keys():
                self.adjacencies[end_point] = {}
            self.adjacencies[start_point][end_point] = idx
            self.adjacencies[end_point][start_point] = idx

    def dijkstra_algorithm(self, point):
        """Finds the shortest paths from the point to all other points.

        :param point: int - point index
        :return: dictionary of shortest paths
        """
        point_to, dist_to, visited = {}, {}, {}
        for point_idx in self.adjacencies.keys():
            dist_to[point_idx] = float('inf') if point_idx != point else 0
        while dist_to:
            closest_point = min(dist_to, key=dist_to.get)
            for point_idx, line_idx in self.adjacencies[closest_point].items():
                if point_idx not in visited:
                    new_dist = dist_to[closest_point] + self.app.lines[line_idx]['weight']
                    if new_dist < dist_to[point_idx]:
                        dist_to[point_idx] = new_dist
                        point_to[point_idx] = closest_point
            visited[closest_point] = dist_to[closest_point]
            dist_to.pop(closest_point)
        return point_to

    def move_train(self, idx, target_point):
        """Moves train from current point to target point.

        :param idx: int - train index
        :param target_point: int - target point index
        :return: None
        """
        current_point = self.get_current_point(idx)
        point_to = self.dijkstra_algorithm(current_point)
        while target_point != current_point:
            if point_to[target_point] != current_point:
                temp_point = point_to[target_point]
                while point_to[temp_point] != current_point:
                    temp_point = point_to[temp_point]
            else:
                temp_point = target_point
            temp_line = self.adjacencies[current_point][temp_point]
            direction = 1 if current_point == self.app.lines[temp_line]['start_point'] else -1
            self.client.move_train(temp_line, direction, idx)
            while temp_point != self.get_current_point(idx):
                self.tick()
            current_point = self.get_current_point(idx)

    def get_current_point(self, idx):
        """Returns the current point of the train.

        :param idx: int - train index
        :return: int - current point index
        """
        current_line = self.trains[idx]['line_idx']
        if self.trains[idx]['position'] < self.app.lines[current_line]['weight']:
            current_point = self.app.lines[current_line]['start_point']
        else:
            current_point = self.app.lines[current_line]['end_point']
        return current_point
