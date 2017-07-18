#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

from health_store import HealthStore
from influxdb import InfluxDBClient


class InfluxDBStore(HealthStore):
    def __init__(self, host, port):
        HealthStore.__init__(self)
        self._database = 'kmx-monitor'
        self._retention_name = '3d'
        self._client = InfluxDBClient(host, port)
        self._client.create_database(self._database)
        self._create_retention_policy()

    def _create_retention_policy(self):
        retention_policies = [ policy["name"] for policy in self._client.get_list_retention_policies(self._database)]
        if self._retention_name not in retention_policies:
            self._client.create_retention_policy(self._retention_name, "3d", "1",
                                                 self._database, True
                                                 )
        if '32d' not in retention_policies:
            self._client.create_retention_policy('32d', "32d", "1",
                                                 self._database, False
                                                 )

    def save(self, group):
        json_body = []

        if 'hosts' in group.keys():
            for h, v in group['hosts'].items():
                tags = group['tags'].copy()
                tags.update({
                    'host': h,
                    'type': 'host'
                })
                json_body.append({
                    'measurement': 'health',
                    'tags': tags,
                    'time': long(v[0] * 1000 * 1000),
                    'fields': {
                        'status': v[1]
                    }
                })
        elif 'services' in group.keys():
            for s, v in group['services'].items():
                tags = group['tags'].copy()
                tags.update({
                    'component': s,
                    'type': 'component'
                })
                json_body.append({
                    'measurement': 'health',
                    'tags': tags,
                    'time': long(v[0] * 1000 * 1000),
                    'fields': {
                        'status': v[1]
                    }
                })
        elif 'cpu' in group.keys():
            for s, v in group['cpu'].items():
                tags = group['tags'].copy()
                tags.update({
                    'component': s,
                })
                json_body.append({
                    'measurement': 'container_cpu_percent',
                    'tags': tags,
                    'time': long(v[0] * 1000 * 1000),
                    'fields': {
                        'value': v[1]
                    }
                })
        elif 'mem' in group.keys():
            for s, v in group['mem'].items():
                tags = group['tags'].copy()
                tags.update({
                    'component': s,
                    'mem_limit': int(v[2]/1024/1024)
                })
                json_body.append({
                    'measurement': 'container_mem_usage',
                    'tags': tags,
                    'time': long(v[0] * 1000 * 1000),
                    'fields': {
                        'value': v[1]
                    }
                })
        else:
            return
        self._client.write_points(json_body, time_precision='u', database=self._database)




