import sys
import time
from os.path import dirname, realpath, abspath

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import requests


class TokenWatcher(FileSystemEventHandler):

    def __init__(self, tk_path, tk_server_url):
        self.tk_path = tk_path
        self.tk_server_url = tk_server_url

    def on_modified(self, event):
        tk_abs_path = abspath(event.src_path)
        if tk_abs_path == self.tk_path:
            with open(tk_abs_path) as token_file:
                token = token_file.read().strip()
                token_full_url = self.tk_server_url + '/' + token
                print("Token notification:", token_full_url)
                requests.get(token_full_url)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: {} token_full_path  token_server_url".format(sys.argv[0]))
        sys.exit(1)

    token_path = abspath(realpath(sys.argv[1]))
    token_dir = dirname(token_path)

    observer = Observer()   # Our filesystem watchdog
    observer.schedule(TokenWatcher(token_path, sys.argv[2]), token_dir, recursive=False)
    observer.start()

    # Checks for new jobs on the job queue, pop, validate and run them.
    try:
        while True:
            time.sleep(10)
    except Exception as ex:
        print("Caught exception: {}".format(str(ex)))
        observer.stop()

    observer.join()

