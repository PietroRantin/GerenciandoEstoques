"""Vendas: registro, baixa de estoque, bloqueio e indicadores."""
from decimal import Decimal

import pytest

from app.models import InventoryMovement, Sale, SaleItem
from app.services import inventory_service as inv
from app.services import sales_service
from app.services.errors import EstoqueInsuficienteError, RegraNegocioError


def test_venda_registra_corretamente(admin, criar_produto):
    p1 = criar_produto(preco_venda="10,00")
    p2 = criar_produto(preco_venda="4,50")
    inv.registrar_entrada(p1.id, 20, "compra", admin)
    inv.registrar_entrada(p2.id, 20, "compra", admin)
    venda = sales_service.registrar_venda(
        [{"product_id": p1.id, "quantidade": "2"}, {"product_id": p2.id, "quantidade": "3", "preco_unitario": "4,00"}],
        admin, forma_pagamento="pix")
    assert venda.valor_total == Decimal("32.00")  # 2*10 + 3*4
    assert len(venda.itens) == 2
    assert venda.usuario_id == admin.id and venda.forma_pagamento == "pix"
    assert InventoryMovement.query.filter_by(sale_id=venda.id, tipo="venda").count() == 2


def test_venda_reduz_estoque(admin, criar_produto):
    p = criar_produto()
    inv.registrar_entrada(p.id, 12, "compra", admin)
    sales_service.registrar_venda([{"product_id": p.id, "quantidade": 5}], admin)
    assert inv.saldo_produto(p.id) == Decimal("7")


def test_venda_acima_do_estoque_e_bloqueada_e_nada_e_baixado(admin, criar_produto):
    p1 = criar_produto()
    p2 = criar_produto()
    inv.registrar_entrada(p1.id, 10, "compra", admin)
    inv.registrar_entrada(p2.id, 1, "compra", admin)
    with pytest.raises(EstoqueInsuficienteError):
        sales_service.registrar_venda([{"product_id": p1.id, "quantidade": 3},
                                       {"product_id": p2.id, "quantidade": 2}], admin)
    assert inv.saldo_produto(p1.id) == 10  # rollback do item 1
    assert Sale.query.count() == 0 and SaleItem.query.count() == 0


def test_mesmo_produto_em_duas_linhas_respeita_saldo(admin, criar_produto):
    p = criar_produto()
    inv.registrar_entrada(p.id, 5, "compra", admin)
    with pytest.raises(EstoqueInsuficienteError):
        sales_service.registrar_venda([{"product_id": p.id, "quantidade": 3},
                                       {"product_id": p.id, "quantidade": 3}], admin)
    assert inv.saldo_produto(p.id) == 5


def test_venda_vazia_e_preco_invalido(admin, criar_produto):
    with pytest.raises(RegraNegocioError, match="pelo menos um produto"):
        sales_service.registrar_venda([], admin)
    p = criar_produto()
    inv.registrar_entrada(p.id, 5, "compra", admin)
    with pytest.raises(RegraNegocioError):
        sales_service.registrar_venda([{"product_id": p.id, "quantidade": 1, "preco_unitario": "-2"}], admin)


def test_venda_produto_com_serie_seleciona_automaticamente(admin, criar_produto):
    p = criar_produto(controla_serie="on", estoque_minimo="0", ponto_pedido="0", estoque_maximo="0")
    inv.registrar_entrada(p.id, 2, "compra", admin, numeros_serie="A1,A2")
    venda = sales_service.registrar_venda([{"product_id": p.id, "quantidade": 1}], admin)
    mov = InventoryMovement.query.filter_by(sale_id=venda.id).one()
    assert mov.numero_serie == "A1"


def test_indicadores(admin, criar_produto):
    p1 = criar_produto(preco_venda="10")
    p2 = criar_produto(preco_venda="2")
    inv.registrar_entrada(p1.id, 50, "compra", admin)
    inv.registrar_entrada(p2.id, 50, "compra", admin)
    sales_service.registrar_venda([{"product_id": p1.id, "quantidade": 3}], admin)
    sales_service.registrar_venda([{"product_id": p2.id, "quantidade": 10}, {"product_id": p1.id, "quantidade": 1}], admin)
    inicio, fim = sales_service.periodo(30)
    resumo = sales_service.resumo_vendas(inicio, fim)
    assert resumo["faturamento"] == Decimal("60") and resumo["numero_vendas"] == 2
    assert resumo["ticket_medio"] == Decimal("30")
    top = sales_service.mais_vendidos(inicio, fim)
    assert top[0]["produto"].id == p2.id and top[0]["quantidade"] == 10
    dias = sales_service.vendas_por_dia(inicio, fim)
    assert len(dias) == 30 and dias[-1]["total"] == Decimal("60")
