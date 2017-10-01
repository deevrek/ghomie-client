# Copyright 2016 Mycroft AI, Inc.
#
# This file is part of Mycroft Core.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mycroft Core.  If not, see <http://www.gnu.org/licenses/>.


import json
import time
from multiprocessing.pool import ThreadPool

from pyee import EventEmitter
from websocket import WebSocketApp

#from ghomie.configuration import ConfigurationManager
from messagebus.message import Message
#from mycroft.util import validate_param
#from mycroft.util.log import getLogger

__author__ = 'seanfitz', 'jdorleans'

#LOG = getLogger(__name__)


class WebsocketClient(object):
    def __init__(self, url):
        self.url=url
        self.emitter = EventEmitter()
        self.client = self.create_client()
        self.pool = ThreadPool(10)
        self.retry = 5

    def create_client(self):
        return WebSocketApp(self.url,
                            on_open=self.on_open, on_close=self.on_close,
                            on_error=self.on_error, on_message=self.on_message)

    def on_open(self, ws):
        self.emitter.emit("open")
        # Restore reconnect timer to 5 seconds on sucessful connect
        self.retry = 5

    def on_close(self, ws):
        self.emitter.emit("close")

    def on_error(self, ws, error):
        try:
            self.emitter.emit('error', error)
            self.client.close()
        except Exception as e:
            print(repr(e))
        print("WS Client will reconnect in %d seconds." % self.retry)
        time.sleep(self.retry)
        self.retry = min(self.retry * 2, 60)
        self.client = self.create_client()
        self.run_forever()

    def on_message(self, ws, message):
        self.emitter.emit('message', message)
        parsed_message = Message.deserialize(message)
        self.pool.apply_async(
            self.emitter.emit, (parsed_message.type, parsed_message))

    def emit(self, message):
        if (not self.client or not self.client.sock or
                not self.client.sock.connected):
            return
        if hasattr(message, 'serialize'):
            self.client.send(message.serialize())
        else:
            self.client.send(json.dumps(message.__dict__))

    def on(self, event_name, func):
        self.emitter.on(event_name, func)

    def once(self, event_name, func):
        self.emitter.once(event_name, func)

    def remove(self, event_name, func):
        self.emitter.remove_listener(event_name, func)

    def remove_all_listeners(self, event_name):
        '''
            Remove all listeners connected to event_name.

            Args:
                event_name: event from which to remove listeners
        '''
        if event_name is None:
            raise ValueError
        self.emitter.remove_all_listeners(event_name)

    def run_forever(self):
        self.client.run_forever()

    def close(self):
        self.client.close()


def echo():
    ws = WebsocketClient('ws://192.168.1.70:8181/core')

    def echo(message):
        print(message)

    def repeat_utterance(message):
        print("repeat")
        message.type = 'respeak'
        ws.emit(message)
    #ws.on('message', echo)
    ws.on('fuffa', repeat_utterance)
    ws.run_forever()


if __name__ == "__main__":
    echo()
