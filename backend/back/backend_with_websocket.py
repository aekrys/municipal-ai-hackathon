from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
import sqlite3
import uuid
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import asyncio
import logging
from pathlib import Path

# Парсер
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Сначала проверяем облачную БД из переменных окружения
DB_PATH = os.environ.get('DATABASE_URL')

if not DB_PATH:
    # Если нет облачной БД - используем локальную
    DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'municipal_monitoring.db')

print(f"📁 Путь к БД: {DB_PATH}")

parser_path = os.path.join(PROJECT_ROOT, 'scripts', 'parser.py')

# Проверяем существует ли файл
if os.path.exists(parser_path):
    print(f"✅ Парсер найден: {parser_path}")
    # Запускаем парсер в фоне
    try:
        subprocess.Popen(['python', parser_path],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        print("✅ Парсер запущен в фоновом режиме")
    except:
        print("⚠️ Не удалось запустить парсер в фоне")
else:
    print(f"⚠️ Парсер не найден по пути: {parser_path}")

# Загружаем переменные окружения
load_dotenv()

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ========== МЕНЕДЖЕР WEBSOCKET СОЕДИНЕНИЙ ==========
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"✅ WebSocket подключен. Всего подключений: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"🔌 WebSocket отключен. Осталось подключений: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Отправка сообщения всем подключенным клиентам"""
        if not self.active_connections:
            return

        message_json = json.dumps(message, ensure_ascii=False)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Ошибка отправки WebSocket: {e}")
                disconnected.append(connection)

        # Удаляем отключенные соединения
        for connection in disconnected:
            self.disconnect(connection)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Отправка сообщения конкретному клиенту"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Ошибка отправки персонального сообщения: {e}")


manager = ConnectionManager()


# ========== СИСТЕМА ОПОВЕЩЕНИЙ ==========
class AlertSystem:
    def __init__(self):
        self.critical_threshold = 2
        self.last_alert_time = {}
        logger.info("🚨 Система оповещений инициализирована")

    async def check_and_alert(self, problem_data: Dict[str, Any]):
        """Проверка и отправка оповещения о критической проблеме"""
        try:
            priority = problem_data.get('priority', 0)
            category = problem_data.get('category', 'unknown')
            location = problem_data.get('location', 'unknown')

            if priority >= self.critical_threshold:
                problem_key = f"{category}_{location}"
                last_time = self.last_alert_time.get(problem_key)

                if not last_time or (datetime.now() - last_time).seconds > 1800:
                    alert_message = await self.create_alert_message(problem_data)

                    await manager.broadcast({
                        "type": "alert",
                        "data": alert_message,
                        "timestamp": datetime.now().isoformat()
                    })

                    logger.warning(f"🚨 Отправлено оповещение: {category} - {location}")
                    self.last_alert_time[problem_key] = datetime.now()
                    return True

        except Exception as e:
            logger.error(f"❌ Ошибка в системе оповещений: {e}")

        return False

    async def create_alert_message(self, problem_data: Dict[str, Any]) -> Dict[str, Any]:
        """Создание сообщения для оповещения"""
        return {
            "id": problem_data.get('id', 'unknown'),
            "title": "🚨 КРИТИЧЕСКАЯ ПРОБЛЕМА",
            "category": problem_data.get('category', 'Неизвестно'),
            "location": problem_data.get('location', 'Не указано'),
            "priority": problem_data.get('priority', 0),
            "text": problem_data.get('text', '')[:100] + '...',
            "time": datetime.now().strftime('%H:%M'),
            "actions": [
                {"label": "Посмотреть на карте", "action": "show_on_map"},
                {"label": "Отметить как обработанную", "action": "mark_resolved"}
            ]
        }


alert_system = AlertSystem()

# ========== ДОБАВЛЯЕМ ПУТЬ ДЛЯ ИМПОРТА ==========
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "neural_network"))

# ========== ЗАГРУЗКА AI МОДУЛЯ ==========
AI_MODULE_LOADED = False
try:
    import importlib.util

    neural_path = os.path.join(PROJECT_ROOT, 'neural_network', 'neural_network.py')

    spec = importlib.util.spec_from_file_location("neural_network_module", neural_path)
    neural_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(neural_module)
    AI_MODULE_LOADED = True
    logger.info(f"✅ neural_network.py загружен из: {neural_path}")
except Exception as e:
    logger.error(f"⚠️ Ошибка загрузки neural_network: {e}")
    AI_MODULE_LOADED = False


# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========
def init_database():
    """Инициализация базы данных"""
    try:
        # Создаем папки если нет
        os.makedirs(os.path.join(PROJECT_ROOT, 'reports'), exist_ok=True)
        os.makedirs(os.path.join(PROJECT_ROOT, 'data'), exist_ok=True)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS problems (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                category TEXT,
                location TEXT,
                source_type TEXT DEFAULT 'system',
                sentiment TEXT DEFAULT 'neutral',
                priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'new',
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS websocket_sessions (
                session_id TEXT PRIMARY KEY,
                user_agent TEXT,
                connected_at TIMESTAMP,
                last_active TIMESTAMP,
                ip_address TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id TEXT,
                alert_type TEXT,
                message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acknowledged BOOLEAN DEFAULT FALSE
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована")

    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")


# ========== LIFESPAN МЕНЕДЖЕР ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Инициализация Municipal AI Assistant с WebSocket...")
    init_database()

    # Фоновая задача для рассылки обновлений
    asyncio.create_task(broadcast_updates_periodically())

    logger.info("✅ Бэкенд с WebSocket готов к работе")
    logger.info("📡 API доступен по: http://localhost:8000")
    logger.info("🔌 WebSocket доступен по: ws://localhost:8000/ws")

    yield

    logger.info("🔴 Бэкенд остановлен")


# ========== ФОНОВАЯ ЗАДАЧА ==========
async def broadcast_updates_periodically():
    """Периодическая рассылка обновлений через WebSocket"""
    while True:
        try:
            await asyncio.sleep(30)

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN priority >= 2 THEN 1 ELSE 0 END) as critical
                FROM problems 
                WHERE created_at > datetime('now', '-1 hour')
            ''')

            stats = cursor.fetchone()
            conn.close()

            if stats and (stats[0] or 0) > 0:
                await manager.broadcast({
                    "type": "stats_update",
                    "data": {
                        "total_last_hour": stats[0] or 0,
                        "critical_last_hour": stats[1] or 0,
                        "timestamp": datetime.now().isoformat()
                    }
                })

        except Exception as e:
            logger.error(f"❌ Ошибка в фоновой задаче: {e}")
            await asyncio.sleep(60)


# ========== СОЗДАНИЕ APP ==========
app = FastAPI(
    title="Municipal AI Assistant - System Only",
    description="Бэкенд для системных данных (парсер, AI-анализ новостей)",
    version="4.0.0",
    lifespan=lifespan
)

# ========== CORS ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== МОДЕЛЬ ДЛЯ СИСТЕМНЫХ ДАННЫХ ==========
class SystemProblemData(BaseModel):
    """Модель для системных данных (парсер, AI-анализ)"""
    text: str
    category: str
    location: str = "Екатеринбург"
    metadata: Optional[Dict] = None


# ========== WEBSOCKET ENDPOINT ==========
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await manager.send_personal_message({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }, websocket)

            elif data.get("type") == "get_stats":
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM problems')
                total = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(*) FROM problems WHERE priority >= 2')
                critical = cursor.fetchone()[0]

                conn.close()

                await manager.send_personal_message({
                    "type": "current_stats",
                    "data": {
                        "total": total or 0,
                        "critical": critical or 0,
                        "updated": datetime.now().isoformat()
                    }
                }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"❌ Ошибка WebSocket: {e}")
        manager.disconnect(websocket)


# ========== API ЭНДПОИНТЫ ==========

@app.get("/")
async def root():
    return {
        "message": "AI-помощник Главы муниципального образования",
        "version": "4.0.0",
        "system": "Обработка новостей и AI-анализ",
        "endpoints": {
            "system_report": "/api/system_report (POST) - для системных данных",
            "get_problems": "/api/problems (GET) - все проблемы",
            "get_stats": "/api/stats (GET) - статистика",
            "get_clusters": "/api/clusters (GET) - кластеры проблем",
            "websocket": "/ws - real-time обновления",
            "health": "/health - проверка работы"
        }
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "websocket_connections": len(manager.active_connections),
        "database": "connected" if os.path.exists(DB_PATH) else "not_found",
        "ai_module": "loaded" if AI_MODULE_LOADED else "stub"
    }


# ========== СИСТЕМНЫЙ ЭНДПОИНТ ==========
@app.post("/api/system_report")
async def system_report(data: dict):
    """ИСПРАВЛЕННЫЙ прием данных от интеграционного слоя"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)  # Увеличиваем таймаут
        cursor = conn.cursor()

        # Проверяем и преобразуем данные
        text = data.get("text", "")[:1000]
        category = data.get("category", "Другое")
        location = data.get("location", "Екатеринбург")
        sentiment = data.get("sentiment", "neutral")
        priority = data.get("priority", 0)
        metadata = data.get("metadata", "{}")

        # Преобразуем priority в int
        try:
            priority = int(priority)
        except:
            priority = 0

        # Вставляем данные
        cursor.execute('''
            INSERT INTO problems (text, category, location, sentiment, priority, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (text, category, location, sentiment, priority, metadata))

        conn.commit()
        conn.close()

        logger.info(f"✅ system_report: {category} - {location}")
        return {"status": "success", "message": "Данные сохранены"}

    except Exception as e:
        logger.error(f"❌ Ошибка в system_report: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )


# ========== ЭНДПОИНТЫ ДЛЯ ЧТЕНИЯ ==========

@app.get("/api/problems")
async def get_problems(
        limit: int = 20,
        offset: int = 0,
        category: str = None,
        priority: int = None,
        last_hours: int = None
):
    """УЛУЧШЕННЫЙ API с фильтрами"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Базовый запрос с фильтрами
        query = '''
            SELECT id, text, category, location, sentiment, priority, metadata, created_at
            FROM problems 
            WHERE category != 'Другое'
        '''
        params = []

        # Добавляем фильтры
        if category and category != 'all':
            query += ' AND category = ?'
            params.append(category)

        if priority is not None:
            query += ' AND priority >= ?'
            params.append(priority)

        if last_hours:
            query += ' AND created_at > datetime(?, ?)'
            params.append('now')
            params.append(f'-{last_hours} hours')

        # Сортировка и пагинация
        query += ' ORDER BY priority DESC, created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Считаем общее количество с теми же фильтрами
        count_query = 'SELECT COUNT(*) FROM problems WHERE category != "Другое"'
        count_params = []

        if category and category != 'all':
            count_query += ' AND category = ?'
            count_params.append(category)

        if priority is not None:
            count_query += ' AND priority >= ?'
            count_params.append(priority)

        if last_hours:
            count_query += ' AND created_at > datetime(?, ?)'
            count_params.append('now')
            count_params.append(f'-{last_hours} hours')

        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]

        conn.close()

        # Форматирование ответа
        problems = []
        for row in rows:
            try:
                metadata = json.loads(row[6]) if row[6] else {}
            except:
                metadata = {}

            # Безопасный парсинг даты
            created_at = row[7]
            display_time = "сегодня"

            if created_at:
                try:
                    # Убираем миллисекунды если есть
                    created_str = str(created_at).split('.')[0]
                    dt = datetime.strptime(created_str, '%Y-%m-%d %H:%M:%S')
                    display_time = dt.strftime('%H:%M')
                except:
                    display_time = str(created_at)[11:16] if len(str(created_at)) > 16 else "сегодня"

            problems.append({
                "id": row[0],
                "text": row[1],
                "category": row[2],
                "location": row[3],
                "sentiment": row[4],
                "priority": row[5],
                "metadata": metadata,
                "created_at": str(created_at),
                "display_time": display_time,
                "priority_label": "🚨 Высокий" if row[5] >= 3 else
                "⚠️ Средний" if row[5] == 2 else
                "📝 Низкий"
            })

        return {
            "problems": problems,
            "count": len(problems),
            "total": total,
            "filters": {
                "category": category,
                "priority": priority,
                "last_hours": last_hours
            }
        }

    except Exception as e:
        logger.error(f"❌ Ошибка получения проблем: {e}")
        return {"problems": [], "count": 0, "total": 0, "error": str(e)}


@app.get("/api/stats")
async def get_stats(timeframe: str = "24h"):
    """Получение статистики"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if timeframe == "24h":
            time_filter = "datetime('now', '-1 day')"
        elif timeframe == "7d":
            time_filter = "datetime('now', '-7 days')"
        else:
            time_filter = "datetime('now', '-1 day')"

        cursor.execute(f'''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN priority >= 2 THEN 1 ELSE 0 END) as critical,
                AVG(priority) as avg_priority
            FROM problems 
            WHERE created_at > {time_filter}
        ''')

        stats_row = cursor.fetchone()

        cursor.execute(f'''
            SELECT category, COUNT(*) as count
            FROM problems 
            WHERE created_at > {time_filter}
            GROUP BY category
            ORDER BY count DESC
            LIMIT 10
        ''')

        categories = cursor.fetchall()

        # Получаем последние критические проблемы
        cursor.execute(f'''
            SELECT text, category, location, priority, created_at
            FROM problems 
            WHERE priority >= 2 AND created_at > {time_filter}
            ORDER BY priority DESC, created_at DESC
            LIMIT 5
        ''')

        critical_issues = cursor.fetchall()

        conn.close()

        return {
            "timeframe": timeframe,
            "total": stats_row[0] or 0,
            "critical": stats_row[1] or 0,
            "avg_priority": round(float(stats_row[2] or 0), 2),
            "by_category": [
                {"category": cat[0], "count": cat[1]}
                for cat in categories
            ],
            "critical_issues": [
                {
                    "text": issue[0][:100] + "..." if len(issue[0]) > 100 else issue[0],
                    "category": issue[1],
                    "location": issue[2],
                    "priority": issue[3],
                    "time": issue[4]
                }
                for issue in critical_issues
            ],
            "updated": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        return {
            "timeframe": timeframe,
            "total": 0,
            "critical": 0,
            "avg_priority": 0,
            "by_category": [],
            "critical_issues": [],
            "updated": datetime.now().isoformat()
        }


@app.get("/api/clusters")
async def get_clusters():
    """Получение кластеризованных проблем"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Кластеры по категории и местоположению
        cursor.execute('''
            SELECT category, location, COUNT(*) as frequency,
                   GROUP_CONCAT(text, ' || ') as examples
            FROM problems 
            WHERE created_at > datetime('now', '-7 days')
            GROUP BY category, location
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT 10
        ''')

        clusters = []
        for row in cursor.fetchall():
            examples = row[3].split(' || ')[:3] if row[3] else []
            severity = min(3, row[2] // 2 + 1)

            clusters.append({
                "id": f"cluster_{hash(row[0] + str(row[1]))}",
                "category": row[0],
                "location": row[1] if row[1] else "Не указано",
                "frequency": row[2],
                "examples": examples,
                "severity": severity,
                "icon": ["🟢", "🟡", "🔴", "⚫"][severity - 1] if severity <= 3 else "⚪"
            })

        conn.close()

        return {
            "clusters": clusters,
            "count": len(clusters),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Ошибка получения кластеров: {e}")
        return {"clusters": [], "count": 0}


# ========== ЭНДПОИНТЫ ДЛЯ ОТЧЕТОВ ==========

@app.get("/api/generate_report")
async def api_generate_report():
    """API для генерации отчета"""
    try:
        # Импортируем функцию
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from integration_layer import generate_report

        report_file = generate_report()

        if report_file and os.path.exists(report_file):
            filename = os.path.basename(report_file)

            return {
                "success": True,
                "message": "Отчет сгенерирован",
                "filename": filename,
                "download_url": f"/api/download_report/{filename}",
                "view_url": f"/api/view_report/{filename}",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "message": "Не удалось создать отчет"
            }

    except Exception as e:
        logger.error(f"❌ Ошибка генерации отчета: {e}")
        return {
            "success": False,
            "message": f"Ошибка: {str(e)}"
        }


@app.get("/api/download_report/{filename}")
async def download_report(filename: str):
    """Скачивание отчета"""
    try:
        import os

        # Безопасное имя файла
        safe_filename = os.path.basename(filename)
        if not safe_filename.startswith("report_"):
            raise HTTPException(status_code=400, detail="Некорректное имя файла")

        # Путь к папке reports
        reports_dir = os.path.join(PROJECT_ROOT, 'reports')
        file_path = os.path.join(reports_dir, safe_filename)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Файл отчета не найден")

        # Отправляем файл
        return FileResponse(
            file_path,
            media_type='text/plain',
            filename=f"отчет_екатеринбург_{datetime.now().strftime('%Y-%m-%d')}.txt"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка скачивания отчета: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/view_report/{filename}")
async def view_report(filename: str):
    """Просмотр отчета в браузере"""
    try:
        import os

        safe_filename = os.path.basename(filename)
        if not safe_filename.startswith("report_"):
            raise HTTPException(status_code=400, detail="Некорректное имя файла")

        reports_dir = os.path.join(PROJECT_ROOT, 'reports')
        file_path = os.path.join(reports_dir, safe_filename)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Файл отчета не найден")

        # Читаем содержимое
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Возвращаем как HTML
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Отчет - {safe_filename}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: #007bff; color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; text-align: center; }}
                pre {{ 
                    background: #f8f9fa; 
                    padding: 15px; 
                    border-radius: 5px;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    font-family: 'Courier New', monospace;
                    font-size: 14px;
                    line-height: 1.5;
                }}
                .actions {{ margin-top: 20px; text-align: center; }}
                .btn {{ 
                    padding: 10px 20px; 
                    background: #28a745; 
                    color: white; 
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                    margin: 0 5px;
                    font-size: 14px;
                }}
                .btn-secondary {{ background: #6c757d; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>📄 Отчет AI-помощника Главы Екатеринбурга</h2>
                    <p>Файл: {safe_filename}</p>
                </div>

                <pre>{content}</pre>

                <div class="actions">
                    <a href="/api/download_report/{safe_filename}" class="btn">⬇️ Скачать отчет</a>
                    <a href="/" class="btn btn-secondary">🏠 На главную</a>
                    <button onclick="window.print()" class="btn">🖨️ Печать</button>
                    <button onclick="window.close()" class="btn btn-secondary">Закрыть</button>
                </div>
            </div>
        </body>
        </html>
        """

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"❌ Ошибка просмотра отчета: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard")
async def get_dashboard_data():
    """Все данные для дашборда в одном запросе"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. ОБЩАЯ СТАТИСТИКА
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN priority >= 3 THEN 1 ELSE 0 END) as urgent,
                SUM(CASE WHEN created_at > datetime('now', '-1 day') THEN 1 ELSE 0 END) as last_24h
            FROM problems 
            WHERE category != 'Другое'
        """)

        stats_row = cursor.fetchone()
        stats = {
            "total": stats_row[0] or 0,
            "urgent": stats_row[1] or 0,
            "last_24h": stats_row[2] or 0,
            "last_update": datetime.now().strftime("%H:%M")
        }

        # 2. РАСПРЕДЕЛЕНИЕ ПО КАТЕГОРИЯМ (последние 7 дней)
        cursor.execute("""
            SELECT category, COUNT(*) as count,
                   SUM(CASE WHEN priority >= 3 THEN 1 ELSE 0 END) as urgent_count
            FROM problems 
            WHERE created_at > datetime('now', '-7 days')
            AND category != 'Другое'
            GROUP BY category
            ORDER BY count DESC
            LIMIT 8
        """)

        categories = []
        for row in cursor.fetchall():
            categories.append({
                "name": row[0],
                "count": row[1],
                "urgent": row[2]
            })

        # 3. ПОСЛЕДНИЕ ИНЦИДЕНТЫ (высокий приоритет)
        cursor.execute("""
            SELECT id, text, category, location, priority, 
                   strftime('%H:%M', created_at) as time,
                   strftime('%d.%m', created_at) as date
            FROM problems 
            WHERE priority >= 2
            AND category != 'Другое'
            ORDER BY created_at DESC
            LIMIT 15
        """)

        incidents = []
        for row in cursor.fetchall():
            incidents.append({
                "id": row[0],
                "text": (row[1][:120] + "...") if len(row[1]) > 120 else row[1],
                "category": row[2],
                "location": row[3],
                "priority": row[4],
                "time": row[5],
                "date": row[6],
                "badge": "🚨" if row[4] >= 3 else "⚠️",
                "status": "critical" if row[4] >= 3 else "warning"
            })

        # 4. ТОП ПРОБЛЕМНЫХ ЛОКАЦИЙ
        cursor.execute("""
            SELECT location, COUNT(*) as problem_count
            FROM problems 
            WHERE location != 'Екатеринбург'
            AND category != 'Другое'
            GROUP BY location
            HAVING problem_count > 1
            ORDER BY problem_count DESC
            LIMIT 5
        """)

        hotspots = []
        for row in cursor.fetchall():
            hotspots.append({
                "location": row[0],
                "count": row[1]
            })

        conn.close()

        return {
            "status": "success",
            "stats": stats,
            "categories": categories,
            "incidents": incidents,
            "hotspots": hotspots,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Ошибка в get_dashboard_data: {e}")
        return {
            "status": "error",
            "message": str(e),
            "stats": {"total": 0, "urgent": 0, "last_24h": 0},
            "categories": [],
            "incidents": [],
            "hotspots": []
        }


# ========== ЗАПУСК СЕРВЕРА ==========
if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 60)
    logger.info("🚀 MUNICIPAL AI ASSISTANT v4.0")
    logger.info("=" * 60)
    logger.info("🤖 AI модуль: ЗАГРУЖЕН" if AI_MODULE_LOADED else "🤖 AI модуль: ЗАГЛУШКА")
    logger.info("📡 API: http://localhost:8000")
    logger.info("🔌 WebSocket: ws://localhost:8000/ws")
    logger.info("📊 Проблемы: http://localhost:8000/api/problems")
    logger.info("📈 Статистика: http://localhost:8000/api/stats")
    logger.info("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )