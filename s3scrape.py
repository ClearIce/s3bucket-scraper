import argparse
import os
from requests import get
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from time import sleep

parser = argparse.ArgumentParser(description='Scrape s3 stuff from grayhatwarefare')
parser.add_argument('pagination_start', metavar='pagination_start', type=int, help='pagination value to start on (0 for the beginning)')
parser.add_argument('search_value', metavar='search_value', type=str, help='search value (e.g. \'xls\')')
parser.add_argument('request_timeout_ms', metavar='request_timeout_ms', type=int, help='timeout between requests to grayhatwarfare in ms')

# 'xls' is the search term
grayhat_host = 'https://buckets.grayhatwarfare.com'
base_url = 'https://buckets.grayhatwarfare.com/results/{0}/{1}'

def simple_get(url):
    try:
        with closing(get(url, stream=True)) as resp:
            if is_good_response(resp):
                return resp.content
            else:
                log('invalid response at {0}'.format(url))
                return None

    except RequestException as ex:
        log('simple_get: error during requests to {0} : {1}'.format(url, str(ex)))
        return None


def get_soup(content):
    try:
        if content is not None:
            return BeautifulSoup(content, 'html.parser')
        else:
            log('get_soup: content cannot be None')

    except Exception as ex:
        log(ex)

"""
the table of s3 bucket links we want to grab files from
"""
def get_s3_table(html):
    try:
        if html is not None:            
            table = html.select('table') #should only be one table, but might need to future-proof
            if table is not None:
                return table[0]
            else:
                log('get_s3_table: table not found on page')
        else:
            log('get_s3_table: html cannot be None')

    except Exception as ex:
        log(ex)

def get_s3_table_links(table):
    try:
        if table is None:
            log('get_s3_table_links: table cannot be None')
            return None
        
        links = table.select('td a')
        result = []

        for link in links:
            href = link.attrs['href']
            if href.startswith('http'):
                result.append(link.attrs['href'])

        return result

    except Exception as ex:
        log(ex)

"""
returns a list 
.pagination will be a ul
url ends with start record index, e.g. https://buckets.grayhatwarfare.com/results/xls/20 lists 21-40
* the last li will contain the maximum record count, e.g. /results/xls/397912
* the second-to-last li will contain the next page to scrape, e.g. if on 20, it should be /results/xls/40
"""
def get_s3_pagination(html):
    
    if html is None:
        log('get_s3_pagination: html cannot be None')
        return None        

    try:
        element = html.select('.pagination')
        if len(element) > 0:
            liList = element.select('li')
            link = liList[len(liList) - 2].select('a')
            if link is not None:
                link.attrs['href']
        else:
            log('get_s3_pagination: could not find pagination element')
    except Exception as ex:
        log(ex)

"""
returns the full url of the next page to be scraped for s3 links
"""
def get_next_s3_page(html):
    if html is None:
        log('get_next_s3_page: html cannot be None')
        return None        

    try:
        element = html.select('.pagination')
        if len(element) > 0:
            liList = element[0].select('li')
            # second to last link is the 'next 20 results' button
            link = liList[len(liList) - 2].select('a')
            if link is not None and len(link) > 0:
                href = link[0].attrs.get('href')
                if href is not None and len(href) > 0:
                    return '{0}/{1}'.format(grayhat_host, href)
                else:
                    log('get_next_s3_page: invalid href value for link: {0}'.format(link))
            else:
                log('get_next_s3_page: invalid link value for element: {0}'.format(element))
        else:
            log('get_next_s3_page: could not find pagination element')
    except Exception as ex:
        log(ex)


"""
get files from s3 bucket links
makes dirs with the hostname and saves the file within that
"""
def get_aws_file(url):
    try:
        r = get(url, allow_redirects=False)
        log('response: {0}'.format(r))
        if is_good_file_response(r):
            parsed = urlparse(url)
            hostname = parsed.hostname
            filename = parsed.path.replace('/', '_').strip('_')
            target = '{0}/{1}'.format(hostname, filename)

            if os.path.isdir(hostname) is False:
                os.makedirs('./{0}'.format(hostname))

            log('writing: {0}'.format(target))
            open(target, 'wb').write(r.content)
        else:
            log('get_aws_file: bad response at {0}, {1}'.format(url, r))
    except Exception as ex:
        log('get_aws_file: error getting file at {0}: {1}'.format(url, ex))

def make_url(search_value, page_start):
    return base_url.format(search_value, page_start)

def log(ex):
    print(ex)
    
def is_good_response(resp):
    content_type = resp.headers['Content-Type'].lower()
    return (resp.status_code == 200 
        and content_type is not None 
        and content_type.find('html') > -1)

def is_good_file_response(resp):
    return resp.status_code == 200



if __name__ == '__main__':
    args = parser.parse_args()
    url = make_url(args.search_value, args.pagination_start)
    timeout = args.request_timeout_ms

    print('Starting point: {0}'.format(url))

    while(True):
        if url is None:
            log('main: no url, exiting')
            exit()
        
        content = simple_get(url)
        soup = get_soup(content)
        table = get_s3_table(soup)
        links = get_s3_table_links(table)

        for link in links:
            log('main: getting {0}'.format(link))
            get_aws_file(link)


        url = get_next_s3_page(soup)
        #testing
        log('sleeping for {0}'.format(timeout))
        sleep(timeout / 1000)
        log('main: next s3 page: {0}'.format(url))
    