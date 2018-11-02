#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from json import load
from os.path import expanduser

import networkx


class Graph(object):

    def __init__(self, path=None):
        self.file = path
        self.name = None
        self.idx = None
        self.points = None
        self.lines = None
        self.graph = None

    def deserialize_data(self):
        if self.file is None:
            raise EmptyPath('Path is not specified')
        with open(expanduser(self.file)) as input_file:
            raw_data = load(input_file)
        self.name = raw_data['name']
        self.idx = raw_data['idx']
        self.points = [(item['idx'], {'post_idx': item['post_idx']}) for item in raw_data['points']]
        self.lines = [(item['points'][0], item['points'][1],
                       {'idx': item['idx'], 'weight': item['length']}) for item in raw_data['lines']]
        return self.points, self.lines

    def build(self, layout='spring', **kwargs):
        layouts = {
            'bipartite': networkx.bipartite_layout,
            'circular': networkx.circular_layout,
            'kamada_kawai': networkx.kamada_kawai_layout,
            'random': networkx.random_layout,
            'rescale': networkx.rescale_layout,
            'shell': networkx.shell_layout,
            'spring': networkx.spring_layout,
            'spectral': networkx.spectral_layout
        }
        self.deserialize_data()
        self.graph = networkx.Graph()
        self.graph.add_nodes_from(self.points)
        self.graph.add_edges_from(self.lines)
        try:
            coordinates = layouts[layout](self.graph, **kwargs)
        except KeyError:
            raise UnknownLayout('Unknown layout')
        for point in self.points:
            point[1]['x'], point[1]['y'] = coordinates[point[0]]
        return self.points, self.lines


class GraphException(Exception):
    pass


class UnknownLayout(GraphException):
    pass


class EmptyPath(GraphException):
    pass


if __name__ == '__main__':
    pass
