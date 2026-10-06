import re
import time
import random
from bs4 import BeautifulSoup

def fetch_deep_metadata(session, article_url):
    """
    Глубокий парсинг страницы статьи.
    Использует HTML-теги и регулярные выражения для поиска DOI, EDN и ISSN.
    """
    metadata = {
        "journal": "",
        "abstract": "",
        "doi": "",
        "issn": "",
        "pages": "",
        "authors": []
    }
    
    time.sleep(random.uniform(1.0, 2.0))
    
    try:
        response = session.get(article_url, timeout=15)
        if response.status_code != 200:
            return metadata
        
        soup = BeautifulSoup(response.text, 'html.parser')
        raw_text = soup.get_text() # Забираем вообще весь текст со страницы статьи
        
        # 1. Аннотация (Abstract Note)
        abstract_tag = soup.find('p', itemprop='description') or soup.find('div', class_='abstract')
        if abstract_tag:
            metadata["abstract"] = abstract_tag.text.strip()
            
        # 2. Список авторов
        author_tags = soup.find_all('li', itemprop='author')
        for auth in author_tags:
            name_span = auth.find('span', itemprop='name')
            if name_span:
                metadata["authors"].append(name_span.text.strip())
        
        if not metadata["authors"]:
            author_tags = soup.find_all('span', class_='author-name')
            metadata["authors"] = [a.text.strip() for a in author_tags]

        # 3. Базовый сбор из стандартных мета-тегов
        meta_journal = soup.find('meta', attrs={"name": "citation_journal_title"})
        if meta_journal: metadata["journal"] = meta_journal.get('content', '')
            
        meta_doi = soup.find('meta', attrs={"name": "citation_doi"})
        if meta_doi: metadata["doi"] = meta_doi.get('content', '')
            
        meta_issn = soup.find('meta', attrs={"name": "citation_issn"})
        if meta_issn: metadata["issn"] = meta_issn.get('content', '')
            
        meta_pages = soup.find('meta', attrs={"name": "citation_firstpage"})
        if meta_pages:
            lp = soup.find('meta', attrs={"name": "citation_lastpage"})
            metadata["pages"] = meta_pages.get('content', '')
            if lp: metadata["pages"] += f"-{lp.get('content', '')}"

        # =====================================================================
        # 🛠️ НОВЫЙ ШАГ: РЕГУЛЯРНЫЕ ВЫРАЖЕНИЯ (ЕСЛИ ТЕГИ ПУСТЫЕ)
        # =====================================================================
        
        # Если DOI не нашли в тегах, выковыриваем его из текста статьи регуляркой
        if not metadata["doi"]:
            # Международный стандартный паттерн для DOI (начинается с 10.)
            doi_match = re.search(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', raw_text, re.IGNORECASE)
            if doi_match:
                # Очищаем от возможных знаков препинания в конце строки
                metadata["doi"] = doi_match.group(0).rstrip('.,;)')

        # Ищем EDN (уникальный код Elibrary, часто пишется как EDN: XXXXXX)
        # EDN всегда состоит из 6 латинских букв
        edn_match = re.search(r'EDN:\s*([A-Z]{6})', raw_text, re.IGNORECASE)
        if edn_match:
            edn_code = edn_match.group(1).upper()
            # Zotero не имеет официального поля для EDN в формате RIS,
            # поэтому мы красиво допишем его в поле аннотации (Abstract Note),
            # чтобы препод видел этот код в итоговой таблице!
            edn_string = f"[EDN: {edn_code}]"
            if metadata["abstract"]:
                metadata["abstract"] = f"{edn_string} {metadata['abstract']}"
            else:
                metadata["abstract"] = edn_string

        # На всякий случай добираем ISSN регуляркой, если тег был пустой
        if not metadata["issn"]:
            issn_match = re.search(r'ISSN:\s*(\d{4}-\d{3}[\dX])', raw_text, re.IGNORECASE)
            if issn_match:
                metadata["issn"] = issn_match.group(1).upper()

    except Exception as e:
        print(f"[ ПРЕДУПРЕЖДЕНИЕ ] Ошибка регулярного выражения/парсинга текста: {e}")
        
    return metadata
