import json
import logging
import logging.handlers
import sys
import os
from os.path import join, abspath, realpath, isdir, isfile, dirname

import importlib.util



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
        # Resolve Ninja' script absolute path
        self.app_root_dir = dirname(abspath(realpath(sys.argv[0])))
        os.chdir(self.app_root_dir)

        self.config = {}             # Configuration stored as a dictionary
        self.module_name = ''        # The specified module on which Ninja will dispatch tasks

        self.logger = None           # Ninja logger instance
        self.task_handler = None     # Task Handler

        self.setup_log()             # 1. setup Logging system
        self.load_configuration()    # 2. Load configuration
        self.check_runtime()         # 3. Check if we are good to go, firefox binary is set, etc
        self.load_module_handler()   # 4. Dynamically load Module handler specified in the configuration.

    def setup_log(self):
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

        self.logger.info("Starting Ninja... App Dir = {}".format(self.app_root_dir))

    def load_configuration(self):
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

    def check_runtime(self):
        self.logger.info("Checking if runtime dependencies are ok...")

        if not isfile(self.config['firefox_binary']):
            self.logger.fatal("Could not locate firefox binary: {}. Aborting...".format(self.config['firefox_binary']))
            sys.exit(1)

        if not isdir(self.config['firefox_profile']):
            self.logger.fatal("Could not locate firefox profile: {}. Aborting...".format(self.config['firefox_profile']))
            sys.exit(1)

        self.logger.info("Runtime check successful.")

    def load_module_handler(self):
        self.logger.info("Loading Module Handler <{}>...".format(self.module_name))

        module_dir = join(self.app_root_dir, self.module_name)
        if not isdir(module_dir):
            self.logger.fatal("Could not locate module dir: {}. Aborting...".format(module_dir))
            sys.exit(1)

        module_path = '{}.{}'.format(self.module_name, Ninja.MODULE_HANDLER_NAME)
        module_spec = importlib.util.find_spec(module_path)

        if module_spec is None:
            self.logger.fatal("Could not load module specified: {}. Aborting...".format(module_path))
            sys.exit(1)

        self.task_handler = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(self.task_handler)

        if not hasattr(self.task_handler, "TaskHandler"):
            self.logger.fatal("Module <{}> has no TaskHandler class implementation! Aborting...".format(module_path))
            sys.exit(1)

        self.logger.info("Module Handler successfully loaded!")


if __name__ == '__main__':
    ninja = Ninja()
