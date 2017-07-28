#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
from docker import APIClient as Client
from operator import itemgetter
# from colorama import Fore
from ..k2cutils.misc import timestamp_to_local_isoformat
from ..common.common import DOCKER_API_VERSION

# import logging
# logging.getLogger().setLevel(logging.DEBUG)
# logging.debug("debug mode enabled")


class ImageHistory:
    def __init__(self, image, tag, host, content=None, client=None):
        self.image = image
        self.tag = tag
        self.host = host
        self.content = content if content else []

        self._docker_client = client if client else Client(self.host, version=DOCKER_API_VERSION)
        pass

    @classmethod
    def load(cls, image, tag, host):
        return store.load(image, tag, host)

    def _save(self):
        return store.save(self)

    def insert(self, one):
        if one is not None:
            if one['current']:
                for item in self.content:
                    item['current'] = False
            self.content.append(one)
            self.content.sort(key=itemgetter('created'), reverse=True)
        self._save()

    def show(self):
        format = "%-1s %-10s %-20s %-20s"
        print '%s record(s) found for image %s:%s' % (len(self.content), self.image, self.tag)
        print ''
        print format % (' ', 'Index', 'Id', "Created")
        print '-------------------------------------------'
        for item in self.content:
            if item['current']:
            #     print Fore.GREEN + format % (
            #     '*', self.content.index(item), item['id'][7:19], timestamp_to_local_isoformat(item['created']))
            # else:
                print format % (
                ' ', self.content.index(item), item['id'][7:19], timestamp_to_local_isoformat(item['created']))
        print ''

    def exists(self, one):
        if one is not None:
            if self.content:
                for item in self.content:
                    if item['created'] == one['created']:
                        return True
        return False

    def get_current(self):
        image = self._docker_client.images(name='%s:%s' % (self.image, self.tag))
        if len(image) == 1:
            return {
                'created': image[0]['Created'],
                'id': image[0]['Id'],
                'current': True
            }
        else:
            return None

    def insert_current(self):
        current = self.get_current()
        if not self.exists(current):
            self.insert(current)

    def change_current(self, index):
        if index in range(0, len(self.content)) and index != self.current_index():
            # tag image
            self._docker_client.tag(self.content[index]['id'], self.image, self.tag)
            # change flag
            self.content[self.current_index()]['current'] = False
            self.content[index]['current'] = True
            self._save()

    def current_index(self):
        for item in self.content:
            if item['current']:
                return self.content.index(item)


class ImageHistoryStore:
    def __init__(self):
        self.store_dir = os.path.expanduser('~/.k2-compose/image-history')
        pass

    def _store_file(self, image, tag, host):
        return os.path.join(self._store_dir(image, tag, host), host.replace('/','_').replace('\\','_'))

    def _store_dir(self, image, tag, host):
        return '%s/%s/%s/' % (self.store_dir, image, tag)

    def save(self, history):
        store_file = self._store_file(history.image, history.tag, history.host)
        store_file_path = self._store_dir(history.image, history.tag, history.host)
        if not os.path.exists(store_file_path):
            os.makedirs(store_file_path)
        with open(store_file, 'w') as f:
            json.dump(history.content, f, indent=2)
        pass

    def load(self, image, tag, host):
        store_file = self._store_file(image, tag, host)
        if os.path.isfile(store_file):
            with open(store_file) as f:
                return ImageHistory(image, tag, host, json.load(f))
        else:
            # print "can not find history file for %s %s %s" % (image, tag, host)
            pass
        return None
        pass


store = ImageHistoryStore()

if __name__ == '__main__':
    # content = [{'a': 'b'}, {'x': 'y'}, {'c': 'd'}]
    # print content
    # content.sort(reverse=True)
    # print content
    history = ImageHistory(image='dev.k2data.com.cn:5001/k2data/k2-compose', tag='dev-0.4.0', host='localhost:4243')
    history.insert_current()
    history.show()
    copy = ImageHistory.load(image='dev.k2data.com.cn:5001/k2data/k2-compose', tag='dev-0.4.0', host='localhost:4243')
    copy.show()
