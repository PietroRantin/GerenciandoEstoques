from datetime import timedelta
from decimal import Decimal

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func

from ..extensions import db
from ..models import InventoryMovement, Product
from ..services import alert_service, sales_service, settings_service
from ..utils.parsing import parse_int

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    alert_service.sincronizar_todos()  # a validade muda com o passar dos dias
    dias = parse_int(request.args.get("dias")) or settings_service.get("dashboard_periodo_dias")
    dias = dias if dias in (7, 30, 90) else settings_service.get("dashboard_periodo_dias")
    inicio, fim = sales_service.periodo(dias)

    ativos = Product.query.filter(Product.ativo.is_(True))
    total_produtos = ativos.count()
    sem_estoque = ativos.filter(Product.estoque_atual <= 0).count()
    estoque_baixo = ativos.filter(Product.estoque_atual > 0, Product.estoque_atual <= Product.ponto_pedido).count()
    valor_estoque = db.session.query(
        func.coalesce(func.sum(Product.estoque_atual * Product.preco_custo), 0)
    ).filter(Product.ativo.is_(True)).scalar()
    validade = alert_service.contagem_validade()

    grafico_inicio, grafico_fim = sales_service.periodo(14 if dias <= 30 else 30)
    return render_template(
        "dashboard.html",
        dias=dias,
        total_produtos=total_produtos,
        sem_estoque=sem_estoque,
        estoque_baixo=estoque_baixo,
        valor_estoque=Decimal(str(valor_estoque)),
        validade=validade,
        vendas=sales_service.resumo_vendas(inicio, fim),
        repor=alert_service.produtos_para_repor().limit(8).all(),
        total_repor=alert_service.produtos_para_repor().count(),
        mais_vendidos=sales_service.mais_vendidos(inicio, fim, limite=5),
        maior_giro=sales_service.maior_giro(inicio, fim, limite=5),
        grafico=sales_service.vendas_por_dia(grafico_inicio, grafico_fim),
        vencendo=alert_service.lotes_vencendo().limit(6).all(),
        ultimas=InventoryMovement.query.options(db.joinedload(InventoryMovement.produto),
                                                db.joinedload(InventoryMovement.usuario))
        .order_by(InventoryMovement.data_hora.desc(), InventoryMovement.id.desc()).limit(8).all(),
        hoje=fim.date(),
        timedelta=timedelta,
    )
