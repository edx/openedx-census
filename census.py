import asyncio
import csv
import json
import pprint
import re

import aiohttp
import attr
import lxml
import lxml.html

@attr.s
class Site:
    url = attr.ib()
    latest_courses = attr.ib()
    current_courses = attr.ib(default=None)
    error = attr.ib(default=None)


SITE_PATTERNS = []

def parse_site(pattern):
    def _decorator(func):
        SITE_PATTERNS.append((pattern, func))
        return func
    return _decorator

async def text_from_url(url, session):
    async with session.get(url) as response:
        return await response.read()

def xpath_from_html(html, xpath):
    parser = lxml.etree.HTMLParser()
    tree = lxml.etree.fromstring(html, parser)
    elts = tree.xpath(xpath)
    return elts


# XuetangX: add up courses by institution.
@parse_site(r"www\.xuetangx\.com$")
async def parser(site, session):
    url = "http://www.xuetangx.com/partners"
    text = await text_from_url(url, session)
    li = xpath_from_html(text, "/html/body/article[1]/section/ul/li/a/div[2]/p[1]")
    courses = 0
    for l in li:
        suffix = "门课程"
        text = l.text
        assert text.endswith(suffix)
        courses += int(text[:-len(suffix)])
    return courses

# FUN has an api that returns a count.
@parse_site(r"france-universite-numerique-mooc\.fr$")
async def parser(site, session):
    url = "https://www.fun-mooc.fr/fun/api/courses/?rpp=50&page=1"
    text = await text_from_url(url, session)
    data = json.loads(text)
    return data['count']

@parse_site(r"courses.openedu.tw$")
async def parser(site, session):
    url = "https://www.openedu.tw/rest/courses/query"
    text = await text_from_url(url, session)
    data = json.loads(text)
    return len(data)

@parse_site(r"courses.zsmu.edu.ua")
@parse_site(r"lms.mitx.mit.edu")
async def front_page_full_of_tiles(site, session):
    text = await text_from_url(site.url, session)
    li = xpath_from_html(text, "//ul/li[@class='courses-listing-item']")
    return len(li)

@parse_site(r"openedu.ru$")
async def parser(site, session):
    url = "https://openedu.ru/course/"
    text = await text_from_url(url, session)
    count = xpath_from_html(text, "//span[@id='courses-found']")[0]
    assert count.text.endswith(" курс")
    return int(count.text.split()[0])

@parse_site(r"puroom.net$")
async def parser(site, session):
    url = "https://lms.puroom.net/search/course_discovery/"
    headers = {'Referer': 'https://lms.puroom.net/courses'}
    # Needs CSRF from ^^
    async with session.post(url, headers=headers) as response:
        text = await response.read()
    print(repr(text))
    data = json.loads(text)
    count = data["facets"]["emonitoring_course"]["total"]
    return count

async def default_parser(site, session):
    text = await text_from_url(site.url, session)
    return len(text) * 1000


MAX_CLIENTS = 100
USER_AGENT = "Open edX census-taker. Tell us about your site: oscm+census@edx.org"


async def fetch(site, session):
    try:
        for pattern, parser in SITE_PATTERNS:
            if re.search(pattern, site.url):
                site.current_courses = await parser(site, session)
                break
        else:
            site.current_courses = await default_parser(site, session)
        print(".", end='', flush=True)
        return True
    except Exception as exc:
        site.error = str(exc)
        print("X", end='', flush=True)
        return False

async def throttled_fetch(site, session, sem):
    async with sem:
        return await fetch(site, session)

async def run(sites):
    tasks = []
    sem = asyncio.Semaphore(MAX_CLIENTS)

    headers = {
        'User-Agent': USER_AGENT,
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        for site in sites:
            task = asyncio.ensure_future(throttled_fetch(site, session, sem))
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
    print()

def get_urls(sites):
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(run(sites))
    loop.run_until_complete(future)
    for site in sorted(sites, key=lambda s: s.latest_courses, reverse=True):
        print(site)

def read_sites(csv_file):
    with open(csv_file) as f:
        next(f)
        for row in csv.reader(f):
            url = row[1].strip().strip("/")
            courses = int(row[2] or 0)
            if courses < 100:
                continue
            if not url.startswith("http"):
                url = "http://" + url
            yield Site(url, courses)

if __name__ == '__main__':
    sites = list(read_sites("sites.csv"))
    print(f"{len(sites)} sites")
    get_urls(sites)
