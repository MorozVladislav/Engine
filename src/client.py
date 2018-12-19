#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The module implements client for communication with game server by it's protocol."""
import socket
from functools import wraps
from json import dumps, loads
from struct import pack, unpack


def connection(func):
    """Checks the connection to be created before request.

    :param func: function - function that calls Client methods
    :return: wrapped function
    """
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        if self.connection is None:
            raise ConnectionNotEstablished('connection is not established')
        return func(self, *args, **kwargs)

    return wrapped


class Response(object):
    """Representation of a server response."""
    STATUS = {
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
        self.status = self.STATUS[status]
        self.length = length
        self.data = data if data != '' else ''


class Client(object):
    """Game server client main class."""

    def __init__(self, host=None, port=None, timeout=None, username=None, password=None):
        """Initiates client.

        :param host: str - server hostname or IP address
        :param port: int - port
        :param timeout: int - socket timeout
        :param username: string - username
        :param password: string - password
        """
        self.host, self.port, self.timeout, self.username, self.password = host, port, timeout, username, password
        self.connection = None

    def connect(self):
        """Creates connection with game server. If host or port are None raises corresponding exceptions."""
        if self.host is None:
            raise HostMissing('host is missing')
        if self.port is None:
            raise PortMissing('port is missing')
        self.connection = socket.create_connection((self.host, self.port), self.timeout)

    def close_connection(self):
        """Closes connection if it is opened."""
        if self.connection:
            self.connection.close()

    @connection
    def send(self, action, body=None):
        """Prepares request and sends it.

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

    @connection
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
        if status != 0:
            message = loads(data)['error'] if data != '' else ''
            raise BadServerResponse('{} {}'.format(Response.STATUS[status], message))
        return Response(status, length, data)

    def login(self, name=None, password=None, game=None, num_players=None, num_turns=None):
        """Sends LOGIN request and receives response. If name is missing throws UsernameMissing exception.

        :param name: str - player's name
        :param password: str - player’s password used to verify the connection, if player with the same name tries to
        connect with another password - login will be rejected
        :param game: str - game’s name
        :param num_players: int - number of players in the game
        :param num_turns: int - number of turns of the game (game duration)
        :return: Response instance
        """
        name = name if name is not None else self.username
        password = password if password is not None else self.password
        if name is None:
            raise UsernameMissing('username is missing')
        body = {'name': name}
        if password is not None:
            body['password'] = password
        if game is not None:
            body['game'] = game
        if num_players is not None:
            body['num_players'] = num_players
        if num_turns is not None:
            body['num_turns'] = num_turns
        self.send(1, body)
        return self.receive()

    def logout(self):
        """Sends LOGOUT request and receives response.

        :return: Response instance
        """
        self.send(2)
        self.connection.close()

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

    def games(self):
        """Sends GAMES request and receives response.

        :return: Response instance
        """
        self.send(7)
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


class ClientException(Exception):
    """Parent class for all Client exceptions."""
    pass


class ConnectionNotEstablished(ClientException):
    """Connection not established exception class."""
    pass


class HostMissing(ClientException):
    """Missing host exception class."""
    pass


class PortMissing(ClientException):
    """Missing port exception class."""
    pass


class UsernameMissing(ClientException):
    """Missing username exception class."""
    pass


class BadServerResponse(ClientException):
    """Bad server response exception class."""
    pass
