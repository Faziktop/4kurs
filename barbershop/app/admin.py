import os
import uuid
import shutil

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, abort,
    current_app,
)
from flask_login import login_required

from . import db
from .models import (
    Salon, Service, Specialist, Booking, User, Region, City, SalonPhoto,
    ROLE_ADMIN, ROLE_MODERATOR, ROLE_CLIENT,
)
from .decorators import roles_required

admin_bp = Blueprint("admin", __name__)

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _save_salon_photo(file, salon_id):
    if not file or not file.filename:
        return None
    if not _allowed(file.filename):
        print(f"[UPLOAD] отклонён файл: {file.filename}")
        return None
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], str(salon_id))
    os.makedirs(folder, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(folder, name)
    file.save(path)
    print(f"[UPLOAD] сохранён: {path}")
    return f"{salon_id}/{name}"


def _delete_salon_folder(salon_id):
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], str(salon_id))
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)


@admin_bp.before_request
@login_required
@roles_required(ROLE_ADMIN)
def guard():
    pass


@admin_bp.route("/")
def dashboard():
    salons_count = Salon.query.count()
    users_count = User.query.count()
    bookings_count = Booking.query.count()
    pending_count = Booking.query.filter_by(status="pending").count()
    salons = Salon.query.order_by(Salon.name).all()
    return render_template(
        "admin/dashboard.html",
        salons_count=salons_count, users_count=users_count,
        bookings_count=bookings_count, pending_count=pending_count,
        salons=salons,
    )


# ---------- Salons ----------

@admin_bp.route("/salons")
def salons():
    items = Salon.query.order_by(Salon.name).all()
    return render_template("admin/salons.html", salons=items)


@admin_bp.route("/salons/new", methods=["GET", "POST"])
def salon_new():
    regions = Region.query.order_by(Region.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:150]
        address = request.form.get("address", "").strip()[:255]
        phone = request.form.get("phone", "").strip()[:30]
        description = request.form.get("description", "").strip()[:2000]
        photo_url = request.form.get("photo_url", "").strip()[:500]
        latitude = request.form.get("latitude", type=float)
        longitude = request.form.get("longitude", type=float)
        city_id = request.form.get("city_id", type=int) or None

        if not name or not address:
            flash("Укажите название и адрес.", "danger")
            return render_template("admin/salon_form.html", salon=None, regions=regions)

        salon = Salon(
            name=name, address=address, phone=phone,
            description=description, photo_url=photo_url,
            latitude=latitude, longitude=longitude, city_id=city_id,
        )
        db.session.add(salon)
        db.session.flush()   # ← получаем salon.id

        files = request.files.getlist("photos")
        for idx, f in enumerate(files):
            rel = _save_salon_photo(f, salon.id)
            if rel:
                db.session.add(SalonPhoto(salon_id=salon.id, url=rel, position=idx))

        db.session.flush()
        if not salon.photo_url:
            first = SalonPhoto.query.filter_by(salon_id=salon.id)\
                                    .order_by(SalonPhoto.position).first()
            if first:
                salon.photo_url = first.url

        db.session.commit()
        flash("Салон добавлен.", "success")
        return redirect(url_for("admin.salons"))

    return render_template("admin/salon_form.html", salon=None, regions=regions)


@admin_bp.route("/salons/<int:salon_id>/edit", methods=["GET", "POST"])
def salon_edit(salon_id):
    salon = Salon.query.get_or_404(salon_id)
    regions = Region.query.order_by(Region.name).all()

    if request.method == "POST":
        salon.name = request.form.get("name", "").strip()[:150]
        salon.address = request.form.get("address", "").strip()[:255]
        salon.phone = request.form.get("phone", "").strip()[:30]
        salon.description = request.form.get("description", "").strip()[:2000]
        salon.photo_url = request.form.get("photo_url", "").strip()[:500]
        salon.latitude = request.form.get("latitude", type=float)
        salon.longitude = request.form.get("longitude", type=float)
        salon.city_id = request.form.get("city_id", type=int) or None
        salon.is_active = bool(request.form.get("is_active"))

        files = request.files.getlist("photos")
        start_pos = SalonPhoto.query.filter_by(salon_id=salon.id).count()
        for idx, f in enumerate(files):
            rel = _save_salon_photo(f, salon.id)
            if rel:
                db.session.add(SalonPhoto(salon_id=salon.id, url=rel,
                                          position=start_pos + idx))

        db.session.flush()
        if not salon.photo_url:
            first = SalonPhoto.query.filter_by(salon_id=salon.id)\
                                    .order_by(SalonPhoto.position).first()
            if first:
                salon.photo_url = first.url

        db.session.commit()
        flash("Салон обновлён.", "success")
        return redirect(url_for("admin.salon_edit", salon_id=salon.id))

    return render_template("admin/salon_form.html", salon=salon, regions=regions)


@admin_bp.route("/salons/<int:salon_id>/delete", methods=["POST"])
def salon_delete(salon_id):
    salon = Salon.query.get_or_404(salon_id)
    for mod in User.query.filter_by(salon_id=salon.id).all():
        mod.salon_id = None
        mod.role = ROLE_CLIENT
    _delete_salon_folder(salon.id)
    db.session.delete(salon)
    db.session.commit()
    flash("Салон удалён.", "info")
    return redirect(url_for("admin.salons"))


@admin_bp.route("/salons/<int:salon_id>/photos/<int:photo_id>/delete", methods=["POST"])
def salon_photo_delete(salon_id, photo_id):
    salon = Salon.query.get_or_404(salon_id)
    photo = SalonPhoto.query.filter_by(id=photo_id, salon_id=salon_id).first_or_404()

    removed_url = photo.url

    # Удаляем файл с диска, если это не внешняя ссылка
    if not removed_url.startswith(("http://", "https://")):
        full = os.path.join(current_app.config["UPLOAD_FOLDER"], removed_url)
        if os.path.isfile(full):
            try:
                os.remove(full)
            except OSError:
                pass

    db.session.delete(photo)
    db.session.flush()

    # Если удалили обложку — переназначить на следующее фото или обнулить
    if salon.photo_url == removed_url:
        next_photo = (SalonPhoto.query
                      .filter_by(salon_id=salon_id)
                      .order_by(SalonPhoto.position)
                      .first())
        salon.photo_url = next_photo.url if next_photo else None

    db.session.commit()
    flash("Фото удалено.", "info")
    return redirect(url_for("admin.salon_edit", salon_id=salon_id))


# ---------- Users ----------

@admin_bp.route("/users")
def users():
    items = User.query.order_by(User.role, User.full_name).all()
    salons = Salon.query.filter_by(is_active=True).order_by(Salon.name).all()
    return render_template("admin/users.html", users=items, salons=salons)


@admin_bp.route("/users/<int:user_id>/assign_moderator", methods=["POST"])
def assign_moderator(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == ROLE_ADMIN:
        flash("Нельзя изменить администратора.", "danger")
        return redirect(url_for("admin.users"))
    salon_id = request.form.get("salon_id", type=int)
    salon = Salon.query.get(salon_id) if salon_id else None
    if not salon:
        flash("Выберите салон.", "danger")
        return redirect(url_for("admin.users"))
    user.role = ROLE_MODERATOR
    user.salon_id = salon.id
    db.session.commit()
    flash(f"{user.full_name} — модератор «{salon.name}».", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/revoke_moderator", methods=["POST"])
def revoke_moderator(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != ROLE_MODERATOR:
        abort(400)
    user.role = ROLE_CLIENT
    user.salon_id = None
    db.session.commit()
    flash("Роль снята.", "info")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle_active", methods=["POST"])
def toggle_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == ROLE_ADMIN:
        flash("Нельзя заблокировать администратора.", "danger")
        return redirect(url_for("admin.users"))
    user.is_active_flag = not user.is_active_flag
    db.session.commit()
    flash("Статус обновлён.", "success")
    return redirect(url_for("admin.users"))


# ---------- Cross-salon management (админ может всё, что модератор) ----------

@admin_bp.route("/salons/<int:salon_id>/bookings")
def salon_bookings(salon_id):
    salon = Salon.query.get_or_404(salon_id)
    items = Booking.query.filter_by(salon_id=salon.id)\
                         .order_by(Booking.booking_datetime.desc()).all()
    return render_template("admin/salon_bookings.html", salon=salon, bookings=items)


@admin_bp.route("/bookings/<int:booking_id>/status", methods=["POST"])
def booking_update_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form.get("status")
    if new_status in ("pending", "confirmed", "cancelled", "completed"):
        booking.status = new_status
        db.session.commit()
        flash("Статус записи обновлён.", "success")
    return redirect(request.referrer or url_for("admin.dashboard"))


@admin_bp.route("/salons/<int:salon_id>/services")
def salon_services(salon_id):
    salon = Salon.query.get_or_404(salon_id)
    items = Service.query.filter_by(salon_id=salon.id).order_by(Service.name).all()
    return render_template("admin/salon_services.html", salon=salon, services=items)


@admin_bp.route("/salons/<int:salon_id>/services/new", methods=["GET", "POST"])
def salon_service_new(salon_id):
    salon = Salon.query.get_or_404(salon_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:150]
        description = request.form.get("description", "").strip()[:2000]
        price = request.form.get("price", type=float) or 0
        duration = request.form.get("duration_minutes", type=int) or 30
        if not name:
            flash("Укажите название.", "danger")
        else:
            db.session.add(Service(salon_id=salon.id, name=name, description=description,
                                   price=price, duration_minutes=duration))
            db.session.commit()
            flash("Услуга добавлена.", "success")
            return redirect(url_for("admin.salon_services", salon_id=salon.id))
    return render_template("admin/service_form.html", salon=salon, service=None)


@admin_bp.route("/salons/<int:salon_id>/services/<int:service_id>/edit", methods=["GET", "POST"])
def salon_service_edit(salon_id, service_id):
    salon = Salon.query.get_or_404(salon_id)
    service = Service.query.filter_by(id=service_id, salon_id=salon.id).first_or_404()
    if request.method == "POST":
        service.name = request.form.get("name", "").strip()[:150]
        service.description = request.form.get("description", "").strip()[:2000]
        service.price = request.form.get("price", type=float) or 0
        service.duration_minutes = request.form.get("duration_minutes", type=int) or 30
        service.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Услуга обновлена.", "success")
        return redirect(url_for("admin.salon_services", salon_id=salon.id))
    return render_template("admin/service_form.html", salon=salon, service=service)


@admin_bp.route("/salons/<int:salon_id>/services/<int:service_id>/delete", methods=["POST"])
def salon_service_delete(salon_id, service_id):
    salon = Salon.query.get_or_404(salon_id)
    service = Service.query.filter_by(id=service_id, salon_id=salon.id).first_or_404()
    db.session.delete(service)
    db.session.commit()
    flash("Услуга удалена.", "info")
    return redirect(url_for("admin.salon_services", salon_id=salon.id))


@admin_bp.route("/salons/<int:salon_id>/specialists")
def salon_specialists(salon_id):
    salon = Salon.query.get_or_404(salon_id)
    items = Specialist.query.filter_by(salon_id=salon.id).order_by(Specialist.full_name).all()
    return render_template("admin/salon_specialists.html", salon=salon, specialists=items)


@admin_bp.route("/salons/<int:salon_id>/specialists/new", methods=["GET", "POST"])
def salon_specialist_new(salon_id):
    salon = Salon.query.get_or_404(salon_id)
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()[:150]
        specialization = request.form.get("specialization", "").strip()[:150]
        description = request.form.get("description", "").strip()[:2000]
        if not full_name:
            flash("Укажите имя.", "danger")
        else:
            db.session.add(Specialist(salon_id=salon.id, full_name=full_name,
                                       specialization=specialization,
                                       description=description))
            db.session.commit()
            flash("Специалист добавлен.", "success")
            return redirect(url_for("admin.salon_specialists", salon_id=salon.id))
    return render_template("admin/specialist_form.html", salon=salon, specialist=None)


@admin_bp.route("/salons/<int:salon_id>/specialists/<int:spec_id>/edit", methods=["GET", "POST"])
def salon_specialist_edit(salon_id, spec_id):
    salon = Salon.query.get_or_404(salon_id)
    specialist = Specialist.query.filter_by(id=spec_id, salon_id=salon.id).first_or_404()
    if request.method == "POST":
        specialist.full_name = request.form.get("full_name", "").strip()[:150]
        specialist.specialization = request.form.get("specialization", "").strip()[:150]
        specialist.description = request.form.get("description", "").strip()[:2000]
        specialist.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Специалист обновлён.", "success")
        return redirect(url_for("admin.salon_specialists", salon_id=salon.id))
    return render_template("admin/specialist_form.html", salon=salon, specialist=specialist)


@admin_bp.route("/salons/<int:salon_id>/specialists/<int:spec_id>/delete", methods=["POST"])
def salon_specialist_delete(salon_id, spec_id):
    salon = Salon.query.get_or_404(salon_id)
    specialist = Specialist.query.filter_by(id=spec_id, salon_id=salon.id).first_or_404()
    db.session.delete(specialist)
    db.session.commit()
    flash("Специалист удалён.", "info")
    return redirect(url_for("admin.salon_specialists", salon_id=salon.id))