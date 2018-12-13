#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements bot for playing the game."""
from Queue import Queue
from functools import wraps
from json import loads
from socket import error, herror, gaierror, timeout

from client import Client, ClientException


def client_exceptions(func):
    """Catches exceptions can be thrown by Client and displays them in status bar.

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
        self.current_tick = 0
        self.last_events = {}
        self.lines = {}
        self.points = {}
        self.adjacent = {}
        self.adjacent_no_markets = {}
        self.adjacent_no_storages = {}
        self.player_idx = None
        self.town = None
        self.idx = None
        self.ratings = {}
        self.posts = {}
        self.trains = {}
        self.expected_goods = {}
        self.occupied = {}

    def refresh_status_bar(self, value):
        """Enqueues application status bar refresh request.

        :param value: string - status string to be displayed in status bar
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
        self.adjacent = self.get_adjacent()

    @client_exceptions
    def refresh_map(self):
        """Requests dynamic objects and enqueues refresh map request."""
        dynamic_objects = loads(self.client.get_dynamic_objects().data)
        self.queue.put((3, dynamic_objects))
        self.idx = dynamic_objects['idx']
        self.ratings = dynamic_objects['ratings']
        for post in dynamic_objects['posts']:
            self.posts[post['point_idx']] = post
            if post['type'] == 1 and post['player_idx'] == self.player_idx:
                self.town = post
                for event in post['events']:
                    if event['type'] == 100:
                        self.stop()
                        self.refresh_status_bar('Game over!')
                        self.queue.put((99, None))
                        return
                    self.last_events[event['type']] = event
        self.occupied = {}
        for train in dynamic_objects['trains']:
            self.trains[train['idx']] = train
            self.occupied[train['idx']] = {'line_idx': train['line_idx'], 'position': train['position']}
            if train['player_idx'] == self.player_idx and train['idx'] not in self.expected_goods:
                self.expected_goods[train['idx']] = {'type': None, 'amount': None, 'trip': None, 'route': None}
        if not self.adjacent_no_markets or not self.adjacent_no_storages:
            markets = [idx for idx, attrs in self.posts.items() if attrs['type'] == 2]
            storages = [idx for idx, attrs in self.posts.items() if attrs['type'] == 3]
            self.adjacent_no_markets = self.get_adjacent(exclude=markets)
            self.adjacent_no_storages = self.get_adjacent(exclude=storages)
        rating = '{}: {}'.format(self.ratings[self.player_idx]['name'], self.ratings[self.player_idx]['rating'])
        self.refresh_status_bar(rating)

    @client_exceptions
    def logout(self):
        """Sends log out request."""
        self.client.logout()

    @client_exceptions
    def tick(self):
        """Sends turn request, updates current tick number and refreshes map."""
        self.client.turn()
        self.current_tick += 1
        self.refresh_map()
        for train_idx, goods in self.expected_goods.items():
            if goods['trip'] and self.trains[train_idx]['speed'] != 0:
                goods['trip'] -= 1

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
            self.started = True
            while self.started:
                self.move_trains()
                self.tick()
            self.queue = None
            self.logout()
        except Exception as exc:
            self.queue.put((99, exc))
            raise exc

    def stop(self):
        """Stops bot."""
        self.started = False

    def get_adjacent(self, exclude=None):
        """Returns new dict of adjacent points. Excludes points with indexes from exclude list.

        :param exclude: list - points to be excluded from adjacent dict
        :return: dict - dict of adjacent points
        """
        adjacent = {}
        for idx, attrs in self.lines.items():
            start_point, end_point = attrs['points'][0], attrs['points'][1]
            if exclude and (start_point in exclude or end_point in exclude):
                continue
            if start_point not in adjacent.keys():
                adjacent[start_point] = {}
            if end_point not in adjacent.keys():
                adjacent[end_point] = {}
            adjacent[start_point][end_point] = idx
            adjacent[end_point][start_point] = idx
        return adjacent

    def dijkstra_algorithm(self, point, adjacent):
        """Calculates shortest paths from the point to all other points.

        :param point: int - point index
        :param adjacent: dict - dict of adjacent points
        :return: 2-tuple of dictionaries where the first one is shortest paths and the second one is distance of paths
        """
        point_to, dist_to, visited = {}, {}, {}
        for point_idx in adjacent.keys():
            dist_to[point_idx] = float('inf') if point_idx != point else 0
        while dist_to:
            closest_point = min(dist_to, key=dist_to.get)
            for point_idx, line_idx in adjacent[closest_point].items():
                if point_idx not in visited:
                    new_dist = dist_to[closest_point] + self.lines[line_idx]['length']
                    if new_dist < dist_to[point_idx]:
                        dist_to[point_idx] = new_dist
                        point_to[point_idx] = closest_point
            visited[closest_point] = dist_to[closest_point]
            dist_to.pop(closest_point)
        return point_to, visited

    def move_trains(self):
        """Moves trains over their rotes."""
        player_trains = [train for train in self.trains.values()
                         if train['player_idx'] == self.player_idx and train['cooldown'] == 0]
        for train in player_trains:
            idx, line_idx, position, speed = train['idx'], train['line_idx'], train['position'], train['speed']
            current_point = self.get_current_point(idx)
            route = self.expected_goods[idx]['route']
            length = self.lines[line_idx]['length']
            occupied_lines = {}
            for train_idx, coordinates in self.occupied.items():
                if train_idx == idx:
                    continue
                if self.trains[train_idx]['player_idx'] == self.player_idx:
                    future_position = coordinates['position']
                else:
                    future_position = coordinates['position'] + self.trains[train_idx]['speed']
                if coordinates['line_idx'] not in occupied_lines.keys():
                    occupied_lines[coordinates['line_idx']] = set()
                occupied_lines[coordinates['line_idx']].add(future_position)

            if position == 0 or position == length:
                if route is None or route[-1] != self.town['point_idx']:
                    self.goods_manager(train)
                    route = self.expected_goods[idx]['route']
                if len(route) > 1:
                    route_point = route.index(current_point)
                    line_idx = self.adjacent[route[route_point]][route[route_point + 1]]
                    length = self.lines[line_idx]['length']
                    speed = 1 if current_point == self.lines[line_idx]['points'][0] else -1
                    position = speed if speed == 1 else length + speed
                else:
                    continue
            else:
                position += speed
            if line_idx in occupied_lines.keys() and position in occupied_lines[line_idx]:
                line_idx, position = train['line_idx'], train['position']
                self.client.move_train(line_idx, 0, idx)
            else:
                if train['speed'] == 0:
                    self.client.move_train(line_idx, speed, idx)
            self.occupied[idx]['line_idx'] = line_idx
            self.occupied[idx]['position'] = position

    def get_current_point(self, train_idx):
        """Returns the current point of the train.

        :param train_idx: int - train index
        :return: int - current point index
        """
        line = self.trains[train_idx]['line_idx']
        position = self.trains[train_idx]['position']
        speed = self.trains[train_idx]['speed']
        weight = self.lines[line]['length']
        town = self.town['point_idx']
        target = self.expected_goods[train_idx]['route'][-1] if self.expected_goods[train_idx]['route'] else None
        if 0 < position < weight:
            current = self.lines[line]['points'][0] if speed >= 0 else self.lines[line]['points'][1]
        else:
            current = self.lines[line]['points'][0] if position == 0 else self.lines[line]['points'][1]
        if target and current == town and target == town:
            self.expected_goods[train_idx]['type'] = None
            self.expected_goods[train_idx]['route'] = None
        return current

    def get_turn_points(self, point_from, target_point, adjacent):
        """Returns a list of turn points of the shortest way from current point to target point.

        :param point_from: int - point index to build way from
        :param target_point: int - target point index
        :param adjacent: dict - dict of adjacent points
        :return: return: 2-tuple where the first item is a trip length to the target point and the second item
        is a list of turn points
        """
        point_to, trip_to = self.dijkstra_algorithm(point_from, adjacent)
        turn_points = [target_point]
        if target_point != point_from:
            temp_point = target_point
            while point_to[temp_point] != point_from:
                temp_point = point_to[temp_point]
                turn_points.append(temp_point)
            turn_points.append(point_from)
        return trip_to[target_point], list(reversed(turn_points))

    def get_route(self, train_idx, goods_type):
        """Returns 3-tuple of most profitable route characteristics or back to town route characteristics.

        :param train_idx: int - train index
        :param goods_type: int - type of goods to be mined by a train
        :return: tuple - 3-tuple where the first item is a trip length, the second item is an amount of goods to be
        mined during the trip and the third item is a list of turn points
        """
        train = self.trains[train_idx]
        current = self.get_current_point(train_idx)
        if train['goods'] < train['goods_capacity']:
            targets = []
            for idx, post in self.posts.items():
                if post['type'] == goods_type and idx != current:
                    targets.append(post)
            if current in self.posts and self.posts[current]['type'] == goods_type:
                targets.append(self.town)
            max_efficiency, trip, goods, route = -1 * float('inf'), 0, 0, [current]
            for post in targets:
                if train['goods'] == 0:
                    if goods_type == 2:
                        trip_to, points_to = self.get_turn_points(current, post['point_idx'], self.adjacent_no_storages)
                    else:
                        trip_to, points_to = self.get_turn_points(current, post['point_idx'], self.adjacent_no_markets)
                else:
                    trip_to, points_to = self.get_turn_points(current, post['point_idx'], self.adjacent)
                trip_from, points_from = self.get_turn_points(post['point_idx'], self.town['point_idx'], self.adjacent)
                if post != self.town:
                    post_goods = post['product'] if goods_type == 2 else post['armor']
                    post_capacity = post['product_capacity'] if goods_type == 2 else post['armor_capacity']
                    mined = sum([goods['amount'] for goods in self.expected_goods.values()
                                 if goods['trip'] and goods['trip'] < trip_to])
                    replenishment = post_goods + post['replenishment'] * trip_to - mined
                    available_goods = post_capacity if replenishment >= post_capacity else replenishment
                    space = train['goods_capacity'] - train['goods']
                    goods = train['goods_capacity'] if available_goods >= space else train['goods'] + available_goods
                    if goods_type == 2:
                        efficiency = goods - (trip_to + trip_from) * self.town['population']
                    else:
                        efficiency = goods / (trip_to + trip_from)
                else:
                    goods = train['goods']
                    efficiency = goods - (trip_to + trip_from) * self.town['population']
                if efficiency > max_efficiency:
                    max_efficiency = efficiency
                    trip = trip_to + trip_from
                    route = points_to
        else:
            trip, route = self.get_turn_points(current, self.town['point_idx'], self.adjacent)
            goods = self.trains[train_idx]['goods']
        return trip, goods, route

    def goods_manager(self, train):
        """Assigns goods type to be mined by a train.

        :param train: dict - dictionary of train attributes
        :return: None
        """
        if 4 in self.last_events.keys():
            next_refuges = 10 * self.last_events[4]['refugees_number'] + self.last_events[4]['tick'] - self.current_tick
        else:
            next_refuges = float('inf')
        if train['goods'] > 0:
            goods_type = self.expected_goods[train['idx']]['type']
            trip, amount, route = self.get_route(train['idx'], goods_type)
            self.expected_goods[train['idx']] = {'type': goods_type, 'amount': amount, 'trip': trip, 'route': route}
        else:
            product_trip, product, product_route = self.get_route(train['idx'], 2)
            armor_trip, armor, armor_route = self.get_route(train['idx'], 3)
            product_inc, armor_inc = 0, 0
            for idx, expected_goods in self.expected_goods.items():
                if idx == train['idx']:
                    continue
                if expected_goods['type'] == 2 and expected_goods['trip'] <= armor_trip:
                    product_inc += expected_goods['amount']
                if expected_goods['type'] == 3 and expected_goods['trip'] <= armor_trip:
                    armor_inc += expected_goods['amount']
            rest = self.town['product'] + product_inc - (armor_trip + product_trip) * self.town['population']
            total_armor = self.town['armor'] + armor_inc
            if armor > 0 and rest > 0 and total_armor < self.town['armor_capacity'] and next_refuges > armor_trip:
                self.expected_goods[train['idx']] = {'type': 3, 'amount': armor, 'trip': armor_trip,
                                                     'route': armor_route}
            else:
                self.expected_goods[train['idx']] = {'type': 2, 'amount': product, 'trip': product_trip,
                                                     'route': product_route}
