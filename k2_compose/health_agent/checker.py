#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

import subprocess
import time
import signal


class CheckerTimeoutException(Exception):
    def __init__(self, *args, **kwargs):
        super(CheckerTimeoutException, self).__init__(*args, **kwargs)


def call(args, timeout, term_signal=signal.SIGINT, poll_interval=0.2):
    start_time = time.time()
    ret = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while time.time() - start_time < timeout and ret.poll() is None:
        time.sleep(poll_interval)
    if ret.poll() is None:
        ret.send_signal(term_signal)
        raise CheckerTimeoutException(ret)
    return ret
