"""
Консольная админка Vibe. Работает без веб-сервера, прямо с базой.

Запуск:
    python manage.py

Доступ:
    Требуется ввести e-mail и пароль пользователя с ролью admin или moderator.
"""
import sys
from datetime import datetime

from app import create_app, db
from app.models import (
    User, Region, City, Salon, Service, Specialist, Booking,
    ROLE_ADMIN, ROLE_MODERATOR, STATUS_LABELS,
)

app = create_app()


# ---------- утилиты ввода ----------

def ask(prompt, default=None):
    v = input(f"{prompt}" + (f" [{default}]" if default is not None else "") + ": ").strip()
    if not v and default is not None:
        return default
    return v


def ask_int(prompt, default=None):
    while True:
        v = ask(prompt, default)
        if v is None or v == "":
            return None
        try:
            return int(v)
        except ValueError:
            print("  Введите число.")


def ask_float(prompt, default=None):
    while True:
        v = ask(prompt, default)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except ValueError:
            print("  Введите число.")


def pause():
    input("\nEnter — продолжить...")


# ---------- авторизация ----------

def login():
    print("=" * 50)
    print(" Vibe — консольная админка")
    print("=" * 50)
    email = ask("E-mail").lower()
    import getpass
    password = getpass.getpass("Пароль: ")
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        print("Неверный e-mail или пароль.")
        sys.exit(1)
    if not (user.is_admin() or user.is_moderator()):
        print("Доступ только для администраторов и модераторов.")
        sys.exit(1)
    if not user.is_active_flag:
        print("Учётная запись заблокирована.")
        sys.exit(1)
    print(f"\nЗдравствуйте, {user.full_name} ({user.role}).")
    return user


# ---------- меню ----------

def menu_admin(user):
    while True:
        print("\n=== МЕНЮ АДМИНИСТРАТОРА ===")
        print("1. Список салонов")
        print("2. Добавить салон")
        print("3. Редактировать салон")
        print("4. Удалить салон")
        print("5. Список пользователей")
        print("6. Назначить модератора")
        print("7. Снять модератора")
        print("8. Заблокировать/разблокировать пользователя")
        print("9. Все записи")
        print("10. Услуги и специалисты салона")
        print("0. Выход")
        c = ask("Выбор", "0")

        if c == "1":
            list_salons()
        elif c == "2":
            add_salon()
        elif c == "3":
            edit_salon()
        elif c == "4":
            delete_salon()
        elif c == "5":
            list_users()
        elif c == "6":
            assign_moderator()
        elif c == "7":
            revoke_moderator()
        elif c == "8":
            toggle_user()
        elif c == "9":
            list_bookings()
        elif c == "10":
            salon_children_menu()
        elif c == "0":
            return
        else:
            print("Неизвестная команда.")


def menu_moderator(user):
    if not user.salon_id:
        print("У вас не назначен салон.")
        return
    while True:
        salon = Salon.query.get(user.salon_id)
        print(f"\n=== МЕНЮ МОДЕРАТОРА «{salon.name}» ===")
        print("1. Записи клиентов")
        print("2. Изменить статус записи")
        print("3. Услуги салона")
        print("4. Добавить услугу")
        print("5. Специалисты салона")
        print("6. Добавить специалиста")
        print("7. Информация о салоне")
        print("8. Изменить информацию о салоне")
        print("0. Выход")
        c = ask("Выбор", "0")

        if c == "1":
            list_bookings(salon_id=salon.id)
        elif c == "2":
            change_booking_status(salon_id=salon.id)
        elif c == "3":
            list_services(salon.id)
        elif c == "4":
            add_service(salon.id)
        elif c == "5":
            list_specialists(salon.id)
        elif c == "6":
            add_specialist(salon.id)
        elif c == "7":
            show_salon(salon)
        elif c == "8":
            edit_salon(salon_id=salon.id)
        elif c == "0":
            return
        else:
            print("Неизвестная команда.")


# ---------- операции ----------

def list_salons():
    salons = Salon.query.order_by(Salon.name).all()
    print(f"\nВсего салонов: {len(salons)}")
    for s in salons:
        city = s.city.name if s.city else "—"
        print(f"  [{s.id}] {s.name} — {s.address} ({city})")
    pause()


def show_salon(s):
    print(f"\n[{s.id}] {s.name}")
    print(f"  Адрес: {s.address}")
    print(f"  Город: {s.city.name if s.city else '—'}")
    print(f"  Телефон: {s.phone or '—'}")
    print(f"  Фото: {s.photo_url or '—'}")
    print(f"  Активен: {'да' if s.is_active else 'нет'}")
    print(f"  Описание: {s.description or '—'}")
    pause()


def _choose_city():
    regions = Region.query.order_by(Region.name).all()
    for r in regions:
        print(f"  Регион: {r.name}")
        for c in r.cities:
            print(f"    [{c.id}] {c.name}")
    return ask_int("city_id (Enter — не менять)", None)


def add_salon():
    name = ask("Название")
    address = ask("Адрес")
    phone = ask("Телефон", "")
    description = ask("Описание", "")
    photo_url = ask("URL фото", "")
    lat = ask_float("Широта", None)
    lon = ask_float("Долгота", None)
    print("\nДоступные города:")
    city_id = _choose_city()
    s = Salon(name=name, address=address, phone=phone, description=description,
              photo_url=photo_url, latitude=lat, longitude=lon, city_id=city_id)
    db.session.add(s)
    db.session.commit()
    print(f"Салон добавлен, id={s.id}")
    pause()


def edit_salon(salon_id=None):
    if salon_id is None:
        salon_id = ask_int("id салона")
    s = Salon.query.get(salon_id)
    if not s:
        print("Не найден.")
        pause(); return
    s.name = ask("Название", s.name)
    s.address = ask("Адрес", s.address)
    s.phone = ask("Телефон", s.phone or "")
    s.description = ask("Описание", s.description or "")
    s.photo_url = ask("URL фото", s.photo_url or "")
    s.latitude = ask_float("Широта", s.latitude)
    s.longitude = ask_float("Долгота", s.longitude)
    new_city = _choose_city()
    if new_city:
        s.city_id = new_city
    db.session.commit()
    print("Обновлено.")
    pause()


def delete_salon():
    sid = ask_int("id салона")
    s = Salon.query.get(sid)
    if not s:
        print("Не найден."); pause(); return
    if ask(f"Удалить «{s.name}»? (yes/no)", "no").lower() != "yes":
        return
    for mod in User.query.filter_by(salon_id=s.id).all():
        mod.salon_id = None
        mod.role = "client"
    db.session.delete(s)
    db.session.commit()
    print("Удалено.")
    pause()


def list_users():
    users = User.query.order_by(User.role, User.full_name).all()
    for u in users:
        salon = u.salon.name if u.salon else "—"
        print(f"  [{u.id}] {u.full_name} | {u.email} | {u.role} | {salon} | "
              f"{'актив' if u.is_active_flag else 'блок'}")
    pause()


def assign_moderator():
    uid = ask_int("id пользователя")
    u = User.query.get(uid)
    if not u:
        print("Не найден."); pause(); return
    print("Выберите салон:")
    list_salons()
    sid = ask_int("id салона")
    s = Salon.query.get(sid)
    if not s:
        print("Салон не найден."); pause(); return
    u.role = ROLE_MODERATOR
    u.salon_id = s.id
    db.session.commit()
    print(f"{u.full_name} теперь модератор «{s.name}».")
    pause()


def revoke_moderator():
    uid = ask_int("id пользователя")
    u = User.query.get(uid)
    if not u or u.role != ROLE_MODERATOR:
        print("Не найден или не модератор."); pause(); return
    u.role = "client"
    u.salon_id = None
    db.session.commit()
    print("Роль снята.")
    pause()


def toggle_user():
    uid = ask_int("id пользователя")
    u = User.query.get(uid)
    if not u or u.role == ROLE_ADMIN:
        print("Не найден или администратор."); pause(); return
    u.is_active_flag = not u.is_active_flag
    db.session.commit()
    print("Статус:", "активен" if u.is_active_flag else "заблокирован")
    pause()


def list_bookings(salon_id=None):
    q = Booking.query
    if salon_id:
        q = q.filter_by(salon_id=salon_id)
    items = q.order_by(Booking.booking_datetime).all()
    for b in items:
        print(f"  [{b.id}] {b.booking_datetime:%d.%m.%Y %H:%M} | {b.salon.name} | "
              f"{b.service.name} | {b.client.full_name} ({b.client.phone or b.client.email}) | "
              f"{STATUS_LABELS.get(b.status, b.status)}")
    pause()


def change_booking_status(salon_id=None):
    bid = ask_int("id записи")
    b = Booking.query.get(bid)
    if not b or (salon_id and b.salon_id != salon_id):
        print("Не найдена."); pause(); return
    print("Доступные статусы: pending, confirmed, completed, cancelled")
    new = ask("Новый статус", b.status)
    if new in STATUS_LABELS:
        b.status = new
        db.session.commit()
        print("Обновлено.")
    else:
        print("Некорректный статус.")
    pause()


def list_services(salon_id):
    items = Service.query.filter_by(salon_id=salon_id).all()
    for s in items:
        print(f"  [{s.id}] {s.name} — {s.price} ₽ / {s.duration_minutes} мин")
    pause()


def add_service(salon_id):
    name = ask("Название услуги")
    desc = ask("Описание", "")
    price = ask_float("Цена", 0)
    dur = ask_int("Длительность, мин", 30)
    db.session.add(Service(salon_id=salon_id, name=name, description=desc,
                           price=price, duration_minutes=dur))
    db.session.commit()
    print("Услуга добавлена.")
    pause()


def list_specialists(salon_id):
    items = Specialist.query.filter_by(salon_id=salon_id).all()
    for s in items:
        print(f"  [{s.id}] {s.full_name} — {s.specialization or '—'}")
    pause()


def add_specialist(salon_id):
    name = ask("ФИО специалиста")
    spec = ask("Специализация", "")
    desc = ask("Описание", "")
    db.session.add(Specialist(salon_id=salon_id, full_name=name,
                              specialization=spec, description=desc))
    db.session.commit()
    print("Специалист добавлен.")
    pause()


def salon_children_menu():
    sid = ask_int("id салона")
    s = Salon.query.get(sid)
    if not s:
        print("Не найден."); pause(); return
    while True:
        print(f"\n=== «{s.name}» ===")
        print("1. Услуги")
        print("2. Добавить услугу")
        print("3. Специалисты")
        print("4. Добавить специалиста")
        print("5. Записи")
        print("0. Назад")
        c = ask("Выбор", "0")
        if c == "1":
            list_services(s.id)
        elif c == "2":
            add_service(s.id)
        elif c == "3":
            list_specialists(s.id)
        elif c == "4":
            add_specialist(s.id)
        elif c == "5":
            list_bookings(salon_id=s.id)
        elif c == "0":
            return


# ---------- вход ----------

def main():
    with app.app_context():
        user = login()
        if user.is_admin():
            menu_admin(user)
        else:
            menu_moderator(user)
        print("\nДо свидания.")


if __name__ == "__main__":
    main()