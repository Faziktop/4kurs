import os
import uuid

from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, abort,
    current_app,
)
from flask_login import login_required, current_user

from . import db
from .models import Service, Specialist, Booking, Salon, Region, SalonPhoto, ROLE_MODERATOR
from .decorators import roles_required

moderator_bp = Blueprint("moderator", __name__)

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _save_salon_photo(file, salon_id):
    if not file or not file.filename:
        return None
    if not _allowed(file.filename):
        return None
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], str(salon_id))
    os.makedirs(folder, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(folder, name)
    file.save(path)
    return f"{salon_id}/{name}"


def _current_salon():
    if not current_user.salon_id:
        abort(403, "У вас не назначена парикмахерская. Обратитесь к администратору.")
    return Salon.query.get_or_404(current_user.salon_id)


@moderator_bp.before_request
@login_required
@roles_required(ROLE_MODERATOR)
def guard():
    pass


@moderator_bp.route("/")
def dashboard():
    salon = _current_salon()
    pending_count = Booking.query.filter_by(salon_id=salon.id, status="pending").count()
    services_count = Service.query.filter_by(salon_id=salon.id).count()
    specialists_count = Specialist.query.filter_by(salon_id=salon.id).count()
    return render_template(
        "moderator/dashboard.html",
        salon=salon,
        pending_count=pending_count,
        services_count=services_count,
        specialists_count=specialists_count,
    )


# ---------- Services ----------

@moderator_bp.route("/services")
def services():
    salon = _current_salon()
    items = Service.query.filter_by(salon_id=salon.id).order_by(Service.name).all()
    return render_template("moderator/services.html", salon=salon, services=items)


@moderator_bp.route("/services/new", methods=["GET", "POST"])
def service_new():
    salon = _current_salon()
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:150]
        description = request.form.get("description", "").strip()[:2000]
        price = request.form.get("price", type=float) or 0
        duration = request.form.get("duration_minutes", type=int) or 30
        if not name:
            flash("Укажите название услуги.", "danger")
        elif price < 0 or price > 1_000_000:
            flash("Некорректная цена.", "danger")
        elif duration < 5 or duration > 24 * 60:
            flash("Некорректная длительность.", "danger")
        else:
            db.session.add(Service(salon_id=salon.id, name=name, description=description,
                                    price=price, duration_minutes=duration))
            db.session.commit()
            flash("Услуга добавлена.", "success")
            return redirect(url_for("moderator.services"))
    return render_template("moderator/service_form.html", salon=salon, service=None)


@moderator_bp.route("/services/<int:service_id>/edit", methods=["GET", "POST"])
def service_edit(service_id):
    salon = _current_salon()
    service = Service.query.filter_by(id=service_id, salon_id=salon.id).first_or_404()
    if request.method == "POST":
        service.name = request.form.get("name", "").strip()[:150]
        service.description = request.form.get("description", "").strip()[:2000]
        price = request.form.get("price", type=float) or 0
        duration = request.form.get("duration_minutes", type=int) or 30
        if price < 0 or price > 1_000_000:
            flash("Некорректная цена.", "danger")
            return render_template("moderator/service_form.html", salon=salon, service=service)
        if duration < 5 or duration > 24 * 60:
            flash("Некорректная длительность.", "danger")
            return render_template("moderator/service_form.html", salon=salon, service=service)
        service.price = price
        service.duration_minutes = duration
        service.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Услуга обновлена.", "success")
        return redirect(url_for("moderator.services"))
    return render_template("moderator/service_form.html", salon=salon, service=service)


@moderator_bp.route("/services/<int:service_id>/delete", methods=["POST"])
def service_delete(service_id):
    salon = _current_salon()
    service = Service.query.filter_by(id=service_id, salon_id=salon.id).first_or_404()
    db.session.delete(service)
    db.session.commit()
    flash("Услуга удалена.", "info")
    return redirect(url_for("moderator.services"))


# ---------- Specialists ----------

@moderator_bp.route("/specialists")
def specialists():
    salon = _current_salon()
    items = Specialist.query.filter_by(salon_id=salon.id).order_by(Specialist.full_name).all()
    return render_template("moderator/specialists.html", salon=salon, specialists=items)


@moderator_bp.route("/specialists/new", methods=["GET", "POST"])
def specialist_new():
    salon = _current_salon()
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()[:150]
        specialization = request.form.get("specialization", "").strip()[:150]
        description = request.form.get("description", "").strip()[:2000]
        photo_url = request.form.get("photo_url", "").strip()[:300]
        if not full_name:
            flash("Укажите имя специалиста.", "danger")
        else:
            db.session.add(Specialist(salon_id=salon.id, full_name=full_name,
                                       specialization=specialization, description=description,
                                       photo_url=photo_url))
            db.session.commit()
            flash("Специалист добавлен.", "success")
            return redirect(url_for("moderator.specialists"))
    return render_template("moderator/specialist_form.html", salon=salon, specialist=None)


@moderator_bp.route("/specialists/<int:specialist_id>/edit", methods=["GET", "POST"])
def specialist_edit(specialist_id):
    salon = _current_salon()
    specialist = Specialist.query.filter_by(id=specialist_id, salon_id=salon.id).first_or_404()
    if request.method == "POST":
        specialist.full_name = request.form.get("full_name", "").strip()[:150]
        specialist.specialization = request.form.get("specialization", "").strip()[:150]
        specialist.description = request.form.get("description", "").strip()[:2000]
        specialist.photo_url = request.form.get("photo_url", "").strip()[:300]
        specialist.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Данные специалиста обновлены.", "success")
        return redirect(url_for("moderator.specialists"))
    return render_template("moderator/specialist_form.html", salon=salon, specialist=specialist)


@moderator_bp.route("/specialists/<int:specialist_id>/delete", methods=["POST"])
def specialist_delete(specialist_id):
    salon = _current_salon()
    specialist = Specialist.query.filter_by(id=specialist_id, salon_id=salon.id).first_or_404()
    db.session.delete(specialist)
    db.session.commit()
    flash("Специалист удалён.", "info")
    return redirect(url_for("moderator.specialists"))


# ---------- Bookings ----------

@moderator_bp.route("/bookings")
def bookings():
    salon = _current_salon()
    status_filter = request.args.get("status")
    query = Booking.query.filter_by(salon_id=salon.id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    items = query.order_by(Booking.booking_datetime).all()
    return render_template("moderator/bookings.html", salon=salon, bookings=items,
                           status_filter=status_filter)


@moderator_bp.route("/bookings/<int:booking_id>/status", methods=["POST"])
def booking_update_status(booking_id):
    salon = _current_salon()
    booking = Booking.query.filter_by(id=booking_id, salon_id=salon.id).first_or_404()
    new_status = request.form.get("status")
    if new_status in ("pending", "confirmed", "cancelled", "completed"):
        booking.status = new_status
        db.session.commit()
        flash("Статус записи обновлён.", "success")
    return redirect(url_for("moderator.bookings"))


# ---------- Salon profile ----------

@moderator_bp.route("/salon", methods=["GET", "POST"])
def salon_edit():
    salon = _current_salon()
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
        flash("Данные салона обновлены.", "success")
        return redirect(url_for("moderator.dashboard"))
    return render_template("moderator/salon_form.html", salon=salon, regions=regions)


@moderator_bp.route("/salon/photos/<int:photo_id>/delete", methods=["POST"])
def salon_photo_delete(photo_id):
    salon = _current_salon()
    photo = SalonPhoto.query.filter_by(id=photo_id, salon_id=salon.id).first_or_404()
    if not photo.url.startswith(("http://", "https://")):
        full = os.path.join(current_app.config["UPLOAD_FOLDER"], photo.url)
        if os.path.isfile(full):
            try:
                os.remove(full)
            except OSError:
                pass
    db.session.delete(photo)
    db.session.commit()
    flash("Фото удалено.", "info")
    return redirect(url_for("moderator.salon_edit"))