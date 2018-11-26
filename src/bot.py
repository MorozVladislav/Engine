#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements bot for playing the game."""


class Bot(object):
    """The bot main class."""

    def __init__(self, app):
        """Initiates bot and creates adjacency list.

        :param app: instance - Application instance
        """
        self.app = app
        self.started = None
        self.adjacencies = {}

    def start(self):
        """Starts bot."""
        self.started = True
        while self.started:
            self.move_train(1, 19)
            self.move_train(1, 16)
            self.move_train(1, 13)

    def stop(self):
        """Stops bot."""
        self.started = False

    def create_adjacency_list(self):
        """Creates dict of adjacencies."""
        for idx, attrs in self.app.lines.items():
            start_point = attrs['start_point']
            end_point = attrs['start_point']
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
        edge_to, dist_to, visited = {}, {}, {}
        for point_idx in self.adjacencies.keys():
            dist_to[point_idx] = float('inf') if point_idx != point else 0
        while dist_to:
            closest_point = min(dist_to, key=dist_to.get)
            for point_idx, line_idx in self.adjacencies[closest_point].items():
                if point_idx not in visited:
                    new_dist = dist_to[closest_point] + self.app.lines[line_idx]['weight']
                    if new_dist < dist_to[point_idx]:
                        dist_to[point_idx] = new_dist
                        edge_to[point_idx] = closest_point
            visited[closest_point] = dist_to[closest_point]
            dist_to.pop(closest_point)
        return edge_to

    def move_train(self, idx, target_point):
        """Moves train from current point to target point.

        :param idx: int - train index
        :param target_point: int - target point index
        :return: None
        """
        current_point = self.train_current_point(idx)
        edge_to = self.dijkstra_algorithm(current_point)
        while target_point != current_point:
            if edge_to[target_point] != current_point:
                temp_point = edge_to[target_point]
                while edge_to[temp_point] != current_point:
                    temp_point = edge_to[temp_point]
            else:
                temp_point = target_point
            temp_line = self.app.points[current_point]['neighbours'][temp_point]
            way = self.app.lines[self.app.points[current_point]['neighbours'][temp_point]]['weight']
            for _ in xrange(way):
                direction = 1 if current_point == self.app.lines[temp_line]['start_point'] else -1
                self.app.client.move_train(temp_line, direction, idx)
                self.app.tick()
            self.app.refresh_map()
            current_point = self.train_current_point(idx)

    def train_current_point(self, idx):
        """Returns the current point of the train.

        :param idx: int - train index
        :return: int - current point index
        """
        current_line = self.app.trains[idx]['line_idx']
        if self.app.trains[idx]['position'] == 0:
            current_point = self.app.lines[current_line]['start_point']
        else:
            current_point = self.app.lines[current_line]['end_point']
        return current_point
