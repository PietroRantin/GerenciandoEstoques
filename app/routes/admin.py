from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..config import DEFAULT_SETTINGS
from ..extensions import db
from ..models import User
from ..models.user import PERFIS
from ..services import alert_service, settings_service, user_service
from ..services.errors import RegraNegocioError
from ..utils.decorators import admin_required

bp = Blueprint("admin", __name__)


@bp.route("/usuarios")
@admin_required
def usuarios():
    return render_template("admin/users.html", usuarios=User.query.order_by(User.ativo.desc(), User.nome).all())


@bp.route("/usuarios/novo", methods=["GET", "POST"])
@bp.route("/usuarios/<int:usuario_id>/editar", methods=["GET", "POST"])
@admin_required
def usuario_form(usuario_id=None):
    usuario = None
    if usuario_id is not None:
        usuario = db.session.get(User, usuario_id) or abort(404)
    if request.method == "POST":
        try:
            salvo = user_service.salvar_usuario(request.form, usuario, editor=current_user)
            flash(f"Usuário \"{salvo.nome}\" salvo.", "success")
            return redirect(url_for("admin.usuarios"))
        except RegraNegocioError as exc:
            db.session.rollback()
            flash(exc.mensagem, "danger")
            return render_template("admin/user_form.html", usuario=usuario, dados=request.form, erros=exc.erros,
                                   perfis=PERFIS), 422
    return render_template("admin/user_form.html", usuario=usuario, dados={}, erros={}, perfis=PERFIS)


@bp.route("/configuracoes", methods=["GET", "POST"])
@admin_required
def configuracoes():
    if request.method == "POST":
        try:
            settings_service.salvar(request.form)
            alert_service.sincronizar_todos()
            flash("Configurações salvas. Os alertas e a Curva ABC já usam os novos valores.", "success")
            return redirect(url_for("admin.configuracoes"))
        except RegraNegocioError as exc:
            db.session.rollback()
            flash(exc.mensagem, "danger")
    return render_template("admin/settings.html", valores=settings_service.todos(), definicoes=DEFAULT_SETTINGS)
