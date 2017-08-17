import os
import time

from os.path import isfile


import logging


# noinspection PyBroadException
def clear_token(token_path):
    try:
        os.unlink(token_path)
    except:
        pass


def read_token(token_path, timeout=10):
    log = logging.getLogger(__name__)
    log.info("Waiting for SMS Token...")

    tt = time.time()
    te = tt + timeout

    while tt < te:
        if isfile(token_path):
            break

        time.sleep(1)
        tt = time.time()

    if not isfile(token_path):
        log.critical('Could not read SMS Token: Operation timed out!')
        return ''

    with open(token_path) as tf:
        tk = tf.read()

    log.info("SMS Auth Token: {}".format(tk))

    return tk

