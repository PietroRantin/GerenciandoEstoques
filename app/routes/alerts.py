from flask import Blueprint, render_template, request
from flask_login import login_required

from ..models import Alert
from ..extensions import db
from ..services import alert_service, settings_service
from ..utils.datas import hoje
from ..utils.parsing import parse_int

bp = Blueprint("alerts", __name__)


@bp.route("/alertas")
@login_required
def index():
    alert_service.sincronizar_todos()
    historico = (Alert.query.filter_by(resolvido=True).options(db.joinedload(Alert.produto))
                 .order_by(Alert.resolvido_em.desc()).limit(15).all())
    return render_template("alerts/index.html", alertas=alert_service.alertas_abertos().all(),
                           repor=alert_service.produtos_para_repor().all(), historico=historico)


@bp.route("/alertas/validade")
@login_required
def validade():
    alert_service.sincronizar_todos()
    ordenar = request.args.get("ordenar", "validade")
    if ordenar not in alert_service.ORDENACOES_VALIDADE:
        ordenar = "validade"
    janela = parse_int(request.args.get("dias")) or settings_service.get("validade_alerta_dias")
    janela = max(1, min(janela, 365))
    lotes = alert_service.lotes_vencendo(janela=janela, ordenar=ordenar).all()
    return render_template("alerts/expiry.html", lotes=lotes, ordenar=ordenar, janela=janela,
                           status_validade=alert_service.status_validade,
                           info=alert_service.STATUS_VALIDADE_INFO, hoje=hoje(),
                           critico=settings_service.get("validade_critico_dias"))
