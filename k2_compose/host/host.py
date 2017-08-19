#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from docker import DockerClient as Client
import socket

from ..k2cutils.basenode import Node
from ..common.common import HOST_CONNECT, HOST_DISCONNECT, HOST_STATUS, COLOR_HOST, DOCKER_API_VERSION
socket.setdefaulttimeout(3)


def host_connect(host_instance=None):
    if not isinstance(host_instance, Host):
        return
    if is_open(host_instance.metadata['dockerHost']):
        for i in range(3):
            try:
                result = host_instance.client.ping()
            except Exception as e:
                continue
            if result:
                host_instance.status_code = HOST_CONNECT
                break
            else:
                if i == 2:
                    logging.error('[%s: %s] connect error.' % (
                        host_instance.id, host_instance.metadata['dockerHost']))
    else:
        host_instance.status_code = HOST_DISCONNECT
    host_instance.status = HOST_STATUS[host_instance.status_code]
    host_instance.color = COLOR_HOST[host_instance.status_code]


def is_open(docker_host):
    if docker_host.startswith("unix://"):
        docker_host=docker_host.replace('unix://', '')
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        for i in range(3):
            try:
                s.connect(docker_host)
                s.shutdown(2)
            except Exception as e:
                if i == 2:
                    return False
                continue
            else:
                return True
    else:
        host_ip, host_port = docker_host.split(':')
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for i in range(3):
            try:
                s.connect((host_ip, int(host_port)))
                s.shutdown(2)
            except Exception:
                if i == 2:
                    return False
                continue
            else:
                return True

class Host(Node):
    def __init__(self, id, dockerhost='', status_code=HOST_DISCONNECT):
        Node.__init__(self)
        self.type = 'host'
        self.id = id
        self.status_code = status_code
        self.status = HOST_STATUS[status_code]
        self.color = COLOR_HOST[self.status_code]
        self.metadata['dockerHost'] = dockerhost

        # self.client = Client(self.metadata['dockerHost'],timeout=10,version='1.23')
        self.client = Client(base_url=self.metadata['dockerHost'],version=DOCKER_API_VERSION,timeout=10)
