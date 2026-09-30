"""
Автосинхронизация фотографий салонов при старте приложения.
- Читает папки static/uploads/salons/<id>/
- Добавляет записи для новых файлов
- Удаляет записи для исчезнувших
- Обновляет salon.photo_url (обложку), проверяя существование файла
- Обнуляет photo_url, если файла нет
"""
import os
from . import db
from .models import Salon, SalonPhoto

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}


def _file_exists(base, rel_url):
    """Проверяет, что файл по относительному URL физически существует."""
    if not rel_url:
        return False
    if rel_url.startswith(("http://", "https://")):
        return True
    return os.path.isfile(os.path.join(base, rel_url))


def sync_salon_photos(app):
    base = app.config["UPLOAD_FOLDER"]
    if not os.path.isdir(base):
        os.makedirs(base, exist_ok=True)
        return

    added_total = 0
    removed_total = 0
    cleared_covers = 0

    for entry in sorted(os.listdir(base)):
        folder_path = os.path.join(base, entry)
        if not os.path.isdir(folder_path):
            continue
        if not entry.isdigit():
            print(f"[SYNC] папка '{entry}' не является id салона — пропущена")
            continue

        salon_id = int(entry)
        salon = Salon.query.get(salon_id)
        if not salon:
            print(f"[SYNC] салон id={salon_id} не найден в БД — папка '{entry}' пропущена")
            continue

        # Файлы на диске
        files_on_disk = []
        for fname in sorted(os.listdir(folder_path)):
            full = os.path.join(folder_path, fname)
            if not os.path.isfile(full):
                continue
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            if ext not in ALLOWED_EXT:
                continue
            files_on_disk.append(fname)

        rel_on_disk = [f"{salon_id}/{fname}" for fname in files_on_disk]

        # Записи в БД
        db_photos = SalonPhoto.query.filter_by(salon_id=salon_id)\
                                    .order_by(SalonPhoto.position).all()
        db_urls = {p.url: p for p in db_photos}

        # 1. Удаляем из БД то, чего нет на диске (только локальные)
        for url, photo in list(db_urls.items()):
            if url.startswith(("http://", "https://")):
                continue
            if url not in rel_on_disk:
                db.session.delete(photo)
                removed_total += 1

        db.session.flush()

        # 2. Добавляем в БД то, чего нет в БД
        existing = {p.url for p in SalonPhoto.query.filter_by(salon_id=salon_id).all()}
        start_pos = len(existing)
        for i, rel in enumerate(rel_on_disk):
            if rel in existing:
                continue
            db.session.add(SalonPhoto(salon_id=salon_id, url=rel, position=start_pos + i))
            added_total += 1

        db.session.flush()

        # 3. Обложка: проверяем существование файла
        if salon.photo_url:
            # Локальный файл, но его нет на диске → сброс
            if not salon.photo_url.startswith(("http://", "https://")):
                if not _file_exists(base, salon.photo_url):
                    salon.photo_url = None
                    cleared_covers += 1

        # Если обложки нет — берём первое фото из папки
        if not salon.photo_url:
            first = (SalonPhoto.query.filter_by(salon_id=salon_id)
                     .order_by(SalonPhoto.position).first())
            if first:
                salon.photo_url = first.url

    db.session.commit()

    print(f"[SYNC] фото: добавлено {added_total}, удалено {removed_total}, "
          f"обнулено обложек {cleared_covers}")


def sync_all_cover_covers(app):
    """Проверяет обложки ВСЕХ салонов, не только тех, у кого есть папки."""
    base = app.config["UPLOAD_FOLDER"]
    cleared = 0
    for salon in Salon.query.all():
        if not salon.photo_url:
            continue
        if salon.photo_url.startswith(("http://", "https://")):
            continue
        if not _file_exists(base, salon.photo_url):
            salon.photo_url = None
            cleared += 1
            # Пробуем подставить первое из БД
            first = (SalonPhoto.query.filter_by(salon_id=salon.id)
                     .order_by(SalonPhoto.position).first())
            if first and _file_exists(base, first.url):
                salon.photo_url = first.url
    if cleared:
        db.session.commit()
        print(f"[SYNC] обнулено битых обложек: {cleared}")