"""Imports"""
import os
import sys
import traceback
import re
import time
import collections
from datetime import datetime, timedelta

import logging as log
import requests

import schedule as sd
from notifypy import Notify

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (NoSuchElementException,
                                        TimeoutException,
                                        WebDriverException,
                                        NoSuchDriverException,
                                        ElementClickInterceptedException)

from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# Local libraries and Classes
from env_vars import EnvironmentVariables
from yaml_loader import YamlLoader
from notif_data import NotificationData

__version__ = "0.01.01"

# Create an instance of the EnvironmentVariables class
# which loads environment variables from .env file
ENV_VARS = EnvironmentVariables()

TIME_SLOT_LIST = collections.defaultdict(list)
opt = {}

OPT_SELECT_MSG = 'Opção "%s" selecionada com sucesso!'
NO_ELEMENT_MSG = "No element found for: %s\\n%s was raised: %s"
LOG_WEBDRIVER_ERROR = 'log_%s_error_%s.png'
NO_BUTTON_MSG = "No button %s available at the moment"


log.basicConfig(
    handlers=[
        log.StreamHandler(sys.stdout),
        log.FileHandler(f'{os.path.splitext(os.path.basename(__file__))[0]}_' +
                        f'{datetime.now().strftime("%Y%m%d")}.log',
                        mode="a+", encoding='utf-8'),
    ],
    level=log.DEBUG,
    format="%(asctime)s - %(name)-12s - %(levelname)-8s:[%(filename)s:%(lineno)-04d]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log.getLogger("selennium").setLevel(log.ERROR)
log.getLogger('selenium.webdriver.remote').setLevel(log.ERROR)
log.getLogger('selenium.webdriver.common').setLevel(log.ERROR)
log.getLogger('urllib3.connectionpool').setLevel(log.ERROR)
log.getLogger('WDM').setLevel(log.ERROR)
log.getLogger('charset_normalizer').setLevel(log.ERROR)
log.getLogger('schedule').setLevel(log.DEBUG)


def check_dotenv_siga():
    """Function to check env if the Telegram env variables were loaded."""
    if not ENV_VARS.validate():
        log.info('Messages to Telegram will not be sent. Please check the env variables!')
    else:
        log.info('Messages to Telegram will be sent.')


def usage():
    """Function to print the usage of this program."""
    print('siga.py -e, --entity (Int)<Entity> -s, \
          --service (dict)<{number values from drop lists}> -l, \
          --location (dict)<{String values from drop lists}>')


def send_message(message_header):
    """Function to send message."""
    if TIME_SLOT_LIST:
        if ENV_VARS.bot_token and ENV_VARS.bot_chat_id:
            response = telegram_bot_sendtext(message_header, TIME_SLOT_LIST)
            log.info('Message sent to Telegram')
            log.info('Telegram response: %s' , list(response.keys())[0])

        notification = Notify()
        notification.title = "SIGA"
        notification.message = f"Time slots available:\n{message_header.get_district()}\
            -{message_header.get_local()}"
        notification.urgency = "critical"
        notification.timeout = 10000  # 5 seconds
        notification.send()
        TIME_SLOT_LIST.clear()


def telegram_bot_sendtext(message_header, time_slots):
    """Function to send a notification to Telegram via chat bot."""
    entity = message_header.get_entity()
    category = message_header.get_category()
    subcategory = message_header.get_subcategory()
    motive = message_header.get_motive()
    district = message_header.get_district()
    local = message_header.get_local()

    message = f"{entity} - {category}\n{subcategory}\n{motive}\n"
    message += f"Distrito: {district}, Localidade: {local}\n\n"

    for key, value_list in time_slots.items():
        if key not in ['entity', 'category', 'subcategory', 'motive', 'district', 'local']:
            message += f"{key}\n"
            message += '\n'.join(value_list) + '\n'

    send_text = 'https://api.telegram.org/bot' + ENV_VARS.bot_token + '/sendMessage?chat_id=' \
                + ENV_VARS.bot_chat_id + '&parse_mode=Markdown&text=' + message

    response = requests.get(send_text, timeout=10)
    return response.json()


def start_chrome():
    """Function to start chrome browser."""
    test_ua = 'Mozilla/5.0 (Windows NT 4.0; WOW64) AppleWebKit/537.36 \
    (KHTML, like Gecko) Chrome/37.0.2049.0 Safari/537.36'

    # Command line arguments for Chrome
    options_args = [
        # '--start-maximized'
        '--headless',
        '--window-size=1920,1080',
        '--disable-gpu',
        '--disable-web-security',
        f'--user-agent={test_ua}',
        '--no-sandbox',
        '--disable-extensions',
        '--ignore-certificate-errors',
        '--allow-running-insecure-content'
    ]

    # Initiate Browser
    log.info('Starting webdriver')
    try:
        options = webdriver.ChromeOptions()
        for o in options_args:
            options.add_argument(o)
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        service = ChromeService(ChromeDriverManager().install())
        l_driver = webdriver.Chrome(service=service, options=options)
    except WebDriverException:
        try:
            options = webdriver.EdgeOptions()
            for o in options_args:
                options.add_argument(o)
            service = EdgeService(EdgeChromiumDriverManager().install())
            l_driver = webdriver.Edge(service=service, options=options)
        except (ConnectionError,NoSuchDriverException):
            log.info('Could not initiate WebDriver. Please check!')
            raise

    # Navigate to the URL
    url = 'https://siga.marcacaodeatendimento.pt/Marcacao/Entidades'
    l_driver.get(url)

    return l_driver


def close_chrome(p_driver):
    """Function to close chrome browser."""
    log.info('Quitting webdriver')
    p_driver.quit()


def set_entity(driver, p_entity):
    """Function to set entity field."""
    btn_label = ''
    if check_elem_exists(driver, By.CLASS_NAME, "btn-selecionar-entidade"):
        btn_entity_lst = driver.find_elements(By.XPATH,
                                              '//button[@class="btn btn-selecionar-entidade"]')
        if btn_entity_lst:
            for btn in btn_entity_lst:
                if btn.get_attribute("id") == str(p_entity):
                    try:
                        btn_label = btn.get_attribute("title")
                        btn.click()
                        log.info('Botão "%s" clicado com sucesso!', btn_label)
                        break
                    except WebDriverException as webd_except:
                        log.critical(webd_except)
                        raise webd_except
    else:
        err_msg = f"Cannot find Entity '{p_entity}' button."
        log.critical(err_msg)
        now = datetime.now().strftime('%d%m%Y_%H%M%S')
        file_name = LOG_WEBDRIVER_ERROR % (set_entity.__name__, now)
        driver.get_screenshot_as_file(filename=file_name)
        raise NoSuchElementException(err_msg + ' Please check if the webpage is normally working')
    return btn_label


def set_district(driver, p_distrito):
    """Function to set district field."""
    try:
        id_distrito_select = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.ID, 'IdDistrito'))
        )
        select = Select(id_distrito_select)
        time.sleep(2)
        select.select_by_value(str(p_distrito))
        log.info(OPT_SELECT_MSG , select.first_selected_option.text)
        return select.first_selected_option.text
    except NoSuchElementException as no_element:
        err_msg = NO_ELEMENT_MSG % (p_distrito, \
                     type(no_element).__name__, no_element)
        log.critical(msg=err_msg)
        now = datetime.now().strftime('%d%m%Y_%H%M%S')
        file_name = LOG_WEBDRIVER_ERROR % set_district.__name__, now
        driver.get_screenshot_as_file(filename=file_name)
        raise no_element


def set_local(driver, p_localidade):
    """Function to set local field."""
    try:
        id_localidade = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.ID, 'IdLocalidade'))
        )
        select = Select(id_localidade)
        time.sleep(2)
        select.select_by_value(str(p_localidade))
        log.info(OPT_SELECT_MSG , select.first_selected_option.text)
        return select.first_selected_option.text
    except NoSuchElementException as no_element:
        err_msg = NO_ELEMENT_MSG % (p_localidade, \
                     type(no_element).__name__, no_element)
        log.critical(msg=err_msg)
        now = datetime.now().strftime('%d%m%Y_%H%M%S')
        file_name = LOG_WEBDRIVER_ERROR % set_local.__name__, now
        driver.get_screenshot_as_file(filename=file_name)
        raise no_element


def set_service_desk(driver, p_local_atendimento):
    """Function to set service field."""
    try:
        id_local_atendimento = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.ID, 'IdLocalAtendimento'))
        )
        select = Select(id_local_atendimento)
        time.sleep(2)
        select.select_by_value(str(p_local_atendimento))
        log.info(OPT_SELECT_MSG , select.first_selected_option.text)
        return select.first_selected_option.text
    except NoSuchElementException as no_element:
        err_msg = NO_ELEMENT_MSG % (p_local_atendimento, \
                     type(no_element).__name__, no_element)
        log.critical(msg=err_msg)
        now = datetime.now().strftime('%d%m%Y_%H%M%S')
        file_name = LOG_WEBDRIVER_ERROR % set_service_desk.__name__, now
        driver.get_screenshot_as_file(filename=file_name)
        raise no_element


def set_step_two(driver):
    """Function to click button."""
    try:
        next_button = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.XPATH,
                                            "//li[@id='liProximoButton']\
                                                //a[@class='set-date-button']"))
        )
        driver.get_screenshot_as_file(f'log_step{2}.png')
        driver.execute_script("arguments[0].click();", next_button) # next_button.click()
        log.info('Botão "Next" clicado com sucesso!')
    except ElementClickInterceptedException as no_button:
        err_msg = NO_BUTTON_MSG % (next_button)
        log.critical(msg=err_msg)
        now = datetime.now().strftime('%d%m%Y_%H%M%S')
        file_name = LOG_WEBDRIVER_ERROR % set_step_two.__name__, now
        driver.get_screenshot_as_file(filename=file_name)
        raise no_button


def set_category(driver, p_category):
    """Function to set category field."""
    try:
        id_category_select = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, 'IdCategoria'))
        )
        select = Select(id_category_select)
        time.sleep(2)
        select.select_by_value(str(p_category))
        log.info(OPT_SELECT_MSG , select.first_selected_option.text)
        return select.first_selected_option.text
    except NoSuchElementException as no_element:
        err_msg = NO_ELEMENT_MSG % (p_category, type(no_element).__name__, no_element)
        log.critical(msg=err_msg)
        now = datetime.now().strftime('%d%m%Y_%H%M%S')
        file_name = LOG_WEBDRIVER_ERROR % (set_category.__name__, now)
        driver.get_screenshot_as_file(filename=file_name)
        raise no_element


def set_subcategory(driver, p_subcategory):
    """Function to set subcategory field."""
    try:
        id_subcategory_select = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, 'IdSubcategoria'))
        )
        select = Select(id_subcategory_select)
        time.sleep(2)
        select.select_by_value(str(p_subcategory))
        txt = select.first_selected_option.text
        log.info(OPT_SELECT_MSG , txt)
        return txt
    except NoSuchElementException as no_element:
        err_msg = NO_ELEMENT_MSG % (p_subcategory, type(no_element).__name__, no_element)
        log.critical(msg=err_msg)
        now = datetime.now().strftime('%d%m%Y_%H%M%S')
        file_name = LOG_WEBDRIVER_ERROR % (set_subcategory.__name__, now)
        driver.get_screenshot_as_file(filename=file_name)
        raise no_element


def set_motive(driver, p_motive):
    """Function to set motive field."""
    try:
        id_motive_select = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, 'IdMotivo'))
        )
        select = Select(id_motive_select)
        time.sleep(2)
        select.select_by_value(str(p_motive))
        txt = select.first_selected_option.text
        log.info(OPT_SELECT_MSG , txt)
        return txt
    except NoSuchElementException as no_element:
        err_msg = NO_ELEMENT_MSG % (p_motive, type(no_element).__name__, no_element)
        log.critical(msg=err_msg)
        now = datetime.now().strftime('%d%m%Y_%H%M%S')
        file_name = LOG_WEBDRIVER_ERROR % (set_motive.__name__, now)
        driver.get_screenshot_as_file(filename=file_name)
        raise no_element


def set_step_three(driver):
    """Function to click button."""
    try:
        if check_elem_exists(driver, By.CLASS_NAME, "set-date-button"):
            next_button = WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located((By.XPATH,
                                                "//li[@id='liProximoButton']\
                                                    //a[@class='set-date-button']"))
            )
            driver.get_screenshot_as_file(f'log_step{3}.png')
            driver.execute_script("arguments[0].click();", next_button) # next_button.click()
            log.info('Botão "Next" clicado com sucesso!')
        else:
            log.critical('Cannot find step-three button')
    except ElementClickInterceptedException as no_button:
        err_msg = NO_BUTTON_MSG % (next_button)
        log.critical(msg=err_msg)
        now = datetime.now().strftime('%d%m%Y_%H%M%S')
        file_name = LOG_WEBDRIVER_ERROR % (set_step_two.__name__, now)
        driver.get_screenshot_as_file(filename=file_name)
        raise no_button

#return boolean value instead of throwing exception
def check_elem_exists(parent, by, selector, wait=False, timeout=False):
    """Function to check if the element exists on the loaded page."""
    ret = None
    if not wait:
        try:
            parent.find_element(by, selector)
        except NoSuchElementException:
            ret = False
        else:
            ret = True
    else:
        #when allowing wait time - print note for what is happening
        log.info('%s - check_elem_exists(%is..)' , selector,timeout)
        try:
            WebDriverWait(parent, timeout).until(EC.presence_of_element_located((by, selector)))
        except NoSuchElementException:
            ret = False
        except TimeoutException:
            ret = False
        else:
            ret = True

    return ret

def word_in_center(string):
    """Function to print a string in center."""
    return f'{string:-^100}'


def get_time_slots(driver, days_max):
    """Function to get all the schedule available."""

    date_max_days = (datetime.now() + timedelta(days=days_max))
    log.info('Max date to search for time slots: %s', date_max_days.strftime("%d-%m-%Y"))

    schedule_list = driver.find_elements(By.XPATH, \
                                         '//div[@class="schedule-list"]\
                                            //div[starts-with(@class, "col-md-5 m-")]')
    if schedule_list:
        for time_slots in schedule_list:
            if time_slots:
                available_dates = re.search('(\\d{2}-\\d{2}-\\d{4})',
                                            time_slots.find_element(By.TAG_NAME, "span").text[0:18])
                date_now = datetime.strptime(available_dates.group(),'%d-%m-%Y')
                if date_now <= date_max_days: #filters de time slots by maximum date wanted
                    TIME_SLOT_LIST[time_slots.get_attribute("title")].append( \
                        time_slots.find_element(By.TAG_NAME, "span").text[0:18])

    if TIME_SLOT_LIST:
        log.info('|'*100)
        log.info('Slots found: %s' , TIME_SLOT_LIST)
        log.info('|'*100)

    try:
        if check_elem_exists(driver, By.CLASS_NAME, "error-message"):
            error_message_div = WebDriverWait(driver, 20).until(
                EC.visibility_of_element_located((By.XPATH, \
                                                  '//div[@class="error-message"]\
                                                    //div[@class="col-md-12 no_padding"]'))
            )

            h5_element = error_message_div.find_element(By.TAG_NAME, 'h5')
            log.info('*'*100)
            log.info(h5_element.text)
            log.info('*'*100)

    except NoSuchElementException as no_element:
        log.critical('No error message')
        log.critical("%s was raised: %s", type(no_element).__name__, no_element)
    except TimeoutException as timeout:
        log.critical('No error message')
        log.critical("%s was raised: %s" , type(timeout).__name__, timeout)


def check_schedule(driver, config_instance) -> NotificationData:
    """Function to manage the automation search."""
    msg_header = NotificationData()

    try:
        now = datetime.now()
        log.info('Start of check_schedule: %s', now.strftime("%H:%M:%S"))

        max_days = config_instance.get_value_by_key('max_days')

        l_screen_shot = 'log_step{}.png'
        l_location_opt = config_instance.get_value_by_key('location_opt')
        l_service_opt = config_instance.get_value_by_key('service_opt')
        l_distrito  = l_location_opt.get('distrito', '')
        l_localidade = l_location_opt.get('localidade', '')
        l_local_atendimento = l_location_opt.get('local_atendimento', '')

        if l_service_opt and l_location_opt:
            # Step 1: Set entity
            driver.get_screenshot_as_file(l_screen_shot.format(1))
            msg_header.set_entity(set_entity(driver,
                                             config_instance.get_value_by_key('entity_opt')))

            # Step 2: Set category, subcategory, and motive
            msg_header.set_category(set_category(driver, l_service_opt.get("tema", '')))
            msg_header.set_subcategory(set_subcategory(driver, l_service_opt.get("subtema", '')))
            msg_header.set_motive(set_motive(driver, l_service_opt.get("motivo", '')))
            driver.get_screenshot_as_file(l_screen_shot.format(2))
            set_step_two(driver)

            # Step 3: Set district, local, and service desk
            msg_header.set_district(set_district(driver, l_distrito))
            msg_header.set_local(set_local(driver, l_localidade))
            if l_localidade > 0 and l_local_atendimento:
                msg_header.set_service_desk(set_service_desk(driver, l_local_atendimento))
            driver.get_screenshot_as_file(l_screen_shot.format(3))
            set_step_three(driver)

            driver.get_screenshot_as_file(l_screen_shot.format(4))
            get_time_slots(driver, max_days)

            log.info('End of check_schedule: %s', datetime.now().strftime("%H:%M:%S"))
        else:
            log.critical('Empty parameter: p_service_opt')

        return msg_header

    except WebDriverException as wd:
        log.error('WebDriverException in check_schedule: %s', wd)
        log_exception(wd)
    except Exception as ex:
        log.error('Exception in check_schedule: %s', ex)
        raise


def task(config_instance) -> None:
    """Function to start the tasks."""
    now = datetime.now()
    log.info('>' * 100)
    log.info(word_in_center(' Task Start '))
    start_time = config_instance.get_value_by_key('start_time')
    end_time = config_instance.get_value_by_key('end_time')
    if start_time <= now.strftime("%H:%M") <= end_time:
        driver = start_chrome()
        msg = check_schedule(driver, config_instance)
        close_chrome(driver)
        send_message(msg)
    else:
        log.info('Outside business hours')
    log.info(word_in_center(' Task End '))
    log.info('<'*100)


def main() -> None:
    """Main."""

    def set_schedule(config_instance) -> None:
        frequency_opt = config_instance.get_value_by_key('frequency')
        log.info('Scheduling configured for: %s', config_instance.get_value_by_key('title'))
        sd.every(frequency_opt).minutes.do(task,
                                           config_instance) \
                                            .tag('siga-tasks',
                                                 config_instance.get_value_by_key('title'))

    check_dotenv_siga()
    yaml_instance = YamlLoader("search_config.yaml")
    for config in yaml_instance.get_instances():
        set_schedule(config)

    while True:
        sd.run_pending()
        time.sleep(1)


def log_exception(exception):
    """
    Log an exception.
    Args:
        exception: The exception to log.
    """
    log.error(exception.__class__.__name__)
    log.error(exception)
    log.error(traceback.format_exc())


#------------------------------------------------------------------------------
if __name__ == "__main__":
    # execute only if run as a script
    try:
        log.info("Press CTRL + C to cancel.")
        main()
    except FileNotFoundError as e:
        log_exception(e)
        os._exit(1)
    except (KeyboardInterrupt, EOFError):
        log.info(word_in_center(' Interrupted by user '))
    except SystemExit as e:
        log.error(word_in_center(' Interrupted by system '))
        log_exception(e)
        raise e
    except Exception as e:
        log.error(word_in_center(' Interrupted by system '))
        log_exception(e)
