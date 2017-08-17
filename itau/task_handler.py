import logging

import time
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.remote_connection import LOGGER
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from itau import command_validator, navigation, tef_ch, operation_codes, ted_doc
from itau.login import login


class TaskHandler:
    # Required configuration parameters for this specific Instance
    REQUIRED_CFG_PARAMS = ('account_branch_itau', 'account_number_itau',
                           'account_pin_itau', 'account_cpf_itau', 'token_path')

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
                self.logger.critical("Invalid JOB: Required field is missing -> '{}'".format(required_field))
                self.ninja.confirm_job(job_data, status='err_sys_invalid_job',
                                       status_message="Required field is missing -> '{}'".format(required_field))
                return False

        if job_data['account_type'] not in ('SV', 'CH'):
            self.ninja.confirm_job(job_data,
                                   status="err_invalid_account_type",
                                   status_message="account_type must be either 'CH' or 'SV'",
                                   admin_message="Could not process job sent from API. (Invalid account_type)")
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

            self.logger.debug("Trying to locate TAB Transferencias...")

            navigation.switch_to_frame(self.web_driver, 'CORPO')
            # Locate Transferencias TAB
            try:
                tab_xpath = '//td[contains(text(), "Transfer") and @class="TRNdado"]'
                tab_element = self.web_driver.wait.until(EC.element_to_be_clickable((By.XPATH, tab_xpath)))
                tab_element.click()
            except TimeoutException:
                self.logger.error('Unable to locate element: {}'.format(tab_xpath))
                self.ninja.confirm_job(job_data, status='err_itau_navigation',
                                       status_message='Unable find TAB <Transferencias>',
                                       admin_message='Unable find TAB <Transferencias>')
                self.ninja.take_ss(self.web_driver)
                return

            # -----------------------------------------------
            #  PROCESS TED/TEF/DOC
            # -----------------------------------------------
            op_code = operation_codes.OP_FAILED

            if job_data['account_type'] == 'CH':
                if job_data['bank_id'] == "341":
                    op_code = tef_ch.execute(self.web_driver, job_data)  # ITAU: TEF between checking accoun
                else:
                    op_code = ted_doc.execute(self.web_driver, job_data)  # TED

            elif job_data['account_type'] == 'SV':
                if job_data['bank_id'] == "341":
                    op_code = operation_codes.OP_FAILED
                else:
                    op_code = operation_codes.OP_FAILED

            if op_code == operation_codes.OP_SUCCESS:
                self.ninja.confirm_job(job_data)
            else:
                msg = "Operation Failed"
                if op_code == operation_codes.OP_CUSTOMER_NOT_FOUND:
                    msg += ": Customer not registered"
                elif op_code == operation_codes.OP_TIMEOUT:
                    msg += ": Timed out"

                self.ninja.confirm_job(job_data, "err_operation_failed", status_message=msg, admin_message=msg)
                self.ninja.take_ss(self.web_driver)
        finally:
            pass
            # self.web_driver.quit()
            # del self.web_driver
