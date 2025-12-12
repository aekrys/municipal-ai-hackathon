import asyncio
from datetime import datetime


class AlertSystem:
    def __init__(self):
        self.critical_threshold = 3
        self.last_alert_time = {}

    async def check_and_alert(self, problem):
        """Проверка и отправка оповещения о критической проблеме"""
        if problem.priority >= self.critical_threshold:
            # Проверяем, не отправляли ли недавно оповещение
            problem_key = f"{problem.category}_{problem.location}"
            last_time = self.last_alert_time.get(problem_key)

            if not last_time or (datetime.now() - last_time).seconds > 3600:  # 1 час
                await self.send_alert(problem)
                self.last_alert_time[problem_key] = datetime.now()

    async def send_alert(self, problem):
        """Отправка оповещения (можно подключить Telegram/Email/SMS)"""
        alert_message = f"""
        🚨 КРИТИЧЕСКАЯ ПРОБЛЕМА
        Категория: {problem.category}
        Место: {problem.location}
        Описание: {problem.text[:100]}...
        Приоритет: {problem.priority}/3
        Время: {datetime.now().strftime('%H:%M')}
        """
        # TODO: Реализовать отправку в Telegram канал администраторов
        print(f"📢 Оповещение отправлено: {alert_message}")