#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

import yaml
import os
import sys


def validate_checkers(cf):
    for s,v in cf['services'].items():
        try:
            shell = v['health_check']['shell']
            checker_script = shell.split()[0]
            open(checker_script)
            timeout = v['health_check']['timeout']
        except Exception as e:
            print e
            sys.exit(-1)
        # print v


def load(f):
    result = None
    try:
        result = yaml.load(open(f))
    except Exception as e:
        print e.message
        sys.exit(-1)
    validate_checkers(result)
    return result
