#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements client for communication with game server by it's protocol."""

import socket
from json import dumps, loads
from struct import pack, unpack
from lya import AttrDict
import os


class Response(object):
    """Representation of a server response."""

    _STATUS = {
        0: 'OK',
        1: 'BAD_COMMAND',
        2: 'RESOURCE_NOT_FOUND',
        3: 'ACCESS_DENIED',
        4: 'NOT_READY',
        5: 'TIMEOUT',
        500: 'INTERNAL_SERVER_ERROR'
    }

    def __init__(self, status, length, data):
        """Creates an object representing server response.

        :param status: int - response status
        :param length: int - response body length
        :param data: str - response body in JASON format
        """
        self.status = self._STATUS[status]
        self.length = length
        self.data = loads(data) if data != '' else ''


class Client(object):
    """Game server client main class."""

    DEFAULTS = 'default_settings.yaml'

    def __init__(self, host=None, port=None):
        """Initiates client. If whether host or port is None assigns default value from default_settings.yaml.

        :param host: str - server hostname or IP address
        :param port: int - port
        """
        with open(os.path.expanduser(self.DEFAULTS), 'r') as cfg:
            defaults = AttrDict.from_yaml(cfg)
        host = host if host is not None else defaults.host
        port = port if port is not None else defaults.port
        self.username = None if defaults.username is None else defaults.username
        self.password = None if defaults.password is None else defaults.password
        self.address = (host, port)
        self.connection = None

    def send(self, action, body=None):
        """Prepares request and sends it

        :param action: int - action ID
        :param body: dict - request body
        :return: None
        """
        if body is None:
            request = pack('<i', action) + pack('<i', 0)
        else:
            data = dumps(body)
            request = pack('<i', action) + pack('<i', len(data)) + data
        self.connection.sendall(request)

    def receive(self):
        """Receives server response.

        :return: Response instance
        """
        status = unpack('<i', self.connection.recv(4))[0]
        length = unpack('<i', self.connection.recv(4))[0]
        data = ''
        while len(data) < length:
            chunk = self.connection.recv(length)
            data += chunk
        return Response(status, length, data)

    def login(self, name, password=None, num_players=None, game=None):
        """Sends LOGIN request and receives response. If name is missing throws UsernameMissing exception.

        :param name: str - player's name
        :param password: str - player’s password used to verify the connection, if player with the same name tries to
        connect with another password - login will be rejected
        :param num_players: int - number of players in the game
        :param game: str - game’s name
        :return: Response instance
        """
        name = name if name is not None else self.username
        password = password if password is not None else self.password
        if name is None:
            raise UsernameMissing('username is missing')
        self.connection = socket.create_connection(self.address)
        body = {'name': name}
        if password is not None:
            body['password'] = password
        if num_players is not None:
            body['num_players'] = num_players
        if game is not None:
            body['game'] = game
        self.send(1, body)
        return self.receive()

    def logout(self):
        """Sends LOGOUT request and receives response.

        :return: Response instance
        """
        self.send(2)
        response = self.receive()
        self.connection.close()
        return response

    def move_train(self, line_idx, speed, train_idx):
        """Sends MOVE request and receives response.

        :param line_idx: int - index of the line where the train should be placed on next turn
        :param speed: int - speed of the train, possible values: 0 - the train will be stopped; 1 - the train will move
        in positive direction; -1 - the train will move in negative direction
        :param train_idx: int - index of the train
        :return: Response instance
        """
        self.send(3, {'line_idx': line_idx, 'speed': speed, 'train_idx': train_idx})
        return self.receive()

    def upgrade(self, posts=None, trains=None):
        """Sends UPGRADE request and receives response.

        :param posts: list - list with indexes of posts to upgrade
        :param trains: list - list with indexes of trains to upgrade
        :return: Response instance
        """
        posts = posts if posts is not None else []
        trains = trains if trains is not None else []
        self.send(4, {'posts': posts, 'trains': trains})
        return self.receive()

    def turn(self):
        """Sends TURN request and receives response. The request forces next turn of the game.

        :return: Response instance
        """
        self.send(5)
        return self.receive()

    def player(self):
        """Sends PLAYER request and receives response.

        :return: Response instance
        """
        self.send(6)
        return self.receive()

    def get_static_objects(self):
        """Sends MAP request for static objects and receives response.

        :return: Response instance
        """
        self.send(10, {'layer': 0})
        return self.receive()

    def get_dynamic_objects(self):
        """Sends MAP request for dynamic objects and receives response.

        :return: Response instance
        """
        self.send(10, {'layer': 1})
        return self.receive()

    def get_point_coordinates(self):
        """Sends MAP request for point coordinates and receives response.

        :return: Response instance
        """
        self.send(10, {'layer': 10})
        return self.receive()


class GameClientException(Exception):
    """Parent class for all Client exceptions."""

    pass


class UsernameMissing(GameClientException):
    """Missing username exception class."""

    pass
