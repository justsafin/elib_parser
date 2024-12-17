# Парсер статей с сайта Elibrary
Парсер собирает информацию с сайтов https://journalrank.rcsi.science/ и https://elibrary.ru/
Для работы с elibrary используется платный прокси с сервиса https://free-proxy-list.net/rotating-proxy.html

Алгоритм работы
1. Создать текстовый файл с наименованиями изданий
2. Запустить файл issn_parse.py, чтобы сформировать файл **issn_codes.json**
3. Запустить с прокси парсер ссылок на издания в elibrary. На основе файла **issn_codes.json** будет сформирован файл **issn_links.json**.
Данные для подключения прокси указываются в функции run_with_constant_proxy и функции change_proxy. (требует доработки)
```
    BASE_URL = 'https://www.elibrary.ru'
    parser = ElibraryParser.run_with_constant_proxy()
    parser.get_issn_links(f'{BASE_URL}/titles.asp')
```
4. Подготовить файл interrest_cats.json в котором перечислить интересующие рубрики ГРНТИ. Запустить парсер, можно без прокси. В директории **/data/journals** будут сформированы папки для каждого издания на основе файла **issn_links.json**. В папках будет лежать файл info.json, в котором указаны счетчики для каждой интересующей рубрики в журнале.
```
    parser = ElibraryParser()
    interrst_cats = parser.read_issn_json("data/interrest_cats.json")
    parser.prepare_journals_info(interrst_cats)
```
5. Запустить парсер журналов. Прокси спасает не всегда (по крайней мере с данного сервиса). В связи с чем процесс парсинга довольно длительный из-за большого количества перезапусков сессиий. Даже при небольшом количестве изданий потребуется несколько раз перезапустить процесс парсинга. В директории журналов появятся csv файлы для каждой рубрики, который содержат данные в формате ['elib_id', 'title', 'link']. Также будет обновляться файл info.json и появится файл done.txt по завершению парсинга этого журнала
```
    parser = ElibraryParser.run_with_constant_proxy()
    parser.parse_journals()
```
6. Парсинг информации о статьях по ссылкам в csv-файлах, полученных на предыдущем шаге. В разработке