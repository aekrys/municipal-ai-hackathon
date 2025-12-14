// app.js - Основной JavaScript для мини-приложения

// Telegram WebApp
const tg = window.Telegram.WebApp;

// WebSocket соединение
let ws = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

// Текущая вкладка
let currentTab = 'dashboard';

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Municipal AI Assistant загружен');

    // Инициализация Telegram WebApp
    if (tg) {
        tg.ready();
        tg.expand();
        console.log('✅ Telegram WebApp активирован');
    }

    // Загрузить начальные данные
    loadDashboardData();
    loadProblems();

    // Подключиться к WebSocket
    connectWebSocket();

    // Обновлять данные каждые 30 секунд
    setInterval(loadDashboardData, 30000);
    setInterval(loadProblems, 60000);
});

// ========== УПРАВЛЕНИЕ ВКЛАДКАМИ ==========
function showTab(tabName) {
    currentTab = tabName;

    // Скрыть все вкладки
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.style.display = 'none';
    });

    // Показать выбранную вкладку
    const activeTab = document.getElementById(`${tabName}-tab`);
    if (activeTab) {
        activeTab.style.display = 'block';
    }

    // Обновить активную кнопку навигации
    document.querySelectorAll('.nav-tab').forEach(btn => {
        btn.classList.remove('active');
    });

    const activeBtn = Array.from(document.querySelectorAll('.nav-tab')).find(btn =>
        btn.textContent.includes(tabName === 'dashboard' ? 'Дашборд' :
                               tabName === 'clusters' ? 'Кластеры' : 'Как работает')
    );

    if (activeBtn) {
        activeBtn.classList.add('active');
    }

    // Загрузить данные для вкладки
    if (tabName === 'dashboard') {
        loadDashboardData();
    } else if (tabName === 'clusters') {
        loadClusters();
    }
}

// ========== WEBSOCKET СОЕДИНЕНИЕ ==========
function connectWebSocket() {
    const wsUrl = 'ws://localhost:8000/ws';

    try {
        ws = new WebSocket(wsUrl);
        updateConnectionStatus('connecting');

        ws.onopen = function() {
            console.log('✅ WebSocket подключен');
            updateConnectionStatus('connected');
            reconnectAttempts = 0;

            // Запросить текущую статистику
            ws.send(JSON.stringify({ type: 'get_stats' }));

            // Периодически отправлять ping
            setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'ping' }));
                }
            }, 25000);
        };

        ws.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                console.log('📩 WebSocket сообщение:', data);
                handleWebSocketMessage(data);
            } catch (e) {
                console.error('❌ Ошибка парсинга WebSocket:', e);
            }
        };

        ws.onclose = function() {
            console.log('🔌 WebSocket отключен');
            updateConnectionStatus('disconnected');

            // Попытка переподключения
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                console.log(`🔄 Попытка переподключения ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}`);
                setTimeout(connectWebSocket, 3000);
            }
        };

        ws.onerror = function(error) {
            console.error('❌ WebSocket ошибка:', error);
            updateConnectionStatus('disconnected');
        };

    } catch (error) {
        console.error('❌ Ошибка создания WebSocket:', error);
        updateConnectionStatus('disconnected');
    }
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'alert':
            showAlertNotification(data.data);
            break;
        case 'new_problem':
            addProblemToList(data.data);
            break;
        case 'stats_update':
            updateStatsDisplay(data.data);
            break;
        case 'current_stats':
            updateStatsDisplay(data.data);
            break;
        case 'pong':
            console.log('🏓 Pong получен');
            break;
        default:
            console.log('📨 Неизвестный тип сообщения:', data.type);
    }
}

function updateConnectionStatus(status) {
    const statusElement = document.getElementById('connection-status');
    if (!statusElement) return;

    const dot = statusElement.querySelector('.status-dot');
    const text = statusElement.querySelector('.status-text');

    statusElement.className = `connection-status ${status}`;
    dot.className = `status-dot ${status}`;

    switch (status) {
        case 'connected':
            text.textContent = 'В реальном времени';
            break;
        case 'disconnected':
            text.textContent = 'Нет соединения';
            break;
        case 'connecting':
            text.textContent = 'Подключение...';
            break;
    }
}

// ========== ЗАГРУЗКА ДАННЫХ ==========
async function loadDashboardData() {
    try {
        const timeframe = document.getElementById('time-filter') ? document.getElementById('time-filter').value : '24h';
        const response = await fetch(`http://localhost:8000/api/stats?timeframe=${timeframe}`);
        const data = await response.json();

        if (data && currentTab === 'dashboard') {
            updateDashboard(data);
        }
    } catch (error) {
        console.error('❌ Ошибка загрузки дашборда:', error);

        // Демо данные при ошибке
        if (currentTab === 'dashboard') {
            showDemoData();
        }
    }
}

async function loadProblems(limit = 50) {
    try {
        const response = await fetch(`http://localhost:8000/api/problems?limit=${limit}`);
        const data = await response.json();

        if (data.problems && data.problems.length > 0) {
            updateProblemsList(data.problems);
        }
    } catch (error) {
        console.error('❌ Ошибка загрузки проблем:', error);
    }
}

async function loadClusters() {
    try {
        const response = await fetch('http://localhost:8000/api/clusters');
        const data = await response.json();

        if (data.clusters && data.clusters.length > 0) {
            updateClustersList(data.clusters);
        } else {
            showNoClustersMessage();
        }
    } catch (error) {
        console.error('❌ Ошибка загрузки кластеров:', error);
        showClustersError();
    }
}

// ========== ОБНОВЛЕНИЕ ИНТЕРФЕЙСА ==========
function updateDashboard(stats) {
    // Обновление цифр статистики
    const totalElement = document.getElementById('total-count');
    const criticalElement = document.getElementById('critical-count');
    const lastHourElement = document.getElementById('last-hour-count');
    const avgPriorityElement = document.getElementById('avg-priority');

    if (totalElement) totalElement.textContent = stats.total || 0;
    if (criticalElement) criticalElement.textContent = stats.critical || 0;
    if (lastHourElement) lastHourElement.textContent = stats.total_last_hour || 0;
    if (avgPriorityElement) avgPriorityElement.textContent = stats.avg_priority ? stats.avg_priority.toFixed(1) : '0.0';

    // Обновление категорий
    const categoriesContainer = document.getElementById('categories-list');
    if (categoriesContainer && stats.by_category) {
        categoriesContainer.innerHTML = stats.by_category.map(cat => `
            <div class="category-item">
                <div class="category-info">
                    <span class="category-name">${cat.category}</span>
                    <span class="category-count">${cat.count}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${Math.min(100, (cat.count / 10) * 100)}%"></div>
                </div>
            </div>
        `).join('');
    }

    // Обновление проблем
    if (stats.critical_issues && stats.critical_issues.length > 0) {
        updateProblemsList(stats.critical_issues);
    }

    // Обновить время последнего обновления
    updateLastUpdateTime();
}

function updateProblemsList(problems) {
    const container = document.getElementById('problems-list');
    if (!container) return;

    if (!problems || problems.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div style="font-size: 48px; color: #ccc;">✅</div>
                <p>Нет проблем за выбранный период</p>
            </div>
        `;
        return;
    }

    container.innerHTML = problems.map(problem => `
        <div class="problem-card ${getPriorityClass(problem.priority || problem.metadata?.criticality || 0)}">
            <div class="problem-header">
                <span class="problem-category">${problem.category || 'Другое'}</span>
                <span class="problem-criticality">${getCriticalityIcon(problem.priority || problem.metadata?.criticality || 0)}</span>
                <span class="problem-time">${formatTime(problem.created_at)}</span>
            </div>

            <div class="problem-summary">
                <strong>${problem.text || 'Нет описания'}</strong>
            </div>

            <div class="problem-details">
                <div class="problem-location">
                    <span>📍 ${problem.location || 'Не указано'}</span>
                    ${problem.metadata?.time_info ? `<span class="time-mentioned">🕐 ${problem.metadata.time_info}</span>` : ''}
                </div>

                <div class="problem-meta">
                    <span class="sentiment ${problem.sentiment || problem.metadata?.sentiment || 'neutral'}">
                        ${getSentimentIcon(problem.sentiment || problem.metadata?.sentiment)} ${problem.sentiment || problem.metadata?.sentiment || 'нейтральная'}
                    </span>

                    ${problem.metadata?.source_url ? `
                    <a href="${problem.metadata.source_url}"
                       target="_blank"
                       class="source-link"
                       title="Перейти к источнику">
                        🔗 Источник
                    </a>
                    ` : ''}

                    ${problem.metadata?.original_preview ? `
                    <button onclick="showFullText('${escapeHtml(problem.metadata.original_preview)}')"
                            class="btn-more">
                        📝 Подробнее
                    </button>
                    ` : ''}
                </div>
            </div>
        </div>
    `).join('');
}

function updateClustersList(clusters) {
    const container = document.getElementById('clusters-list');
    if (!container) return;

    container.innerHTML = clusters.map(cluster => `
        <div class="cluster-card severity-${cluster.severity}">
            <div class="cluster-header">
                <span class="cluster-category">${cluster.category}</span>
                <span class="cluster-location">📍 ${cluster.location}</span>
                <span class="cluster-frequency">${cluster.frequency} повторений</span>
            </div>

            <div class="cluster-examples">
                <strong>Примеры проблем:</strong>
                <ul>
                    ${cluster.examples.map(example =>
                        `<li>${escapeHtml(example.substring(0, 80))}...</li>`
                    ).join('')}
                </ul>
            </div>

            <div class="cluster-footer">
                <span class="cluster-severity">
                    ${cluster.icon || '⚠️'} Серьезность: ${cluster.severity}/3
                </span>
                <button onclick="viewClusterProblems('${cluster.category}', '${cluster.location}')"
                        class="btn-view">
                    Показать все
                </button>
            </div>
        </div>
    `).join('');
}

function addProblemToList(problem) {
    const container = document.getElementById('problems-list');
    if (!container) return;

    const problemHtml = `
        <div class="problem-card new-problem ${getPriorityClass(problem.priority)}">
            <div class="problem-header">
                <span class="problem-category">${problem.category || 'Другое'}</span>
                <span class="problem-criticality">${getCriticalityIcon(problem.priority)}</span>
                <span class="problem-time">Только что</span>
            </div>

            <div class="problem-summary">
                <strong>${problem.text || 'Нет описания'}</strong>
            </div>

            <div class="problem-details">
                <div class="problem-location">
                    <span>📍 ${problem.location || 'Не указано'}</span>
                </div>

                <div class="problem-meta">
                    <span class="sentiment ${problem.sentiment || 'neutral'}">
                        ${getSentimentIcon(problem.sentiment)} ${problem.sentiment || 'нейтральная'}
                    </span>
                </div>
            </div>
        </div>
    `;

    // Добавить в начало
    container.insertAdjacentHTML('afterbegin', problemHtml);

    // Анимация нового элемента
    const newElement = container.querySelector('.new-problem');
    if (newElement) {
        setTimeout(() => {
            newElement.classList.remove('new-problem');
        }, 3000);
    }

    // Показать уведомление
    showAlertNotification({
        title: "Новая проблема",
        category: problem.category,
        location: problem.location,
        text: problem.text
    });
}

function updateStatsDisplay(stats) {
    const totalElement = document.getElementById('total-count');
    const criticalElement = document.getElementById('critical-count');

    if (totalElement && stats.total_last_hour !== undefined) {
        totalElement.textContent = stats.total_last_hour;
    }

    if (criticalElement && stats.critical_last_hour !== undefined) {
        criticalElement.textContent = stats.critical_last_hour;
    }
}

function updateLastUpdateTime() {
    const timeElement = document.getElementById('last-update-time');
    if (timeElement) {
        const now = new Date();
        timeElement.textContent = now.toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }
}

// ========== УВЕДОМЛЕНИЯ ==========
function showAlertNotification(alert) {
    // Создать уведомление
    const notification = document.createElement('div');
    notification.className = 'alert-notification';
    notification.innerHTML = `
        <div class="alert-header">
            <span class="alert-icon">🚨</span>
            <strong>${alert.title}</strong>
        </div>
        <div class="alert-body">
            <p><strong>${alert.category}</strong> - ${alert.location}</p>
            <p>${alert.text}</p>
        </div>
        <div class="alert-time">${new Date().toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'})}</div>
    `;

    // Добавить на страницу
    document.body.appendChild(notification);

    // Автоматическое удаление через 10 секунд
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 10000);
}

function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container');
    if (!container) return;

    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <strong>${type === 'alert' ? '🚨' : type === 'error' ? '❌' : type === 'warning' ? '⚠️' : 'ℹ️'}</strong>
            <span>${message}</span>
        </div>
        <button onclick="this.parentElement.remove()" class="notification-close">×</button>
    `;

    container.appendChild(notification);

    // Автоматическое удаление через 5 секунд
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
function getPriorityClass(priority) {
    if (priority >= 2) return 'critical';
    if (priority >= 1) return 'warning';
    return 'normal';
}

function getCriticalityIcon(criticality) {
    const icons = ['🟢', '🟡', '🟠', '🔴', '🟣', '⚫'];
    return icons[Math.min(criticality, 5)] || '⚪';
}

function getSentimentIcon(sentiment) {
    const icons = {
        'негативная': '😠',
        'нейтральная': '😐',
        'позитивная': '😊'
    };
    return icons[sentiment] || '😐';
}

function formatTime(dateString) {
    if (!dateString) return 'Неизвестно';

    try {
        const date = new Date(dateString);
        const now = new Date();
        const diff = Math.floor((now - date) / 1000);

        if (diff < 60) return 'Только что';
        if (diff < 3600) return `${Math.floor(diff / 60)} мин. назад`;
        if (diff < 86400) return `${Math.floor(diff / 3600)} ч. назад`;
        return date.toLocaleDateString('ru-RU');
    } catch (e) {
        return dateString;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showFullText(text) {
    alert(text);
}

function viewClusterProblems(category, location) {
    alert(`Показать все проблемы: ${category} в ${location}`);
    // В реальной реализации здесь можно загрузить и отфильтровать проблемы
}

// ========== ДЕМО-РЕЖИМ ==========
function showDemoData() {
    console.log('📱 Показываем демо-данные...');

    // Демо статистика
    const totalElement = document.getElementById('total-count');
    const criticalElement = document.getElementById('critical-count');
    const lastHourElement = document.getElementById('last-hour-count');
    const avgPriorityElement = document.getElementById('avg-priority');

    if (totalElement) totalElement.textContent = "15";
    if (criticalElement) criticalElement.textContent = "3";
    if (lastHourElement) lastHourElement.textContent = "5";
    if (avgPriorityElement) avgPriorityElement.textContent = "1.8";

    // Демо проблемы
    const demoProblems = [
        {
            text: "Большая яма на проезжей части ул. Ленина, движение затруднено",
            category: "Дороги",
            location: "ул. Ленина, 15",
            priority: 2,
            sentiment: "негативная",
            metadata: {
                criticality: 2,
                time_info: "сегодня утром",
                source_url: "https://t.me/ekb_news",
                original_preview: "На улице Ленина образовалась яма размером 1x1 метр. Движение затруднено, есть риск ДТП."
            }
        },
        {
            text: "Прорыв трубы на улице Малышева, подтопление проезжей части",
            category: "ЖКХ",
            location: "ул. Малышева, 58",
            priority: 3,
            sentiment: "негативная",
            metadata: {
                criticality: 3,
                time_info: "2 часа назад",
                source_url: "https://66.ru",
                original_preview: "В результате прорыва трубы затоплена проезжая часть. Коммунальные службы на месте."
            }
        }
    ];

    updateProblemsList(demoProblems);

    // Демо категории
    const demoCategories = [
        { category: "Дороги", count: 7 },
        { category: "ЖКХ", count: 4 },
        { category: "Благоустройство", count: 3 },
        { category: "Транспорт", count: 1 }
    ];

    const categoriesContainer = document.getElementById('categories-list');
    if (categoriesContainer) {
        categoriesContainer.innerHTML = demoCategories.map(cat => `
            <div class="category-item">
                <div class="category-info">
                    <span class="category-name">${cat.category}</span>
                    <span class="category-count">${cat.count}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${Math.min(100, (cat.count / 10) * 100)}%"></div>
                </div>
            </div>
        `).join('');
    }
}

function showNoClustersMessage() {
    const container = document.getElementById('clusters-list');
    if (!container) return;

    container.innerHTML = `
        <div class="empty-state">
            <div style="font-size: 48px; color: #ccc;">📊</div>
            <p>Кластеры не найдены</p>
            <p class="empty-subtitle">Система автоматически группирует повторяющиеся проблемы</p>
        </div>
    `;
}

function showClustersError() {
    const container = document.getElementById('clusters-list');
    if (!container) return;

    container.innerHTML = `
        <div class="error-state">
            <div style="font-size: 48px; color: #ff6b6b;">❌</div>
            <p>Не удалось загрузить кластеры</p>
            <button onclick="loadClusters()" class="btn-retry">Повторить</button>
        </div>
    `;
}

// ========== ГЕНЕРАЦИЯ ОТЧЕТА ==========
async function generateReport() {
    try {
        showNotification('⏳ Генерирую отчет...', 'info');

        const response = await fetch('http://localhost:8000/api/generate_report');
        const data = await response.json();

        if (data.success && data.download_url) {
            const userChoice = confirm("Отчет сгенерирован!\n\nНажмите ОК, чтобы открыть в браузере.\nОтмена - чтобы скачать файл.");

            if (userChoice) {
                window.open(`http://localhost:8000/api/view_report/${data.filename}`, '_blank');
                showNotification('📄 Отчет открыт в новой вкладке', 'success');
            } else {
                window.open(`http://localhost:8000${data.download_url}`, '_blank');
                showNotification('⬇️ Отчет скачивается...', 'success');
            }
        } else {
            throw new Error(data.message || 'Неизвестная ошибка');
        }

    } catch (error) {
        console.error('❌ Ошибка генерации отчета:', error);
        showNotification('⚠️ Не удалось сгенерировать отчет', 'error');
    }
}

// Экспорт функций для использования в HTML
window.showTab = showTab;
window.connectWebSocket = connectWebSocket;
window.loadDashboardData = loadDashboardData;
window.loadClusters = loadClusters;
window.generateReport = generateReport;
window.showFullText = showFullText;
window.viewClusterProblems = viewClusterProblems;

console.log('✅ app.js загружен');
