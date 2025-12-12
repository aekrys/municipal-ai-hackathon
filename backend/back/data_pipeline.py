import time
from datetime import datetime
import schedule


class MunicipalDataPipeline:
    def __init__(self):
        self.parser = NewsParser()
        self.integration = IntegrationLayer()
        self.quality_checker = DataQualityChecker()

    def run_pipeline(self):
        """Основной пайплайн обработки данных"""
        print(f"\n{'=' * 60}")
        print(f"🚀 ЗАПУСК ПАЙПЛАЙНА: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'=' * 60}")

        # 1. Сбор данных
        print("1️⃣ СБОР ДАННЫХ...")
        raw_data = self.parser.collect_data()
        print(f"   Собрано: {len(raw_data)} сообщений")

        # 2. Фильтрация
        print("2️⃣ ФИЛЬТРАЦИЯ...")
        filtered_data = [
            item for item in raw_data
            if self.quality_checker.is_municipal_problem(item['text'])
        ]
        print(f"   После фильтрации: {len(filtered_data)} муниципальных проблем")

        # 3. Обработка ИИ
        print("3️⃣ АНАЛИЗ ИИ...")
        processed = []
        for item in filtered_data[:10]:  # Ограничиваем для скорости
            try:
                result = self.integration.process_item(item)
                if result and result['priority'] > 0:
                    processed.append(result)
                    print(f"   ✅ {result['category']} (приоритет: {result['priority']})")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")

        # 4. Сохранение
        print("4️⃣ СОХРАНЕНИЕ В БД...")
        if processed:
            self.integration.save_to_database(processed)
            print(f"   Сохранено: {len(processed)} проблем")
        else:
            print("   ℹ️ Новых проблем не обнаружено")

        print(f"\n✅ ПАЙПЛАЙН ЗАВЕРШЕН")
        return len(processed)


# Запуск каждые 30 минут
if __name__ == "__main__":
    pipeline = MunicipalDataPipeline()

    # Первый запуск сразу
    pipeline.run_pipeline()

    # Планировщик
    schedule.every(30).minutes.do(pipeline.run_pipeline)

    print("\n📡 Патйплайн запущен. Ожидание новых данных...")
    while True:
        schedule.run_pending()
        time.sleep(60)