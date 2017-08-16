import importlib.util
import json
import logging
import logging.handlers
import os
import sys
import time
from collections import deque
from json.decoder import JSONDecodeError
from os.path import join, abspath, realpath, basename, isdir, isfile, dirname
from threading import Lock

import shutil
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


from utils import atomic_write


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

    # Default job confirmation file extension
    CONFIRM_FILE_EXT = ".confirm"

    def __init__(self):
        # Resolve Ninja's script absolute path
        self.app_root_dir = dirname(abspath(realpath(sys.argv[0])))
        os.chdir(self.app_root_dir)

        # Setup Ninja variables
        self.job_queue = deque()     # Pending jobs' queue
        self.job_mutex = Lock()      # queue Mutex
        self.job_folder = ""         # Absolute path of jobs folder, will be loaded from settings.
        self.current_job = ""        # Current job file being processed
        self.config = {}             # Configuration read and stored as a dictionary
        self.module_name = ''        # Configured module on which Ninja will dispatch tasks to
        self.observer = Observer()   # Our filesystem watchdog
        self.logger = None           # Ninja logger instance
        self.task_handler = None     # TaskHandler class instance
        self.ss_dir = ''             # Screen Shots directory, for debugging possible errors.

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
        self.logger.info("Waiting for jobs on folder {}...".format(self.config['jobs_folder']))

        # Job dispatcher loop.
        # Checks for new jobs on the job queue, pop, validate and run them.
        try:
            while True:
                # if queue is not empty
                if self.job_queue:
                    with self.job_mutex:
                        job_file_name = self.job_queue.popleft()

                    self.validate_job(job_file_name)

                time.sleep(1)
        except Exception as ex:
            self.logger.critical("Caught exception: {}".format(str(ex)))
            self.observer.stop()

        self.observer.join()

    def validate_job(self, job_file_name):
        self.logger.info("Validating job {} ...".format(job_file_name))

        job_file_name = join(self.job_folder, job_file_name)
        self.current_job = job_file_name

        try:
            job_fp = open(job_file_name)
        except IOError as io_err:
            self.logger.critical("Failed to open job file {}: {}".format(job_file_name, str(io_err)))
            self.job_load_failed()
        else:
            try:
                job_data = json.load(job_fp)
            except (JSONDecodeError, ValueError) as json_err:
                self.logger.critical("FAILED TO DECODE(json) JOB FILE {}: {}".format(job_file_name, str(json_err)))
                self.job_load_failed()
            else:
                if 'operation' in job_data:
                    self.logger.info("Running job {} ...".format(job_file_name))
                    self.run_job(job_data)
                else:
                    self.logger.critical("INVALID JOB FILE: Required field is missing -> 'operation'")
                    self.confirm_job(data=job_data, status='err_sys_invalid_job',
                                     status_message="Required field is missing -> 'operation'")
            finally:
                job_fp.close()

    def run_job(self, job_data):
        operation = job_data['operation']

        # Forward job validation to configured module of this instance
        if not self.task_handler.validate(job_data):
            return

        if not hasattr(self.task_handler, operation) or not callable(getattr(self.task_handler, operation)):
            self.logger.critical("Operation not implemented by module. Module({}) Operation({}). Ignoring job...".
                                 format(self.module_name, operation))
            return

        # Invoke module handler to handle this Job
        op_handler = getattr(self.task_handler, operation)
        op_handler(job_data)

    def confirm_job(self, job_data, status='ok', status_message='', admin_message=''):
        status_data = {
            "status": status
        }

        if status_message:
            status_data["status_message"] = status_message

        if admin_message:
            status_data["admin_message"] = admin_message

        job_data.update(status_data)

        try:
            data = json.dumps(job_data, separators=(',', ':'))
        except (JSONDecodeError, ValueError) as err:
            self.logger.critical("Failed to create output json: {}".format(str(err)))
        else:
            confirm_file_name = join(self.job_folder, self.current_job + Ninja.CONFIRM_FILE_EXT)

            if atomic_write(data, confirm_file_name):
                self.logger.info("Confirmation file successfully written: {}".format(confirm_file_name))
            else:
                self.logger.critical("Failed to create confirmation file: {}".format(confirm_file_name))

    def job_load_failed(self):
        """Create an error-confirmation file for current job.

        If, for some reason, it wasn't possible to load source job file, this method should be called.
        When things like I/O Error or invalid json format are detected on source file.
        In that case, just copy source file to destination confirm file, cause there is nothing else we could do.


        :param job_file_name Current job file nasme
        :return:
        """

        confirm_file_name = join(self.job_folder, self.current_job + Ninja.CONFIRM_FILE_EXT)

        try:
            shutil.copyfile(self.current_job, confirm_file_name)
        except Exception as err:
            self.logger.critical("FAILED TO CREATE CONFIRMATION FILE {}: {}".format(confirm_file_name, str(err)))
        else:
            self.logger.info("ERROR-Confirm file created for job {}.".format(self.current_job))

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

        if 'ss_dir' in self.config:
            self.ss_dir = self.config['ss_dir']
        else:
            self.ss_dir = join(self.app_root_dir, 'screenshots')

        if not isdir(self.ss_dir):
            self.logger.info("Creating screenshots directory: {}".format(self.ss_dir))
            try:
                os.mkdir(self.ss_dir)
            except IOError as io_err:
                self.logger.fatal("Unable to create screenshots directory {}: {}. Aborting...".format(self.ss_dir, str(io_err)))
                sys.exit(1)

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
            except IOError as io_err:
                self.logger.fatal("Unable to create jobs directory: {}. Aborting...".format(str(io_err)))
                sys.exit(1)

        self.job_folder = abspath(realpath(self.config['jobs_folder']))

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

        self.task_handler = self.task_handler(ninja=self)
        if hasattr(self.task_handler, 'setup') and callable(self.task_handler.setup):
            self.logger.info("Initializing TaskHandler...")
            if not self.task_handler.setup():
                self.logger.fatal("Failed to initialize TaskHandler. Aborting...")
                sys.exit(1)

        self.logger.info("Module successfully loaded!")

    def take_ss(self, driver):
        ss_file = join(self.app_root_dir, self.current_job + ".png")
        driver.get_screenshot_as_file(ss_file)

    class TaskManager(FileSystemEventHandler):

        def __init__(self, *args, **kwargs):
            self.logger = logging.getLogger('TaskManager')
            self.queue = kwargs['job_queue']
            self.queue_mutex = kwargs['job_mutex']

        def on_created(self, event):
            if not event.src_path.endswith(".json"):
                return

            job_abs_path = abspath(realpath(event.src_path))

            self.logger.info("New job file: {}".format(job_abs_path))

            with self.queue_mutex:
                self.queue.append(basename(event.src_path))


if __name__ == '__main__':
    ninja = Ninja()
    ninja.setup()
    ninja.run()
