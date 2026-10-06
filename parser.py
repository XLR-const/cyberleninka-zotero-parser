import os
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Библиотеки для управления реальным браузером
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from meta_parser import fetch_deep_metadata


# =====================================================================
# ⚙️ БЛОК НАСТРОЕК
# =====================================================================
TOTAL_ARTICLES_NEEDED = 100  # Сколько всего статей нужно собрать
DOWNLOAD_DIR = "cyberleninka_live_articles" # Папка для PDF
RIS_FILE_PATH = "articles_for_zotero.ris"   # Файл для Zotero
# =====================================================================

def clean_filename(filename):
    forbidden = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in forbidden:
        filename = filename.replace(char, '')
    return filename.strip()[:110]

def main():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        print(f"[ СИСТЕМА ] Создана папка: '{DOWNLOAD_DIR}'")

    # Открываем файл с жестким принуждением к правильному формату для Zotero
    with open(RIS_FILE_PATH, "w", encoding="utf-8-sig", newline="\r\n") as ris_file:
        
        print("[ БРАУЗЕР ] Запуск управляемого окна Chrome...")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get("https://cyberleninka.ru")
        
        print("\n==================================================================")
        print(" 🛑 ДЕЙСТВИЯ ДЛЯ ТЕБЯ В ОТКРЫВШЕМСЯ БРАУЗЕРЕ:")
        print(" 1. Вбей запрос, например: \"прогнозирование кассовых сборов машинное обучение\"")
        print("    (Лучше бери фразы в кавычки, чтобы поиск был точнее)")
        print(" 2. Нажми кнопку Поиск и дождись загрузки первой страницы результатов.")
        print(" 3. Вернись в эту консоль и нажми ENTER. Скрипт ВСЁ сделает сам!")
        print("==================================================================\n")
        
        input("👉 Как только результаты поиска загрузятся, нажми ENTER здесь...")

        downloaded_count = 0
        page = 1

        # Синхронизируем куки браузера и сессии requests
        selenium_cookies = driver.get_cookies()
        session = requests.Session()
        for cookie in selenium_cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        
        session.headers.update({
            "User-Agent": driver.execute_script("return navigator.userAgent;"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        })

        while downloaded_count < TOTAL_ARTICLES_NEEDED:
            print(f"\n--- Обработка страницы №{page} (Собрано: {downloaded_count}/{TOTAL_ARTICLES_NEEDED}) ---")
            
            # Ждем появления результатов поиска на странице
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'title'))
                )
            except Exception:
                print("[ ОШИБКА ] Не удалось дождаться загрузки статей на странице. Прерываем.")
                break

            html_source = driver.page_source
            soup = BeautifulSoup(html_source, 'html.parser')
            
            # Ищем карточки (блоки li в списке выдачи)
            cards = soup.find_all('li')
            valid_cards_found = False

            for card in cards:
                if downloaded_count >= TOTAL_ARTICLES_NEEDED:
                    break

                title_tag = card.find('h2', class_='title')
                if not title_tag:
                    continue
                
                link_tag = title_tag.find('a', href=True)
                if not link_tag:
                    continue
                
                valid_cards_found = True
                raw_title = link_tag.text.strip()
                article_title = clean_filename(raw_title)
                article_url = urljoin("https://cyberleninka.ru", link_tag['href'])
                pdf_url = article_url + "/pdf"
                
                # Парсим автора и год прямо из карточки
                authors = ""
                year = ""
                authors_tag = card.find('span', class_='authors')
                year_tag = card.find('span', class_='year')
                
                if authors_tag:
                    authors = authors_tag.text.strip()
                if year_tag:
                    year = year_tag.text.strip().replace(" / ", "")

                print(f"[ НАЙДЕНО ] Статья: '{article_title}' | Год: {year}")
                
                # Вежливая пауза, чтобы КиберЛенинка не банила
                time.sleep(random.uniform(1.8, 3.2))
                
                try:
                    file_response = session.get(pdf_url, timeout=20)
                    
                    if file_response.status_code == 200 and b'%PDF' in file_response.content[:4]:
                        file_path = os.path.join(DOWNLOAD_DIR, f"{downloaded_count + 1}_{article_title}.pdf")
                        
                        with open(file_path, 'wb') as f:
                            f.write(file_response.content)
                        
                        downloaded_count += 1
                        print(f"[ УСПЕХ ] Статья №{downloaded_count} сохранена!")
                        
                        # --- НАШ НОВЫЙ ШАГ В ПАЙПЛАЙНЕ ---
                        # Вызываем внешнюю функцию для сбора глубоких метаданных
                        deep_data = fetch_deep_metadata(session, article_url)
                        
                        # Если внутри статьи нашли более полный список авторов — берем его
                        final_authors = deep_data["authors"] if deep_data["authors"] else (authors.split(',') if authors else [])

                        # Пишем расширенный RIS набор тегов
                        ris_file.write("TY  - JOUR\n")
                        ris_file.write(f"TI  - {raw_title}\n")
                        
                        for author in final_authors:
                            ris_file.write(f"AU  - {author.strip()}\n")
                        
                        if deep_data["journal"]: 
                            ris_file.write(f"JO  - {deep_data['journal']}\n")
                        if year: 
                            ris_file.write(f"PY  - {year}\n")
                        if deep_data["doi"]: 
                            ris_file.write(f"DO  - {deep_data['doi']}\n")
                        if deep_data["issn"]: 
                            ris_file.write(f"SN  - {deep_data['issn']}\n")
                        if deep_data["pages"]: 
                            ris_file.write(f"SP  - {deep_data['pages']}\n")
                        if deep_data["abstract"]: 
                            ris_file.write(f"N2  - {deep_data['abstract']}\n")
                            
                        ris_file.write(f"UR  - {article_url}\n")
                        ris_file.write("ER  - \n\n")
                        ris_file.flush()

                        
                    else:
                        print("[ ПРОПУСК ] Ссылка не отдала валидный PDF.")
                except Exception as e:
                    print(f"[ ОШИБКА ] Не удалось скачать файл: {e}")
                    continue

            if downloaded_count >= TOTAL_ARTICLES_NEEDED:
                break

            if not valid_cards_found:
                print("[ КОНЕЦ ВЫДАЧИ ] Статьи на странице больше не найдены.")
                break

                        # --- АВТОМАТИЧЕСКИЙ ПЕРЕХОД НА СЛЕДУЮЩУЮ СТРАНИЦУ ---
            print("[ СИСТЕМА ] Переходим на следующую страницу через URL...")
            try:
                page += 1
                
                # Получаем текущий базовый URL поиска без старого номера страницы
                current_url = driver.current_url
                if "page=" in current_url:
                    # Если в URL уже был номер страницы, отрезаем его
                    base_url = current_url.split("page=")[0]
                else:
                    # Если это была первая страница, добавляем знак амперсанда или вопроса
                    base_url = current_url + ("&" if "?" in current_url else "?")
                
                # Формируем идеальную ссылку на следующую страницу
                next_page_url = f"{base_url}page={page}"
                print(f"[ СИСТЕМА ] Загружаем страницу №{page}: {next_page_url}")
                
                # Просто переходим по прямой ссылке
                driver.get(next_page_url)
                time.sleep(random.uniform(3.5, 5.0)) # Спокойно ждем полной загрузки новой страницы
                
            except Exception as e:
                print(f"[ ПРЕДУПРЕЖДЕНИЕ ] Не удалось автоматически переключить URL ({e}).")
                input("👉 Вбей в браузере нужную страницу вручную и нажми ENTER здесь для продолжения...")


        print(f"\n[ ИТОГ ] Скрипт полностью завершил работу!")
        print(f"Успешно собрано статей: {downloaded_count}.")
        print(f"Файл '{RIS_FILE_PATH}' готов к импорту в Zotero!")
        driver.quit()

if __name__ == "__main__":
    main()
