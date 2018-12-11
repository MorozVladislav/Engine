#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements bot for playing the game."""
from Queue import Queue
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
            message = exc.message if exc.message != '' else exc.strerror
            self.refresh_status_bar('Error: {}'.format(message))
            raise exc

    return wrapped


class Bot(object):
    """The bot main class."""

    def __init__(self):
        """Initiates bot."""
        self.host = None
        self.port = None
        self.timeout = None
        self.username = None
        self.password = None
        self.client = None
        self.queue = None
        self.started = False
        self.lines = {}
        self.points = {}
        self.adjacencies = {}
        self.player_idx = None
        self.town = None
        self.idx = None
        self.ratings = {}
        self.posts = {}
        self.trains = {}

    def refresh_status_bar(self, value):
        """Enqueues application status bar refresh request.

        :param value: string - status string
        :return: None
        """
        self.queue.put((0, value))

    @client_exceptions
    def login(self):
        """Creates Client, sends log in request and displays username and rating in status bar."""
        self.refresh_status_bar('Connecting...')
        self.client = Client(host=self.host,
                             port=self.port,
                             timeout=self.timeout,
                             username=self.username,
                             password=self.password)
        response = loads(self.client.login().data)
        self.player_idx = response['idx']
        self.queue.put((1, self.player_idx))
        self.refresh_status_bar('{}: {}'.format(response['name'], response['rating']))

    @client_exceptions
    def build_map(self):
        """Requests static objects and enqueues draw map request."""
        static_objects = self.client.get_static_objects().data
        self.queue.put((2, static_objects))
        static_objects = loads(static_objects)
        for point in static_objects['points']:
            self.points[point['idx']] = point
        for line in static_objects['lines']:
            self.lines[line['idx']] = line

    @client_exceptions
    def refresh_map(self):
        """Requests dynamic objects and enqueues refresh map request."""
        dynamic_objects = loads(self.client.get_dynamic_objects().data)
        self.idx = dynamic_objects['idx']
        self.ratings = dynamic_objects['ratings']
        for post in dynamic_objects['posts']:
            self.posts[post['point_idx']] = post
            if post['type'] == 1 and post['player_idx'] == self.player_idx:
                self.town = post
        for train in dynamic_objects['trains']:
            self.trains[train['idx']] = train
        rating = '{}: {}'.format(self.ratings[self.player_idx]['name'], self.ratings[self.player_idx]['rating'])
        self.refresh_status_bar(rating)
        self.queue.put((3, dynamic_objects))

    @client_exceptions
    def logout(self):
        """Sends log out request."""
        self.client.logout()

    @client_exceptions
    def tick(self):
        """Sends turn request and refreshes map."""
        self.client.turn()
        self.refresh_map()

    def start(self, host=None, port=None, time_out=None, username=None, password=None):
        """Logs in and starts bot.

        :param host: string - host
        :param port: int - port
        :param time_out: int - timeout
        :param username: string - username
        :param password: string - password
        """
        self.host, self.port, self.timeout, self.username, self.password = host, port, time_out, username, password
        self.queue = Queue()
        try:
            self.login()
            self.build_map()
            self.refresh_map()
            self.create_adjacency_list()
            self.started = True
            while self.started:
                route = self.get_route(1, 2)
                self.move_train(1, route)
            self.queue = None
            self.logout()
        except Exception as exc:
            self.queue.put((99, exc))
            raise exc

    def stop(self):
        """Stops bot."""
        self.started = False

    def create_adjacency_list(self):
        """Creates new dict of adjacencies."""
        self.adjacencies = {}
        for idx, attrs in self.lines.items():
            start_point, end_point = attrs['points'][0], attrs['points'][1]
            if start_point not in self.adjacencies.keys():
                self.adjacencies[start_point] = {}
            if end_point not in self.adjacencies.keys():
                self.adjacencies[end_point] = {}
            self.adjacencies[start_point][end_point] = idx
            self.adjacencies[end_point][start_point] = idx

    def dijkstra_algorithm(self, point):
        """Finds the shortest paths from the point to all other points.

        :param point: int - point index
        :return: 2-tuple of dictionaries where the first one is shortest paths and the second one is distance of paths
        """
        point_to, dist_to, visited = {}, {}, {}
        for point_idx in self.adjacencies.keys():
            dist_to[point_idx] = float('inf') if point_idx != point else 0
        while dist_to:
            closest_point = min(dist_to, key=dist_to.get)
            for point_idx, line_idx in self.adjacencies[closest_point].items():
                if point_idx not in visited:
                    new_dist = dist_to[closest_point] + self.lines[line_idx]['length']
                    if new_dist < dist_to[point_idx]:
                        dist_to[point_idx] = new_dist
                        point_to[point_idx] = closest_point
            visited[closest_point] = dist_to[closest_point]
            dist_to.pop(closest_point)
        return point_to, visited

    def move_train(self, idx, rote):
        """Moves train over a rote.

        :param idx: int - train index
        :param rote: list - list of turn points indexes
        :return: None
        """
        for i in xrange(len(rote) - 1):
            line_idx = self.adjacencies[rote[i]][rote[i + 1]]
            direction = 1 if rote[i] == self.lines[line_idx]['points'][0] else -1
            self.client.move_train(line_idx, direction, idx)
            while rote[i + 1] != self.get_current_point(idx):
                self.tick()

    def get_current_point(self, idx):
        """Returns the current point of the train.

        :param idx: int - train index
        :return: int - current point index
        """
        line = self.trains[idx]['line_idx']
        position = self.trains[idx]['position']
        speed = self.trains[idx]['speed']
        weight = self.lines[line]['length']
        if 0 < position < weight:
            current_point = self.lines[line]['points'][0] if speed >= 0 else self.lines[line]['points'][1]
        else:
            current_point = self.lines[line]['points'][0] if position == 0 else self.lines[line]['points'][1]
        return current_point

    def get_turn_points(self, train_idx, target_point, point_from=None):
        """Returns a list of turn points of the shortest way from current point to target point.

        :param train_idx: int - train index
        :param target_point: int - target point index
        :param point_from: int - point index to build way from, if None - the way builds from current point
        :return: return: 2-tuple where the first item is a trip length to the target point and the second item
        is a list of turn points
        """
        current_point = self.get_current_point(train_idx) if not point_from else point_from
        point_to, trip_to = self.dijkstra_algorithm(current_point)
        turn_points = [target_point]
        if target_point != current_point:
            temp_point = target_point
            while point_to[temp_point] != current_point:
                temp_point = point_to[temp_point]
                turn_points.append(temp_point)
            turn_points.append(current_point)
        return trip_to[target_point], list(reversed(turn_points))

    def get_route(self, train_idx, goods_type):
        """Returns most profitable route for a train or returns closest route back to town if the train is full.

        :param train_idx: int - train index
        :param goods_type: int - type of goods to be mined
        :return: list - list of points to be passed when moving from current point to target point
        """
        train = self.trains[train_idx]
        if train['goods'] < train['goods_capacity']:
            target_posts = []
            current = self.get_current_point(train_idx)
            for post in self.posts.values():
                if (post['type'] == goods_type or post['type'] == self.town['type']) and post['point_idx'] != current:
                    target_posts.append(post)
            max_efficiency, route = -1 * float('inf'), None
            for post in target_posts:
                trip_to, points_to = self.get_turn_points(train_idx, post['point_idx'])
                trip_from, points_from = self.get_turn_points(train_idx, self.town['point_idx'],
                                                              point_from=post['point_idx'])
                if post != self.town:
                    post_goods = post['product'] if goods_type == 2 else post['armor']
                    post_capacity = post['product_capacity'] if goods_type == 2 else post['armor_capacity']
                    replenishment = post_goods + post['replenishment'] * trip_to
                    available_goods = post_capacity if replenishment >= post_capacity else replenishment
                    space = train['goods_capacity'] - train['goods']
                    goods = train['goods_capacity'] if available_goods >= space else train['goods'] + available_goods
                    if goods_type == 2:
                        efficiency = goods - (trip_to + trip_from) * self.town['population']
                    else:
                        efficiency = goods
                else:
                    efficiency = train['goods'] - (trip_to + trip_from) * self.town['population']
                if efficiency > max_efficiency:
                    max_efficiency = efficiency
                    route = points_to
            return route[:2]
        trip_to, points_to = self.get_turn_points(train_idx, self.town['point_idx'])
        return points_to
