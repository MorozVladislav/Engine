#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements interface for creating a graph from *.json file describing it."""
from json import load
from os.path import expanduser
from functools import wraps

import networkx
from attrdict import AttrDict


def default_layout(func):
    """Sets default layout type depending on whether a graph is weighted or not.

    :param func: function - function that provides coordinates for building a graph
    :return: wrapped function
    """
    @wraps(func)
    def wrapped(self, layout=None, **kwargs):
        if layout is None:
            if self.weighted:
                layout = self.LAYOUTS.KAMADA_KAWAI
            else:
                layout = self.LAYOUTS.SPRING
        return func(self, layout, **kwargs)

    return wrapped


class Graph(object):
    """Base class for undirected graphs"""
    LAYOUTS = AttrDict({
        'BIPARTITE': networkx.bipartite_layout,
        'CIRCULAR': networkx.circular_layout,
        'KAMADA_KAWAI': networkx.kamada_kawai_layout,
        'RANDOM': networkx.random_layout,
        'RESCALE': networkx.rescale_layout,
        'SHELL': networkx.shell_layout,
        'SPRING': networkx.spring_layout,
        'SPECTRAL': networkx.spectral_layout
    })

    def __init__(self, path, weighted=False):
        """Deserializes *.json file into four attributes: name, idx, points, lines, and creates graph.

        :param path: string - path to *.json file describing a graph
        :param weighted: boolean - creates weighted graph when True
        :return: None
        """
        self.path = path
        self.weighted = weighted
        self.graph = networkx.Graph()
        with open(expanduser(self.path)) as input_file:
            raw_data = load(input_file)
        self.name = raw_data['name']
        self.idx = raw_data['idx']
        self.points = [(item['idx'], {'post_idx': item['post_idx']}) for item in raw_data['points']]
        self.graph.add_nodes_from(self.points)
        self.lines = [(item['points'][0], item['points'][1],
                       {'idx': item['idx'], 'weight': item['length']}) for item in raw_data['lines']]
        if self.weighted:
            weighted_lines = [(line[0], line[1], line[2]['weight']) for line in self.lines]
            self.graph.add_weighted_edges_from(weighted_lines)
        else:
            self.graph.add_edges_from(self.lines)

    @default_layout
    def get_coordinates(self, layout, **kwargs):
        """Calculates coordinates for building a graph.

        :param layout: string - graph layout type. Default layout is provided by @default_layout decorator
        :param kwargs: dict - keyword arguments of networkx layout methods
        :return: 2-tuple of lists; points and lines. The first one is a List of tuples where each tuple denotes separate
        point. Each point is represented by two values which are point idx and a dict of point attributes including
        point coordinates with keys 'x' and 'y'. The second one is a List of tuples where each tuple denotes
        separate line. Each line is represented by three values which are two idxs of points which are connected
        with the line and a dict of line attributes including line weight with the key 'weight'
        """
        coordinates = layout(self.graph, **kwargs)
        points = self.points
        for point in points:
            point[1]['x'], point[1]['y'] = coordinates[point[0]]
        return points, self.lines
