import threading
import queue
import requests
import time
import lxml.html
import multiprocessing
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException

url = "https://iwilltravelagain.com"
regions = ["/usa/", "/europe/", "/canada/", "/latin-america-caribbean/", "/australia-new-zealand-asia/"]
queues = {}
threads_per_region = 10


def parse_pages(region):
    options = Options()
    # options.add_argument("--headless")
    driver = webdriver.Chrome(ChromeDriverManager().install(),
                              options=options)
    page_number = 1
    driver.get("%s%s?page=%s" % (url, region, str(page_number)))
    alert_closed = False

    while True:
        try:
            time.sleep(1)
            wanted_url = "%s%s?page=%s" % (url, region, str(page_number))
            WebDriverWait(driver, 30, 2).until(EC.presence_of_element_located((By.XPATH,
                                                                               "//h4[@class='activity__title']")))
            if wanted_url not in driver.current_url:
                print(wanted_url)
                print(driver.current_url)
                continue

            print(region + ": " + str(page_number))
            tree = lxml.html.document_fromstring(driver.page_source)
            links = tree.xpath("//h4[@class='activity__title']/a/@href")

            for link in links:
                queues[region].put(link)
            if not alert_closed:
                driver.find_element_by_xpath("//button[@class='cookie-notice__dismiss js-close-cookie-notice']").click()
                alert_closed = True

        except Exception as e:
            print(e)

        try:
            driver.find_element_by_xpath("//button[@class='pagination-button' and contains(text(),'»')]").click()
            page_number += 1

        except NoSuchElementException:
            print(region + ": no next page, leaving on page " + str(page_number))
            break

    driver.close()


def parse_item(region):
    while True:
        try:
            item_url = url + queues[region].get(timeout=60)
            page = requests.get(item_url).text

            tree = lxml.html.document_fromstring(page)

            # Если под "Name (title)" подразумевался title html-страницы:
            name = tree.xpath("//head/title/text()")[0].strip()

            # Если под "Name (title)" подразумевалось просто название карточки:
            # name = tree.xpath("//h1/text()")[0]

            category_location = [tree.xpath("//li[1]/div[@class='quick-details-content']/span/text()"),
                                 tree.xpath("//li[2]/div[@class='quick-details-content']/span/text()")]

            for i in range(len(category_location)):
                if category_location[i]:
                    del (category_location[i][0])
                    category_location[i] = ', '.join(category_location[i])
                else:
                    category_location[i] = "None"

            website = tree.xpath("//div[@class='block activity-buttons']/div[2]/a/@href")
            if website:
                website = website[0]
            else:
                website = "None"

            with open(region.replace("/", "") + ".txt", "a", encoding="utf-8") as f:
                f.write("%s; %s; %s; %s\n" % (name, category_location[0], category_location[1], website))

            queues[region].task_done()

        except queue.Empty:
            break

        except Exception as e:
            print(e)


def start_region(region):
    queues[region] = queue.Queue()
    open(region.replace("/", "") + ".txt", "tw", encoding="utf-8").close()
    threading.Thread(target=parse_pages, args=(region,)).start()
    for i in range(threads_per_region):
        threading.Thread(target=parse_item, args=(region,)).start()


if __name__ == '__main__':
    for region in regions:
        multiprocessing.Process(target=start_region, args=(region,)).start()
