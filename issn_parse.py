import time
import json
import requests
from bs4 import BeautifulSoup
from typing import List


def get_issn(jrnl_name: str) -> List:
    jrnl_name = jrnl_name.strip().lower()
    jrnl_name_replaced = jrnl_name.replace(" ", "+")
    result = requests.get(url=f"https://journalrank.rcsi.science/ru/record-sources/?s={jrnl_name_replaced}&adv=true")    
    result.raise_for_status()  # Проверка на ошибки

    # Создаем объект BeautifulSoup
    soup = BeautifulSoup(result.text, 'html.parser')

    # Находим все элементы с классом "list-group-item"
    items = soup.find_all("div", class_="list-group-item")

    numbers = []
    for item in items:
        # Получаем текст из <a class="tx-uppercase">
        title_element = item.find("a", class_="tx-uppercase")
        if title_element and title_element.text.strip().lower() == jrnl_name:
            # Если текст совпадает, извлекаем числа
            collapsible_container = item.find("div", class_="collapsible-container")
            if collapsible_container:
                # Извлекаем все числа
                numbers = [a.text for a in collapsible_container.find_all("a")]
                # print(f"Числа: {numbers}")

    return numbers


def main():
    with open("journals.txt", "r", encoding="utf-8") as file:
        # Читаем строки и записываем в список
        jrnl_list = [line.strip() for line in file]

    result_data = {}
    for jrnl in jrnl_list:
        issn_codes = get_issn(jrnl)
        if len(issn_codes) != 0:
            result_data[jrnl] = issn_codes
        time.sleep(0.5)

    with open('issn_codes.json', 'w') as fp:
        json.dump(result_data, fp, ensure_ascii=False)


if __name__ == "__main__":
    main()
