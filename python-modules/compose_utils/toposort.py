#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import sys


def indegree(services, dependency_list):
    """
    :param services: service list
    :param dependency_list: service dependency list
    :return: service sorted by dependency order
    """

    if services == []:
        return None
    tmp = services[:]
    for iterm in dependency_list:
        if iterm[1] in tmp:
            tmp.remove(iterm[1])
    if tmp == []:
        for d in dependency_list:
            if d[0] not in services:
                logging.error("In Yaml. [%s] depends on [%s], " \
                              "but [%s] is not exist in services." % (
                                  d[1], d[0], d[0]))
                sys.exit(-1)
    for t in tmp:
        for index in range(len(dependency_list)):
            if t in dependency_list[index]:
                dependency_list[index] = 'toDel'
    if dependency_list:
        eset = set(dependency_list)
        if 'toDel' in eset:
            eset.remove('toDel')
        dependency_list[:] = list(eset)
    if services:
        for t in tmp:
            services.remove(t)
    return tmp


def toposort(services, dependency_list):
    """
    """
    services.sort()
    result = []
    while True:
        nodes = indegree(services, dependency_list)
        if nodes is None:
            break
        result.extend(nodes)
    return result
