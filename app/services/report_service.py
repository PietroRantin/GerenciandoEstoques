"""Consultas dos relatórios (filtros executados no banco)."""
from datetime import datetime, time

from sqlalchemy import func

from ..extensions import db
from ..models import InventoryMovement, Lote, Product, Sale, SaleItem
from . import alert_service


def intervalo(inicio, fim):
    return (datetime.combine(inicio, time.min) if inicio else None,
            datetime.combine(fim, time.max) if fim else None)


def relatorio_estoque(categoria_id=None, situacao=""):
    from .product_service import buscar_produtos
    return buscar_produtos(categoria_id=categoria_id, situacao=situacao)


def relatorio_movimentacoes(inicio=None, fim=None, product_id=None, natureza=None, tipo=None, usuario_id=None):
    query = InventoryMovement.query.options(
        db.joinedload(InventoryMovement.produto), db.joinedload(InventoryMovement.usuario),
        db.joinedload(InventoryMovement.lote),
    )
    ini, fi = intervalo(inicio, fim)
    if ini:
        query = query.filter(InventoryMovement.data_hora >= ini)
    if fi:
        query = query.filter(InventoryMovement.data_hora <= fi)
    if product_id:
        query = query.filter(InventoryMovement.product_id == product_id)
    if natureza in ("entrada", "saida"):
        query = query.filter(InventoryMovement.natureza == natureza)
    if tipo:
        query = query.filter(InventoryMovement.tipo == tipo)
    if usuario_id:
        query = query.filter(InventoryMovement.usuario_id == usuario_id)
    return query.order_by(InventoryMovement.data_hora.desc(), InventoryMovement.id.desc())


def relatorio_vendas(inicio=None, fim=None, product_id=None):
    query = (
        db.session.query(Product, func.sum(SaleItem.quantidade).label("quantidade"),
                         func.sum(SaleItem.subtotal).label("faturamento"),
                         func.count(func.distinct(SaleItem.sale_id)).label("vendas"))
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
    )
    ini, fi = intervalo(inicio, fim)
    if ini:
        query = query.filter(Sale.data_hora >= ini)
    if fi:
        query = query.filter(Sale.data_hora <= fi)
    if product_id:
        query = query.filter(Product.id == product_id)
    return query.group_by(Product.id).order_by(func.sum(SaleItem.subtotal).desc()).all()


def relatorio_validade(situacao="", ordenar="validade"):
    """Todos os lotes com saldo e validade, com a situação de cada um."""
    query = (
        Lote.query.join(Product).options(db.contains_eager(Lote.produto))
        .filter(Lote.quantidade > 0, Lote.validade.isnot(None), Product.ativo.is_(True))
        .order_by(*alert_service.ORDENACOES_VALIDADE.get(ordenar, alert_service.ORDENACOES_VALIDADE["validade"]))
    )
    linhas = [(lote, alert_service.status_validade(lote.validade)) for lote in query]
    if situacao:
        linhas = [(l, s) for l, s in linhas if (s or "ok") == situacao]
    return linhas
