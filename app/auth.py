from functools import wraps
from flask import session, redirect, url_for, request, flash


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Silakan login terlebih dahulu.", "error")
            return redirect(url_for("admin.login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped
