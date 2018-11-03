#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from json import load
from os.path import expanduser

import networkx


class Layouts(object):
    BIPARTITE = 'BIPARTITE'
    CIRCULAR = 'CIRCULAR'
    KAMADA_KAWAI = 'KAMADA_KAWAI'
    RANDOM = 'RANDOM'
    RESCALE = 'RESCALE'
    SHELL = 'SHELL'
    SPRING = 'SPRING'
    SPECTRAL = 'SPECTRAL'


class Graph(object):

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

    def __init__(self, path):
        self.path = path
        self.graph = networkx.Graph()
        with open(expanduser(self.path)) as input_file:
            raw_data = load(input_file)
        self.name = raw_data['name']
        self.idx = raw_data['idx']
        self.points = []
        for item in raw_data['points']:
            self.points.append((item['idx'], {'post_idx': item['post_idx']}))
        self.lines = []
        for item in raw_data['lines']:
            self.lines.append((item['points'][0], item['points'][1], {'idx': item['idx'], 'weight': item['length']}))
        self.graph.add_nodes_from(self.points)
        self.graph.add_edges_from(self.lines)

    def get_coordinates(self, layout=Layouts.SPRING, **kwargs):
        coordinates = self.LAYOUT_MAP[layout](self.graph, **kwargs)
        points = self.points
        for point in points:
            point[1]['x'], point[1]['y'] = coordinates[point[0]]
        return points, self.lines
