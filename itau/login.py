import time

import logging

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


ITAU_LOGIN_PAGE = "https://www.itau.com.br"


# PAGE 1: account / branch
def login_page_1(log, config, driver):
    branch_field = driver.wait.until(EC.visibility_of_element_located((By.ID, "campo_agencia")))
    account_field = driver.wait.until(EC.visibility_of_element_located((By.ID, "campo_conta")))

    branch_field.click()
    branch_field.send_keys(config['account_branch_itau'])

    account_field.click()
    account_field.send_keys(config['account_number_itau'])

    submit_btn = driver.wait.until(EC.presence_of_element_located((By.XPATH, "//a[@class='btnSubmit']")))

    log.info("Submiting account/branch credentials...")
    submit_btn.click()


# PAGE 2: Identification Method (CPF Preferred)
def login_page_2(log, config, driver):
    ident_type_field = driver.wait.until(EC.visibility_of_element_located(
        (By.XPATH, '//select[@id="tipoDocumento"]/option[@value="CPF"]')))

    if not ident_type_field.is_selected():
        ident_type_field.click()
        time.sleep(1)

    log.info("Locating CPF field...")

    cpf_field = driver.wait.until(EC.element_to_be_clickable(
        (By.XPATH, '//input[@id="campoCpf"]')))
    cpf_field.click()
    time.sleep(1)
    cpf_field.send_keys(config['account_cpf_itau'])

    submit_btn = driver.wait.until(EC.element_to_be_clickable(
        (By.XPATH, '//a[@id="botao-continuar"]')))

    log.info("Submiting CPF credentials...")
    submit_btn.click()


# PAGE 3: PIN Authentication -> Virtual Keyboard
def login_page_3(log, config, driver):
    pin_unique_digits = set(config['account_pin_itau'])
    pin_buttons = {}

    log.info("Mapping PIN buttons...")

    for pin_digit in pin_unique_digits:
        pin_btn = driver.wait.until(EC.element_to_be_clickable(
            (By.XPATH, '//a[@id="campoTeclado" and contains(text(), "{}")]'.format(pin_digit))))
        pin_buttons[pin_digit] = pin_btn

    for pin_digit in config['account_pin_itau']:
        pin_buttons[pin_digit].click()
        time.sleep(1)

    submit_btn = driver.wait.until(EC.element_to_be_clickable((By.XPATH, '//a[@id="acessar"]')))
    submit_btn.click()


# PAGE 4: SMS TOKEN
def login_page_4(log, config, driver):
    # sms_btn = driver.wait.until(EC.visibility_of_element_located((By.XPATH, '//a[@id="sms-gerarCodigo"]')))
    # sms_btn.click()

    # TODO: Read SMS token
    # token = read_token()
    # sms_input = driver.wait.until(EC.visibility_of_element_located((By.XPATH, '//input[@id="sms-codigoRecebido"]')))
    # sms_input.click()
    # sms_input.send_keys(token)

    time.sleep(30)

    # submit_btn = driver.find_element_by_xpath('//a[@id="sms-codigoOk"]')
    # submit_btn.click()


def login(config, driver):
    log = logging.getLogger(__name__)
    log.info("Fetching ITAU home page: {}".format(ITAU_LOGIN_PAGE))

    driver.get(ITAU_LOGIN_PAGE)

    try:

        login_page_1(log, config, driver)
        time.sleep(3)

        login_page_2(log, config, driver)
        time.sleep(4)

        login_page_3(log, config, driver)
        time.sleep(3)

        login_page_4(log, config, driver)
        time.sleep(4)

    except NoSuchElementException as err_not_found:
        log.critical("Unable to login, element not found: {}".format(str(err_not_found)))
        return False

    except TimeoutException as err_timeout:
        log.critical("Timeout locating element: {}".format(err_timeout))
        return False
    else:
        log.info("Login successful.")
        return True
