import re
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from . import db, limiter
from .models import User, ROLE_CLIENT
from .sms import generate_code, send_sms, send_email

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p or "")
    if digits.startswith("8"):
        digits = "7" + digits[1:]
    if not digits.startswith("7") and len(digits) == 10:
        digits = "7" + digits
    return "+" + digits if digits else ""


def _find_user_by_login(login: str):
    login = login.strip().lower()
    if EMAIL_RE.match(login):
        return User.query.filter_by(email=login).first()
    phone = _normalize_phone(login)
    if phone:
        return User.query.filter_by(phone=phone).first()
    return None


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute;20 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()[:150]
        email = request.form.get("email", "").strip().lower()[:150]
        phone = _normalize_phone(request.form.get("phone", ""))[:30]
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        error = None
        if not full_name or not email or not phone or not password:
            error = "Заполните все поля."
        elif not EMAIL_RE.match(email):
            error = "Некорректный e-mail."
        elif len(phone) < 11:
            error = "Некорректный телефон."
        elif password != password2:
            error = "Пароли не совпадают."
        elif len(password) < 6:
            error = "Пароль должен быть минимум 6 символов."
        elif User.query.filter_by(email=email).first():
            error = "Пользователь с таким e-mail уже зарегистрирован."
        elif User.query.filter_by(phone=phone).first():
            error = "Пользователь с таким телефоном уже зарегистрирован."

        if error:
            flash(error, "danger")
            return render_template("register.html", full_name=full_name,
                                   email=email, phone=phone)

        user = User(full_name=full_name, email=email, phone=phone, role=ROLE_CLIENT)
        user.set_password(password)
        user.phone_verified = False
        user.phone_code = generate_code(5)
        user.phone_code_expires = datetime.utcnow() + timedelta(minutes=10)
        db.session.add(user)
        db.session.commit()

        send_sms(phone, f"Vibe: код подтверждения {user.phone_code}")

        session["pending_user_id"] = user.id
        flash("Мы отправили код на телефон. В демо-режиме смотрите консоль.", "info")
        return redirect(url_for("auth.verify_phone"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute;50 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        login_value = request.form.get("login", "").strip()[:150]
        password = request.form.get("password", "")
        user = _find_user_by_login(login_value)

        if user is None or not user.check_password(password):
            flash("Неверный логин или пароль.", "danger")
            return render_template("login.html", login=login_value)

        if not user.is_active_flag:
            flash("Учётная запись заблокирована.", "danger")
            return render_template("login.html", login=login_value)

        if not user.phone_verified:
            user.phone_code = generate_code(5)
            user.phone_code_expires = datetime.utcnow() + timedelta(minutes=10)
            db.session.commit()
            send_sms(user.phone, f"Vibe: код подтверждения {user.phone_code}")
            session["pending_user_id"] = user.id
            flash("Подтвердите номер. Код отправлен.", "info")
            return redirect(url_for("auth.verify_phone"))

        login_user(user)
        flash(f"Здравствуйте, {user.full_name}!", "success")
        return _redirect_by_role(user)

    return render_template("login.html")


@auth_bp.route("/verify-phone", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def verify_phone():
    pending_id = session.get("pending_user_id")
    if not pending_id:
        flash("Сначала войдите.", "warning")
        return redirect(url_for("auth.login"))

    user = User.query.get(pending_id)
    if not user:
        session.pop("pending_user_id", None)
        return redirect(url_for("auth.login"))

    if user.phone_verified:
        session.pop("pending_user_id", None)
        login_user(user)
        return _redirect_by_role(user)

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if not user.phone_code or not user.phone_code_expires:
            flash("Код не отправлен.", "warning")
        elif user.phone_code_expires < datetime.utcnow():
            flash("Код истёк.", "danger")
        elif code != user.phone_code:
            flash("Неверный код.", "danger")
        else:
            user.phone_verified = True
            user.phone_code = None
            user.phone_code_expires = None
            db.session.commit()
            session.pop("pending_user_id", None)
            login_user(user)
            flash("Номер подтверждён.", "success")
            return _redirect_by_role(user)
        return redirect(url_for("auth.verify_phone"))

    return render_template("verify_phone.html", phone=user.phone)


@auth_bp.route("/send-code-again", methods=["POST"])
@limiter.limit("3 per minute;10 per hour")
def send_code_again():
    pending_id = session.get("pending_user_id")
    if not pending_id:
        return redirect(url_for("auth.login"))
    user = User.query.get(pending_id)
    if not user or not user.phone:
        return redirect(url_for("auth.login"))

    user.phone_code = generate_code(5)
    user.phone_code_expires = datetime.utcnow() + timedelta(minutes=10)
    db.session.commit()
    send_sms(user.phone, f"Vibe: код подтверждения {user.phone_code}")
    flash("Код отправлен повторно.", "info")
    return redirect(url_for("auth.verify_phone"))


# ---------- Сброс пароля ----------

@auth_bp.route("/forgot", methods=["GET", "POST"])
@limiter.limit("5 per minute;20 per hour", methods=["POST"])
def forgot():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        login_value = request.form.get("login", "").strip()[:150]
        channel = request.form.get("channel", "email")
        if channel not in ("email", "phone"):
            channel = "email"

        user = _find_user_by_login(login_value)
        # По требованиям безопасности не сообщаем, найден ли пользователь
        if user:
            code = generate_code(5)
            user.reset_code = code
            user.reset_code_expires = datetime.utcnow() + timedelta(minutes=15)
            user.reset_channel = channel
            db.session.commit()

            if channel == "email":
                send_email(user.email, "Vibe — восстановление пароля",
                           f"Ваш код восстановления: {code}")
            else:
                if user.phone:
                    send_sms(user.phone, f"Vibe: код восстановления {code}")

            session["reset_user_id"] = user.id

        flash("Если такой пользователь есть, код отправлен. "
              "В демо-режиме смотрите консоль сервера.", "info")
        return redirect(url_for("auth.reset_password"))

    return render_template("forgot.html")


@auth_bp.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    uid = session.get("reset_user_id")
    if not uid:
        flash("Сначала запросите сброс пароля.", "warning")
        return redirect(url_for("auth.forgot"))

    user = User.query.get(uid)
    if not user:
        session.pop("reset_user_id", None)
        return redirect(url_for("auth.forgot"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        pwd1 = request.form.get("password", "")
        pwd2 = request.form.get("password2", "")

        if not user.reset_code or not user.reset_code_expires:
            flash("Код не был отправлен.", "danger")
        elif user.reset_code_expires < datetime.utcnow():
            flash("Срок действия кода истёк.", "danger")
        elif code != user.reset_code:
            flash("Неверный код.", "danger")
        elif len(pwd1) < 6:
            flash("Пароль минимум 6 символов.", "danger")
        elif pwd1 != pwd2:
            flash("Пароли не совпадают.", "danger")
        else:
            user.set_password(pwd1)
            user.reset_code = None
            user.reset_code_expires = None
            user.reset_channel = None
            db.session.commit()
            session.pop("reset_user_id", None)
            flash("Пароль изменён. Войдите с новым паролем.", "success")
            return redirect(url_for("auth.login"))

        return redirect(url_for("auth.reset_password"))

    return render_template("reset_password.html", channel=user.reset_channel,
                           email=user.email,
                           phone=user.phone)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли.", "info")
    return redirect(url_for("main.index"))


def _redirect_by_role(user):
    if user.is_admin():
        return redirect(url_for("admin.dashboard"))
    if user.is_moderator():
        return redirect(url_for("moderator.dashboard"))
    return redirect(url_for("main.index"))