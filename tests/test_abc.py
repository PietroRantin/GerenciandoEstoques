"""RF-002 (proposta): Curva ABC."""
from decimal import Decimal

from app.services import abc_service, sales_service
from app.services import inventory_service as inv


def _cenario(admin, criar_produto, faturamentos):
    produtos = []
    for valor in faturamentos:
        p = criar_produto(preco_venda=str(valor or 1), estoque_minimo="0", ponto_pedido="0", estoque_maximo="0")
        inv.registrar_entrada(p.id, 100, "compra", admin)
        if valor:
            sales_service.registrar_venda([{"product_id": p.id, "quantidade": 1}], admin)
        produtos.append(p)
    return produtos


def test_classificacao_e_calculada(admin, criar_produto):
    # faturamentos: 70, 15, 8, 5, 2  (total 100)
    produtos = _cenario(admin, criar_produto, [70, 15, 8, 5, 2])
    inicio, fim = sales_service.periodo(30)
    r = abc_service.calcular_curva_abc(inicio, fim, limite_a=80, limite_b=95)
    classes = {l["produto"].id: l["classe"] for l in r["linhas"]}
    # acumulado antes de cada item: 0, 70, 85, 93, 98
    assert [classes[p.id] for p in produtos] == ["A", "A", "B", "B", "C"]


def test_percentuais_sao_coerentes(admin, criar_produto):
    _cenario(admin, criar_produto, [50, 30, 20, 0])
    inicio, fim = sales_service.periodo(30)
    r = abc_service.calcular_curva_abc(inicio, fim)
    assert r["total"] == Decimal("100")
    assert sum(l["participacao"] for l in r["linhas"]) == Decimal("100")
    acumulados = [l["acumulado"] for l in r["linhas"]]
    assert acumulados == sorted(acumulados) and acumulados[-1] == Decimal("100")
    assert r["linhas"][-1]["classe"] == "C"  # sem venda
    assert sum(r["resumo"][c]["produtos"] for c in "ABC") == 4


def test_classificacao_atualiza_apos_vendas(admin, criar_produto):
    p1, p2 = _cenario(admin, criar_produto, [97, 3])
    inicio, fim = sales_service.periodo(30)
    assert abc_service.classe_do_produto(p2.id, inicio, fim) == "C"
    sales_service.registrar_venda([{"product_id": p2.id, "quantidade": 50}], admin)  # +150 -> passa a ser o maior faturamento
    assert abc_service.classe_do_produto(p2.id, inicio, fim) == "A"


def test_sem_vendas_tudo_c(admin, criar_produto):
    criar_produto()
    inicio, fim = sales_service.periodo(30)
    r = abc_service.calcular_curva_abc(inicio, fim)
    assert r["total"] == 0 and all(l["classe"] == "C" for l in r["linhas"])
