from datetime import datetime
from flask import url_for
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import db

ROLE_CLIENT = "client"
ROLE_MODERATOR = "moderator"
ROLE_ADMIN = "admin"

STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"
STATUS_COMPLETED = "completed"

STATUS_LABELS = {
    STATUS_PENDING: "Ожидает подтверждения",
    STATUS_CONFIRMED: "Подтверждена",
    STATUS_CANCELLED: "Отменена",
    STATUS_COMPLETED: "Завершена",
}


class Region(db.Model):
    __tablename__ = "regions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    cities = db.relationship("City", backref="region", cascade="all, delete-orphan")


class City(db.Model):
    __tablename__ = "cities"
    id = db.Column(db.Integer, primary_key=True)
    region_id = db.Column(db.Integer, db.ForeignKey("regions.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    salons = db.relationship("Salon", backref="city")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_CLIENT)
    salon_id = db.Column(db.Integer, db.ForeignKey("salons.id"), nullable=True)
    is_active_flag = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    phone_verified = db.Column(db.Boolean, default=False, nullable=False)
    phone_code = db.Column(db.String(10), nullable=True)
    phone_code_expires = db.Column(db.DateTime, nullable=True)

    reset_code = db.Column(db.String(10), nullable=True)
    reset_code_expires = db.Column(db.DateTime, nullable=True)
    reset_channel = db.Column(db.String(10), nullable=True)

    salon = db.relationship("Salon", foreign_keys=[salon_id], backref="moderators")
    bookings = db.relationship("Booking", backref="client", foreign_keys="Booking.user_id")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.is_active_flag

    def is_admin(self):
        return self.role == ROLE_ADMIN

    def is_moderator(self):
        return self.role == ROLE_MODERATOR

    def is_client(self):
        return self.role == ROLE_CLIENT

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Salon(db.Model):
    __tablename__ = "salons"

    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30))
    description = db.Column(db.Text)
    photo_url = db.Column(db.String(500))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    kind = db.Column(db.String(20), default="barber")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    services = db.relationship("Service", backref="salon", cascade="all, delete-orphan")
    specialists = db.relationship("Specialist", backref="salon", cascade="all, delete-orphan")
    bookings = db.relationship("Booking", backref="salon", cascade="all, delete-orphan")
    photos = db.relationship("SalonPhoto", backref="salon",
                             cascade="all, delete-orphan",
                             order_by="SalonPhoto.position")

    @property
    def photo_src(self):
        return _resolve_media(self.photo_url)

    def __repr__(self):
        return f"<Salon {self.name}>"


class SalonPhoto(db.Model):
    __tablename__ = "salon_photos"

    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salons.id"), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    position = db.Column(db.Integer, default=0)

    @property
    def src(self):
        return _resolve_media(self.url)


def _resolve_media(path):
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    return url_for("static", filename=f"uploads/salons/{path}")


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salons.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    duration_minutes = db.Column(db.Integer, nullable=False, default=30)
    is_active = db.Column(db.Boolean, default=True)

    bookings = db.relationship("Booking", backref="service")


class Specialist(db.Model):
    __tablename__ = "specialists"

    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salons.id"), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    specialization = db.Column(db.String(150))
    description = db.Column(db.Text)
    photo_url = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)

    bookings = db.relationship("Booking", backref="specialist")


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    salon_id = db.Column(db.Integer, db.ForeignKey("salons.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    specialist_id = db.Column(db.Integer, db.ForeignKey("specialists.id"), nullable=True)
    booking_datetime = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def status_label(self):
        return STATUS_LABELS.get(self.status, self.status)