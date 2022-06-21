from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import gspread
from oauth2client.service_account import ServiceAccountCredentials

import re
import difflib
from pathlib import Path
import os
import time

venv_path = '/Users/buntaro/Documents/CS/Python/Web Scraping/'

test_URLs = ["https://jlptsensei.com/learn-japanese-grammar/%e9%96%93-aida-meaning/",
             "https://jlptsensei.com/learn-japanese-grammar/%e9%96%93%e3%81%ab-aida-ni-meaning/"]

local_test_URLs = ["file:///source html/fake-url-0.html"
                   "file:///source html/fake-url-1.html"]

def crawl_links(jlpt):
    """
    INPUTS int JLPT level
    RETURNS string[] of URLs
    """
    driver = webdriver.Chrome(executable_path=
                              '/Users/buntaro/Documents/CS/Python/Web Scraping/venv/bin/chromedriver')

    # driver.get(f"https://jlptsensei.com/jlpt-n{jlpt}-grammar-list/")
    # with open(f'List of N{jlpt} Links.html', 'w+') as source_doc:
    #     source_doc.truncate(0)
    #     source_doc.write(driver.page_source)
    driver.get('https://jlptsensei.com/jlpt-n4-grammar-list/page/2/')
    # wait = WebDriverWait(driver, 10)
    # paragraph = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="jl-grammar"]/tbody/tr[1]/td[3]/a')))
    # paragraph.getText()
    i, link, links = 1, None, []
    while True:
        try:
            link = driver.find_elements(By.XPATH, f'//*[@id="jl-grammar"]/tbody/tr[{i}]/td[3]/a')
            links.append(link[0].get_attribute('href'))
            i += 1
        except IndexError:
            break
    return links

def save_html(jlpt, name, URL):
    """
    desired name: str, URL: str -> document(str)
    """
    driver = webdriver.Chrome(executable_path=
                              '/Users/buntaro/Documents/CS/Python/Web Scraping/venv/bin/chromedriver')
    driver.get(URL)
    with open(f'source html/JLPT N{jlpt}-{name}.html', 'w+') as source_doc:
        source_doc.truncate(0)
        source_doc.write(driver.page_source)
    driver.close()

def format_html(filename):
    """
    INPUTS a path filename
    RETURNS none, improves HTML formatting
    """
    with open(filename, 'r+') as source_doc:
        doc_old = BeautifulSoup(source_doc.read(), 'html.parser')
    doc_new = doc_old.prettify()
    with open(filename, 'w+') as source_doc:
        source_doc.truncate(0)
        source_doc.write(doc_new)

def get_elements_re(filename):
    """
    INPUTS path filename
    RETURNS list of list of each type of sentence
    """
    JP_list = []
    KA_list = []
    EN_list = []
    FU_list = []
    with open(filename, 'r') as file:
        text = file.read()
    jp_re = re.compile(r"<div class=\"alert alert-secondary example-main\">\n\s*?<p class=\".*\">\n\s*?(\S.*)\n\s*?<span class=\"color\">\n\s*?(\S.*)\n\s*?</span>\n\s*?(\S.*)\n\s*?</p>\n\s*?</div>\n")
    ka_re = re.compile(r"<div class=\"alert alert-success\">\n\s*?(\S.*)\n\s*?</div>")
    en_re = re.compile(r"<div class=\"alert alert-primary\">\n\s*?(\S.*)\n\s*?</div>")
    jp_matches = re.finditer(jp_re, text)
    ka_matches = re.finditer(ka_re, text)
    en_matches = re.finditer(en_re, text)
    for i in jp_matches:
        JP_list.append(f"{i.group(1)}<strong>{i.group(2)}</strong>{i.group(3)}")
    for i in ka_matches:
        KA_list.append(f"{i.group(1)}")
    for i in en_matches:
        EN_list.append(f"{i.group(1)}")
    for i, s in enumerate(zip(JP_list, KA_list)):
        FU_list.append(furigana(JP_list[i], KA_list[i]))
    return list(zip(JP_list, FU_list, KA_list, EN_list))

def apply_to_sheet(filename):
    """
    INPUTS path filename
    RETURNS none, adds sentences to spreadsheet
    """
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file",
             "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    gc = gspread.authorize(credentials)

    sheet = gc.open('Python Test Sheet').worksheet('Japanese Sentences')
    data = get_elements_re(filename)
    rows = sheet.col_values(1)
    filled = 0
    for i in rows:
        if i == '':
            break
        filled += 1
    sheet.update(f'A{1+filled}:D{len(data)+1+filled}', data)

def get_reading_indices(kana, no_kanji):
    """
    INPUTS a kana sentence and a kanji-stripped sentence
    RETURNS a 2-dimensional list of consecutive indices
    """
    sentences = [(kana.strip(), no_kanji.strip())]
    additions = []
    for a, b in sentences:
        for i, s in enumerate(difflib.ndiff(a, b)):
            if s[0] == ' ':
                continue
            elif s[0] == '-':
                additions.append(i)
            elif s[0] == '+':
                print(f'Something went wrong: {kana}')
    additions_sorted = []
    additions_substr = []
    previous = -1
    for i in additions:
        if i == previous + 1:
            additions_substr.append(i)
        else:
            additions_sorted.append(additions_substr)
            additions_substr = [i]
        previous = i
    additions_sorted.append(additions_substr)
    return additions_sorted

def get_readings(kana, no_kanji):
    """
    INPUTS a kanji sentence and a kana sentence
    RETURNS a list of readings
    """
    readings = []
    for i, lst in enumerate(get_reading_indices(kana, no_kanji)):
        readings.append('')
        for k in lst:
            readings[i] += kana[k]
    return readings

def furigana(kanji, kana):
    """
    INPUTS kanji and kana sentences
    RETURNS furigana sentence
    """
    kana_re = re.compile(r"[\u3040-\u309F|\u30A0-\u30FF]")
    kanji_re = re.compile(r"[\u4E00-\u9FFF]+|<strong>|</strong>")
    kanji_strip = re.sub(kanji_re, '', kanji)
    result = re.sub(r"([\u4E00-\u9FFF]+)", r" \1[]", kanji).strip()
    readings_list = get_readings(kana, kanji_strip)
    for i, lst in enumerate(readings_list):
        result = result.replace("[]", f"[{readings_list[i]}]", 1)
    return result

def initiate_scrape(jlpt: int, URLs: list):
    print(URLs)
    try:
        for i, URL in enumerate(URLs):
            filename = f'source html/JLPT N{jlpt}-{i}.html'
            if f'JLPT N{jlpt}-{i}.html' not in os.listdir("./source html"):
                save_html(jlpt, i, URL)
                format_html(filename)
                apply_to_sheet(filename)
    except IndexError:
        print('All Done!')

URLs = crawl_links(4)
initiate_scrape(4, URLs)
