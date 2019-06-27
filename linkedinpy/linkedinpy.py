"""OS Modules environ method to get the setup vars from the Environment"""
# import built-in & third-party modules
import time
from math import ceil
import random
from sys import platform
from platform import python_version
import os
import json
import sqlite3

import pprint as pp

from selenium.webdriver.common.action_chains import ActionChains

from pyvirtualdisplay import Display
import logging
from contextlib import contextmanager
from copy import deepcopy
from sys import exit as clean_exit
from tempfile import gettempdir

from .login_util import login_user

from socialcommons.time_util import sleep

from .util import update_activity
from .util import web_address_navigator
from .util import interruption_handler
from .util import highlight_print
from .util import truncate_float
from .util import save_account_progress
from .util import parse_cli_args

from .database_engine import get_database
from socialcommons.browser import set_selenium_local_session
from socialcommons.browser import close_browser
from socialcommons.file_manager import get_workspace
from socialcommons.file_manager import get_logfolder

from socialcommons.quota_supervisor import quota_supervisor

from .unconnect_util import connect_restriction

# import exceptions
from selenium.common.exceptions import NoSuchElementException
from socialcommons.exceptions import SocialPyError
from .settings import Settings

class LinkedinPy:
    """Class to be instantiated to use the script"""
    def __init__(self,
                 username=None,
                 userid=None,
                 password=None,
                 nogui=False,
                 selenium_local_session=True,
                 use_firefox=False,
                 browser_profile_path=None,
                 page_delay=25,
                 show_logs=True,
                 headless_browser=False,
                 proxy_address=None,
                 proxy_chrome_extension=None,
                 proxy_port=None,
                 disable_image_load=False,
                 bypass_suspicious_attempt=False,
                 bypass_with_mobile=False,
                 multi_logs=True):

        cli_args = parse_cli_args()
        username = cli_args.username or username
        password = cli_args.password or password
        use_firefox = cli_args.use_firefox or use_firefox
        page_delay = cli_args.page_delay or page_delay
        headless_browser = cli_args.headless_browser or headless_browser
        proxy_address = cli_args.proxy_address or proxy_address
        proxy_port = cli_args.proxy_port or proxy_port
        disable_image_load = cli_args.disable_image_load or disable_image_load
        bypass_suspicious_attempt = (
            cli_args.bypass_suspicious_attempt or bypass_suspicious_attempt)
        bypass_with_mobile = cli_args.bypass_with_mobile or bypass_with_mobile
        if not get_workspace(Settings):
            raise SocialPyError(
                "Oh no! I don't have a workspace to work at :'(")

        self.nogui = nogui
        if nogui:
            self.display = Display(visible=0, size=(800, 600))
            self.display.start()

        self.browser = None
        self.headless_browser = headless_browser
        self.proxy_address = proxy_address
        self.proxy_port = proxy_port
        self.proxy_chrome_extension = proxy_chrome_extension
        self.selenium_local_session = selenium_local_session
        self.bypass_suspicious_attempt = bypass_suspicious_attempt
        self.bypass_with_mobile = bypass_with_mobile
        self.disable_image_load = disable_image_load

        self.username = username or os.environ.get('LINKEDIN_USER')
        self.password = password or os.environ.get('LINKEDIN_PW')
        Settings.profile["name"] = self.username

        self.page_delay = page_delay
        self.switch_language = True
        self.use_firefox = use_firefox
        Settings.use_firefox = self.use_firefox
        self.browser_profile_path = browser_profile_path
        self.liked_img = 0
        self.already_liked = 0
        self.liked_comments = 0
        self.commented = 0
        self.replied_to_comments = 0
        self.connected = 0
        self.already_connected = 0
        self.unconnected = 0
        self.connected_by = 0
        self.connecting_num = 0
        self.inap_img = 0
        self.not_valid_users = 0
        self.connect_times = 1
        self.start_time = time.time()

        # assign logger
        self.show_logs = show_logs
        Settings.show_logs = show_logs or None
        self.multi_logs = multi_logs
        self.logfolder = get_logfolder(self.username, self.multi_logs, Settings)
        self.logger = self.get_linkedinpy_logger(self.show_logs)

        get_database(Settings, make=True)  # IMPORTANT: think twice before relocating

        if self.selenium_local_session is True:
            self.set_selenium_local_session(Settings)

    def get_linkedinpy_logger(self, show_logs):
        """
        Handles the creation and retrieval of loggers to avoid
        re-instantiation.
        """

        existing_logger = Settings.loggers.get(self.username)
        if existing_logger is not None:
            return existing_logger
        else:
            # initialize and setup logging system for the LinkedinPy object
            logger = logging.getLogger(self.username)
            logger.setLevel(logging.DEBUG)
            file_handler = logging.FileHandler(
                '{}general.log'.format(self.logfolder))
            file_handler.setLevel(logging.DEBUG)
            extra = {"username": self.username}
            logger_formatter = logging.Formatter(
                '%(levelname)s [%(asctime)s] [%(username)s]  %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(logger_formatter)
            logger.addHandler(file_handler)

            if show_logs is True:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                console_handler.setFormatter(logger_formatter)
                logger.addHandler(console_handler)

            logger = logging.LoggerAdapter(logger, extra)

            Settings.loggers[self.username] = logger
            Settings.logger = logger
            return logger

    def set_selenium_local_session(self, Settings):
        self.browser, err_msg = \
            set_selenium_local_session(self.proxy_address,
                                       self.proxy_port,
                                       self.proxy_chrome_extension,
                                       self.headless_browser,
                                       self.use_firefox,
                                       self.browser_profile_path,
                                       # Replaces
                                       # browser User
                                       # Agent from
                                       # "HeadlessChrome".
                                       self.disable_image_load,
                                       self.page_delay,
                                       self.logger,
                                       Settings)
        if len(err_msg) > 0:
            raise SocialPyError(err_msg)

    def login(self):
        """Used to login the user either with the username and password"""
        if not login_user(self.browser,
                          self.username,
                          None,
                          self.password,
                          self.logger,
                          self.logfolder,
                          self.switch_language,
                          self.bypass_suspicious_attempt,
                          self.bypass_with_mobile):
            message = "Wrong login data!"
            highlight_print(Settings, self.username,
                            message,
                            "login",
                            "critical",
                            self.logger)

            # self.aborting = True

        else:
            message = "Logged in successfully!"
            highlight_print(Settings, self.username,
                            message,
                            "login",
                            "info",
                            self.logger)
            # try to save account progress
            try:
                save_account_progress(self.browser,
                                    "https://www.linkedin.com/",
                                    self.username,
                                    self.logger)
            except Exception:
                self.logger.warning(
                    'Unable to save account progress, skipping data update')
        return self

    def withdraw_old_invitations(self,
            skip_pages=10,
            sleep_delay=6):
        page_no = skip_pages
        while page_no < 100:
            page_no = page_no + 1
            try:
                url = "https://www.linkedin.com/mynetwork/invitation-manager/sent/?page=" + str(page_no)
                web_address_navigator(Settings,self.browser, url)
                print("Starting page:", page_no)
                if self.browser.current_url=="https://www.linkedin.com/mynetwork/invitation-manager/sent/" or len(self.browser.find_elements_by_css_selector("li.invitation-card div.pl5"))==0:
                    print("============Last Page Reached==============")
                    break
                checked_in_page = 0
                for i in range(0, len(self.browser.find_elements_by_css_selector("li.invitation-card div.pl5"))):
                    try:
                        res_item = self.browser.find_elements_by_css_selector("li.invitation-card div.pl5")[i]
                        try:
                            link = res_item.find_element_by_css_selector("div > a")
                            profile_link = link.get_attribute("href")
                            user_name = profile_link.split('/')[4]
                            self.logger.info("user_name : {}".format(user_name))
                        except Exception as e:
                            print("Might be a stale profile", e)
                        time = res_item.find_element_by_css_selector("div > time")
                        self.logger.info("time : {}".format(time.text))
                        check_button = res_item.find_element_by_css_selector("div > div:nth-child(1) > input")
                        check_status = check_button.get_attribute("data-artdeco-is-focused")
                        self.logger.info("check_status : {}".format(check_status))

                        self.browser.execute_script("window.scrollTo(0, " + str((i+1)*104) + ");")

                        if "month" in time.text:
                            (ActionChains(self.browser)
                             .move_to_element(check_button)
                             .click()
                             .perform())
                            self.logger.info("check_button clicked")
                            checked_in_page = checked_in_page + 1
                            delay_random = random.randint(
                                        ceil(sleep_delay * 0.42),
                                        ceil(sleep_delay * 0.57))
                            sleep(delay_random)
                    except Exception as e:
                        self.logger.error(e)
                if checked_in_page > 0:
                    self.logger.info("Widraw to be pressed")
                    try:
                        self.browser.execute_script("window.scrollTo(0, 0);")
                        withdraw_button = self.browser.find_element_by_css_selector("ul > li.mn-list-toolbar__right-button > button")
                        self.logger.info("withdraw_button : {}".format(withdraw_button.text))
                        if "Withdraw" in withdraw_button.text:
                            (ActionChains(self.browser)
                             .move_to_element(withdraw_button)
                             .click()
                             .perform())
                            self.logger.info("withdraw_button clicked")
                            page_no = page_no - 1
                            delay_random = random.randint(
                                        ceil(sleep_delay * 0.85),
                                        ceil(sleep_delay * 1.14))
                            sleep(delay_random)
                    except Exception as e:
                        print("For some reason there is no withdraw_button inspite of checkings", e)
                else:
                    self.logger.info("Nothing checked in this page")
            except Exception as e:
                self.logger.error(e)
            self.logger.info("============Next Page==============")


    def search_1stconnects_and_savetodb(self,
              query,
              city_code,
              school_code=None,
              past_company=None,
              random_start=True,
              max_pages=10,
              max_connects=25,
              sleep_delay=6):
        """ search linkedin and connect from a given profile """

        self.logger.info("Searching for: query={}, city_code={}, school_code={}".format(query, city_code, school_code))
        search_url = "https://www.linkedin.com/search/results/people/?&facetNetwork=%5B%22F%22%5D"
        if city_code:
            search_url = search_url + "&facetGeoRegion=" + city_code
        if school_code:
            search_url = search_url + "&facetSchool=" + school_code
        if past_company:
            search_url = search_url + "&facetPastCompany=" + past_company

        search_url = search_url + "&keywords=" + query
        search_url = search_url + "&origin=" + "FACETED_SEARCH"

        for page_no in range(1,101):
            try:
                temp_search_url = search_url + "&page=" + str(page_no)
                web_address_navigator(Settings,self.browser, temp_search_url)
                self.logger.info("Starting page: {}".format(page_no))

                for jc in range(2, 11):
                    sleep(1)
                    self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight/" + str(jc) + ");")

                if len(self.browser.find_elements_by_css_selector("div.search-result__wrapper"))==0:
                    self.logger.info("============Last Page Reached or asking for Premium membership==============")
                    break
                for i in range(0, len(self.browser.find_elements_by_css_selector("div.search-result__wrapper"))):
                    try:
                        res_item = self.browser.find_elements_by_css_selector("li.search-result div.search-entity div.search-result__wrapper")[i]
                        link = res_item.find_element_by_css_selector("div > a")
                        profile_link = link.get_attribute("href")
                        user_name = profile_link.split('/')[4]
                        self.logger.info("user_name : {}".format(user_name))
                        msg_button = res_item.find_element_by_xpath("//div[3]/div/div/button[text()='Message']")
                        print(msg_button.text, "present")
                        if msg_button.text=="Message":
                            connect_restriction("write", user_name, None, self.logger)
                            self.logger.info("saved {} to db".format(user_name))
                    except Exception as e:
                        self.logger.error(e)
            except Exception as e:
                self.logger.error(e)
            self.logger.info("============Next Page==============")

    def test_page(self, search_url, page_no):
        web_address_navigator(Settings,self.browser, search_url)
        self.logger.info("Testing page: {}".format(page_no))
        if len(self.browser.find_elements_by_css_selector("div.search-result__wrapper")) > 0:
            return True
        return False

    def search_and_connect(self,
              query,
              connection_relationship_code,
              city_code,
              school_code=None,
              past_company=None,
              random_start=True,
              max_pages=10,
              max_connects=25,
              sleep_delay=6):
        """ search linkedin and connect from a given profile """

        if quota_supervisor(Settings, "connects") == "jump":
            return 0

        self.logger.info("Searching for: query={}, connection_relationship_code={}, city_code={}, school_code={}".format(query, connection_relationship_code, city_code, school_code))
        connects = 0
        prev_connects = -1
        search_url = "https://www.linkedin.com/search/results/people/?"
        if connection_relationship_code:
            search_url = search_url + "&facetNetwork=" + connection_relationship_code
        if city_code:
            search_url = search_url + "&facetGeoRegion=" + city_code
        if school_code:
            search_url = search_url + "&facetSchool=" + school_code
        if past_company:
            search_url = search_url + "&facetPastCompany=" + past_company

        search_url = search_url + "&keywords=" + query
        search_url = search_url + "&origin=" + "FACETED_SEARCH"


        temp_search_url = search_url + "&page=1"
        print(temp_search_url)
        time.sleep(10)
        if self.test_page(search_url=temp_search_url, page_no=1)==False:
            self.logger.info("============Definitely no Result, Next Query==============")
            return 0

        if random_start:
            trial = 0
            st = 5
            while True and trial < 5 and st > 1:
                st = random.randint(1, st-1)
                temp_search_url = search_url + "&page=" + str(st)
                if self.test_page(temp_search_url,st):
                    break
                trial = trial + 1
        else:
            st = 1

        for page_no in list(range(st, st + max_pages)):

            if prev_connects==connects:
                self.logger.info("============Limits might have exceeded or all Invites pending from this page(let's exit either case)==============")
                break
            else:
                prev_connects = connects

            try:
                temp_search_url = search_url + "&page=" + str(page_no)
                if page_no > st and st > 1:
	                web_address_navigator(Settings,self.browser, temp_search_url)
                self.logger.info("Starting page: {}".format(page_no))

                for jc in range(2, 11):
                    sleep(1)
                    self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight/" + str(jc) + "-100);")

                if len(self.browser.find_elements_by_css_selector("div.search-result__wrapper"))==0:
                    self.logger.info("============Last Page Reached or asking for Premium membership==============")
                    break
                for i in range(0, len(self.browser.find_elements_by_css_selector("div.search-result__wrapper"))):
                    try:
                        res_item = self.browser.find_elements_by_css_selector("li.search-result div.search-entity div.search-result__wrapper")[i]# div.search-result__actions div button")
                        # pp.pprint(res_item.get_attribute('innerHTML'))
                        link = res_item.find_element_by_css_selector("div > a")
                        profile_link = link.get_attribute("href")
                        self.logger.info("Profile : {}".format(profile_link))
                        user_name = profile_link.split('/')[4]
                        # self.logger.info("user_name : {}".format(user_name))
                        name = res_item.find_element_by_css_selector("h3 > span > span > span")#//span/span/span[1]")
                        self.logger.info("Name : {}".format(name.text))

                        if connect_restriction("read", user_name,  self.connect_times, self.logger):
                            self.logger.info("already connected")
                            continue

                        try:
                            connect_button = res_item.find_element_by_xpath("//div[3]/div/button[text()='Connect']")
                            self.logger.info("Connect button found, connecting...")
                            self.browser.execute_script("var evt = document.createEvent('MouseEvents');" + "evt.initMouseEvent('click',true, true, window, 0, 0, 0, 0, 0, false, false, false, false, 0,null);" + "arguments[0].dispatchEvent(evt);", res_item.find_element_by_xpath('//div[3]/div/button[text()="Connect"]'))
                            self.logger.info("Clicked {}".format(connect_button.text))
                            sleep(2)
                        except Exception:
                            invite_sent_button = res_item.find_element_by_xpath("//div[3]/div/button[text()='Invite Sent']")
                            self.logger.info("Already {}".format(invite_sent_button.text))
                            continue

                        try:
                            modal = self.browser.find_element_by_css_selector("div.modal-wormhole-content > div")
                            if modal:
                                try:
                                    sendnow_or_done_button = modal.find_element_by_xpath("//div[1]/div/section/div/div[2]/button[2]")#text()='Send now']")
                                    self.logger.info(sendnow_or_done_button.text)
                                    if not (sendnow_or_done_button.text=='Done' or sendnow_or_done_button.text=='Send now'):
                                        raise Exception("Send Now or Done button not found")
                                    if sendnow_or_done_button.is_enabled():
                                        (ActionChains(self.browser)
                                         .move_to_element(sendnow_or_done_button)
                                         .click()
                                         .perform())
                                        self.logger.info("Clicked {}".format(sendnow_or_done_button.text))
                                        connects = connects + 1
                                        connect_restriction("write", user_name, None, self.logger)
                                        try:
                                            # update server calls
                                            update_activity(Settings, 'connects')
                                        except Exception as e:
                                            self.logger.error(e)
                                        sleep(2)
                                    else:
                                        try:
                                            #TODO: input("find correct close XPATH")
                                            close_button = modal.find_element_by_xpath("//div[1]/div/section/div/header/button")
                                            (ActionChains(self.browser)
                                             .move_to_element(close_button)
                                             .click()
                                             .perform())
                                            print(sendnow_or_done_button.text, "disabled, clicked close")
                                            sleep(2)
                                        except Exception as e:
                                            print("close_button not found, Failed with:", e)
                                except Exception as e:
                                    print("sendnow_or_done_button not found, Failed with:", e)
                            else:
                                self.logger.info("Popup not found")
                        except Exception as e:
                            print("Popup not found, Failed with:", e)
                            try:
                                new_popup_buttons = self.browser.find_elements_by_css_selector("#artdeco-modal-outlet div.artdeco-modal-overlay div.artdeco-modal div.artdeco-modal__actionbar button.artdeco-button")
                                gotit_button = new_popup_buttons[1]
                                (ActionChains(self.browser)
                                 .move_to_element(gotit_button)
                                 .click()
                                 .perform())
                                print(gotit_button.text, " clicked")
                                sleep(2)
                            except Exception as e:
                                print("New Popup also not found, Failed with:", e)

                        self.logger.info("Connects sent in this iteration: {}".format(connects))
                        delay_random = random.randint(
                                    ceil(sleep_delay * 0.85),
                                    ceil(sleep_delay * 1.14))
                        sleep(delay_random)
                        if connects >= max_connects:
                            self.logger.info("max_connects({}) for this iteration reached , Returning...".format(max_connects))
                            return
                    except Exception as e:
                        self.logger.error(e)
            except Exception as e:
                self.logger.error(e)
            self.logger.info("============Next Page==============")
            return connects

    def endorse(self,
              profile_link,
              sleep_delay):
        try:
            web_address_navigator(Settings,self.browser, profile_link)

            for jc in range(1, 10):
                sleep(1)
                self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight*" + str(jc) + "/10);")

            skills_pane = self.browser.find_element_by_css_selector("div.profile-detail > div.pv-deferred-area > div > section.pv-profile-section.pv-skill-categories-section")
            if (skills_pane.text.split('\n')[0] == 'Skills & Endorsements'):
                try:
                    first_skill_button_icon = self.browser.find_element_by_css_selector("div.profile-detail > div.pv-deferred-area > div > section.pv-profile-section.pv-skill-categories-section > ol > li > div > div > div > button > li-icon")
                    button_type = first_skill_button_icon.get_attribute("type")
                    if button_type=='plus-icon':
                        first_skill_button = self.browser.find_element_by_css_selector("div.profile-detail > div.pv-deferred-area > div > section.pv-profile-section.pv-skill-categories-section > ol > li > div > div > div > button")
                        self.browser.execute_script("var evt = document.createEvent('MouseEvents');" + "evt.initMouseEvent('click',true, true, window, 0, 0, 0, 0, 0, false, false, false, false, 0,null);" + "arguments[0].dispatchEvent(evt);", first_skill_button)
                        first_skill_title = self.browser.find_element_by_css_selector("div.profile-detail > div.pv-deferred-area > div > section.pv-profile-section.pv-skill-categories-section > ol > li > div > div > p > a > span")
                        print(first_skill_title.text, "clicked")
                        delay_random = random.randint(
                                    ceil(sleep_delay * 0.85),
                                    ceil(sleep_delay * 1.14))
                        sleep(delay_random)
                    else:
                        self.logger.info('button_type already {}'.format(button_type))
                except Exception as e:
                    self.logger.error(e)
            else:
                self.logger.info('Skill & Endorsements pane not found')
        except Exception as e:
            self.logger.error(e)

    def search_and_endorse(self,
              query,
              city_code,
              school_code,
              random_start=True,
              max_pages=3,
              max_endorsements=25,
              sleep_delay=6):
        """ search linkedin and endose few first connections """

        if quota_supervisor(Settings, "connects") == "jump":
            return #False, "jumped"

        print("Searching for: ", query, city_code, school_code)
        search_url = "https://www.linkedin.com/search/results/people/?"
        if city_code:
            search_url = search_url + "&facetGeoRegion=" + city_code
        if school_code:
            search_url = search_url + "&facetSchool=" + school_code

        search_url = search_url + "&facetNetwork=%5B%22F%22%5D"
        search_url = search_url + "&keywords=" + query
        search_url = search_url + "&origin=" + "FACETED_SEARCH"

        if random_start:
            trial = 0
            while True and trial < 3:
                st = random.randint(1, 3)
                temp_search_url = search_url + "&page=" + str(st)
                web_address_navigator(Settings,self.browser, temp_search_url)
                self.logger.info("Testing page:".format(st))
                result_items = self.browser.find_elements_by_css_selector("div.search-result__wrapper")
                if len(result_items) > 0:
                    break
                trial = trial + 1
        else:
            st = 1

        connects = 0
        for page_no in list(range(st, st + 1)):
            collected_profile_links = []
            try:
                temp_search_url = search_url + "&page=" + str(page_no)
                if page_no > st and st > 1:
	                web_address_navigator(Settings,self.browser, temp_search_url)
                self.logger.info("Starting page: {}".format(page_no))

                for jc in range(2, 11):
                    sleep(1)
                    self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight/" + str(jc) + "-100);")

                result_items = self.browser.find_elements_by_css_selector("div.search-result__wrapper")

                # print(result_items)
                for result_item in result_items:
                    try:
                        link = result_item.find_element_by_css_selector("div > a")
                        self.logger.info("Profile : {}".format(link.get_attribute("href")))
                        collected_profile_links.append(link.get_attribute("href"))
                        name = result_item.find_element_by_css_selector("h3 > span > span > span")
                        self.logger.info("Name : {}".format(name.text))
                    except Exception as e:
                        self.logger.error(e)
            except Exception as e:
                self.logger.error(e)

            for collected_profile_link in collected_profile_links:
                self.endorse(collected_profile_link, sleep_delay=sleep_delay)
                connects = connects + 1
                if connects >= max_endorsements:
                    self.logger.info("max_endorsements({}) for this iteration reached , Returning...".format(max_endorsements))
                    return


            self.logger.info("============Next Page==============")


    def dump_connect_restriction(self, profile_name, logger, logfolder):
        """ Dump connect restriction data to a local human-readable JSON """

        try:
            # get a DB and start a connection
            db, id = get_database(Settings)
            conn = sqlite3.connect(db)

            with conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                cur.execute(
                    "SELECT * FROM connectRestriction WHERE profile_id=:var",
                    {"var": id})
                data = cur.fetchall()

            if data:
                # get the existing data
                filename = "{}connectRestriction.json".format(logfolder)
                if os.path.isfile(filename):
                    with open(filename) as connectResFile:
                        current_data = json.load(connectResFile)
                else:
                    current_data = {}

                # pack the new data
                connect_data = {user_data[1]: user_data[2] for user_data in
                               data or []}
                current_data[profile_name] = connect_data

                # dump the fresh connect data to a local human readable JSON
                with open(filename, 'w') as connectResFile:
                    json.dump(current_data, connectResFile)

        except Exception as exc:
            logger.error(
                "Pow! Error occurred while dumping connect restriction data to a "
                "local JSON:\n\t{}".format(
                    str(exc).encode("utf-8")))

        finally:
            if conn:
                # close the open connection
                conn.close()

    def end(self):
        """Closes the current session"""

        # IS_RUNNING = False
        close_browser(self.browser, False, self.logger)

        with interruption_handler():
            # close virtual display
            if self.nogui:
                self.display.stop()

            # write useful information
            self.dump_connect_restriction(self.username,
                                    self.logger,
                                    self.logfolder)
            # dump_record_activity(self.username,
            #                      self.logger,
            #                      self.logfolder,
            #                      Settings)

            with open('{}connected.txt'.format(self.logfolder), 'w') \
                    as connectFile:
                connectFile.write(str(self.connected))

            # output live stats before leaving
            self.live_report()

            message = "Session ended!"
            highlight_print(Settings, self.username, message, "end", "info", self.logger)
            print("\n\n")

    def set_quota_supervisor(self,
                             Settings,
                             enabled=False,
                             sleep_after=[],
                             sleepyhead=False,
                             stochastic_flow=False,
                             notify_me=False,
                             peak_likes=(None, None),
                             peak_comments=(None, None),
                             peak_connects=(None, None),
                             peak_unconnects=(None, None),
                             peak_server_calls=(None, None)):
        """
         Sets aside QS configuration ANY time in a session
        """
        # take a reference of the global configuration
        configuration = Settings.QS_config

        # strong type checking on peaks entered
        peak_values_combined = [peak_likes, peak_comments, peak_connects,
                                peak_unconnects, peak_server_calls]
        peaks_are_tuple = all(type(item) is tuple for
                              item in peak_values_combined)

        if peaks_are_tuple:
            peak_values_merged = [i for sub in peak_values_combined
                                  for i in sub]
            integers_filtered = filter(lambda e: isinstance(e, int),
                                       peak_values_merged)

            peaks_are_provided = all(len(item) == 2 for
                                     item in peak_values_combined)
            peaks_are_valid = all(type(item) is int or type(item) is
                                  type(None) for item in peak_values_merged)
            peaks_are_good = all(item >= 0 for item in integers_filtered)

        # set QS if peak values are eligible
        if (peaks_are_tuple and
                peaks_are_provided and
                peaks_are_valid and
                peaks_are_good):

            peaks = {"likes": {"hourly": peak_likes[0],
                               "daily": peak_likes[1]},
                     "comments": {"hourly": peak_comments[0],
                                  "daily": peak_comments[1]},
                     "connects": {"hourly": peak_connects[0],
                                 "daily": peak_connects[1]},
                     "unconnects": {"hourly": peak_unconnects[0],
                                   "daily": peak_unconnects[1]},
                     "server_calls": {"hourly": peak_server_calls[0],
                                      "daily": peak_server_calls[1]}}

            if not isinstance(sleep_after, list):
                sleep_after = [sleep_after]

            rt = time.time()
            latesttime = {"hourly": rt, "daily": rt}
            orig_peaks = deepcopy(peaks)  # original peaks always remain static
            stochasticity = {"enabled": stochastic_flow,
                             "latesttime": latesttime,
                             "original_peaks": orig_peaks}

            if (platform.startswith("win32") and
                    python_version() < "2.7.15"):
                # UPDATE ME: remove this block once plyer is
                # verified to work on [very] old versions of Python 2
                notify_me = False

            # update QS configuration with the fresh settings
            configuration.update({"state": enabled,
                                  "sleep_after": sleep_after,
                                  "sleepyhead": sleepyhead,
                                  "stochasticity": stochasticity,
                                  "notify": notify_me,
                                  "peaks": peaks})

        else:
            # turn off QS for the rest of the session
            # since peak values are ineligible
            configuration.update(state="False")

            # user should be warned only if has had QS turned on
            if enabled is True:
                self.logger.warning("Quota Supervisor: peak rates are misfit! "
                                    "Please use supported formats."
                                    "\t~disabled QS")

    def live_report(self):
        """ Report live sessional statistics """

        print('')

        stats = [self.liked_img, self.already_liked,
                 self.commented,
                 self.connected, self.already_connected,
                 self.unconnected,
                 self.inap_img,
                 self.not_valid_users]

        if self.connecting_num and self.connected_by:
            owner_relationship_info = (
                "On session start was connectING {} users"
                " & had {} connectERS"
                .format(self.connecting_num,
                        self.connected_by))
        else:
            owner_relationship_info = ''

        sessional_run_time = self.run_time()
        run_time_info = ("{} seconds".format(sessional_run_time) if
                         sessional_run_time < 60 else
                         "{} minutes".format(truncate_float(
                             sessional_run_time / 60, 2)) if
                         sessional_run_time < 3600 else
                         "{} hours".format(truncate_float(
                             sessional_run_time / 60 / 60, 2)))
        run_time_msg = "[Session lasted {}]".format(run_time_info)

        if any(stat for stat in stats):
            self.logger.info(
                "Sessional Live Report:\n"
                "\t|> LIKED {} images  |  ALREADY LIKED: {}\n"
                "\t|> COMMENTED on {} images\n"
                "\t|> connected {} users  |  ALREADY connected: {}\n"
                "\t|> UNconnected {} users\n"
                "\t|> LIKED {} comments\n"
                "\t|> REPLIED to {} comments\n"
                "\t|> INAPPROPRIATE images: {}\n"
                "\t|> NOT VALID users: {}\n"
                "\n{}\n{}"
                .format(self.liked_img,
                        self.already_liked,
                        self.commented,
                        self.connected,
                        self.already_connected,
                        self.unconnected,
                        self.liked_comments,
                        self.replied_to_comments,
                        self.inap_img,
                        self.not_valid_users,
                        owner_relationship_info,
                        run_time_msg))
        else:
            self.logger.info("Sessional Live Report:\n"
                             "\t|> No any statistics to show\n"
                             "\n{}\n{}"
                             .format(owner_relationship_info,
                                     run_time_msg))

    def run_time(self):
        """ Get the time session lasted in seconds """

        real_time = time.time()
        run_time = (real_time - self.start_time)
        run_time = truncate_float(run_time, 2)

        return run_time

@contextmanager
def smart_run(session):
    try:
        if session.login():
            yield
        else:
            self.logger.info("Not proceeding as login failed")

    except (Exception, KeyboardInterrupt) as exc:
        if isinstance(exc, NoSuchElementException):
            # the problem is with a change in IG page layout
            log_file = "{}.html".format(time.strftime("%Y%m%d-%H%M%S"))
            file_path = os.path.join(gettempdir(), log_file)
            with open(file_path, "wb") as fp:
                fp.write(session.browser.page_source.encode("utf-8"))
            print("{0}\nIf raising an issue, "
                  "please also upload the file located at:\n{1}\n{0}"
                  .format('*' * 70, file_path))

        # provide full stacktrace (else than external interrupt)
        if isinstance(exc, KeyboardInterrupt):
            clean_exit("You have exited successfully.")
        else:
            raise

    finally:
        session.end()
