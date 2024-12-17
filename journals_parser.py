import os
import re
import csv
import json
import time
import copy
import random
import logging

from tqdm import tqdm
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError
from playwright.sync_api._generated import Page
from playwright_stealth import stealth_sync, StealthConfig

from typing import List, Dict, Union


logging.basicConfig(
    level=logging.INFO,
    filename = "parser_log.log",
    format = "%(asctime)s - %(module)s - %(levelname)s - %(funcName)s: %(lineno)d - %(message)s",
    datefmt='%H:%M:%S',
)


class CaptchaException(Exception):
    def __init__(self, *args):
        if args:
            self.message = args[0]
        else:
            self.message = None

    def __str__(self):
        if self.message:
            return 'CaptchaException, {0} '.format(self.message)
        else:
            return 'Error: Captcha detected'


class ElibraryParser():
    def __init__(self, headless_mode=False, proxy=None):
        self.playwright = sync_playwright().start()
        self.headless_mode = headless_mode
        self.browser = None
        self.context = None
        self.jrnls_issn_dict = {}
        self.issn_links_dict = {}
        self.proxy_cntr = 0
        self.proxy_pool = []
        self.proxy = proxy
        self.start_browser(headless_mode)
        self.last_opened_url = ""
        self.interest_cats = []
        self.max_retries = 50
        self.base_url = 'https://www.elibrary.ru'
        self.issn_codes_path = "./data/issn_codes.json"
        self.issn_links_path = "./data/issn_links.json"

    @classmethod
    def run_with_constant_proxy(cls, proxy_port=2000):
        proxy_ip = ""
        proxy_login = ""
        proxy_pass = ""

        proxy = {
             "server": f"http://{proxy_ip}:{proxy_port}",
             "username": proxy_login,
             "password": proxy_pass
        }
        return cls(proxy=proxy)

    @classmethod
    def run_with_proxy_pool(cls):
        proxy_pool = [
            {"server": "67.43.236.18:1853"}
        ]
        parser = cls(proxy=proxy_pool[0])
        parser.proxy_pool = proxy_pool
        return parser

    def start_browser(self, headless_mode=True):
        if self.context is not None:
            self.context.close()
            self.browser.close()
        self.browser = self.playwright.chromium.launch(headless=headless_mode,
                                                       proxy=self.proxy,
                                                       args=["--disable-web-security"],
                                                       )
        self.context = self.browser.new_context(ignore_https_errors=True,
                                                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36")

    def change_proxy(self):
        self.proxy_cntr += 1
        proxy_ip = ""
        proxy_port = 2001 + self.proxy_cntr
        proxy_login = ""
        proxy_pass = ""

        self.proxy = {
             "server": f"http://{proxy_ip}:{proxy_port}",
             "username": proxy_login,
             "password": proxy_pass
        }
        if self.proxy_cntr >= 445:
            logging.error("No more proxies")
            return False
        self.start_browser(self.headless_mode)
        return True

    def open_url(self, url, num_attempts=25) -> Page:
        cntr = 0
        status = True
        while True:
            page = self.context.new_page()
            config = StealthConfig(webdriver=True,
                                   webgl_vendor=True,
                                   chrome_app=True,
                                   chrome_csi=True,
                                   chrome_load_times=True,
                                   chrome_runtime=True,
                                   iframe_content_window=True,
                                   media_codecs=True,
                                   navigator_hardware_concurrency=4,
                                   navigator_languages=True,
                                   navigator_permissions=True,
                                   navigator_platform=True,
                                   navigator_plugins=True,
                                   navigator_user_agent=False,
                                   navigator_vendor=True,
                                   outerdimensions=True,
                                   hairline=True)
            stealth_sync(page, config=config)

            try:
                # page.on("request", lambda request: print(f"Запрос: {request.url}"))
                # page.on("response", lambda response: print(f"Ответ: {response.url}, статус: {response.status}"))
                page.goto(url)
                page.wait_for_load_state('networkidle')
                self._check_server_err(page)
                break
            except Exception as e:
                cntr += 1
                logging.error(f"Exception found while opening URL:\n {e}")
                if cntr < num_attempts:
                    logging.debug("Sleep and restart for trying again")
                    # time.sleep(30)
                    # self.start_browser(False)
                    if not self.change_proxy():
                        status = False
                        break
                else:
                    logging.error("Max attempts reached, stop parsing")
                    status = False
                    break

        if not status:
            raise RuntimeError(f"Error encountered while opening url {url}")
        self.last_opened_url = url
        # page.screenshot(path='./demo.png')
        return page

    def read_issn_json(self, path):
        with open(path) as f:
            json_dict = json.load(f)
        return json_dict

    def get_issn_links(self, url: str):
        self.jrnls_issn_dict = self.read_issn_json(self.issn_codes_path)
        self.issn_links_dict = self.read_issn_json(self.issn_links_path)

        page = self.open_url(url)

        for issn_sublist in tqdm(self.jrnls_issn_dict.values()):
            for issn in issn_sublist:
                if issn in self.issn_links_dict:  # skip if already exist
                    logging.info(f"{issn} already exist, skip")
                    break

                err_cntr = 0
                while True:
                    try:
                        link = self.get_journal_link(page, issn)
                        break
                    except Exception as e:
                        logging.error(f"Exception found: {e}")
                        if err_cntr < self.max_retries:
                            logging.debug("Trying to sleep and restart")
                            # time.sleep(30)
                            if not self.change_proxy():
                                break
                            page = self.open_url(url)
                            err_cntr += 1
                        else:
                            break

                if err_cntr > self.max_retries:
                    raise RuntimeError("Cant working normally, stopping")

                self.issn_links_dict[issn] = link
                time.sleep(random.uniform(1, 5))
                if len(link) != 0:
                    break

            with open(self.issn_links_path, 'w') as fp:
                json.dump(self.issn_links_dict, fp, ensure_ascii=False)

    def __del__(self):
        if self.context is not None:
            self.context.close()
            self.browser.close()

    def _check_server_err(self, page):
        if page.locator("h1:has-text('Server Error')").is_visible():
            raise RuntimeError("Server error catch")

        if page.locator("div#blockedip").is_visible():
            raise RuntimeError("Anonymous ip blocked!")

        if page.locator("iframe[title='reCAPTCHA']").is_visible():
            raise CaptchaException("CAPTCHA CHECK DETECTED!")

    def get_journal_link(self, page: Page, issn_code: str) -> str:
        links = []

        page.locator("#titlename").fill(issn_code)
        button = page.locator("[onclick='title_search()']")
        button.click()
        time.sleep(1.5)

        if page.locator('td.redref:has-text("Не найдено журналов, соответствующих параметрам запроса")').count() > 0:
            logging.info(f"ISSN {issn_code} журналов не найдено.")
            return links

        self._check_server_err(page)
        page.wait_for_selector("#restab", state="attached", timeout=10000)

        result_table = page.locator("#restab")
        rows = result_table.locator("tr")

        for i in range(rows.count()):
            row = rows.nth(i)
            link = row.locator("a[href^='title_items.asp?id='][title]")
            if link.count() > 0:
                href = link.first.get_attribute("href")
                if href:
                    links.append(href)

        if len(links) == 0:
            return ""

        return links[0]

    def get_journal_pubs_info(self, suburl: str) -> Dict:
        id = re.search(r"title_items.asp\?id=(\d+)", suburl).group(1)
        url = f"{self.base_url}/title_items_rubrics.asp?id={id}&order=0&selids=&show_multi=0&hide_doubles=0"
        page = self.open_url(url)

        page.wait_for_selector("#rubrics_table", state="attached", timeout=10000)
        rubrics_table = page.locator("#rubrics_table")
        rows = rubrics_table.locator("tr[id^='rubric_']")

        data = {}

        for i in range(rows.count()):  # Проходим по каждой строке
            row = rows.nth(i)

            # Получаем значение атрибута id
            row_id = row.get_attribute("id")
            try:
                cat_id = re.search(r"rubric_(\d+)", row_id).group(1)
            except:
                logging.error(f"Cant find rubric id from {row_id}. Skip")
                continue

            # Получаем текст внутри строки
            row_text = row.locator("td:nth-child(2)").text_content()
            # try:
                # cat_id = re.search(r"rubric_(\d+)", row_text).group(1)
            # except:
                # print(f"Cant find cat_id from {row_text}. Skip")
                # continue
            try:
                number_in_brackets = re.search(r"\((\d+)\)", row_text).group(1)
            except:
                logging.error(f"Cant find count id from {row_text}. Skip")
                continue

            data[cat_id] = {}
            data[cat_id]["amount"] = int(number_in_brackets)
            data[cat_id]["parsed"] = 0
        page.close()
        return data

    def prepare_journals_info(self, categories):
        issn_links = self.read_issn_json(self.issn_links_path)
        for issn, link in issn_links.items():
            if link == "":
                logging.info(f"Empty info {issn}. Skip")
                continue
            journal_path = Path(f"data/journals/{issn}")
            journal_path.mkdir(parents=True, exist_ok=True)
            info_file = journal_path / "info.json"
            if info_file.exists():
                issn_info = self.read_issn_json(info_file)
            else:
                err_cntr = 0
                while True:
                    try:
                        print(issn)
                        issn_info = self.get_journal_pubs_info(link)
                        break
                    except Exception as e:
                        logging.error(f"Exception found: {e}")
                        if err_cntr <= self.max_retries:
                            logging.debug("Trying to sleep and restart")
                            # time.sleep(30)
                            # self.start_browser(False)
                            if not self.change_proxy():
                                break
                            err_cntr += 1
                        else:
                            break

                if err_cntr >= self.max_retries:
                    raise RuntimeError("Cant working normally, stopping")

            cleared_info = copy.deepcopy(issn_info)
            for category in issn_info.keys():
                if category not in categories:
                    del cleared_info[category]

            with open(info_file, 'w') as fp:
                json.dump(cleared_info, fp, ensure_ascii=False)

    def parse_journals(self):
        issn_links = self.read_issn_json(self.issn_links_path)
        for issn, link in issn_links.items():
            if link == "":
                logging.info(f"Empty info {issn}. Skip")
                continue

            journal_path = Path(f"data/journals/{issn}")
            info_file = self.read_issn_json(journal_path / "info.json")

            if (journal_path/"done.txt").exists():
                logging.info(f"Issn {issn} already parsed, skip")
                continue

            if len(list(info_file.keys())) == 0:
                logging.info(f"ISSN {issn} dont have useful categories, skip")
                continue

            logging.info(f"start parse {issn}")
            self.parse_journal(f"{self.base_url}/{link}", info_file, journal_path)
            self.update_info(journal_path)

    def update_info(self, journal_path: Path):
        info_dict = self.read_issn_json(journal_path / "info.json")
        rubrics_in_journal = len(list(info_dict.keys()))
        done_rubrics = 0
        for rubric, counter in info_dict.items():
            csv_file = journal_path / f"{rubric}.csv"
            if not csv_file.exists():
                continue

            with open(csv_file) as f:
                parsed_cntr = len(f.readlines())

            info_dict[rubric]["amount"] = int(counter["amount"])

            if parsed_cntr != counter["parsed"]:
                info_dict[rubric]["parsed"] = parsed_cntr

            if parsed_cntr >= counter["amount"]:
                done_rubrics += 1

        if rubrics_in_journal == done_rubrics:
            with open(journal_path / "done.txt", 'w') as fp:
                fp.write("1")

        with open(journal_path / "info.json", 'w') as fp:
            json.dump(info_dict, fp, ensure_ascii=False)

    def select_category(self, page: Page, category: str) -> Union[Page, bool]:
        page.wait_for_selector("#hdr_rubrics", state="attached")
        element = page.locator("#hdr_rubrics")
        element.click()
        self._check_server_err(page)

        page.wait_for_selector("#rubrics_table", state="attached")
        rubrics_table = page.locator("#rubrics_table")

        rubric_row = rubrics_table.locator(f"#rubric_{category}")
        if not rubric_row.is_visible():
            return page, False

        page.evaluate('deselect_options("rubric");')
        rubric_row.click()
        button = page.locator("[onclick='pub_search()']")
        button.click()
        page.wait_for_load_state('domcontentloaded')
        self._check_server_err(page)
        return page, True

    def parse_journal(self, url: str, cats_info: Dict, journal_path: Path) -> Dict:

        page = self.open_url(url)
        try:
            for category, counters in cats_info.items():
                logging.info(f"Start parse category {category}")
                if counters["amount"] == counters["parsed"]:
                    continue

                csv_file = journal_path / f"{category}.csv"
                if csv_file.exists():
                    with open(csv_file) as f:
                        parsed_cntr = len(f.readlines())
                else:
                    parsed_cntr = 0

                if parsed_cntr >= int(counters["amount"]):
                    logging.info(f"Parsed links {parsed_cntr} more or equal to {counters['amount']}, skip")
                    continue

                page, status = self.select_category(page, category)
                if not status:
                    continue
                self.get_links_from_selected_category(page, category, journal_path)

        except Exception as e:
            logging.error(f"Exception found {e}")
        finally:
            return cats_info

    def get_links_from_selected_category(self, page, category: str, journal_path: Path) -> int:
        # headers = ['elib_id', 'title', 'link']
        filename = journal_path / f"{category}.csv"
        parsed_cntr = 0
        err_cntr = 0
        while True:
            try:
                if filename.exists():
                    with open(filename) as f:
                        parsed_cntr = len(f.readlines())
                # Открываем файл для добавления данных (append mode)
                with open(filename, mode="a", newline="", encoding="utf-8") as file:
                    writer = csv.writer(file)
                    self.parse_links_from_table(page, parsed_cntr, writer)
                break
            except Exception as e:
                err_cntr += 1
                logging.error(f"Error founded = {e}")
                if err_cntr <= self.max_retries:
                    # print("sleep and try again")
                    if not self.change_proxy():
                        break
                    page = self.open_url(self.last_opened_url)
                    page, status = self.select_category(page, category)
                    if not status:
                        logging.info("cant find category, stoping")
                        break
                else:
                    logging.error("max retries exceeded")
                    break

    def parse_links_from_table(self, page, already_parsed: int, writer):
        curr_cntr = 0

        table = page.locator("table#restab")
        table.wait_for(state="visible")
        list_parsed = already_parsed//20

        if list_parsed != 0:
            page.evaluate(f'goto_page({list_parsed+1});')
            page.wait_for_load_state('domcontentloaded')
            curr_cntr = list_parsed*20

        while True:
            self._check_server_err(page)
            table = page.locator("table#restab")
            table.wait_for(state="visible")

            selection_locator = page.locator("#rubricsheader:has-text('(выделено: 1)')")
            if not selection_locator.is_visible():
                raise RuntimeError("Categoty selection dropped")

            # Получаем все строки с публикациями
            rows = table.locator("tr[id^='arw']")
            for i in range(rows.count()):
                curr_cntr += 1
                if curr_cntr <= already_parsed:
                    continue
                row = rows.nth(i)
                link = row.locator("a[href^='/item.asp?id=']").first

                href = link.get_attribute("href") if link else None
                id_value = href.split("=")[1] if href else None

                title_element = row.locator("b span")
                title_text = title_element.text_content().strip() if title_element else None

                pub_link = [id_value, title_text.lower(), href]  # headers = ['elib_id', 'title', 'link']
                writer.writerow(pub_link)

            next_page_button = page.locator("td.mouse-hovergr a[title='Следующая страница']")
            if next_page_button.is_visible():
                time.sleep(1)
                next_page_button.click()
            else:
                break


def main():
    BASE_URL = 'https://www.elibrary.ru'
    parser = ElibraryParser.run_with_constant_proxy()
    # parser.get_issn_links(f'{BASE_URL}/titles.asp')

    # page = parser.open_url('https://elibrary.ru/title_items.asp?id=27941', 2)
    # parser.open_url('https://www.google.com', 2)

    # parser = ElibraryParser()
    # interrst_cats = parser.read_issn_json("data/interrest_cats.json")
    # parser.prepare_journals_info(interrst_cats)
    for i in range(20):
        parser.parse_journals()
        logging.info("Sleep 10min")
        time.sleep(600)


if __name__ == "__main__":
    main()
