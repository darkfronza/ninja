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

logger = logging.getLogger(__name__)


def _locate_customer(driver, job_data):
    small_wait = WebDriverWait(driver, 8)
    account_nick = job_data['branch'] + job_data['account']
    account_nick = account_nick.strip()

    logger.info("Locating customer: Nick({}) Name({})".format(account_nick, job_data['fullname']))

    # 1. First locate ITAU customer by using its nickname
    try:
        search_box = driver.wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@name="FOCO"]')))
        search_box.click()
        search_box.clear()
        search_box.send_keys(account_nick)
    except TimeoutException:
        logger.critical('Unable to locate element: //input[@name="FOCO"]')
        return operation_codes.OP_TIMEOUT

    logger.info("Search box found! submitting search...")

    # 2. Submit search
    try:
        submit_btn = small_wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@name="Sub1"]')))
        submit_btn.click()
    except TimeoutException:
        logger.critical('Unable to locate submit button: //input[@name="Sub1"]')
        return operation_codes.OP_TIMEOUT

    time.sleep(2)

    navigation.switch_to_frame(driver, 'CORPO')

    logger.info("Query submitted, trying to locate customer in result table...")

    # 4. Select customer in table
    select_xpath = '//*[text()="{}"]/../..//a[@class="TabelaSelecionar"]'.format(account_nick)
    try:
        customer = small_wait.until(EC.element_to_be_clickable((By.XPATH, select_xpath)))
        customer.click()
    except TimeoutException:
        logger.info("Unable to select customer: {}".format(select_xpath))

        logger.info("Verifying if customer must be added/registered...")

        # 3. Check if customer exists.
        check_if_customer_not_exists_xtag = '//span[contains(text(), "o existe favorecido cadastrado") and @class="MsgTxt"]'
        try:
            small_wait.until(EC.visibility_of_element_located, check_if_customer_not_exists_xtag)
        except TimeoutException:
            logger.info("Customer not found! Need to be registered first.")
            return operation_codes.OP_CUSTOMER_NOT_FOUND

    # Customer was found, good.
    return operation_codes.OP_SUCCESS


def _fill_input(wait, xpath, value):
    element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    element.click()
    element.clear()
    element.send_keys(value)


def _register_tef(driver, job_data):
    navigation.switch_to_frame(driver, "CORPO")

    small_wait = WebDriverWait(driver, 8)

    logger.info("Filling in TEF form...")
    try:
        # TEF amount
        _fill_input(small_wait, '//input[@name="valor" and @size="16"]', job_data['amount'])

        _fill_input(small_wait, '//input[@id="FOCO"]', job_data['day'])
        _fill_input(small_wait, '//input[@name="mes"]', job_data['month'])
        _fill_input(small_wait, '//input[@name="ano"]', job_data['year'])

    except TimeoutException as ex:
        logger.critical('Timeout when filling in form: {}'.format(str(ex)))
        return operation_codes.OP_TIMEOUT

    logger.info("Submitting TEF...")
    submit_xtag = '//input[@name="Enviar" and @type="button"]'
    try:
        submit_btn = driver.find_element(By.XPATH, submit_xtag)
        submit_btn.click()
    except NoSuchElementException:
        logger.critical("Unable to locate submit button: {}".format(submit_xtag))
        return operation_codes.OP_FAILED

    time.sleep(3)

    logger.info("TEF submitted, checking if operation was approved...")
    success_xpath = '//*[contains(text(), "sucesso")]'
    try:
        small_wait.until(EC.visibility_of_element_located((By.XPATH, success_xpath)))
    except TimeoutException as ex:
        logger.critical("Unable to find operation approval status!")
        return operation_codes.OP_FAILED

    logger.info("TEF successfully registered!")

    return operation_codes.OP_SUCCESS


def execute(driver, job_data):
    logger.info("Requesting TEF between ITAU checking accounts...")

    # This is the same as clicking on the TEF radio button and clicking on submit.
    driver.execute_script("passaParam('01','CCCC','', '30')")

    time.sleep(2)

    # Lookup customer
    op_code = _locate_customer(driver, job_data)
    if op_code != operation_codes.OP_SUCCESS:
        return op_code

    time.sleep(4)
    return _register_tef(driver, job_data)
