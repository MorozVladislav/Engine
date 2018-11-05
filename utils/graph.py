#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements interface for creating a graph from *.json file describing it."""

from json import load
from os.path import expanduser

import networkx


def default_layout(func):
    """Sets default layout type depending on whether a graph is weighted or not."""

    def wrapped(self, layout=None, **kwargs):
        if layout is None:
            if self.weighted:
                layout = Layouts.KAMADA_KAWAI
            else:
                layout = Layouts.SPRING
        return func(self, layout, **kwargs)
    return wrapped


class Layouts(object):
    """Implements a set of layouts."""

    BIPARTITE = 'BIPARTITE'
    CIRCULAR = 'CIRCULAR'
    KAMADA_KAWAI = 'KAMADA_KAWAI'
    RANDOM = 'RANDOM'
    RESCALE = 'RESCALE'
    SHELL = 'SHELL'
    SPRING = 'SPRING'
    SPECTRAL = 'SPECTRAL'


class Graph(object):
    """Base class for undirected graphs"""

    LAYOUT_MAP = {
        Layouts.BIPARTITE: networkx.bipartite_layout,
        Layouts.CIRCULAR: networkx.circular_layout,
        Layouts.KAMADA_KAWAI: networkx.kamada_kawai_layout,
        Layouts.RANDOM: networkx.random_layout,
        Layouts.RESCALE: networkx.rescale_layout,
        Layouts.SHELL: networkx.shell_layout,
        Layouts.SPRING: networkx.spring_layout,
        Layouts.SPECTRAL: networkx.spectral_layout
    }

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
        self.points = []
        for item in raw_data['points']:
            self.points.append((item['idx'], {'post_idx': item['post_idx']}))
        self.graph.add_nodes_from(self.points)
        self.lines = []
        for item in raw_data['lines']:
            self.lines.append((item['points'][0], item['points'][1], {'idx': item['idx'], 'weight': item['length']}))
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

        coordinates = self.LAYOUT_MAP[layout](self.graph, **kwargs)
        points = self.points
        for point in points:
            point[1]['x'], point[1]['y'] = coordinates[point[0]]
        return points, self.lines
