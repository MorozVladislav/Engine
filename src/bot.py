#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements bot of the game."""


class Bot(object):
    """The application main class."""

    def __init__(self, app):
        """Initiates bot.

        :param app: instance - app.py
        """
        self.app = app
        self.points = None
        self.lines = None
        self.posts = None
        self.trains = None
        self.client = None
        self.game = None

    def start_game(self):
        """Start bot."""
        self.game = True
        self.points = self.app.points
        self.lines = self.app.lines
        self.posts = self.app.posts
        self.trains = self.app.trains
        self.client = self.app.client
        self.create_list_adjacency()
        while self.game:
            self.move_train(1, 19)
            self.move_train(1, 16)
            self.move_train(1, 13)

    def end_game(self):
        """Closes bot."""
        self.game = False

    def create_list_adjacency(self):
        """Creates adjacency list of the graph."""
        for point in self.points:
            self.points[point]['neighbourhood'] = {}

        for line in self.lines:
            self.points[self.lines[line]['start_point']]['neighbourhood'][self.lines[line]['end_point']] = line
            self.points[self.lines[line]['end_point']]['neighbourhood'][self.lines[line]['start_point']] = line

    def dijkstra_algorithm(self, main_edge, list_adjacency):
        """Finds the shortest paths from the main edge of the graph to all other vertices.

        :param main_edge: int - main edge
        :param list_adjacency: int - adjacency list of the graph
        :return: dictionary of shortest paths
        """
        edgeTo = {}
        distTo = {}
        visited = {}

        for point in list_adjacency:
            distTo[point] = float('inf') if point != main_edge else 0

        while distTo:
            min_edge = min(distTo, key=distTo.get)

            for neighbour in list_adjacency[min_edge]['neighbourhood']:
                if neighbour not in visited:

                    new_dist = distTo[min_edge] + self.lines[list_adjacency[min_edge]['neighbourhood'][neighbour]][
                        'weight']
                    if new_dist < distTo[neighbour]:
                        distTo[neighbour] = new_dist
                        edgeTo[neighbour] = min_edge

            visited[min_edge] = distTo[min_edge]
            distTo.pop(min_edge)

        return edgeTo

    def move_train(self, idx, target_point):
        """Move train from current point to target point.

        :param idx: int - idx train
        :param target_point: int - target point of the movement
        :return: None
        """
        current_point = self.train_current_point(idx)
        edgeTo = self.dijkstra_algorithm(current_point, self.points)

        while target_point != current_point:

            if edgeTo[target_point] != current_point:
                temp_point = edgeTo[target_point]
                while edgeTo[temp_point] != current_point:
                    temp_point = edgeTo[temp_point]
            else:
                temp_point = target_point

            temp_line = self.points[current_point]['neighbourhood'][temp_point]
            way = self.lines[self.points[current_point]['neighbourhood'][temp_point]]['weight']
            for _ in xrange(way):
                self.client.move_train(temp_line, self.train_direction(temp_line, current_point), idx)
                self.app.tick()

            self.refresh_dynamic_obj()
            current_point = self.train_current_point(idx)

    def refresh_dynamic_obj(self):
        """Refresh dynamic objects."""
        self.posts = self.app.posts
        self.trains = self.app.trains

    def train_current_point(self, idx):
        """Find current point of the train.

        :param idx: int - idx train
        :return: int - current point
        """
        current_line = self.trains[idx]['line_idx']
        if self.trains[idx]['position'] == 0:
            current_point = self.lines[current_line]['start_point']
        else:
            current_point = self.lines[current_line]['end_point']
        return current_point

    def train_direction(self, current_line, current_point):
        """Calculates direction.

        :param current_line: int - current train line
        :param current_point: int - current train point
        :return: int - direction
        """
        if current_point == self.lines[current_line]['start_point']:
            direction = 1
        else:
            direction = -1

        return direction
