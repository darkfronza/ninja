import logging

import time
from selenium import webdriver
from selenium.webdriver.remote.remote_connection import LOGGER
from selenium.webdriver.support.wait import WebDriverWait

from itau import command_validator, navigation
from itau.login import login


class TaskHandler:

    # Required configuration parameters for this specific Instance
    REQUIRED_CFG_PARAMS = ('account_branch_itau', 'account_number_itau', 'account_pin_itau', 'account_cpf_itau')

    def __init__(self, *args, **kwargs):
        self.ninja = kwargs['ninja']
        self.logger = logging.getLogger(__name__)
        self.web_driver = None

    def init_driver(self):
        LOGGER.setLevel(logging.WARNING)

        self.web_driver = webdriver.Firefox(firefox_profile=self.ninja.config['firefox_profile'],
                                            firefox_binary=self.ninja.config['firefox_binary'])
        # self.web_driver.implicitly_wait(30)
        self.web_driver.wait = WebDriverWait(self.web_driver, 30)

    def setup(self):
        self.logger.info("Checking required configuration parameters...")

        for cfg in TaskHandler.REQUIRED_CFG_PARAMS:
            if cfg not in self.ninja.config:
                self.logger.critical("Required configuration param is missing: <{}>".format(cfg))
                return False

        self.logger.info("Configuration is correct.")

        return True

    def validate(self, job_data):
        operation = job_data['operation']
        if operation not in command_validator.REQUIRED_FIELDS_BY_COMMAND:
            self.logger.critical("Operation not supported: {}".format(operation))
            return False

        # Check if current job fulfills required arguments.
        for required_field in command_validator.REQUIRED_FIELDS_BY_COMMAND[operation]:
            if required_field not in job_data:
                self.ninja.confirm_job(job_data, status='err_sys_invalid_job',
                                       status_message="Required field is missing -> '{}'".format(required_field))
                return False

        return True

    def transfer_bank(self, job_data):
        self.init_driver()
        try:
            if not login(self.ninja.config, self.web_driver):
                self.ninja.confirm_job(job_data, status='err_itau_login', status_message='Unable to login',
                                       admin_message='Failed to login on Itau.')
                self.ninja.take_ss(self.web_driver)
                return

            time.sleep(4)

            if not navigation.goto_screen(self.web_driver, 'transfer_bank'):
                self.ninja.confirm_job(job_data, status='err_itau_navigation', status_message='Unable to navigate',
                                       admin_message='Failed to navigate to <Transferencias> screen')
                self.logger.critical("Unable to navigate on ITAU web page as expected. Aborting...")
                self.ninja.take_ss(self.web_driver)
                return

            self.ninja.confirm_job(job_data)
        finally:
            self.web_driver.quit()
            del self.web_driver
