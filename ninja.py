import json
import logging
import logging.handlers
import sys
import os
from json.decoder import JSONDecodeError
from threading import Lock
import time
from collections import deque

from os.path import join, abspath, realpath, isdir, isfile, dirname

import importlib.util

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class Ninja:

    # Default configuration file
    CONFIG_FILE = 'config.json'

    # Default log file
    LOG_FILE = "ninja.log"

    # Default Log Level (can be overridden by env var LOGLEVEL)
    LOG_LEVEL = "INFO"

    # Required configuration parameters, shared among all modules (set in CONFIG_FILE).
    REQUIRED_CFG_PARAMS = ('firefox_binary', 'firefox_profile', 'firefox_port', 'jobs_folder')

    # Default module name on which Ninja will forward tasks
    MODULE_HANDLER_NAME = 'task_handler'

    def __init__(self):
        # Resolve Ninja's script absolute path
        self.app_root_dir = dirname(abspath(realpath(sys.argv[0])))
        os.chdir(self.app_root_dir)

        # Setup Ninja variables
        self.job_queue = deque()     # Pending jobs' queue
        self.job_mutex = Lock()      # queue Mutex
        self.config = {}             # Configuration stored as a dictionary
        self.module_name = ''        # The specified module on which Ninja will dispatch tasks to
        self.observer = Observer()   # Our filesystem watchdog
        self.logger = None           # Ninja logger instance
        self.task_handler = None     # TaskHandler class instance

        self.task_manager = Ninja.TaskManager(job_queue=self.job_queue, job_mutex=self.job_mutex)  # our watchdog, job dispatcher

    def setup(self):
        # Setup Ninja
        self._setup_log()            # 1. setup Logging system
        self._load_configuration()   # 2. Load configuration
        self._check_runtime()        # 3. Check if we are good to go, firefox binary is set, jobs_folder exists, etc
        self._load_module_handler()  # 4. Dynamically load Module handler specified in the configuration param 'module'.

    def run(self):
        self.observer.schedule(self.task_manager, self.config['jobs_folder'], recursive=False)
        self.observer.start()
        self.logger.info("Ninja started successfully!")
        self.logger.info("Waiting for jobs at {}...".format(self.config['jobs_folder']))

        # Job dispatcher loop.
        # Checks for new jobs on the job queue, pop and process them.
        try:
            while True:
                # if queue is not empty
                if self.job_queue:
                    with self.job_mutex:
                        job_file = self.job_queue.popleft()
                        self.run_job(job_file)

                time.sleep(1)
        except Exception as ex:
            self.logger.critical("Caught exception: {}".format(str(ex)))
            self.observer.stop()

        self.observer.join()

    def run_job(self, job_file):
        try:
            job_fp = open(job_file)
        except IOError as io_err:
            self.logger.critical("FAILED TO OPEN JOB FILE {}: {}".format(job_file, str(io_err)))
        else:
            try:
                job_data = json.load(job_fp)
            except (JSONDecodeError, ValueError) as json_err:
                self.logger.critical("FAILED TO DECODE(json) JOB FILE {}: {}".format(job_file, str(json_err)))
            else:
                self.logger.info("Running job {}".format(job_file))
                pass
            finally:
                job_fp.close()


    def _setup_log(self):
        log_dir = join(self.app_root_dir, "log")
        if not isdir(log_dir):
            os.mkdir(log_dir)

        # Log format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # WatchedFileHandler auto reopen file in case it is rotated
        handler = logging.handlers.WatchedFileHandler(join(log_dir, Ninja.LOG_FILE))
        handler.setFormatter(formatter)

        self.logger = logging.getLogger()
        self.logger.setLevel(os.environ.get("LOGLEVEL", Ninja.LOG_LEVEL))
        self.logger.addHandler(handler)
        self.logger.propagate = True

        if os.environ.get("LOGLEVEL", None) is not None:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        self.logger.info("Starting Ninja... App Dir = {}".format(self.app_root_dir))

    def _load_configuration(self):
        cfg_file_path = join(self.app_root_dir, Ninja.CONFIG_FILE)
        self.logger.info("Loading configuration file {} ...".format(cfg_file_path))

        with open(cfg_file_path) as cfg_file:
            self.config = json.load(cfg_file)

        self.logger.info("Validating configuration...")

        for required_cfg in Ninja.REQUIRED_CFG_PARAMS:
            if required_cfg not in self.config:
                self.logger.fatal('Missing configuration parameter: <{}>. Aborting...'.format(required_cfg))
                sys.exit(1)

        self.module_name = self.config['module']

    def _check_runtime(self):
        self.logger.info("Checking if runtime dependencies are ok...")

        if not isfile(self.config['firefox_binary']):
            self.logger.fatal("Could not locate firefox binary: {}. Aborting...".format(self.config['firefox_binary']))
            sys.exit(1)

        if not isdir(self.config['firefox_profile']):
            self.logger.fatal("Could not locate firefox profile: {}. Aborting...".format(self.config['firefox_profile']))
            sys.exit(1)

        if not isdir(self.config['jobs_folder']):
            self.logger.info("Jobs folder not found, trying to create it: {}".format(self.config["jobs_folder"]))
            try:
                os.mkdir(self.config['jobs_folder'])
            except:
                self.logger.fatal("Unable to create jobs directory! Aborting...")
                sys.exit(1)

        self.logger.info("Runtime check successful.")

    def _load_module_handler(self):
        self.logger.info("Loading Module <{}>...".format(self.module_name))

        module_dir = join(self.app_root_dir, self.module_name)
        if not isdir(module_dir):
            self.logger.fatal("Could not locate module dir: {}. Aborting...".format(module_dir))
            sys.exit(1)

        # 1. Load module spec
        module_path = '{}.{}'.format(self.module_name, Ninja.MODULE_HANDLER_NAME)
        module_spec = importlib.util.find_spec(module_path)

        if module_spec is None:
            self.logger.fatal("Could not load specified module: {}. Aborting...".format(module_path))
            sys.exit(1)

        # 2. Load module from its spec
        self.module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(self.module)

        # 3. Load TaskHandler class, modules should implement this class
        if not hasattr(self.module, "TaskHandler"):
            self.logger.fatal("Module <{}> has no TaskHandler class implementation! Aborting...".format(module_path))
            sys.exit(1)

        self.task_handler = getattr(self.module, "TaskHandler")
        if not isinstance(self.task_handler, type):
            self.logger.fatal("TaskHandler from Module <{}> must be a class. Detected type was {}. Aborting...".format(
                module_path, str(type(self.task_handler))
            ))
            sys.exit(1)

        self.task_handler = self.task_handler(config=self.config)
        if hasattr(self.task_handler, 'setup') and callable(self.task_handler.setup):
            self.logger.info("Initializing TaskHandler...")
            if not self.task_handler.setup():
                self.logger.fatal("Failed to initialize TaskHandler. Aborting...")
                sys.exit(1)

        self.logger.info("Module successfully loaded!")

    class TaskManager(FileSystemEventHandler):

        def __init__(self, *args, **kwargs):
            self.logger = logging.getLogger('TaskManager')
            self.queue = kwargs['job_queue']
            self.queue_mutex = kwargs['job_mutex']

        def on_created(self, event):
            self.logger.info("New job file: {}".format(event.src_path))
            with self.queue_mutex:
                self.queue.append(event.src_path)


if __name__ == '__main__':
    ninja = Ninja()
    ninja.setup()
    ninja.run()
