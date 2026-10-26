"""Vendas: registro (com baixa de estoque) e indicadores."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func

from ..extensions import db
from ..models import Product, Sale, SaleItem
from ..models.sale import FORMAS_PAGAMENTO
from ..utils.datas import agora, hoje
from ..utils.parsing import ValorInvalido, parse_decimal
from . import inventory_service
from .errors import RegraNegocioError


def registrar_venda(itens: list[dict], usuario, forma_pagamento=None, observacao=None,
                    data_hora: datetime | None = None) -> Sale:
    """itens: [{"product_id":.., "quantidade":.., "preco_unitario": opcional}]

    Tudo ou nada: se faltar estoque de qualquer item, nenhuma baixa é feita.
    """
    itens = [i for i in itens if i.get("product_id") or i.get("quantidade")]
    if not itens:
        raise RegraNegocioError("Adicione pelo menos um produto à venda.")
    if forma_pagamento and forma_pagamento not in FORMAS_PAGAMENTO:
        raise RegraNegocioError("Forma de pagamento inválida.")
    momento = data_hora or agora()
    try:
        venda = Sale(usuario_id=usuario.id, data_hora=momento, forma_pagamento=forma_pagamento or None,
                     observacao=(observacao or "").strip()[:255] or None, valor_total=0)
        db.session.add(venda)
        db.session.flush()
        total = Decimal(0)
        for numero, item in enumerate(itens, start=1):
            if not item.get("product_id"):
                raise RegraNegocioError(f"Item {numero}: selecione o produto.")
            produto = inventory_service._produto(item["product_id"])
            preco = item.get("preco_unitario")
            try:
                preco = (parse_decimal(preco, "o preço", casas=2) if preco not in (None, "")
                         else Decimal(produto.preco_venda))
            except ValorInvalido as exc:
                raise RegraNegocioError(f"Item {numero} ({produto.nome}): {exc}")
            if preco < 0:
                raise RegraNegocioError(f"Item {numero} ({produto.nome}): o preço não pode ser negativo.")
            movimentos = inventory_service.registrar_saida(
                produto.id, item.get("quantidade"), "venda", usuario, valor_unitario=preco,
                sale_id=venda.id, data_hora=momento, commit=False,
                selecionar_series_automaticamente=True, observacao=f"Venda nº {venda.id}",
            )
            quantidade = sum((m.quantidade for m in movimentos), Decimal(0))
            subtotal = (Decimal(quantidade) * preco).quantize(Decimal("0.01"))
            db.session.add(SaleItem(sale_id=venda.id, product_id=produto.id, quantidade=quantidade,
                                    preco_unitario=preco, subtotal=subtotal))
            total += subtotal
        venda.valor_total = total
        db.session.commit()
        return venda
    except Exception:
        db.session.rollback()
        raise


# ---- Indicadores ----------------------------------------------------------
def periodo(dias: int, fim: date | None = None) -> tuple[datetime, datetime]:
    fim = fim or hoje()
    inicio = fim - timedelta(days=dias - 1)
    return datetime.combine(inicio, time.min), datetime.combine(fim, time.max)


def resumo_vendas(inicio: datetime, fim: datetime) -> dict:
    total, quantidade = db.session.query(
        func.coalesce(func.sum(Sale.valor_total), 0), func.count(Sale.id)
    ).filter(Sale.data_hora.between(inicio, fim)).one()
    itens = db.session.query(func.coalesce(func.sum(SaleItem.quantidade), 0)).join(Sale).filter(
        Sale.data_hora.between(inicio, fim)).scalar()
    total = Decimal(str(total))
    return {
        "faturamento": total,
        "numero_vendas": quantidade,
        "itens_vendidos": Decimal(str(itens)),
        "ticket_medio": (total / quantidade) if quantidade else Decimal(0),
    }


def mais_vendidos(inicio: datetime, fim: datetime, limite: int = 10) -> list[dict]:
    linhas = (
        db.session.query(Product, func.sum(SaleItem.quantidade).label("qtd"),
                         func.sum(SaleItem.subtotal).label("fat"))
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.data_hora.between(inicio, fim))
        .group_by(Product.id)
        .order_by(func.sum(SaleItem.quantidade).desc())
        .limit(limite)
        .all()
    )
    dias = max((fim.date() - inicio.date()).days + 1, 1)
    resultado = []
    for produto, quantidade, faturamento in linhas:
        quantidade = Decimal(str(quantidade))
        estoque = Decimal(produto.estoque_atual or 0)
        media_dia = quantidade / dias
        # Giro aproximado = vendido no período / estoque médio (início ≈ atual + vendido; fim = atual)
        estoque_medio = estoque + quantidade / 2
        resultado.append({
            "produto": produto,
            "quantidade": quantidade,
            "faturamento": Decimal(str(faturamento)),
            "giro": (quantidade / estoque_medio) if estoque_medio > 0 else Decimal(0),
            "cobertura_dias": (estoque / media_dia) if media_dia > 0 else None,
        })
    return resultado


def maior_giro(inicio: datetime, fim: datetime, limite: int = 5) -> list[dict]:
    itens = mais_vendidos(inicio, fim, limite=1000)
    return sorted(itens, key=lambda i: i["giro"], reverse=True)[:limite]


def vendas_por_dia(inicio: datetime, fim: datetime) -> list[dict]:
    dia = func.date(Sale.data_hora)
    linhas = dict(
        db.session.query(dia, func.sum(Sale.valor_total)).filter(Sale.data_hora.between(inicio, fim))
        .group_by(dia).all()
    )
    resultado = []
    atual = inicio.date()
    while atual <= fim.date():
        valor = linhas.get(atual.isoformat()) or linhas.get(atual) or 0
        resultado.append({"dia": atual, "total": Decimal(str(valor))})
        atual += timedelta(days=1)
    maximo = max((r["total"] for r in resultado), default=0) or 1
    for r in resultado:
        r["percentual"] = float(r["total"] / maximo * 100)
    return resultado
