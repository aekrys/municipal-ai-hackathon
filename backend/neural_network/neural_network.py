import os
import json
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
AUTH_KEY = os.getenv('AUTH_KEY')


def clean_json_response(text: str) -> list:
    """Разделяет строку, содержащую несколько JSON объектов, и возвращает список словарей"""
    text = text.strip()
    json_objects = []
    stack = 0
    start = 0

    for i, char in enumerate(text):
        if char == '{':
            if stack == 0:
                start = i
            stack += 1
        elif char == '}':
            stack -= 1
            if stack == 0:
                try:
                    json_obj = json.loads(text[start:i + 1])
                    json_objects.append(json_obj)
                except json.JSONDecodeError:
                    continue  # Пропускаем некорректные объекты

    return json_objects


def analyze_citizen_message(text: str):
    """Анализ сообщения гражданина (старая функция для совместимости)"""
    return analyze_news_article(text)


def analyze_news_article(news_text, source_url="", source_name="", parse_time=""):
    """Анализ новости и создание краткой выжимки для дашборда"""
    # ПУТЬ К ФАЙЛУ sys_prompt.txt
    current_file_path = os.path.abspath(__file__)  # полный путь к neural_network.py
    current_dir = os.path.dirname(current_file_path)  # папка neural_network

    # Полный путь к sys_prompt.txt в той же папке
    prompt_path = os.path.join(current_dir, 'sys_prompt.txt')

    print(f"🔍 Neural Network: анализирую новость")
    print(f"   Длина текста: {len(news_text)} символов")

    with open(prompt_path, 'r', encoding='utf-8') as prompt_file:
        system_prompt = prompt_file.read()

    # Улучшенный промпт для новостей
    news_prompt = system_prompt + """

    ВАЖНО: Верни ОДИН JSON объект с краткой выжимкой новости для дашборда Главы города.

    Поля JSON:
    - summary: краткое описание (1-2 предложения) - ЧТО произошло
    - category: одна категория (ЖКХ, Транспорт, Благоустройство, Образование, Здравоохранение, Спорт, Туризм, Безопасность, Другое)
    - criticality: от 0 до 5 по градации из системного промпта
    - sentiment: 'негативная', 'позитивная', 'нейтральная'
    - emotion: 'гнев', 'тревога/опасность', 'благодарность', 'надежда', 'раздражение', 'нейтрально', 'страх'
    - location: улица/район/место (если есть в тексте), иначе null
    - time_info: время события (утро/день/вечер/ночь или конкретное время если есть)
    - source_preview: краткое название источника или первые слова

    Пример ответа:
    {
        "summary": "На улице Ленина образовалась большая яма, движение затруднено",
        "category": "Дороги",
        "criticality": 2,
        "sentiment": "негативная",
        "emotion": "раздражение",
        "location": "ул. Ленина",
        "time_info": "сегодня утром",
        "source_preview": "Телеграм-канал 'Новости Екб'"
    }
    """

    with GigaChat(
            credentials=AUTH_KEY,
            verify_ssl_certs=False,
            model="GigaChat",
            timeout=60,
    ) as client:
        chat_request = Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM, content=news_prompt),
                Messages(role=MessagesRole.USER, content=news_text[:1200]),  # Ограничиваем длину
            ],
            temperature=0.1,  # Меньше креатива, больше фактов
            max_tokens=500,
        )
        response = client.chat(chat_request)
        raw_content = response.choices[0].message.content.strip()

        print(f"   Получен ответ от GigaChat ({len(raw_content)} символов)")

        # Разделяем и возвращаем список JSON-объектов
        result = clean_json_response(raw_content)

        if result and len(result) > 0:
            ai_data = result[0]

            # Добавляем метаданные
            ai_data["original_preview"] = news_text[:200] + "..." if len(news_text) > 200 else news_text
            ai_data["source_url"] = source_url
            ai_data["source_name"] = source_name if source_name else source_url
            ai_data["parse_time"] = parse_time
            ai_data["analyzed_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            print(f"   ✅ AI анализ: {ai_data.get('category')} - criticality {ai_data.get('criticality')}")
            return [ai_data]
        else:
            print(f"   ⚠️ AI вернул пустой результат")
            # Возвращаем заглушку
            return [{
                "summary": news_text[:150] + "...",
                "category": "Новости",
                "criticality": 0,
                "sentiment": "нейтральная",
                "emotion": "нейтрально",
                "location": "Екатеринбург",
                "time_info": parse_time.split()[0] if parse_time else "сегодня",
                "source_preview": source_url.split('/')[-1] if source_url else "Источник",
                "original_preview": news_text[:200] + "..." if len(news_text) > 200 else news_text,
                "source_url": source_url,
                "source_name": source_name,
                "parse_time": parse_time,
                "analyzed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }]


def start_analysis(file_path, auth_key):
    """
    Анализ файла с новостями и возврат JSON результатов
    Упрощенная версия для совместимости
    """
    print(f"\n{'=' * 60}")
    print(f"🤖 АНАЛИЗ ФАЙЛА (упрощенный)")
    print(f"📁 Файл: {file_path}")
    print(f"{'=' * 60}")

    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        return {"status": "error", "message": "File not found"}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return {"status": "error", "message": f"Read error: {e}"}

    # Просто анализируем первый абзац для демо
    paragraphs = content.split('\n\n')
    if paragraphs and len(paragraphs[0]) > 100:
        test_text = paragraphs[0][:500]
        print(f"📝 Анализирую текст: {test_text[:100]}...")

        result = analyze_news_article(test_text, "file://" + file_path, "Файл",
                                      datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        return {
            "status": "success",
            "results": result,
            "analyzed_count": 1
        }

    return {"status": "warning", "message": "No text to analyze"}


if __name__ == "__main__":
    # Тестирование
    print("\n🧪 ТЕСТИРОВАНИЕ NEURAL NETWORK")

    test_text = "В центре Екатеринбурга на улице Ленина образовалась большая яма. Жители жалуются уже неделю, но коммунальные службы не реагируют. Проезд затруднён, есть риск ДТП."

    print(f"\n📝 Тестовый текст: {test_text}")

    try:
        result = analyze_news_article(test_text, "https://t.me/test", "Тест-канал", "2025-12-10 10:00:00")
        print(f"\n✅ Результат анализа:")
        print(f"   Кратко: {result[0].get('summary')}")
        print(f"   Категория: {result[0].get('category')}")
        print(f"   Критичность: {result[0].get('criticality')}")
        print(f"   Место: {result[0].get('location')}")
        print(f"   Время: {result[0].get('time_info')}")
        print(f"   Источник: {result[0].get('source_preview')}")
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")