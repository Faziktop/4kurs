"""
Отправка кодов. Демо-режим — печать в консоль.
Реальные каналы: SMTP для email, SMS.ru/Twilio для телефона.
"""
import os
import random
import smtplib
from email.mime.text import MIMEText

DEMO_MODE = os.environ.get("DELIVERY_DEMO", "1") == "1"


def generate_code(length: int = 5) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def send_sms(phone: str, text: str) -> bool:
    if DEMO_MODE:
        print(f"\n=== SMS (демо) ===\nКому: {phone}\nТекст: {text}\n==================\n")
        return True
    # Реальный провайдер — вставить позже
    return False


def send_email(to_email: str, subject: str, text: str) -> bool:
    if DEMO_MODE:
        print(f"\n=== EMAIL (демо) ===\nКому: {to_email}\nТема: {subject}\n{text}\n====================\n")
        return True

    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    pwd = os.environ.get("SMTP_PASS")
    if not all([host, user, pwd]):
        return False

    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_email

    try:
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
        return True
    except Exception:
        return False