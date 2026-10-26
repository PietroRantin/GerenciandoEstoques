"""Curva ABC (Pareto) pelo faturamento das vendas no período.

Classificação (limites configuráveis em Configurações):
  * A: produtos que, somados do maior para o menor faturamento, formam os
       primeiros ``abc_limite_a``% (padrão 80%) do faturamento;
  * B: os seguintes, até ``abc_limite_b``% (padrão 95%);
  * C: o restante, incluindo produtos sem venda no período.
Um produto é classificado pela participação acumulada ANTES dele, de modo
que o item que "cruza" o limite ainda pertence à classe anterior.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func

from ..extensions import db
from ..models import Product, Sale, SaleItem
from . import settings_service

CORES = {"A": "success", "B": "warning", "C": "secondary"}


def calcular_curva_abc(inicio: datetime, fim: datetime, limite_a=None, limite_b=None) -> dict:
    limite_a = Decimal(str(settings_service.get("abc_limite_a") if limite_a is None else limite_a))
    limite_b = Decimal(str(settings_service.get("abc_limite_b") if limite_b is None else limite_b))

    vendas = {
        pid: (Decimal(str(q)), Decimal(str(f)))
        for pid, q, f in db.session.query(SaleItem.product_id, func.sum(SaleItem.quantidade),
                                          func.sum(SaleItem.subtotal))
        .join(Sale).filter(Sale.data_hora.between(inicio, fim))
        .group_by(SaleItem.product_id).all()
    }
    produtos = Product.query.options(db.joinedload(Product.categoria)).filter(
        db.or_(Product.ativo.is_(True), Product.id.in_(list(vendas)))
    ).all()
    total = sum((f for _, f in vendas.values()), Decimal(0))

    linhas = []
    for produto in produtos:
        qtd, fat = vendas.get(produto.id, (Decimal(0), Decimal(0)))
        linhas.append({"produto": produto, "quantidade": qtd, "faturamento": fat})
    linhas.sort(key=lambda l: (-l["faturamento"], -l["quantidade"], l["produto"].nome))

    acumulado = Decimal(0)
    for posicao, linha in enumerate(linhas, start=1):
        participacao = (linha["faturamento"] / total * 100) if total else Decimal(0)
        anterior = acumulado
        acumulado += participacao
        if linha["faturamento"] <= 0:
            classe = "C"
        elif anterior < limite_a:
            classe = "A"
        elif anterior < limite_b:
            classe = "B"
        else:
            classe = "C"
        linha.update(posicao=posicao, participacao=participacao,
                     acumulado=min(acumulado, Decimal(100)), classe=classe, cor=CORES[classe])

    resumo = {}
    for classe in "ABC":
        do_grupo = [l for l in linhas if l["classe"] == classe]
        fat = sum((l["faturamento"] for l in do_grupo), Decimal(0))
        resumo[classe] = {
            "produtos": len(do_grupo),
            "percentual_produtos": (Decimal(len(do_grupo)) / len(linhas) * 100) if linhas else Decimal(0),
            "faturamento": fat,
            "percentual_faturamento": (fat / total * 100) if total else Decimal(0),
            "cor": CORES[classe],
        }
    return {"linhas": linhas, "resumo": resumo, "total": total,
            "limite_a": limite_a, "limite_b": limite_b}


def classe_do_produto(product_id: int, inicio: datetime, fim: datetime) -> str:
    for linha in calcular_curva_abc(inicio, fim)["linhas"]:
        if linha["produto"].id == product_id:
            return linha["classe"]
    return "C"
