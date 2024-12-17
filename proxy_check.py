import requests
import json
from tqdm import tqdm


proxy_ip = ""
proxy_port = 2000
proxy_login = ""
proxy_pass = ""

proxies = {
    "http": f"http://{proxy_login}:{proxy_pass}@{proxy_ip}:{proxy_port}",
    "https": f"http://{proxy_login}:{proxy_pass}@{proxy_ip}:{proxy_port}"
}

# Pretend to be Firefox
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:87.0) Gecko/20100101 Firefox/87.0',
    'Accept-Language': 'en-US,en;q=0.5'
}


# # Change the URL to your target website
url = "https://checkip.amazonaws.com"
try:
    r = requests.get(url, proxies=proxies, headers=headers, timeout=20)
    print(r.text)
except Exception as e:
    print(e)
