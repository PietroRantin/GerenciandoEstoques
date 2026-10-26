from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..services import user_service

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        usuario = user_service.autenticar(email, request.form.get("senha", ""))
        if usuario:
            session.permanent = True
            login_user(usuario, remember=bool(request.form.get("lembrar")))
            flash(f"Bem-vindo(a), {usuario.primeiro_nome}!", "success")
            destino = request.args.get("next", "")
            if not destino or urlparse(destino).netloc or not destino.startswith("/"):
                destino = url_for("dashboard.index")
            return redirect(destino)
        flash("E-mail ou senha incorretos. Confira os dados e tente novamente.", "danger")
    return render_template("auth/login.html", email=email), (401 if request.method == "POST" else 200)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema com segurança.", "info")
    return redirect(url_for("auth.login"))
