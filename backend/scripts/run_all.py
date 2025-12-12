import asyncio
import subprocess
import time
import sys
import os
from threading import Thread


def run_parser():
    """Запуск парсера"""
    print("📰 Запуск парсера...")
    subprocess.Popen(['python', 'parser.py'])


def run_backend():
    """Запуск backend_with_websocket.py"""
    print("🚀 Запуск бэкенда...")
    # Запускаем файл в текущей директории
    subprocess.Popen(['python', 'backend_with_websocket.py'])


if __name__ == "__main__":
    run_backend()