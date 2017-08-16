import logging

import time
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# Dictionary mapping how to navigate between ITAU screens according to operation requested by the current JOB.
ITAU_NAVIGATION = {
    'transfer_bank': {
        'menu': ('Contas a pagar', 'Incluir pagamentos e transfer'),
        'search': 'Contas a Pagar > Incluir e alterar > Incluir pagamentos e transfe'
    }
}


def switch_to_frame(driver, frame_name):
    driver.switch_to.default_content()

    try:
        frame = driver.find_element(By.XPATH, '//frame[@name="{}"]'.format(frame_name))
    except NoSuchElementException:
        pass
    else:
        logging.getLogger(__name__).info("Switching to frame {}".format(frame_name))
        driver.switch_to.frame(frame)


def goto_screen(driver, screen_name):
    log = logging.getLogger(__name__)
    wait = WebDriverWait(driver, 8)

    if screen_name not in ITAU_NAVIGATION:
        log.critical("There is no configured navigation for the screen '{}'.".format(screen_name))
        return False

    log.info("Navigating to screen {} ...".format(screen_name))

    switch_to_frame(driver, 'MENU')

    nav = ITAU_NAVIGATION[screen_name]

    # Try to navigate through search box first
    search_found = False
    if nav['search'] is not None:
        log.info("Locating search field...")

        try:
            search_element = wait.until(EC.visibility_of_element_located((By.XPATH, '//input[@id="input-busca"]')))
        except TimeoutException:
            log.info('Search field not found: //input[@id="input-busca"]')
            return False
        else:
            log.info("Search field was successfully found!")
            search_found = True

    # If ITAU search-navigation element was found, use it, faster.
    if search_found:
        hover = ActionChains(driver).move_to_element(search_element)
        hover.perform()

        search_element.click()
        search_element.clear()
        search_element.send_keys(nav['search'])

        search_element.click()
        time.sleep(2)

        try:
            target = '//div[contains(text(),"{}")]/parent::a'.format(nav['search'][-30:])
            log.info("Waiting for element to appear: {}".format(target))
            link = wait.until(EC.element_to_be_clickable((By.XPATH, target)))
        except TimeoutException:
            log.error('Unable to locate element: {}'.format(target))
            return False

        log.info("Clicking on link {}".format(target))

        link.click()

        return True

    elif nav['menu'] is not None:  # Navigate by MENU button
        menu_xpath = '//a[@class="btn-nav"][contains(text(),"menu")]'
        log.info("Trying to locate MENU: {}".format(menu_xpath))

        try:
            menu_element = wait.until(EC.visibility_of_element_located((By.XPATH, menu_xpath)))
        except TimeoutException:
            log.critical('Unable to locate MENU: {}'.format(menu_xpath))
            return False

        log.info("MENU successfully found! hovering over it...")

        hover = ActionChains(driver).move_to_element(menu_element)
        hover.perform()
        time.sleep(1)

        link_xtag = '//a[text()="{}"]'.format(nav['menu'][0])
        log.debug("Trying to locate link {} ...".format(link_xtag))

        try:
            menu_element = wait.until(EC.element_to_be_clickable((By.XPATH, link_xtag)))
        except NoSuchElementException:
            log.critical("Unable to locate menu item: {}".format(link_xtag))
            return False

        menu_element.click()
        time.sleep(5)

        driver.switch_to.default_content()

        link_xtag = '//a[contains(text(),"{}")]'.format(nav['menu'][1])
        log.debug("Trying to locate element: {}".format(link_xtag))
        try:
            link = wait.until(EC.element_to_be_clickable((By.XPATH, link_xtag)))
        except NoSuchElementException:
            log.critical("Unable to locate link: {}".format(link_xtag))
            return False

        log.debug("Link found! clicking on it...")
        link.click()

        return True

    else:
        log.critical('Unable to locate search field: //input[@id="input-busca"].')
        return False




