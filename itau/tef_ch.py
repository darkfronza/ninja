""" ITAU TEF between checking account

    This module executes the TEF operation between ITAU checking accounts
"""
import logging

import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from itau import operation_codes, navigation

LOG_PREFIX = "[ITAU_TEF_CH] "
logger = logging.getLogger(__name__)


def log(msg):
    logger.info(LOG_PREFIX + msg)


def log_critical(msg):
    logger.critical(LOG_PREFIX + msg)


def _locate_customer(driver, job_data):
    small_wait = WebDriverWait(driver, 8)
    account_nick = job_data['branch'] + job_data['account']
    account_nick = account_nick.strip()

    log("Locating customer: Nick({}) Name({})".format(account_nick, job_data['fullname']))

    # 1. First locate ITAU customer by using its nickname
    try:
        search_box = driver.wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@name="FOCO"]')))
        search_box.click()
        search_box.clear()
        search_box.send_keys(account_nick)
    except TimeoutException:
        log_critical('Unable to locate element: //input[@name="FOCO"]')
        return operation_codes.OP_TIMEOUT

    log("Search box found! submitting search...")

    # 2. Submit search
    try:
        submit_btn = small_wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@name="Sub1"]')))
        submit_btn.click()
    except TimeoutException:
        log_critical('Unable to locate submit button: //input[@name="Sub1"]')
        return operation_codes.OP_TIMEOUT

    time.sleep(2)

    navigation.switch_to_frame(driver, 'CORPO')
    log("Verifying if customer is already registered...")

    # 3. Check if customer exists, if not, notify caller so it can register customer on ITAU and call us again later.
    check_if_customer_not_exists_xtag = '//span[contains(text(), "o existe favorecido cadastrado") and @class="MsgTxt"]'
    try:
        small_wait.until(EC.visibility_of_element_located, check_if_customer_not_exists_xtag)
    except TimeoutException:
        log("Customer found! Trying to select it on table...")
    else:
        log("Customer not found! Need to be registered first.")
        return operation_codes.OP_CUSTOMER_NOT_FOUND

    navigation.switch_to_frame(driver, 'CORPO')
    # 4. Select customer in table
    select_xtag = '//*[text()="{}"]/../..//a[@class="TabelaSelecionar"]'.format(account_nick)
    try:
        customer = small_wait.until(EC.element_to_be_clickable, check_if_customer_not_exists_xtag)
        customer.click()
    except TimeoutException:
        log("Unable to select customer: {}".format(select_xtag))
        return operation_codes.OP_TIMEOUT

    # Customer was found, good.
    return operation_codes.OP_SUCCESS


def _fill_input(wait, xtag, value):
    element = wait.until(EC.element_to_be_clickable((By.XPATH, xtag)))
    element.click()
    element.clear()
    element.send_keys(value)


def _register_tef(driver, job_data):
    navigation.switch_to_frame(driver, "CORPO")

    small_wait = WebDriverWait(driver, 8)

    log("Filling in TEF form...")
    try:
        # TEF amount
        _fill_input(small_wait, '//input[@name="valor" and @size="16"]', job_data['amount'])

        _fill_input(small_wait, '//input[@id="FOCO"]', job_data['day'])
        _fill_input(small_wait, '//input[@name="mes"]', job_data['month'])
        _fill_input(small_wait, '//input[@name="ano"]', job_data['year'])

    except TimeoutException as ex:
        log_critical('Timeout when filling in form: {}'.format(str(ex)))
        return operation_codes.OP_TIMEOUT

    log("Submitting TEF...")
    submit_xtag = '//input[@name="Enviar" and @type="button"]'
    try:
        submit_btn = driver.find_element(By.XPATH, submit_xtag)
        submit_btn.click()
    except NoSuchElementException:
        log_critical("Unable to locate submit button: {}".format(submit_xtag))
        return operation_codes.OP_FAILED

    return operation_codes.OP_SUCCESS


def execute(driver, job_data):
    log("Requesting TEF between ITAU checking accounts...")

    # This is the same as clicking on the TEF radio button and clicking on submit.
    driver.execute_script("passaParam('01','CCCC','', '30')")

    time.sleep(2)

    # Lookup customer
    op_code = _locate_customer(driver, job_data)
    if op_code != operation_codes.OP_SUCCESS:
        return op_code

    time.sleep(4)
    return _register_tef(driver, job_data)
