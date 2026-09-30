from functools import wraps
from flask import abort
from flask_login import current_user

from .models import ROLE_ADMIN, ROLE_MODERATOR


def roles_required(*roles):
    """Доступ разрешён указанным ролям.
    Админ ВСЕГДА проходит — у него суперправа."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role == ROLE_ADMIN:
                return f(*args, **kwargs)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator