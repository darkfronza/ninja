import logging

import time

from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from itau import operation_codes, navigation

logger = logging.getLogger(__name__)


def _locate_customer(driver, job_data):
    acc_full_name = job_data['fullname'][:30].strip()
    small_wait = WebDriverWait(driver, 8)

    logger.info("Locating customer, name:{}".format(acc_full_name))

    # 1. First locate ITAU customer by using its nickname
    try:
        search_box = driver.wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@id="nome"]')))
        search_box.click()
        search_box.clear()
        search_box.send_keys(acc_full_name)
    except TimeoutException:
        logger.critical('Unable to locate element: //input[@id="nome"]')
        return operation_codes.OP_TIMEOUT

    logger.info("Search box found! submitting search...")

    # 2. Submit search
    try:
        submit_btn = small_wait.until(EC.element_to_be_clickable((By.XPATH, '//a[contains(text(), "buscar")]')))
        submit_btn.click()
    except TimeoutException:
        logger.critical('Unable to locate submit button: //a[contains(text(), "buscar")]')
        return operation_codes.OP_TIMEOUT

    time.sleep(2)

    navigation.switch_to_frame(driver, 'CORPO')

    # 4. Select customer in table
    select_xpath = '//td[contains(text(), "{}")]/..//a[contains(text(), "selecionar")]'.format(job_data['account'])
    logger.info("Search submitted, trying to locate customer in result table...")
    logger.info("Query xpath = {}".format(select_xpath))
    try:
        customer = small_wait.until(EC.element_to_be_clickable((By.XPATH, select_xpath)))
        customer.click()
    except TimeoutException:
        logger.info("Unable to select customer: {}".format(select_xpath))

        logger.info("Verifying if customer must be added/registered...")

        # 3. Check if customer exists.
        # check_if_customer_not_exists_xtag = '//span[contains(text(), "o existe favorecido cadastrado") and @class="MsgTxt"]'
        # try:
        #     small_wait.until(EC.visibility_of_element_located, check_if_customer_not_exists_xtag)
        # except TimeoutException:
        #     logger.info("Customer not found! Need to be registered first.")
        #     return operation_codes.OP_CUSTOMER_NOT_FOUND
        return operation_codes.OP_CUSTOMER_NOT_FOUND

    # Customer was found, good.
    return operation_codes.OP_SUCCESS


def _fill_input(wait, xpath, value):
    element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    element.click()
    element.clear()
    element.send_keys(value)


def _register_ted(driver, job_data):
    time.sleep(1)
    navigation.switch_to_frame(driver, "CORPO")
    time.sleep(1)

    small_wait = WebDriverWait(driver, 8)

    logger.info("Filling in TED form...")
    try:
        # TEF amount
        _fill_input(small_wait, '//input[@id="dia"]', job_data['day'])
        _fill_input(small_wait, '//input[@id="mes"]', job_data['month'])
        _fill_input(small_wait, '//input[@id="ano"]', job_data['year'])

        _fill_input(small_wait, '//input[@name="valor" and @size="16"]', job_data['amount'])

    except TimeoutException as ex:
        logger.critical('Timeout when filling in form: {}'.format(str(ex)))
        return operation_codes.OP_TIMEOUT

    # If checking account, must select "Credit on account" purpose of the operation
    if job_data['account_type'] == 'CH':
        try:
            # Operation code: Credit on account
            credit_op_xpath = '//select[@id="Finalidade"]/option[@value="9"]'
            op_element = driver.find_element(By.XPATH, credit_op_xpath)
            op_element.click()
        except NoSuchElementException:
            logger.critical("Unable to select operation code element : {}".format(credit_op_xpath))
            return operation_codes.OP_FAILED

    # navigation.switch_to_frame(driver, "CORPO")

    logger.info("Locating submit button...")
    submit_xtag = '//input[@name="Incluir" and @type="button"]'

    try:
        submit_btn = small_wait.until(EC.element_to_be_clickable((By.XPATH, submit_xtag)))
        hover = ActionChains(driver).move_to_element(submit_btn)
        hover.perform()
        logger.info("Submitting TED...")

        click_action = ActionChains(driver).click(submit_btn)
        click_action.perform()
    except TimeoutException:
        logger.critical("Unable to locate submit button: {}".format(submit_xtag))
        return operation_codes.OP_FAILED

    time.sleep(3)

    logger.info("TED submitted, checking if operation was approved...")
    success_xpath = '//*[contains(text(), "sucesso")]'
    try:
        small_wait.until(EC.visibility_of_element_located((By.XPATH, success_xpath)))
    except TimeoutException as ex:
        logger.critical("Unable to find operation approval status!")
        return operation_codes.OP_FAILED

    logger.info("TEF successfully registered!")

    return operation_codes.OP_SUCCESS


def execute(driver, job_data):
    logger.info("TED operation, starting...")

    # This is the same as clicking on the TEF radio button and clicking on submit.
    if job_data['account_type'] == 'CH':
        driver.execute_script("passaParam('41','','', '34')")
    else:
        driver.execute_script("passaParam('03','','', '32')")

    time.sleep(2)

    # Lookup customer
    op_code = _locate_customer(driver, job_data)
    if op_code != operation_codes.OP_SUCCESS:
        return op_code

    time.sleep(4)

    return _register_ted(driver, job_data)