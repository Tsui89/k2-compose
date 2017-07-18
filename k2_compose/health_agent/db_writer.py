#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from health_store import HealthStore
from influxdb_store import InfluxDBStore
import urlparse
import sys
import logging

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


class Writer:
    def __init__(self, status_store):
        try:
            url = urlparse.urlparse(status_store)
        except Exception as e:
            logging.error('Invalid status store URL %s' % status_store)
            sys.exit(-1)
        if url.scheme == 'influxdb':
            host = url.netloc.split(':')[0]
            port = url.netloc.split(':')[1]
            self._store = InfluxDBStore(host, port)
        pass

    def write(self, group):
        self._store.save(group)
