"""
Наполнение БД тестовыми данными. Запуск: python seed.py
Фото салонов не задаются — их нужно загружать через админку.
"""
from app import create_app, db
from app.models import (
    User, Region, City, Salon, Service, Specialist,
    ROLE_ADMIN, ROLE_MODERATOR, ROLE_CLIENT,
)
from app.regions import REGIONS

app = create_app()


# Шаблоны услуг по типам салонов
SERVICES_BARBER = [
    ("Мужская стрижка", "Стрижка машинкой и ножницами", 1200, 40),
    ("Стрижка бороды", "Оформление бороды", 800, 30),
    ("Королевское бритьё", "Опасная бритва + горячее полотенце", 1000, 30),
    ("Детская стрижка", "Для детей до 12 лет", 700, 30),
    ("Камуфляж седины", "Тонирование седых волос", 900, 40),
]
SERVICES_SALON = [
    ("Женская стрижка", "Стрижка и укладка", 2000, 60),
    ("Окрашивание", "Однотонное окрашивание", 3500, 120),
    ("Укладка", "Укладка феном и стайлером", 1200, 40),
    ("Уход за волосами", "Маска и восстановление", 1500, 50),
    ("Мелирование", "Классическое мелирование", 3000, 120),
]
SERVICES_BEAUTY = [
    ("Маникюр", "Классический маникюр", 1500, 60),
    ("Педикюр", "Аппаратный педикюр", 2000, 70),
    ("Наращивание ресниц", "Классика", 2500, 90),
    ("Коррекция брови", "Коррекция и окрашивание", 900, 40),
    ("Чистка лица", "Ультразвуковая чистка", 3500, 80),
]

SPECIALISTS = [
    ("Игорь Соколов", "Барбер"),
    ("Максим Петров", "Барбер, бритьё"),
    ("Анна Кузнецова", "Стилист-колорист"),
    ("Елена Смирнова", "Стилист"),
    ("Дмитрий Орлов", "Барбер"),
    ("Ольга Иванова", "Мастер маникюра"),
    ("Светлана Белова", "Косметолог"),
    ("Артём Гусев", "Парикмахер-универсал"),
]


def make_services(salon, templates):
    return [Service(salon_id=salon.id, name=n, description=d, price=p, duration_minutes=m)
            for n, d, p, m in templates]


def make_specialists(salon):
    return [Specialist(salon_id=salon.id, full_name=name, specialization=spec)
            for name, spec in SPECIALISTS[:5]]


with app.app_context():
    db.drop_all()
    db.create_all()

    # ---- Регионы и города ----
    city_by_name = {}
    for reg in REGIONS:
        region = Region(name=reg["name"])
        db.session.add(region)
        db.session.flush()
        for c in reg["cities"]:
            city = City(region_id=region.id, name=c["name"],
                        latitude=c["lat"], longitude=c["lon"])
            db.session.add(city)
            db.session.flush()
            city_by_name[c["name"]] = city

    # ---- Админ ----
    admin = User(full_name="Администратор Vibe", email="admin@barber.local",
                 phone="+79000000001", role=ROLE_ADMIN, phone_verified=True)
    admin.set_password("admin123")
    db.session.add(admin)

    # ---- Салоны ----
    SALONS_DATA = [
        ("Vibe Barber на Тверской", "Москва", "г. Москва, ул. Тверская, д. 10",
         "+7 (495) 111-22-33", 55.764989, 37.605549, "barber"),
        ("Vibe Studio на Арбате", "Москва", "г. Москва, ул. Арбат, д. 5",
         "+7 (495) 444-55-66", 55.751244, 37.591767, "salon"),
        ("Vibe Beauty в Химках", "Химки", "г. Химки, ул. Ленина, д. 3",
         "+7 (495) 777-88-99", 55.8970, 37.4297, "beauty"),
        ("Vibe Barber на Невском", "Санкт-Петербург", "г. СПб, Невский пр., д. 28",
         "+7 (812) 111-22-33", 59.9356, 30.3256, "barber"),
        ("Vibe Studio на Рубинштейна", "Санкт-Петербург", "г. СПб, ул. Рубинштейна, д. 15",
         "+7 (812) 222-33-44", 59.9289, 30.3435, "salon"),
        ("Vibe Barber в Казани", "Казань", "г. Казань, ул. Баумана, д. 20",
         "+7 (843) 111-22-33", 55.7903, 49.1203, "barber"),
        ("Vibe Beauty в Казани", "Казань", "г. Казань, ул. Петербургская, д. 50",
         "+7 (843) 555-66-77", 55.7794, 49.1358, "beauty"),
        ("Vibe Barber в Ижевске", "Ижевск", "г. Ижевск, ул. Пушкинская, д. 15",
         "+7 (341) 111-22-33", 56.8527, 53.2115, "barber"),
        ("Vibe Beauty в Ижевске", "Ижевск", "г. Ижевск, ул. Советская, д. 8",
         "+7 (341) 222-33-44", 56.8490, 53.2050, "beauty"),
        ("Vibe Barber в Екатеринбурге", "Екатеринбург", "г. Екатеринбург, ул. Вайнера, д. 12",
         "+7 (343) 111-22-33", 56.8367, 60.6144, "barber"),
        ("Vibe Studio в Новосибирске", "Новосибирск", "г. Новосибирск, Красный пр., д. 100",
         "+7 (383) 111-22-33", 55.0302, 82.9204, "salon"),
        ("Vibe Beauty в Сочи", "Сочи", "г. Сочи, ул. Навагинская, д. 9",
         "+7 (862) 111-22-33", 43.5855, 39.7231, "beauty"),
    ]

    for name, city_name, addr, phone, lat, lon, kind in SALONS_DATA:
        s = Salon(city_id=city_by_name[city_name].id, name=name, address=addr,
                  phone=phone, latitude=lat, longitude=lon, kind=kind,
                  description=f"{name} — {kind} с опытными мастерами.")
        db.session.add(s)
        db.session.flush()

        if kind == "barber":
            db.session.add_all(make_services(s, SERVICES_BARBER))
        elif kind == "salon":
            db.session.add_all(make_services(s, SERVICES_SALON))
        else:
            db.session.add_all(make_services(s, SERVICES_BEAUTY))

        db.session.add_all(make_specialists(s))

    db.session.flush()

    # ---- Модератор ----
    moderator = User(full_name="Модератор Vibe", email="moderator@barber.local",
                     phone="+79000000002", role=ROLE_MODERATOR,
                     salon_id=Salon.query.first().id, phone_verified=True)
    moderator.set_password("moder123")
    db.session.add(moderator)

    # ---- Клиент ----
    client = User(full_name="Тестовый Клиент", email="client@barber.local",
                  phone="+79000000003", role=ROLE_CLIENT, phone_verified=True)
    client.set_password("client123")
    db.session.add(client)

    db.session.commit()

    print("База данных наполнена.")
    print("Админ:     admin@barber.local / admin123  (или +79000000001 / admin123)")
    print("Модератор: moderator@barber.local / moder123")
    print("Клиент:    client@barber.local / client123")
    print()
    print("Фотографии салонов не заданы — загрузите их через админку:")
    print("  /admin/salons -> Изменить -> поле 'Загрузить фотографии'")
    print("  Файлы сохранятся в static/uploads/salons/<id>/")