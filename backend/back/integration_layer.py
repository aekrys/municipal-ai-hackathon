import sys
import os
import json
import requests
import logging
import sqlite3
import time
import uuid
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# ========== ИМПОРТ NEURAL NETWORK ==========
print(f"\n🔍 ИМПОРТ NEURAL NETWORK")

# 1. Определяем путь к neural_network
current_file = os.path.abspath(__file__)  # .../back/integration_layer.py
back_dir = os.path.dirname(current_file)  # .../back
backend_dir = os.path.dirname(back_dir)  # .../backend
neural_network_dir = os.path.join(backend_dir, 'neural_network')

print(f"📁 back_dir: {back_dir}")
print(f"📁 backend_dir: {backend_dir}")
print(f"📁 neural_network_dir: {neural_network_dir}")

# 2. Проверяем существует ли папка
if not os.path.exists(neural_network_dir):
    print(f"❌ Папка neural_network не найдена!")
    print(f"   Ищем в других местах...")

    # Ищем в радиусе 3 уровней
    for root, dirs, files in os.walk(backend_dir, topdown=True):
        if 'neural_network' in dirs:
            neural_network_dir = os.path.join(root, 'neural_network')
            print(f"   ✅ Найден альтернативный путь: {neural_network_dir}")
            break

# 3. Путь к файлу
neural_network_file = os.path.join(neural_network_dir, 'neural_network.py')
print(f"📄 Файл neural_network.py: {neural_network_file}")
print(f"📂 Существует: {os.path.exists(neural_network_file)}")

# 4. Импортируем
analyze_news_article = None

if os.path.exists(neural_network_file):
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("neural_network", neural_network_file)
        neural_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(neural_module)

        if hasattr(neural_module, 'analyze_news_article'):
            analyze_news_article = neural_module.analyze_news_article
            print("✅ Функция analyze_news_article импортирована!")
        else:
            print("⚠️ Функция analyze_news_article не найдена в модуле")

    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        import traceback

        traceback.print_exc()
else:
    print("❌ Файл neural_network.py не найден!")

# 5. Если импорт не удался - создаем заглушку
if analyze_news_article is None:
    print("⚠️ Использую заглушку для analyze_news_article")


    def analyze_news_article(text, source_url="", source_name="", parse_time=""):
        print(f"[ЗАГЛУШКА] analyze_news_article: {text[:50]}...")
        return [{
            "category": "Другое",
            "criticality": 0,
            "sentiment": "нейтральная",
            "original_preview": text[:150] + "...",
            "street": "Екатеринбург"
        }]

print("✅ Импорт neural network завершен\n")


# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ========== ФУНКЦИЯ ФИЛЬТРАЦИИ МУНИЦИПАЛЬНОГО КОНТЕНТА ==========
def is_municipal_problem(text):
    """ВСЕГДА возвращает True - принимаем ВСЕ новости для кластеризации"""
    if not text or len(text) < 30:
        print(f"      ⏭️ Текст слишком короткий ({len(text)} символов)")
        return False

    text_lower = text.lower()

    # Считаем ключевые слова для определения типа контента
    municipal_keywords = [
        'авария', 'прорыв', 'затопление', 'отключение', 'не работает',
        'свалка', 'мусор', 'яма', 'дорог', 'светофор', 'лифт',
        'отопление', 'вода', 'свет', 'электричество', 'тепло',
        'жалоба', 'обращение', 'проблема', 'инцидент', 'ДТП',
        'уборка', 'благоустройство', 'ЖКХ', 'коммуналка'
    ]

    commercial_keywords = [
        'акция', 'скидка', 'распродажа', 'открытие', 'запуск',
        'новинка', 'коллекция', 'игрушка', 'магазин', 'ресторан',
        'продукт', 'услуга', 'цена', 'купить', 'заказ'
    ]

    event_keywords = [
        'фестиваль', 'концерт', 'выставка', 'мероприятие',
        'праздник', 'соревнование', 'турнир', 'шоу', 'спектакль'
    ]

    # Считаем сколько ключевых слов каждого типа
    municipal_count = sum(1 for word in municipal_keywords if word in text_lower)
    commercial_count = sum(1 for word in commercial_keywords if word in text_lower)
    event_count = sum(1 for word in event_keywords if word in text_lower)

    # Определяем тип контента для логирования
    if municipal_count >= 2:
        content_type = "МУНИЦИПАЛЬНАЯ проблема"
    elif commercial_count >= 2:
        content_type = "КОММЕРЧЕСКАЯ новость"
    elif event_count >= 1:
        content_type = "МЕРОПРИЯТИЕ"
    else:
        content_type = "ОБЩАЯ новость"

    print(f"      📊 Тип: {content_type}")
    print(f"      📝 Муниц. слова: {municipal_count}, Коммерч.: {commercial_count}, События: {event_count}")

    # ВСЕГДА возвращаем True (принимаем все новости)
    return True


# ========== ФУНКЦИЯ ВАЛИДАЦИИ ОТВЕТА ИИ ==========
def process_ai_response(ai_result, source_url="", parse_time="", news_text=""):
    """Обработка ответа от ИИ - РАБОЧАЯ ВЕРСИЯ"""
    try:
        if not ai_result or not isinstance(ai_result, list):
            print("      ❌ Пустой ответ от ИИ")
            return None

        result = ai_result[0]

        if 'category' not in result or result.get('category') is None:
            print("      ⚠️ Нейросеть вернула None вместо категории")
            # Создаем дефолтную категорию по типу контента
            result = {
                "category": "Новости",
                "criticality": 0,
                "sentiment": "нейтральная",
                "original_preview": "Общая новость"
            }

            # Продолжаем обработку...
        criticality = result.get('criticality', 0)
        category = result.get('category', 'Другое')

        # Если категория None - заменяем на "Другое"
        if category is None:
            category = "Другое"

        # ⚠️ ДЕБАГ: покажем что получили
        print(f"      📋 Ключи ответа ИИ: {list(result.keys())}")

        # АДАПТИРУЕМСЯ К ФОРМАТУ НЕЙРОСЕТИ
        # 1. criticality → priority
        priority = result.get('criticality', 0)
        if priority is None:
            priority = 0

        # 2. category (обязательное поле)
        category = result.get('category', 'Другое')

        # 3. summary
        summary = result.get('original_preview', '')
        if not summary:
            summary = result.get('problem_type', '')

        # 4. location (street или house)
        location = result.get('street', 'Екатеринбург')
        if location == 'ул. Центральная' and result.get('house'):
            location = f"{location}, {result['house']}"

        # 5. sentiment (конвертируем)
        sentiment_ru = result.get('sentiment', 'нейтральная')
        if 'негатив' in sentiment_ru:
            sentiment = 'negative'
        elif 'позитив' in sentiment_ru:
            sentiment = 'positive'
        else:
            sentiment = 'neutral'

        # ФОРМИРУЕМ ДАННЫЕ
        data = {
            "text": summary[:500] if summary else news_text[:200],
            "category": category,
            "location": location,
            "sentiment": sentiment,
            "priority": int(priority),
            "metadata": json.dumps({
                "source_url": source_url,
                "parse_time": parse_time,
                "ai_response": result,  # Сохраняем ВЕСЬ ответ
                "processed_at": datetime.now().isoformat()
            }, ensure_ascii=False)
        }

        print(f"      ✅ Обработано: {category} (приоритет: {priority})")
        return data

    except Exception as e:
        print(f"      ❌ Ошибка process_ai_response: {e}")
        import traceback
        traceback.print_exc()
        return None


def extract_location(text):
    """Извлекаем локацию из текста"""
    if not text:
        return "Екатеринбург"

    # Паттерны для поиска адресов
    patterns = [
        r'ул\.\s*[\w\s\.\-]+(?=\s|$)',
        r'проспект\s*[\w\s\.\-]+',
        r'пр\.\s*[\w\s\.\-]+',
        r'район\s*[\w\s\.\-]+',
        r'мкрн\.\s*[\w\s\.\-]+',
        r'дом\s*\d+',
        r'д\.\s*\d+',
        r'возле\s*[\w\s\.\-]+',
        r'на\s*[\w\s]+улице',
        r'в\s*районе\s*[\w\s\.\-]+'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return matches[0]

    # Если не нашли, проверяем есть ли упоминание районов Екатеринбурга
    districts = [
        'Верх-Исетский', 'Железнодорожный', 'Кировский', 'Ленинский',
        'Октябрьский', 'Орджоникидзевский', 'Чкаловский', 'Уралмаш',
        'Эльмаш', 'ВИЗ', 'Центр', 'Академический', 'Ботаника'
    ]

    for district in districts:
        if district.lower() in text.lower():
            return f"{district} район"

    return "Екатеринбург"


# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========
def init_database():
    """Инициализация базы данных"""
    try:
        # Создаем папку для отчетов в корне проекта
        reports_dir = os.path.join(backend_dir, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        print(f"✅ Папка reports создана/проверена: {reports_dir}")

        # Путь к БД в корне проекта
        db_path = os.path.join(backend_dir, 'data', 'municipal_monitoring.db')
        print(f"📁 Путь к БД: {db_path}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS problems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                category TEXT,
                location TEXT,
                sentiment TEXT,
                priority INTEGER DEFAULT 0,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cluster_id INTEGER,
                is_incident BOOLEAN DEFAULT 0
            )
        ''')

        # ИСПРАВЛЕННАЯ таблица clusters
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                location TEXT,
                frequency INTEGER DEFAULT 0,
                severity INTEGER DEFAULT 1,
                example_problems TEXT,  -- ПРАВИЛЬНОЕ ИМЯ КОЛОНКИ
                first_seen TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована")

    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        raise


# ========== ФУНКЦИЯ ДЛЯ ОТПРАВКИ В БЭКЕНД ==========
def send_to_backend(analysis_result, source_url="", parse_time=""):
    """ИСПРАВЛЕННАЯ функция отправки данных в бэкенд"""
    try:
        # Преобразуем приоритет в int
        priority = analysis_result.get("priority", 0)
        if priority is None:
            priority = 0
        elif isinstance(priority, str):
            try:
                priority = int(priority)
            except:
                priority = 0

        # Преобразуем sentiment
        sentiment = analysis_result.get("sentiment", "neutral")
        if sentiment is None:
            sentiment = "neutral"

        # Готовим данные
        data_to_send = {
            "text": analysis_result.get("text", analysis_result.get("summary", ""))[:500],
            # ИЗМЕНЕНО: проверяем оба поля
            "category": analysis_result.get("category", "Другое"),
            "location": analysis_result.get("location", "Екатеринбург"),
            "sentiment": sentiment,
            "priority": priority,
            "metadata": analysis_result.get("metadata", json.dumps({}))  # ИЗМЕНЕНО: берем готовый metadata
        }

        # Пропускаем если категория "Новости" или "Другое"
        if data_to_send["category"] in ["Новости", "Другое", "Новость"]:
            logger.info(f"⏭️ Пропускаем: {data_to_send['category']}")
            return False

        # Отправляем в бэкенд API
        backend_url = "http://localhost:8000/api/system_report"
        response = requests.post(backend_url, json=data_to_send, timeout=10)

        if response.status_code == 200:
            logger.info(f"✅ Отправлено в бэкенд: {data_to_send['category']} (приоритет: {priority})")
            return True
        else:
            logger.error(f"❌ Ошибка {response.status_code}: {response.text[:100]}")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка send_to_backend: {e}")
        return False


# ========== ФУНКЦИЯ ДЛЯ СОЗДАНИЯ КЛАСТЕРОВ ==========
def create_clusters_from_problems():
    """Создание кластеров из существующих проблем"""
    try:
        db_path = os.path.join(backend_dir, 'data', 'municipal_monitoring.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT category, COUNT(*) as count, GROUP_CONCAT(text, ' || ') as examples
            FROM problems 
            WHERE created_at > datetime('now', '-7 days')
            GROUP BY category
            HAVING COUNT(*) > 1
        ''')

        clusters = []
        rows = cursor.fetchall()

        for row in rows:
            category = row[0]
            frequency = row[1]
            examples = row[2]

            # Определяем серьезность
            if frequency >= 5:
                severity = 3
            elif frequency >= 3:
                severity = 2
            else:
                severity = 1

            description = f"{frequency} проблем в категории '{category}'"
            cluster_id = f"cluster_{category.lower()}_{int(time.time())}"

            cursor.execute('''
                INSERT OR REPLACE INTO clusters (id, category, description, severity, frequency, example_problems)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (cluster_id, category, description, severity, frequency, examples))

            clusters.append({
                "id": cluster_id,
                "category": category,
                "description": description,
                "severity": severity,
                "frequency": frequency
            })

        conn.commit()
        conn.close()

        logger.info(f"✅ Создано {len(clusters)} кластеров")
        return clusters

    except Exception as e:
        logger.error(f"❌ Ошибка создания кластеров: {e}")
        return []


def cluster_similar_problems():
    """Кластеризация схожих проблем по категории и местоположению"""
    try:
        db_path = os.path.join(backend_dir, 'data', 'municipal_monitoring.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Находим проблемы с одинаковой категорией и локацией
        cursor.execute('''
            SELECT category, location, COUNT(*) as frequency,
                   GROUP_CONCAT(text, ' || ') as examples,
                   MIN(created_at) as first_seen,
                   MAX(created_at) as last_seen
            FROM problems 
            WHERE created_at > datetime('now', '-7 days')
            GROUP BY category, location
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
        ''')

        clusters = []
        for row in cursor.fetchall():
            cluster = {
                "id": f"cluster_{hash(row[0] + str(row[1]))}",
                "category": row[0],
                "location": row[1] if row[1] else "Не указано",
                "frequency": row[2],
                "examples": row[3].split(' || ')[:3] if row[3] else [],
                "first_seen": row[4],
                "last_seen": row[5],
                "severity": min(3, row[2] // 2 + 1)  # 1-3 по частоте
            }
            clusters.append(cluster)

        conn.close()
        logger.info(f"✅ Создано {len(clusters)} кластеров по местоположению")
        return clusters

    except Exception as e:
        logger.error(f"❌ Ошибка кластеризации: {e}")
        return []


# ========== ФУНКЦИЯ ДЛЯ ЗАГРУЗКИ И ОБРАБОТКИ НОВОСТЕЙ ==========
def process_and_save_news():
    """Обработка новостей и сохранение в БД для дашборда"""
    try:
        print(f"\n🔍 [process_and_save_news] НАЧАЛО обработки новостей")

        # Путь к файлу с новостями
        news_file = os.path.join(backend_dir, 'data', 'ekb_news.txt')

        print(f"   📁 Путь к файлу: {news_file}")
        print(f"   📂 Файл существует: {os.path.exists(news_file)}")

        if not os.path.exists(news_file):
            print(f"❌ Файл новостей не найден: {news_file}")
            return 0

        with open(news_file, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"   📄 Размер файла: {len(content)} символов")

        if not content:
            print("❌ Файл новостей пуст")
            return 0

        # Разделяем на отдельные новости по разделителям
        news_sections = content.split("=" * 80)
        print(f"   📰 Найдено секций новостей: {len(news_sections)}")

        processed_count = 0

        for i, section in enumerate(news_sections):
            if not section.strip():
                continue

            print(f"\n   🔄 Обрабатываю секцию #{i + 1}")

            # Ищем текст новости и метаданные
            lines = section.strip().split('\n')
            news_text = ""
            source_url = ""
            parse_time = ""

            in_news = False

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("ССЫЛКА:"):
                    source_url = line.replace("ССЫЛКА:", "").strip()
                    print(f"      🔗 Источник: {source_url[:50]}...")
                    continue
                elif "ВРЕМЯ ПАРСИНГА:" in line:
                    parse_time = line.replace("ВРЕМЯ ПАРСИНГА:", "").strip()
                    print(f"      🕐 Время парсинга: {parse_time}")
                    continue
                elif "-" * 40 in line:
                    in_news = True
                    continue
                elif in_news and line:
                    # Пропускаем разделители
                    if not line.startswith("=") and not line.startswith("&"):
                        news_text += line + " "

            news_text = news_text.strip()

            if news_text and len(news_text) > 50:
                print(f"      📝 Текст новости ({len(news_text)} символов):")
                print(f"      {news_text[:100]}...")

                # ============= ИЗМЕНЕНИЕ: УБИРАЕМ ФИЛЬТРАЦИЮ =============
                # Вместо фильтрации просто определяем тип контента
                text_lower = news_text.lower()

                municipal_keywords = ['авария', 'прорыв', 'затопление', 'не работает', 'свалка', 'мусор', 'яма',
                                      'дорог', 'светофор', 'отопление']
                commercial_keywords = ['акция', 'скидка', 'распродажа', 'открытие', 'запуск', 'коллекция', 'игрушка',
                                       'магазин', 'ресторан']
                event_keywords = ['фестиваль', 'концерт', 'выставка', 'мероприятие', 'праздник']

                municipal_count = sum(1 for word in municipal_keywords if word in text_lower)
                commercial_count = sum(1 for word in commercial_keywords if word in text_lower)
                event_count = sum(1 for word in event_keywords if word in text_lower)

                if municipal_count >= 2:
                    content_type = "МУНИЦИПАЛЬНАЯ проблема"
                elif commercial_count >= 2:
                    content_type = "КОММЕРЧЕСКАЯ новость"
                elif event_count >= 1:
                    content_type = "МЕРОПРИЯТИЕ"
                else:
                    content_type = "ОБЩАЯ новость"

                print(f"      📊 Тип контента: {content_type}")
                # =======================================================

                # AI анализ новости
                try:
                    print(f"      🤖 Отправляю на AI анализ...")

                    ai_results = analyze_news_article(
                        news_text[:1500],
                        source_url,
                        "parser",
                        parse_time if parse_time else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    )

                    if ai_results and len(ai_results) > 0:
                        # Валидируем ответ ИИ
                        validated_data = process_ai_response(ai_results, source_url, parse_time)

                        if not validated_data:
                            print(f"      ⏭️ Ответ ИИ не прошел валидацию")
                            continue

                        print(
                            f"      ✅ AI анализ: {validated_data['category']} (приоритет: {validated_data['priority']})")
                        print(f"      📤 Отправляю в бэкенд...")

                        # Отправляем в бэкенд
                        if send_to_backend(validated_data, source_url, parse_time):
                            processed_count += 1
                            print(f"      ✅ Успешно отправлено! Всего: {processed_count}")
                        else:
                            print(f"      ❌ Не удалось отправить в бэкенд")

                    else:
                        print(f"      ⚠️ AI вернул пустой результат")

                except Exception as e:
                    print(f"      ❌ Ошибка AI анализа: {e}")

            else:
                print(f"      ⚠️ Текст новости слишком короткий ({len(news_text)} символов)")

        print(f"\n🎯 ИТОГО: Обработано {processed_count} новостей")

        # После обработки создаем кластеры
        if processed_count > 0:
            clusters = cluster_similar_problems()
            print(f"📊 Создано {len(clusters)} кластеров проблем")

        return processed_count

    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА в process_and_save_news: {e}")
        import traceback
        traceback.print_exc()
        return 0


# ========== ФУНКЦИЯ ДЛЯ ГЕНЕРАЦИИ ОТЧЕТА ==========
def generate_report():
    """Генерация отчета о текущем состоянии"""
    try:
        # Создаем папку reports если нет
        reports_dir = os.path.join(backend_dir, 'reports')
        os.makedirs(reports_dir, exist_ok=True)

        # Имя файла отчета
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(reports_dir, f"report_{timestamp}.txt")

        db_path = os.path.join(backend_dir, 'data', 'municipal_monitoring.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получаем статистику
        cursor.execute('SELECT COUNT(*) FROM problems WHERE created_at > datetime("now", "-24 hours")')
        problems_24h = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM problems WHERE priority >= 2')
        critical_problems = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM clusters')
        clusters_count = cursor.fetchone()[0]

        cursor.execute('SELECT category, COUNT(*) as count FROM problems GROUP BY category ORDER BY count DESC LIMIT 5')
        top_categories = cursor.fetchall()

        # Получаем последние проблемы
        cursor.execute('''
            SELECT text, category, location, priority, created_at 
            FROM problems 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        recent_problems = cursor.fetchall()

        conn.close()

        # Создаем отчет
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write(f"ОТЧЕТ AI-ПОМОЩНИКА ГЛАВЫ ЕКАТЕРИНБУРГА\n")
            f.write(f"Сгенерирован: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

            f.write("📊 СТАТИСТИКА:\n")
            f.write(f"  • Проблем за 24 часа: {problems_24h}\n")
            f.write(f"  • Критических проблем: {critical_problems}\n")
            f.write(f"  • Активных кластеров: {clusters_count}\n\n")

            f.write("🏆 ТОП-5 КАТЕГОРИЙ ПРОБЛЕМ:\n")
            for category, count in top_categories:
                f.write(f"  • {category}: {count} проблем\n")

            f.write("\n🚨 ПОСЛЕДНИЕ ПРОБЛЕМЫ:\n")
            for problem in recent_problems:
                f.write(f"  • [{problem[3]}] {problem[1]}: {problem[0][:80]}...\n")
                f.write(f"    📍 {problem[2]} | 🕐 {problem[4][:19]}\n")

            f.write("\n" + "=" * 60 + "\n")
            f.write("🎯 РЕКОМЕНДАЦИИ:\n")
            f.write("1. Проверить критические проблемы в первую очередь\n")
            f.write("2. Обратить внимание на часто встречающиеся категории\n")
            f.write("3. Мониторить новые инциденты из парсера новостей\n")
            f.write("4. Координировать работу служб по кластерам проблем\n")
            f.write("=" * 60 + "\n")

        logger.info(f"✅ Отчет сгенерирован: {report_file}")
        return report_file

    except Exception as e:
        logger.error(f"❌ Ошибка генерации отчета: {e}")
        return None


# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    """Основная функция интеграционного слоя"""
    logger.info("🚀 Инициализация интеграционного слоя...")

    # Инициализируем БД
    init_database()

    logger.info("✅ Интеграционный слой готов")

    # Тестирование
    print("\n🧪 Тестирование интеграционного слоя...")

    # Тест 1: Отправка тестовой проблемы
    test_problem = {
        "text": "Тестовая проблема от интеграционного слоя",
        "category": "Тест",
        "location": "Центр города",
        "sentiment": "neutral",
        "priority": 1,
        "metadata": json.dumps({
            "source_url": "test",
            "tags": ["тест"],
            "is_incident": False
        })
    }

    if send_to_backend(test_problem):
        print("✅ Тестовая проблема отправлена успешно")
    else:
        print("⚠️ Не удалось отправить тестовую проблему")

    # Тест 2: Создание кластеров
    clusters = create_clusters_from_problems()
    print(f"✅ Создано {len(clusters)} кластеров по категориям")

    # Тест 3: Кластеризация по местоположению
    location_clusters = cluster_similar_problems()
    print(f"✅ Создано {len(location_clusters)} кластеров по местоположению")

    if location_clusters:
        print("\n🎯 Примеры кластеров:")
        for i, cluster in enumerate(location_clusters[:3]):
            print(f"   {i + 1}. {cluster['category']} в {cluster['location']}")
            print(f"      Частота: {cluster['frequency']} раз")

    # Тест 4: Обработка новостей
    news_count = process_and_save_news()
    print(f"✅ Обработано {news_count} новостей из парсера")

    # Тест 5: Проверка БД
    try:
        db_path = os.path.join(backend_dir, 'data', 'municipal_monitoring.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM problems")
        total_count = cursor.fetchone()[0]
        print(f"📊 В БД всего записей: {total_count}")

        cursor.execute("SELECT text, category, location FROM problems ORDER BY created_at DESC LIMIT 3")
        recent = cursor.fetchall()
        print("📰 Последние записи:")
        for problem in recent:
            print(f"   • {problem[1]}: {problem[0][:50]}...")

        conn.close()
    except Exception as e:
        print(f"⚠️ Не удалось проверить БД: {e}")

    # Тест 6: Генерация отчета
    report_file = generate_report()
    if report_file:
        print(f"✅ Отчет сгенерирован: {report_file}")
    else:
        print("❌ Не удалось сгенерировать отчет")

    print("\n🎯 Интеграционный слой работает в фоновом режиме...")
    print("📡 Ожидание данных от парсера и обработка в реальном времени")

    # Бесконечный цикл для периодической проверки
    while True:
        try:
            # Каждый час проверяем новости и обновляем кластеры
            time.sleep(3600)  # 1 час

            logger.info("🔄 Проверка обновлений...")
            process_and_save_news()
            cluster_similar_problems()

        except KeyboardInterrupt:
            logger.info("🔴 Интеграционный слой остановлен")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в основном цикле: {e}")
            time.sleep(300)  # Ждем 5 минут при ошибке


if __name__ == "__main__":
    main()