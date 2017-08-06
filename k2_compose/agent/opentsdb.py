#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import requests
import json


class OpenTSDB_Sender(object):
    def __init__(self, server):
        self.server = server
        self.url = "http://%s/api/put" % server
        self.session = requests.Session()

    def send(self, lines):
        json_metric=[]
        for line in lines:
            if not line.startswith("put "):
                print 'error: ',line
                continue
            json_metric.append(self._opentsdb_line_to_json(line))

        if json_metric:
            self._opentsdb_send(json_metric)

    def _opentsdb_send(self, metric):
        try:
            response = self.session.post(self.url, json=metric)
            if response.status_code == 204:
                print 'send success', metric
            else:
                print 'send failed: ' + str(response)
        except requests.exceptions.RequestException as e:
            print 'send failed', metric
            print e.message

    def _opentsdb_line_to_json(self,line):
        parts = line.split()
        tags = {}
        for tag in parts[4:]:
            key, value = tag.split('=')
            tags[key] = value
        value = parts[3]
        if value.lstrip('-').isdigit():
            value = long(value)
            return {
                'metric': parts[1],
                'timestamp': int(parts[2]),
                'value': value,
                'tags': tags
            }
        elif "." in value :
            value = float(value)
            return {
                    'metric': parts[1],
                    'timestamp': int(parts[2]),
                    'value': value,
                    'tags': tags
            }
        else:
            print 'value format error %s'% value

    @classmethod
    def _test(cls):
        print cls._opentsdb_line_to_json(
            'put goldwind.kafka.raw_binary.offset.processed 1494988590 591865736 host=pc foo=bar a=b')
        print cls._opentsdb_line_to_json(
            'put goldwind.kafka.raw_binary.offset.processed 1494988590 591865736 host=pc')
        print cls._opentsdb_line_to_json(
            'put goldwind.kafka.raw_binary.offset.processed 1494988590 591865736')
        print cls._opentsdb_line_to_json(
            'put goldwind.kafka.raw_binary.offset.processed 1494988590 haha host=pc')


if __name__ == '__main__':
    sender = OpenTSDB_Sender(server=os.getenv('OPENTSDB_HTTP_API',
                                              '106.120.241.178:4242'))
    while True:
        line = raw_input()
        sender.send(line)