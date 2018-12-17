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
        self.markets = []
        self.storages = []
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
        self.current_tick = 0
        self.last_events, self.expected_goods = {}, {}
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
        if not self.markets or not self.storages:
            self.markets = [idx for idx, attrs in self.posts.items() if attrs['type'] == 2]
            self.storages = [idx for idx, attrs in self.posts.items() if attrs['type'] == 3]
            self.adjacent_no_markets = self.get_adjacent(exclude_points=self.markets)
            self.adjacent_no_storages = self.get_adjacent(exclude_points=self.storages)
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
                self.upgrade()
                self.tick()
            self.logout()
        except Exception as exc:
            self.queue.put((99, exc))
            raise exc

    def stop(self):
        """Stops bot."""
        self.started = False

    def get_adjacent(self, exclude_points=None, exclude_lines=None):
        """Returns new dict of adjacent points. Excludes points and lines from exclude_point and exclude_line lists.

        :param exclude_points: list - points to be excluded from adjacent dict
        :param exclude_lines: list - lines to be excluded from adjacent dict
        :return: dict - dict of adjacent points
        """
        if not exclude_lines and not exclude_points and self.adjacent:
            adjacent = self.adjacent
        elif exclude_points == self.markets and not exclude_lines and self.adjacent_no_markets:
            adjacent = self.adjacent_no_markets
        elif exclude_points == self.storages and not exclude_lines and self.adjacent_no_storages:
            adjacent = self.adjacent_no_storages
        else:
            adjacent = {}
            for idx, attrs in self.lines.items():
                if exclude_lines and idx in exclude_lines:
                    continue
                start_point, end_point = attrs['points'][0], attrs['points'][1]
                if exclude_points and (start_point in exclude_points or end_point in exclude_points):
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
        """Moves trains over their rotes and checks if a collision can occur in next move position."""
        player_trains = [train for train in self.trains.values()
                         if train['player_idx'] == self.player_idx and train['cooldown'] == 0]
        for train in player_trains:
            idx, line_idx, position, speed = train['idx'], train['line_idx'], train['position'], train['speed']
            if position == 0 or position == self.lines[line_idx]['length'] or speed == 0:
                line_idx, position, speed = self.get_direction(idx)
            else:
                position += speed
            line_idx, position, speed = self.check_collision(idx, line_idx, position, speed)
            self.client.move_train(line_idx, speed, idx)
            self.occupied[idx]['line_idx'] = line_idx
            self.occupied[idx]['position'] = position

    def get_current_point(self, train_idx):
        """Returns the current point of the train.

        :param train_idx: int - train index
        :return: int - current point index
        """
        line_idx = self.trains[train_idx]['line_idx']
        position = self.trains[train_idx]['position']
        line_length = self.lines[line_idx]['length']
        town = self.town['point_idx']
        target = self.expected_goods[train_idx]['route'][-1] if self.expected_goods[train_idx]['route'] else None
        if 0 < position < line_length:
            route = self.expected_goods[train_idx]['route']
            start_point, end_point = self.lines[line_idx]['points'][0], self.lines[line_idx]['points'][1]
            current = route[min(route.index(start_point), route.index(end_point))]
        else:
            current = self.lines[line_idx]['points'][0] if position == 0 else self.lines[line_idx]['points'][1]
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

    def get_route(self, train_idx, goods_type, exclude_points=None, exclude_lines=None):
        """Returns 3-tuple of most profitable route characteristics or back-to-town route characteristics.

        Returns 3-tuple of None if there is no route from current point.
        :param train_idx: int - train index
        :param goods_type: int - type of goods to be mined by a train
        :param exclude_points: list - points to be excluded from route, default is None
        :param exclude_lines: list - lines to be avoided when calculating a route, default is None
        :return: tuple - 3-tuple where the first item is a trip length, the second item is an amount of goods to be
        mined during the trip and the third item is a list of turn points
        """
        exclude_points = exclude_points if exclude_points else []
        exclude_lines = exclude_lines if exclude_lines else []
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
            if train['goods'] == 0:
                if goods_type == 2:
                    adjacent = self.get_adjacent(exclude_points=self.storages + exclude_points,
                                                 exclude_lines=exclude_lines)
                else:
                    adjacent = self.get_adjacent(exclude_points=self.markets + exclude_points,
                                                 exclude_lines=exclude_lines)
            else:
                adjacent = self.get_adjacent(exclude_points=exclude_points, exclude_lines=exclude_lines)
            for post in targets:
                if current in adjacent.keys():
                    trip_to, points_to = self.get_turn_points(current, post['point_idx'], adjacent)
                else:
                    return None, None, None
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
            adjacent = self.get_adjacent(exclude_points=exclude_points, exclude_lines=exclude_lines)
            trip, route = self.get_turn_points(current, self.town['point_idx'], adjacent)
            goods = self.trains[train_idx]['goods']
        current_line_idx = self.trains[train_idx]['line_idx']
        start_point, end_point = self.lines[current_line_idx]['points'][0], self.lines[current_line_idx]['points'][1]
        route = [start_point] + route if start_point not in route else route
        route = [end_point] + route if end_point not in route else route
        return trip, goods, route

    def get_direction(self, train_idx, exclude_points=None, exclude_lines=None):
        """Returns new train moving attributes. Excludes points from exclude_points and lines from exclude_lines.

        If a route is empty or has only one point - returns current train line index and position with speed 0.
        :param train_idx: train_idx: int - train index
        :param exclude_points: list - points to be excluded when calculating a direction, default is None
        :param exclude_lines: list - lines to be excluded when calculating a direction, default is None
        :return: tuple - 3-tuple: line_idx, position, speed. line_idx: int - line index, position: int - position
        within the line, speed: int - speed value
        """
        position = self.trains[train_idx]['position']
        line_length = self.lines[self.trains[train_idx]['line_idx']]['length']
        self.goods_manager(train_idx, exclude_points=exclude_points, exclude_lines=exclude_lines)
        route = self.expected_goods[train_idx]['route']
        if route and len(route) > 1:
            current_point = self.get_current_point(train_idx)
            route_point = route.index(current_point)
            line_idx = self.adjacent[route[route_point]][route[route_point + 1]]
            speed = 1 if current_point == self.lines[line_idx]['points'][0] else -1
            if position == 0 or position == line_length:
                position = 1 if speed == 1 else self.lines[line_idx]['length'] - 1
            else:
                position = position + speed
        else:
            line_idx = self.trains[train_idx]['line_idx']
            position = self.trains[train_idx]['position']
            speed = 0
        return line_idx, position, speed

    def check_collision(self, train_idx, line_idx, position, speed):
        """Returns a new direction for a train if there might be collision in the next position.

        :param train_idx: train_idx: int - train index
        :param line_idx: int - line index
        :param position: int - position within the line
        :param speed: int - speed value
        :return: tuple - 3-tuple: line_idx, position, speed. line_idx: int - line index, position: int - position
        within the line, speed: int - speed value
        """
        current_line_idx, current_position = self.trains[train_idx]['line_idx'], self.trains[train_idx]['position']
        occupied_lines, occupied_points = {}, []
        for idx, coordinates in self.occupied.items():
            start_point = self.lines[coordinates['line_idx']]['points'][0]
            end_point = self.lines[coordinates['line_idx']]['points'][1]
            length = self.lines[coordinates['line_idx']]['length']
            if idx == train_idx:
                continue
            if self.trains[train_idx]['player_idx'] == self.player_idx:
                future_position = coordinates['position']
            else:
                future_position = coordinates['position'] + self.trains[train_idx]['speed']
            if start_point in self.posts.keys() and self.posts[start_point]['type'] == 1 and future_position == 0:
                continue
            if end_point in self.posts.keys() and self.posts[end_point]['type'] == 1 and future_position == length:
                continue
            if coordinates['line_idx'] not in occupied_lines.keys():
                occupied_lines[coordinates['line_idx']] = set()
            occupied_lines[coordinates['line_idx']].add(future_position)
            if future_position == 0:
                occupied_points.append(start_point)
            if future_position == length:
                occupied_points.append(end_point)
        if position == 0 or position == self.lines[line_idx]['length']:
            point = self.lines[line_idx]['points'][0] if position == 0 else self.lines[line_idx]['points'][1]
        else:
            point = None
        if line_idx in occupied_lines.keys() and position in occupied_lines[line_idx] and not point:
            if current_position == 0 or current_position == self.lines[current_line_idx]['length']:
                busy_lines = [line_idx]
                while line_idx in occupied_lines.keys() and position in occupied_lines[line_idx]:
                    line_idx, position, speed = self.get_direction(train_idx, exclude_lines=busy_lines)
                    busy_lines.append(line_idx)
            else:
                line_idx, position, speed = current_line_idx, current_position, 0
        if point in occupied_points:
            line_idx, position, speed = current_line_idx, current_position, 0
        return line_idx, position, speed

    def goods_manager(self, train_idx, exclude_points=None, exclude_lines=None):
        """Assigns goods type to be mined by a train.

        :param train_idx: int - train index
        :param exclude_points: list - points to be excluded from route, default is None
        :param exclude_lines: list - lines to be excluded from route, default is None
        :return: None
        """
        if self.trains[train_idx]['goods'] > 0 and self.expected_goods[train_idx]['type']:
            goods_type = self.expected_goods[train_idx]['type']
            trip, amount, route = self.get_route(train_idx, goods_type, exclude_points=exclude_points,
                                                 exclude_lines=exclude_lines)
            if trip and amount and route:
                self.expected_goods[train_idx] = {'type': goods_type, 'amount': amount, 'trip': trip, 'route': route}
            else:
                self.expected_goods[train_idx] = {'type': None, 'amount': None, 'trip': None, 'route': None}
        else:
            product_trip, product, product_route = self.get_route(train_idx, 2, exclude_points=exclude_points,
                                                                  exclude_lines=exclude_lines)
            armor_trip, armor, armor_route = self.get_route(train_idx, 3, exclude_points=exclude_points,
                                                            exclude_lines=exclude_lines)
            if product_trip and product and product_route and armor_trip and armor and armor_route:
                with_armor, with_product = 0, 0
                for attributes in self.expected_goods.values():
                    if attributes['type'] == 2:
                        with_product += 1
                    else:
                        with_armor += 1
                if with_product > 2 * with_armor:
                    self.expected_goods[train_idx] = {'type': 3, 'amount': armor, 'trip': armor_trip,
                                                      'route': armor_route}
                else:
                    self.expected_goods[train_idx] = {'type': 2, 'amount': product, 'trip': product_trip,
                                                      'route': product_route}
            else:
                self.expected_goods[train_idx] = {'type': None, 'amount': None, 'trip': None, 'route': None}

    def upgrade(self):
        """Upgrades trains and town."""
        trains, towns = [], []
        available_armor = self.town['armor'] * 0.5
        trains_to_upgrade = []
        for idx, coordinates in self.occupied.items():
            line = self.lines[coordinates['line_idx']]
            if line['points'][0] == self.town['point_idx'] and coordinates['position'] == 0:
                trains_to_upgrade.append(idx)
            if line['points'][0] == self.town['point_idx'] and coordinates['position'] == line['length']:
                trains_to_upgrade.append(idx)
        for idx in trains_to_upgrade:
            if self.trains[idx]['next_level_price'] and self.trains[idx]['next_level_price'] <= available_armor:
                trains.append(idx)
                available_armor -= self.trains[idx]['next_level_price']
        if not trains_to_upgrade and self.town['next_level_price'] and self.town['next_level_price'] <= available_armor:
            towns.append(self.town['idx'])
            available_armor -= self.town['next_level_price']
        self.client.upgrade(towns, trains)
