import requests
import time
import re
import logging
import hashlib
import sqlite3
import sys
import os
import json
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ========== НАСТРОЙКА ПУТЕЙ ДЛЯ ИМПОРТА ==========
# Получаем абсолютный путь к текущему файлу (parser.py)
current_file = os.path.abspath(__file__)  # C:\Users\...\scripts\parser.py
scripts_dir = os.path.dirname(current_file)  # C:\Users\...\scripts
project_root = os.path.dirname(scripts_dir)  # C:\Users\...\project

# Путь к neural_network.py
neural_path = os.path.join(project_root, 'neural_network', 'neural_network.py')

# Проверяем существует ли файл
if not os.path.exists(neural_path):
    print(f"❌ Файл не найден: {neural_path}")
    print("🔍 Проверяю наличие файла...")
    # Проверяем правильное имя файла
    neural_dir = os.path.join(project_root, 'neural_network')
    if os.path.exists(neural_dir):
        files = os.listdir(neural_dir)
        print(f"Файлы в папке neural_network: {files}")

        # Ищем neural_network.py (правильное имя)
        correct_files = [f for f in files if f.lower() == 'neural_network.py']

        if correct_files:
            neural_path = os.path.join(neural_dir, correct_files[0])
            print(f"✅ Найден файл: {neural_path}")
        else:
            print(f"❌ neural_network.py не найден в {neural_dir}")
            # Создаем путь без опечатки
            neural_path = os.path.join(neural_dir, 'neural_network.py')

# Импортируем neural_network через importlib
try:
    import importlib.util

    spec = importlib.util.spec_from_file_location("gigachat_analysis", neural_path)
    gigachat_analysis_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gigachat_analysis_module)
    gigachat_analysis = gigachat_analysis_module
    print(f"✅ Neural network импортирован из: {neural_path}")
except Exception as e:
    print(f"❌ Ошибка импорта neural_network: {e}")
    print("🚨 Создаем заглушку для neural_network")


    # Создаем заглушку если не удалось импортировать
    class NeuralNetworkStub:
        @staticmethod
        def start_analysis(file_path, auth_key):
            print(f"⚠️ Заглушка: start_analysis({file_path}, {auth_key})")
            return {"status": "stub", "message": "Neural network not available"}

    gigachat_analysis = NeuralNetworkStub()


from dotenv import load_dotenv
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ключевые слова для фильтрации новостей
NEWS_KEYWORDS = [
    'новости', 'новость', 'авария', 'дтп', 'пожар', 'чп', 'происшествие',
    'задержание', 'арест', 'суд', 'полиция', 'мчс', 'гибдд', 'отставка',
    'назначение', 'блокировка', 'штраф', 'запрет', 'кредит', 'министр',
    'строительство', 'девелопер', 'транспорт', 'метро', 'автобус',
    'трамвай', 'инвестиции', 'развитие', 'финансы', 'доллар', 'рубль',
    'экономика', 'бизнес', 'ресторан', 'реабилитация', 'мессенджер',
    'застройщик', 'управляющий', 'гиперкар', 'ноутбук', 'компьютер',
    'подорожание', 'квартал', 'район', 'диаспора', 'памятник',
    'спецоперация', 'конкурс', 'отпуск', 'каникулы', 'интервью',
    'общество', 'больница', 'главврач', 'здравоохранение', 'мэр',
    'президент', 'правительство', 'закон', 'проект', 'аналитика',
    'расследование', 'обзор', 'прогноз', 'тенденция', 'статистика',
    'данные', 'отчет', 'заявление', 'комментарий', 'эксперт',
    'программа', 'мероприятие', 'форум', 'конференция', 'событие'
]

# Слова для исключения (не новости)
EXCLUDE_KEYWORDS = [
    'согласие', 'соглашение', 'согласен', 'принимаю', 'условия', 'рассылку', 'Подписаться',
    'cookies', 'куки', 'персональных', 'персональные данные', 'политика',
    'конфиденциальность', 'реклама', 'маркетинг', 'подписка', 'телефон'
                                                              'рассылка', 'рассылки', 'обновление', 'версия', 'beta',
    'свидетельство', 'регистрация', 'роскомнадзор', 'учредитель',
    'редактор', 'редакция', 'электронная почта', 'appstore',
    'rustore', 'миа', 'россия сегодня', 'правила использования',
    'правила применения', 'материалов', 'технологий',
    'фс77', 'миа', 'информационное агентство', 'сетевое издание',
    'зарегистрировано', 'версия 2023', 'версия 2024', 'версия 2025'
]

# Регулярные выражения для технической информации
TECHNICAL_PATTERNS = [
    r'©\s*\d{4}\s*.+',  # Копирайты
    r'Версия\s+.+',  # Версии приложений
    r'Свидетельство о регистрации.+',  # Свидетельства
    r'Сетевое издание.+зарегистрировано.+',  # Регистрация СМИ
    r'Учредитель:.+',  # Учредители
    r'Главный редактор:.+',  # Редакторы
    r'Адрес электронной почты:.+',  # Email адреса
    r'Телефон:.+',  # Телефоны
    r'ФС\d{2}-\d{5}',  # Номер свидетельства
    r'Роскомнадзор',  # Упоминание Роскомнадзора
    r'МИА «Россия сегодня»',  # Название агентства
    r'в AppStore',  # Магазины приложений
    r'в RuStore',  # Магазины приложений
    r'Правила использования материалов',  # Правила
    r'Правила применения.+',  # Правила
    r'\d{1,2}\s+[а-я]+\s+\d{4}\s+года',  # Даты регистрации
]


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ==========
# только при первом запуске, если не создана бд
# def init_database():
#     """Инициализация базы данных SQLite"""
#     conn = sqlite3.connect('news_sources.db')
#     cursor = conn.cursor()
#
#     # Создание таблицы для источников
#     cursor.execute('''
#     CREATE TABLE IF NOT EXISTS sources (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         name TEXT NOT NULL,
#         url TEXT NOT NULL,
#         type TEXT NOT NULL,
#         level TEXT,
#         theme TEXT,
#         is_active INTEGER DEFAULT 1,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#         updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     )
#     ''')
#
#     # Создание таблицы для результатов парсинга
#     cursor.execute('''
#     CREATE TABLE IF NOT EXISTS parsing_results (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         source_id INTEGER,
#         text TEXT,
#         parsing_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#         FOREIGN KEY (source_id) REFERENCES sources (id)
#     )
#     ''')
#
#     conn.commit()
#     conn.close()
#     logger.info("База данных инициализирована")
#
#
# def import_from_excel_to_db(file_path='ekb_sources.xlsx'):
#     """Импорт источников из Excel файла в базу данных"""
#     try:
#         # Читаем Excel файл
#         df = pd.read_excel(file_path)
#         logger.info(f"Прочитано {len(df)} источников из Excel файла")
#
#         # Подключаемся к базе данных
#         conn = sqlite3.connect('news_sources.db')
#         cursor = conn.cursor()
#
#         # Проверяем структуру DataFrame
#         required_columns = ['Название', 'Ссылка', 'Тип']
#         for col in required_columns:
#             if col not in df.columns:
#                 logger.error(f"Отсутствует обязательная колонка: {col}")
#                 return False
#
#         # Добавляем недостающие колонки, если их нет в Excel
#         if 'Уровень' not in df.columns:
#             df['Уровень'] = ''
#         if 'Тематика' not in df.columns:
#             df['Тематика'] = ''
#
#         # Очищаем старые данные (опционально)
#         cursor.execute("DELETE FROM sources")
#
#         # Импортируем данные
#         imported_count = 0
#         for _, row in df.iterrows():
#             cursor.execute('''
#             INSERT INTO sources (name, url, type, level, theme)
#             VALUES (?, ?, ?, ?, ?)
#             ''', (
#                 row['Название'],
#                 row['Ссылка'],
#                 row['Тип'],
#                 row['Уровень'],
#                 row['Тематика']
#             ))
#             imported_count += 1
#
#         conn.commit()
#         conn.close()
#
#         logger.info(f"Импортировано {imported_count} источников в базу данных")
#         return True
#
#     except Exception as e:
#         logger.error(f"Ошибка при импорте из Excel: {e}")
#         return False

def get_sources_from_db():
    """Получение всех активных источников из базы данных"""
    try:
        conn = sqlite3.connect('../data/news_sources.db')
        cursor = conn.cursor()

        cursor.execute('''
        SELECT id, name, url, type, level, theme 
        FROM sources 
        WHERE is_active = 1
        ORDER BY id
        ''')

        rows = cursor.fetchall()
        conn.close()

        # Преобразуем в список словарей для совместимости с существующим кодом
        sources = []
        for row in rows:
            sources.append({
                'id': row[0],
                'Название': row[1],
                'Ссылка': row[2],
                'Тип': row[3],
                'Уровень': row[4],
                'Тематика': row[5]
            })

        logger.info(f"Получено {len(sources)} источников из базы данных")
        return sources

    except Exception as e:
        logger.error(f"Ошибка при получении источников из БД: {e}")
        return []


def save_parsing_result_to_db(source_id, text):
    """Сохранение результата парсинга в базу данных"""
    try:
        if not text or not text.strip():
            return False

        conn = sqlite3.connect('../data/news_sources.db')
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO parsing_results (source_id, text, parsing_time)
        VALUES (?, ?, ?)
        ''', (source_id, text.strip(), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        # Обновляем время последнего обновления источника
        cursor.execute('''
        UPDATE sources 
        SET updated_at = ?
        WHERE id = ?
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), source_id))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"Ошибка при сохранении результата в БД: {e}")
        return False


# ========== ОСТАВШИЕСЯ ФУНКЦИИ БЕЗ ИЗМЕНЕНИЙ ==========

# Вспомогательная функция для хэширования
def create_hash(text):
    """Создание хэша для текста"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


# Инициализация Selenium WebDriver
def init_webdriver():
    """Инициализация headless Chrome драйвера"""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Режим без интерфейса
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        # ДОБАВЬ ЭТИ АРГУМЕНТЫ чтобы убрать предупреждения:
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-webgl")
        chrome_options.add_argument("--disable-dev-tools")
        chrome_options.add_argument("--log-level=3")  # Минимальный уровень логов
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # ПУТЬ К CHROMEDRIVER
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        driver_path = os.path.join(scripts_dir, 'chromedriver.exe')

        print(f"🔍 Ищу chromedriver по пути: {driver_path}")

        if os.path.exists(driver_path):
            print(f"✅ Chromedriver найден: {driver_path}")

            try:
                from selenium.webdriver.chrome.service import Service

                # Настройка сервиса чтобы скрыть логи
                service = Service(executable_path=driver_path)
                service.creationflags = 0x08000000  # CREATE_NO_WINDOW

                # Подавление логов Selenium
                import warnings
                warnings.filterwarnings("ignore")

                driver = webdriver.Chrome(service=service, options=chrome_options)
                print("✅ Chrome драйвер успешно инициализирован")
                return driver

            except Exception as e:
                print(f"⚠️ Ошибка инициализации драйвера: {e}")
                print("🔄 Пробую альтернативный способ...")

                # Пробуем без указания пути
                try:
                    driver = webdriver.Chrome(options=chrome_options)
                    print("✅ Chrome драйвер успешно инициализирован (автоматически)")
                    return driver
                except Exception as e2:
                    print(f"❌ Альтернативный способ не сработал: {e2}")
                    return None
        else:
            print(f"❌ Chromedriver не найден по пути: {driver_path}")

            # Пробуем автоматическое определение
            try:
                driver = webdriver.Chrome(options=chrome_options)
                print("✅ Chrome драйвер найден автоматически")
                return driver
            except Exception as e:
                print(f"❌ Не удалось найти Chrome драйвер: {e}")
                return None

    except Exception as e:
        print(f"❌ Критическая ошибка инициализации WebDriver: {e}")
        return None


# Очистка текста от ненужных элементов
def clean_news_text(text):
    """Очистка текста новостей от согласий, куки и другой ненужной информации"""
    if not text:
        return ""

    # Удаляем фразы о согласии с условиями, куках и т.д.
    patterns_to_remove = [
        r'Принимаю условия.*?\n',
        r'Согласие на обработку.*?\n',
        r'Согласен.*?\n',
        r'Принимаю.*?\n',
        r'cookies.*?\n',
        r'куки.*?\n',
        r'персональные данные.*?\n',
        r'Подписаться.*?\n',
        r'Подписка.*?\n',
        r'Рассылка.*?\n',
        r'Реклама.*?\n',
        r'Маркетинг.*?\n',
        r'Ria\.ru.*AppStore.*\n?',
        r'Ria\.ru.*RuStore.*\n?',
        r'Версия \d{4}\.\d+.*\n?',
        r'© \d{4}.*\n?',
        r'МИА «Россия сегодня».*\n?',
        r'Сетевое издание.*зарегистрировано.*\n?',
        r'Свидетельство о регистрации.*\n?',
        r'Учредитель.*\n?',
        r'Правила использования материалов.*\n?',
        r'Правила применения.*\n?',
        r'Главный редактор.*\n?',
        r'Адрес электронной почты.*\n?',
        r'ФС77-\d+.*\n?',
        r'\d{1,2}\s+[а-я]+\s+\d{4}\s+года.*\n?',
    ]

    for pattern in patterns_to_remove:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

    # Дополнительно удаляем все строки, содержащие техническую информацию
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue

        # Проверяем, не содержит ли строка техническую информацию
        is_technical = False

        # Проверка по ключевым словам исключения
        if any(excl_word.lower() in line.lower() for excl_word in EXCLUDE_KEYWORDS):
            is_technical = True

        # Проверка по регулярным выражениям
        for pattern in TECHNICAL_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                is_technical = True
                break

        # Проверяем, не является ли строка просто контактами или служебной информацией
        if ('@' in line and ('.ru' in line or '.com' in line)) or 'тел.' in line.lower():
            is_technical = True

        # Проверяем, не является ли строка просто датой или номером
        if re.match(r'^\d{1,2}[\.\/]\d{1,2}[\.\/]\d{4}', line) or re.match(r'^№?\s*\d+', line):
            is_technical = True

        if not is_technical:
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


# Проверка, является ли текст новостью
def is_news_text(text, min_length=15, max_length=8000):
    """Проверяет, является ли текст новостью"""
    if not text:
        return False

    # Проверяем длину текста
    if len(text) < min_length or len(text) > max_length:
        return False

    # Разбиваем текст на строки для более тщательной проверки
    lines = text.split('\n')
    valid_lines_count = 0

    for line in lines:
        line = line.strip()
        # Проверяем, не является ли строка технической информацией
        is_technical_line = False
        for pattern in TECHNICAL_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                is_technical_line = True
                break

        if is_technical_line:
            continue

        # Проверяем наличие ключевых слов новостей в строке
        line_lower = line.lower()
        news_word_count = sum(1 for keyword in NEWS_KEYWORDS if keyword.lower() in line_lower)

    # Если найдено достаточное количество ключевых слов - это новость
    if news_word_count >= 2:
        return True

    # Проверяем, нет ли слишком много технической информации
    technical_count = 0
    for pattern in TECHNICAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            technical_count += 1

    # Если слишком много технической информации - это не новость
    if technical_count > 2:
        return False

    return True


def remove_duplicate_paragraphs(text):
    """Удаление дублирующихся абзацев из текста"""
    if not text:
        return ""

    paragraphs = text.split('\n\n')
    unique_paragraphs = []
    seen_hashes = set()

    for para in paragraphs:
        if not para.strip():
            continue

        # Нормализуем текст для сравнения
        normalized = re.sub(r'\s+', ' ', para.strip().lower())

        # Удаляем временные метки и даты для лучшего сравнения
        normalized = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', '', normalized)
        normalized = re.sub(r'\d{1,2}:\d{2}', '', normalized)
        normalized = re.sub(r'\d{1,2}\.\d{2}\.\d{4}', '', normalized)

        # Удаляем лишние пробелы
        normalized = normalized.strip()

        if not normalized or len(normalized) < 30:
            continue

        # Создаем хэш из первых 100 символов
        if len(normalized) > 100:
            hash_text = normalized[:100]
        else:
            hash_text = normalized

        para_hash = create_hash(hash_text)

        if para_hash not in seen_hashes:
            seen_hashes.add(para_hash)
            unique_paragraphs.append(para.strip())

    return '\n\n'.join(unique_paragraphs)


# Функция для форматирования текста с разделителями в отдельных строках
def format_news_with_separators(text, source_type):
    """Форматирует текст, добавляя разделители между новостями в отдельных строках"""
    if not text:
        return ""

    # Разделяем текст на отдельные новости
    news_items = []

    if source_type == 'TG':
        # Для Telegram разделяем по двойным переносам строк
        items = text.split('\n\n')
        for item in items:
            item = item.strip()
            if item and len(item) > 50 and is_news_text(item):
                news_items.append(item)

    elif source_type == 'VK':
        # Для VK также разделяем по двойным переносам
        items = text.split('\n\n')
        for item in items:
            item = item.strip()
            if item and len(item) > 50 and is_news_text(item):
                news_items.append(item)

    else:  # Для веб-сайтов
        # Разделяем на абзацы и группируем
        paragraphs = text.split('\n')
        current_item = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                if current_item and len(current_item) > 50:
                    news_items.append(current_item.strip())
                    current_item = ""
                continue

            if len(para) < 100 and para and para[0].isupper() and current_item:
                if len(current_item) > 50:
                    news_items.append(current_item.strip())
                current_item = para
            else:
                if current_item:
                    current_item += "\n" + para
                else:
                    current_item = para

        if current_item and len(current_item) > 50:
            news_items.append(current_item.strip())

    # Форматируем с разделителями в отдельных строках
    if not news_items:
        return ""

    formatted_parts = []
    for i, item in enumerate(news_items[:5]):  # Не более 5 новостей
        formatted_parts.append(item.strip())
        if i < len(news_items[:5]) - 1:
            formatted_parts.append("&" * 40)

    return '\n'.join(formatted_parts)


# Парсинг Telegram через веб-версию
def parse_telegram_channel_web(channel_url):
    """Парсинг Telegram каналов через веб-версию с разделителями в отдельных строках"""
    try:
        logger.debug(f"Парсинг Telegram канала: {channel_url}")

        # Извлекаем username канала из URL
        username = channel_url.split('/')[-1]
        username = username.split('?')[0]

        if username.startswith('s/'):
            username = username[2:]
        if username.startswith('@'):
            username = username[1:]

        web_url = f"https://t.me/s/{username}"
        logger.debug(f"Web URL: {web_url}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }

        response = requests.get(web_url, headers=headers, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Ищем сообщения
            messages = []

            # Способ 1: Ищем по классу tgme_widget_message_text
            message_divs = soup.find_all('div', class_='tgme_widget_message_text')

            if message_divs:
                logger.debug(f"Найдено {len(message_divs)} сообщений по классу tgme_widget_message_text")
                for msg_div in message_divs:
                    text = msg_div.get_text(separator='\n', strip=False)
                    if text and len(text.strip()) > 50:
                        messages.append(text.strip())

            # Способ 2: Если не нашли, ищем по другим селекторам
            if not messages:
                # Ищем все элементы с текстом
                all_text_elements = soup.find_all(['div', 'p', 'span'])
                for element in all_text_elements:
                    text = element.get_text(separator='\n', strip=True)
                    # Фильтруем короткие тексты и техническую информацию
                    if text and len(text) > 100 and not any(
                            excl_word in text.lower() for excl_word in EXCLUDE_KEYWORDS):
                        # Проверяем, не является ли это временем или датой
                        if not re.match(r'^\d{1,2}:\d{2}$', text) and not re.match(r'^\d{1,2}\s+[а-я]+', text):
                            messages.append(text)

            # Обрабатываем сообщения
            news_items = []
            for msg in messages:
                # Очищаем от технической информации
                msg_cleaned = clean_news_text(msg)

                if msg_cleaned and len(msg_cleaned) > 50 and is_news_text(msg_cleaned):
                    # Дополнительная очистка
                    msg_cleaned = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', '', msg_cleaned).strip()
                    msg_cleaned = re.sub(r'\d{1,2}:\d{2}', '', msg_cleaned).strip()
                    msg_cleaned = re.sub(r'\n{3,}', '\n\n', msg_cleaned)

                    if msg_cleaned:
                        news_items.append(msg_cleaned)

            # Удаляем дубликаты
            unique_news = []
            seen_hashes = set()

            for news in news_items:
                # Нормализуем для сравнения
                normalized = re.sub(r'\s+', ' ', news.lower().strip())
                normalized = re.sub(r'[^\w\s]', '', normalized)
                if len(normalized) > 30:
                    news_hash = create_hash(normalized[:100])
                    if news_hash not in seen_hashes:
                        seen_hashes.add(news_hash)
                        unique_news.append(news)

            # Форматируем с разделителями в отдельных строках
            if unique_news:
                formatted_parts = []
                for i, news in enumerate(unique_news[:5]):  # Берем до 5 новостей
                    formatted_parts.append(news.strip())
                    if i < len(unique_news[:5]) - 1:
                        formatted_parts.append("&" * 40)

                formatted_text = '\n'.join(formatted_parts)
                logger.debug(f"Успешно спарсено {len(unique_news)} новостей из {channel_url}")
                return formatted_text
            else:
                logger.warning(f"Не найдено новостей в канале {channel_url}")
                return ""

        else:
            logger.error(f"Ошибка HTTP {response.status_code} для {channel_url}")
            return ""

    except requests.exceptions.Timeout:
        logger.error(f"Таймаут при парсинге Telegram канала {channel_url}")
        return ""
    except Exception as e:
        logger.error(f"Ошибка при парсинге Telegram канала {channel_url}: {e}")
        return ""


# Функции парсинга разных типов ресурсов
def parse_website(url, driver=None):
    """Парсинг обычных веб-сайтов"""
    try:
        if driver:
            # Пробуем использовать Selenium если драйвер доступен
            try:
                driver.get(url)
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.common.by import By

                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                page_source = driver.page_source
            except Exception as selenium_error:
                print(f"⚠️ Ошибка Selenium для {url}: {selenium_error}")
                # Пробуем через requests
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                page_source = response.text
        else:
            # Используем requests если нет драйвера
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            page_source = response.text

        soup = BeautifulSoup(page_source, 'html.parser')

        # Удаляем ненужные элементы
        for script in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            script.decompose()

        # Получаем текст
        text = soup.get_text(separator='\n', strip=True)

        # Очистка текста
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        # Применяем фильтрацию новостей
        text = clean_news_text(text)

        return text[:5000]  # Ограничиваем длину текста
    except Exception as e:
        logger.error(f"Ошибка при парсинге сайта {url}: {e}")
        return ""


def parse_vk_group(group_url):
    """Парсинг VK групп с разделителями в отдельных строках"""
    try:
        # Используем мобильную версию для обхода ограничений
        if 'm.vk.com' not in group_url:
            mobile_url = group_url.replace('vk.com', 'm.vk.com')
        else:
            mobile_url = group_url

        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36'
        }

        response = requests.get(mobile_url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Поиск постов
        posts = []

        # Ищем по разным селекторам
        selectors = [
            'div.wall_item',
            'div.wi_body',
            'div.post_content',
            'div.wall_post_text',
            'div.post_text'
        ]

        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    post_text = element.get_text(separator='\n', strip=True)
                    if post_text and len(post_text) > 100:
                        posts.append(post_text)

        # Если не нашли по селекторам, ищем любой значимый текст
        if not posts:
            for div in soup.find_all('div'):
                text = div.get_text(separator='\n', strip=True)
                if text and 200 < len(text) < 2000:
                    posts.append(text)

        # Обрабатываем посты
        news_items = []
        for post in posts:
            post_cleaned = clean_news_text(post)
            if post_cleaned and len(post_cleaned) > 50 and is_news_text(post_cleaned):
                news_items.append(post_cleaned)

        # Удаляем дубликаты
        unique_news = []
        seen_hashes = set()

        for news in news_items:
            normalized = re.sub(r'\s+', ' ', news.lower().strip())
            normalized = re.sub(r'[^\w\s]', '', normalized)
            if len(normalized) > 30:
                news_hash = create_hash(normalized[:100])
                if news_hash not in seen_hashes:
                    seen_hashes.add(news_hash)
                    unique_news.append(news)

        # Форматируем с разделителями в отдельных строках
        if unique_news:
            formatted_parts = []
            for i, news in enumerate(unique_news[:5]):  # Не более 5 новостей
                formatted_parts.append(news.strip())
                if i < len(unique_news[:5]) - 1:
                    formatted_parts.append("&" * 40)

            return '\n'.join(formatted_parts)
        else:
            return ""

    except Exception as e:
        logger.error(f"Ошибка при парсинге VK группы {group_url}: {e}")
        return ""


# Основная функция парсинга
def parse_source(row, driver=None):
    """Парсинг одного источника"""
    name = row['Название']
    url = row['Ссылка']
    source_type = row['Тип']
    source_id = row['id']

    logger.info(f"Парсинг: {name} ({source_type})")

    text = ""

    try:
        if source_type == 'TG':
            # Используем веб-парсинг для Telegram
            text = parse_telegram_channel_web(url)
        elif source_type == 'VK':
            text = parse_vk_group(url)
        else:
            # Для веб-сайтов получаем текст и форматируем его
            raw_text = parse_website(url, driver)
            if raw_text:
                text = format_news_with_separators(raw_text, source_type)

        # Дополнительная очистка
        if text:
            # Убираем лишние пробелы и пустые строки
            lines = text.split('\n')
            cleaned_lines = []

            for line in lines:
                line = line.strip()
                if line or line == "&" * 40:  # Сохраняем разделители и непустые строки
                    cleaned_lines.append(line)

            text = '\n'.join(cleaned_lines)

        # Сохраняем результат в базу данных
        if text:
            save_parsing_result_to_db(source_id, text)

        return {
            'id': source_id,
            'name': name,
            'url': url,
            'type': source_type,
            'level': row.get('Уровень', ''),
            'theme': row.get('Тематика', ''),
            'text': text[:10000] if text else "",
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        logger.error(f"Критическая ошибка при парсинге {name}: {e}")
        return None


# Функция сохранения результатов
def save_results(results, filename='../data/ekb_news.txt'):
    """Сохранение результатов в текстовый файл И в JSON"""
    try:
        # ====== СТАРЫЙ КОД (сохранение в txt) ======
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"ОБНОВЛЕНО: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

            sources_with_news = 0
            for result in results:
                if result and result.get('text') and result['text'].strip():
                    sources_with_news += 1

                    f.write(f"ССЫЛКА: {result['url']}\n")
                    f.write(f"ВРЕМЯ ПАРСИНГА: {result['timestamp']}\n")
                    f.write("-" * 40 + "\n")

                    f.write(result['text'] + "\n")
                    f.write("=" * 80 + "\n\n")

            if sources_with_news == 0:
                f.write("Нет новостей в этом обновлении\n\n")

        logger.info(f"Результаты сохранены в {filename}")
        logger.info(f"Найдено источников с новостями: {sources_with_news}")

        # ====== НОВЫЙ КОД (сохранение в структурированном JSON) ======
        json_filename = filename.replace('.txt', '_structured.json')
        structured_news = []

        for result in results:
            if result and result.get('text') and result['text'].strip():
                # Разделяем текст на отдельные новости
                news_items = result['text'].split("&" * 40)

                for news_text in news_items:
                    if news_text.strip():
                        structured_news.append({
                            "source_name": result['name'],
                            "source_url": result['url'],
                            "source_type": result['type'],
                            "parse_time": result['timestamp'],
                            "raw_text": news_text.strip(),
                            # Эти поля заполнит AI позже
                            "summary": "",
                            "category": "",
                            "criticality": 0,
                            "sentiment": "",
                            "ai_analyzed": False,
                            "analyzed_at": None
                        })

        # Сохраняем структурированные данные
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump({
                "version": "1.0",
                "generated_at": datetime.now().isoformat(),
                "total_news": len(structured_news),
                "sources_count": sources_with_news,
                "news": structured_news
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"Структурированные данные сохранены в {json_filename}")
        logger.info(f"Собрано новостей: {len(structured_news)}")

        return structured_news  # Возвращаем для обработки AI

    except Exception as e:
        logger.error(f"Ошибка при сохранении результатов: {e}")
        return []


# Основной цикл парсинга
def main_loop():
    """Основной цикл парсинга с интервалом 10 минут"""

    # Инициализация драйвера
    driver = None

    try:
        # Инициализируем базу данных
        # init_database()

        # Импортируем источники из Excel
        # if import_from_excel_to_db():
        #     logger.info("Источники успешно импортированы в базу данных")
        # else:
        #     logger.warning("Не удалось импортировать источники из Excel. Используем существующие в БД.")

        # Инициализируем Selenium С ПРАВИЛЬНЫМ ПУТЕМ
        try:
            driver = init_webdriver()
            if driver:
                logger.info("✅ Selenium WebDriver инициализирован")
            else:
                logger.warning("⚠️ Selenium WebDriver не удалось инициализировать, работаем без него")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Selenium: {e}")
            logger.warning("⚠️ Продолжаем работу без Selenium")
            driver = None

        while True:
            try:
                logger.info("Начинаем новый цикл парсинга...")

                # Получаем источники из базы данных
                sources = get_sources_from_db()
                if not sources:
                    logger.error("Не удалось получить источники из базы данных")
                    time.sleep(600)
                    continue

                # Парсим все источники
                results = []
                for row in sources:
                    # Передаем драйвер, даже если он None
                    result = parse_source(row, driver)
                    if result:
                        results.append(result)
                    # Небольшая задержка между запросами
                    time.sleep(2)

                # Сохраняем результаты
                save_results(results)

                # Запускаем AI анализ
                try:
                    load_dotenv()
                    auth_key = os.getenv('AUTH_KEY')
                    if auth_key:
                        logger.info("🤖 Запускаю AI анализ новостей...")
                        gigachat_analysis.start_analysis('../data/ekb_news.txt', auth_key)
                    else:
                        logger.warning("⚠️ Ключ GigaChat не найден, пропускаю AI анализ")
                except Exception as ai_error:
                    logger.error(f"❌ Ошибка AI анализа: {ai_error}")

                # Сохраняем анализы в БД через integration_layer
                try:
                    import json
                    json_file = '../data/ekb_news_analyzed.json'
                    if os.path.exists(json_file):
                        with open(json_file, 'r', encoding='utf-8') as f:
                            analysis_data = json.load(f)

                        if analysis_data.get('status') == 'success':
                            # Импортируем здесь, чтобы избежать циклических импортов
                            try:
                                # Добавляем путь для импорта integration_layer
                                import sys
                                import os
                                current_dir = os.path.dirname(os.path.abspath(__file__))
                                project_root = os.path.dirname(os.path.dirname(current_dir))
                                sys.path.insert(0, project_root)

                                from integration_layer import process_and_save_news
                                processed = process_and_save_news()
                                logger.info(f"✅ Анализы обработаны: {processed} новостей")
                            except ImportError:
                                logger.warning("⚠️ Не удалось импортировать integration_layer")
                            except Exception as e:
                                logger.error(f"❌ Ошибка обработки анализов: {e}")
                except Exception as e:
                    logger.error(f"❌ Ошибка сохранения анализов: {e}")

                logger.info(f"✅ Парсинг завершен. Обработано источников: {len(results)}")
                logger.info("⏳ Следующий парсинг через час...")
                # Ждем час
                time.sleep(3600)

            except KeyboardInterrupt:
                logger.info("🛑 Парсинг остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в основном цикле: {e}")
                time.sleep(300)  # Ждем 5 минут при ошибке

    finally:
        # Закрываем драйвер, если он был создан
        if driver:
            try:
                driver.quit()
                logger.info("🔌 Selenium WebDriver закрыт")
            except:
                pass


def is_municipal_problem(text):
    """Фильтруем только муниципальные проблемы"""
    if not text or len(text) < 50:
        return False

    text_lower = text.lower()

    # Ключевые слова МУНИЦИПАЛЬНЫХ проблем
    problem_keywords = [
        'авария', 'прорыв', 'затопление', 'отключение', 'не работает',
        'свалка', 'мусор', 'яма', 'дорог', 'светофор', 'лифт',
        'отопление', 'вода', 'свет', 'электричество', 'тепло',
        'жалоба', 'обращение', 'проблема', 'инцидент', 'ДТП',
        'уборка', 'благоустройство', 'ЖКХ', 'коммуналка', 'подвал',
        'крыша', 'труба', 'канализация', 'утечка', 'засор'
    ]

    # Слова-фильтры (что пропускаем)
    skip_keywords = [
        'новость', 'анонс', 'мероприятие', 'фестиваль', 'концерт',
        'выставка', 'открытие', 'поздравление', 'награждение',
        'реклама', 'акция', 'скидка', 'распродажа', 'чебурашка',
        'игрушка', 'коллекция', 'кино', 'фильм', 'премьера'
    ]

    # Пропускаем если есть skip-слова
    if any(skip_word in text_lower for skip_word in skip_keywords):
        return False

    # Считаем проблемные слова
    problem_count = sum(1 for word in problem_keywords if word in text_lower)

    return problem_count >= 2


if __name__ == "__main__":
    print("Запуск парсера новостей Екатеринбурга")
    print("=" * 60)
    print(" Запуск полного режима с Selenium и базой данных...")
    main_loop()
