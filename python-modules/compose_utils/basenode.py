#!/usr/bin/env python
# -*- coding: utf-8 -*-


class Node:
    def __init__(self):
        self.id = ''
        self.type = ''
        self.label = ''
        self.metadata = {}
        self._status_code = -1
        self._status = ''
        self._color = ''

    @property
    def status_code(self):
        return self._status_code

    @status_code.setter
    def status_code(self, code):
        self._status_code = code

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        self.status = status

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        self.color = color

    def get_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'label': self.label,
            'metadata': self.metadata,
            'statusCode': self.status_code,
            'status': self.status
        }

    def to_string(self):
        return "N: %s %s" % (self.type, self.id)


class Edge():
    def __init__(self, relation, source, target):
        self.relation = relation
        self.source = source
        self.target = target
        self.directed = True
        self.label = ''
        self.metadata = {}

    def get_dict(self):
        return {
            'source': self.source,
            'relation': self.relation,
            'target': self.target,
            'directed': self.directed,
            'label': self.label,
            'metadata': self.metadata
        }

    def to_string(self):
        return "E: %s %s %s" % (self.source, self.relation, self.target)


class RunsOn(Edge):
    def __init__(self, source, target):
        Edge.__init__(self, "runs_on", source, target)


class DependsOn(Edge):
    def __init__(self, source, target):
        Edge.__init__(self, "depends_on", source, target)


