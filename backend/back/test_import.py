import sys
import os

# Добавляем пути
sys.path.append('.')
sys.path.append('neural_network')

print("🔍 Проверка импорта...")

try:
    # Пробуем импортировать напрямую
    from neural_network.neural_network import analyze_news_article

    print("✅ analyze_news_article импортирована напрямую")

    # Тестируем
    test_result = analyze_news_article("Тест", "url", "parser", "2025-12-11")
    print(f"✅ Функция работает, возвращает: {type(test_result)}")

except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback

    traceback.print_exc()