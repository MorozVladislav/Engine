#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements interface for creating a graph from *.json file describing it."""
from functools import wraps
from json import load, loads
from os.path import expanduser, exists

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

    def __init__(self, source, weighted=False):
        """Deserializes *.json source into four attributes: name, idx, points, lines, and creates graph.

        :param source: string - path to *.json file describing a graph or json string
        :param weighted: boolean - creates weighted graph when True
        :return: None
        """
        self.source = source
        self.weighted = weighted
        self.graph = networkx.Graph()
        if exists(str(self.source)):
            with open(expanduser(self.source)) as input_file:
                raw_data = load(input_file)
        else:
            raw_data = loads(self.source)
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
        :return: 2 dicts; points and lines. Both Dicts has point or line index as a key and a Dict of attributes as a
        value. Point attributes are: x-coordinate, y-coordinate and post idx. Line attributes are: start point,
        end point and weight
        """
        coordinates = layout(self.graph, **kwargs)
        points = {}
        for point in self.points:
            x, y = coordinates[point[0]]
            points[point[0]] = {'x': x, 'y': y, 'post_idx': point[1]['post_idx']}
        lines = {}
        for line in self.lines:
            lines[line[2]['idx']] = {'start_point': line[0], 'end_point': line[1], 'weight': line[2]['weight']}
        return points, lines
