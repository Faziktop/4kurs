"""
Защита от DDoS/спама: скользящее окно + временный бан IP.
При бане соединение ЖЁСТКО ЗАКРЫВАЕТСЯ — браузер видит ERR_CONNECTION_REFUSED.
"""
import socket
import time
from collections import defaultdict

from flask import request

# Настройки
WINDOW_SECONDS = 60
MAX_REQUESTS = 120
BAN_SECONDS = 5 * 60

_attempts = defaultdict(list)
_banned_until = {}


def _client_ip():
    return request.remote_addr or "unknown"


def _hard_close_connection():
    """
    Обрывает TCP-соединение без HTTP-ответа.
    Браузер покажет обычную ошибку «Не удаётся получить доступ к сайту».
    """
    try:
        # Пытаемся закрыть сокет через внутренний API Werkzeug
        sock = request.environ.get("werkzeug.socket")
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
    except Exception:
        pass

    # На случай, если сокет не закрылся, принудительно бросаем исключение,
    # чтобы Werkzeug не успел сформировать HTTP-ответ.
    raise ConnectionResetError("banned")


def register_ddos_guard(app):
    @app.before_request
    def _ddos_guard():
        ip = _client_ip()
        now = time.time()

        until = _banned_until.get(ip)
        if until:
            if until > now:
                _hard_close_connection()
            _banned_until.pop(ip, None)

        attempts = _attempts[ip]
        while attempts and now - attempts[0] > WINDOW_SECONDS:
            attempts.pop(0)
        attempts.append(now)

        if len(attempts) > MAX_REQUESTS:
            _banned_until[ip] = now + BAN_SECONDS
            _attempts.pop(ip, None)
            _hard_close_connection()