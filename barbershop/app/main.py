import math
from datetime import datetime, timedelta, date

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, abort, jsonify)
from flask_login import login_required, current_user

from . import db, limiter
from .models import (Salon, Service, Specialist, Booking, City, Region,
                     STATUS_PENDING, STATUS_CANCELLED)

main_bp = Blueprint("main", __name__)

WORK_START_HOUR = 9
WORK_END_HOUR = 20
SLOT_STEP_MINUTES = 30


def generate_slots_for_date(day):
    slots = []
    current = datetime.combine(day, datetime.min.time()).replace(hour=WORK_START_HOUR)
    end = datetime.combine(day, datetime.min.time()).replace(hour=WORK_END_HOUR)
    while current < end:
        slots.append(current)
        current += timedelta(minutes=SLOT_STEP_MINUTES)
    return slots


@main_bp.route("/")
def index():
    q = (request.args.get("q") or "").strip()
    city_id = request.args.get("city_id", type=int)
    view = request.args.get("view", "cards")
    if view not in ("cards", "list"):
        view = "cards"

    query = Salon.query.filter_by(is_active=True)
    if city_id:
        query = query.filter_by(city_id=city_id)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Salon.address.ilike(like),
                                    Salon.name.ilike(like),
                                    Salon.description.ilike(like)))
    salons = query.order_by(Salon.name).all()

    regions = Region.query.order_by(Region.name).all()

    return render_template("index.html", salons=salons, regions=regions,
                           q=q, selected_city_id=city_id, view=view)


@main_bp.route("/api/cities")
def api_cities():
    q = (request.args.get("q") or "").strip().lower()
    all_cities = City.query.order_by(City.name).all()
    if q:
        all_cities = [c for c in all_cities if q in (c.name or "").strip().lower()]
    all_cities = all_cities[:30]
    return jsonify([{"id": c.id, "name": c.name,
                     "region": c.region.name if c.region else ""}
                    for c in all_cities])


@main_bp.route("/api/find-city")
def api_find_city():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"ok": False}), 400

    cities = City.query.all()
    if not cities:
        return jsonify({"ok": False})

    def hv(c):
        if c.latitude is None or c.longitude is None:
            return 1e18
        R = 6371.0
        phi1 = math.radians(lat)
        phi2 = math.radians(c.latitude)
        dphi = math.radians(c.latitude - lat)
        dl = math.radians(c.longitude - lon)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
        return 2 * R * math.asin(math.sqrt(a))

    best = min(cities, key=hv)
    dist_km = hv(best)
    if dist_km > 60:
        return jsonify({"ok": False, "nearest": best.name, "distance_km": round(dist_km, 1)})
    return jsonify({"ok": True, "city_id": best.id, "city_name": best.name,
                    "distance_km": round(dist_km, 1)})


@main_bp.route("/salon/<int:salon_id>")
def salon_detail(salon_id):
    salon = Salon.query.get_or_404(salon_id)
    services = Service.query.filter_by(salon_id=salon.id, is_active=True).all()
    specialists = Specialist.query.filter_by(salon_id=salon.id, is_active=True).all()
    return render_template("salon_detail.html", salon=salon,
                           services=services, specialists=specialists)


@main_bp.route("/salon/<int:salon_id>/book", methods=["GET", "POST"])
@login_required
@limiter.limit("20 per minute;100 per hour", methods=["POST"])
def book(salon_id):
    salon = Salon.query.get_or_404(salon_id)
    services = Service.query.filter_by(salon_id=salon.id, is_active=True).all()
    specialists = Specialist.query.filter_by(salon_id=salon.id, is_active=True).all()

    selected_service_id = request.values.get("service_id", type=int)
    selected_specialist_id = request.values.get("specialist_id", type=int)
    selected_date_str = request.values.get("date")
    try:
        selected_date = (datetime.strptime(selected_date_str, "%Y-%m-%d").date()
                         if selected_date_str else date.today())
    except ValueError:
        selected_date = date.today()
    if selected_date < date.today():
        selected_date = date.today()

    available_slots = []
    if selected_specialist_id:
        all_slots = generate_slots_for_date(selected_date)
        taken = {
            b.booking_datetime
            for b in Booking.query.filter_by(specialist_id=selected_specialist_id)
            .filter(Booking.status.in_(["pending", "confirmed"])).all()
        }
        now = datetime.now()
        available_slots = [s for s in all_slots if s not in taken and s > now]

    if request.method == "POST":
        service_id = request.form.get("service_id", type=int)
        specialist_id = request.form.get("specialist_id", type=int)
        slot_str = request.form.get("slot")
        note = request.form.get("note", "").strip()[:500]

        service = Service.query.filter_by(id=service_id, salon_id=salon.id).first()
        specialist = Specialist.query.filter_by(id=specialist_id, salon_id=salon.id).first()

        error = None
        booking_dt = None
        if not service or not specialist:
            error = "Выберите услугу и специалиста."
        elif not slot_str:
            error = "Выберите время."
        else:
            try:
                booking_dt = datetime.strptime(slot_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                error = "Некорректное время."

        if not error and booking_dt:
            clash = Booking.query.filter_by(
                specialist_id=specialist.id, booking_datetime=booking_dt
            ).filter(Booking.status.in_(["pending", "confirmed"])).first()
            if clash:
                error = "Время занято."
            elif booking_dt < datetime.now():
                error = "Нельзя на прошедшее время."

        if error:
            flash(error, "danger")
        else:
            db.session.add(Booking(
                user_id=current_user.id, salon_id=salon.id,
                service_id=service.id, specialist_id=specialist.id,
                booking_datetime=booking_dt, status=STATUS_PENDING, note=note))
            db.session.commit()
            flash("Заявка отправлена.", "success")
            return redirect(url_for("main.profile"))

    return render_template("booking_form.html", salon=salon, services=services,
                           specialists=specialists,
                           selected_service_id=selected_service_id,
                           selected_specialist_id=selected_specialist_id,
                           selected_date=selected_date, available_slots=available_slots)


@main_bp.route("/profile")
@login_required
def profile():
    bookings = (Booking.query.filter_by(user_id=current_user.id)
                .order_by(Booking.booking_datetime.desc()).all())
    return render_template("profile.html", bookings=bookings)


@main_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.full_name = request.form.get("full_name",
                                                  current_user.full_name).strip()[:150]
        new_phone = request.form.get("phone", current_user.phone or "").strip()[:30]
        if new_phone != (current_user.phone or ""):
            current_user.phone = new_phone
            current_user.phone_verified = False
        new_password = request.form.get("password", "")
        if new_password:
            if len(new_password) < 6:
                flash("Пароль минимум 6 символов.", "danger")
                return render_template("edit_profile.html")
            current_user.set_password(new_password)
        db.session.commit()
        flash("Профиль обновлён.", "success")
        return redirect(url_for("main.profile"))
    return render_template("edit_profile.html")


@main_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        abort(403)
    if booking.status in ("pending", "confirmed"):
        booking.status = STATUS_CANCELLED
        db.session.commit()
        flash("Запись отменена.", "info")
    else:
        flash("Эту запись нельзя отменить.", "warning")
    return redirect(url_for("main.profile"))


@main_bp.route("/rules")
def rules():
    return render_template("rules.html")


@main_bp.route("/contacts")
def contacts():
    return render_template("contacts.html")