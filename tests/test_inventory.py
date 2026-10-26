"""RF-002/003/004/005/006: entradas, saídas, saldo, bloqueio e ponto de pedido."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import Alert, InventoryMovement, Lote, SerialNumber
from app.services import inventory_service as inv
from app.services.errors import EstoqueInsuficienteError, RegraNegocioError


def test_entrada_aumenta_saldo(admin, criar_produto):
    p = criar_produto()
    inv.registrar_entrada(p.id, "20", "compra", admin)
    assert p.estoque_atual == Decimal("20")
    assert inv.saldo_produto(p.id) == Decimal("20")


def test_saida_diminui_saldo(admin, criar_produto):
    p = criar_produto()
    inv.registrar_entrada(p.id, 20, "compra", admin)
    inv.registrar_saida(p.id, 7, "perda", admin)
    assert inv.saldo_produto(p.id) == Decimal("13")


def test_saida_maior_que_estoque_e_bloqueada(admin, criar_produto):
    p = criar_produto()
    inv.registrar_entrada(p.id, 5, "compra", admin)
    with pytest.raises(EstoqueInsuficienteError) as exc:
        inv.registrar_saida(p.id, 6, "consumo", admin)
    assert "Estoque insuficiente. Não é possível realizar esta saída." in exc.value.mensagem
    assert inv.saldo_produto(p.id) == Decimal("5")
    assert InventoryMovement.query.filter_by(natureza="saida").count() == 0


def test_saldo_nunca_fica_negativo(admin, criar_produto):
    p = criar_produto()
    with pytest.raises(EstoqueInsuficienteError):
        inv.registrar_saida(p.id, 1, "perda", admin)
    inv.registrar_entrada(p.id, 3, "compra", admin)
    inv.registrar_saida(p.id, 3, "perda", admin)
    with pytest.raises(EstoqueInsuficienteError):
        inv.registrar_saida(p.id, 1, "perda", admin)
    assert inv.saldo_produto(p.id) == 0


def test_update_atomico_impede_negativo_mesmo_com_dado_desatualizado(admin, criar_produto, db):
    """Simula dois usuários: o objeto em memória acha que há saldo, mas o banco não tem."""
    p = criar_produto()
    inv.registrar_entrada(p.id, 2, "compra", admin)
    db.session.execute(db.text("UPDATE produtos SET estoque_atual = 0 WHERE id = :i"), {"i": p.id})
    p.estoque_atual = Decimal("2")  # visão desatualizada
    with pytest.raises(EstoqueInsuficienteError):
        inv._alterar_saldo_produto(p, Decimal("-1"))
    db.session.rollback()


@pytest.mark.parametrize("quantidade", ["0", "-3", "abc", "", "1,5"])
def test_quantidade_invalida(admin, criar_produto, quantidade):
    p = criar_produto()  # unidade "un" exige inteiro
    with pytest.raises(RegraNegocioError):
        inv.registrar_entrada(p.id, quantidade, "compra", admin)


def test_quantidade_fracionada_em_kg(admin, criar_produto):
    p = criar_produto(unidade="kg", estoque_minimo="0", ponto_pedido="0", estoque_maximo="0")
    inv.registrar_entrada(p.id, "2,5", "compra", admin)
    inv.registrar_saida(p.id, "0,7", "venda", admin)
    inv.registrar_saida(p.id, "1,8", "venda", admin)
    assert inv.saldo_produto(p.id) == 0


def test_produto_inexistente_e_tipo_invalido(admin, criar_produto):
    with pytest.raises(RegraNegocioError, match="Produto não encontrado"):
        inv.registrar_entrada(9999, 1, "compra", admin)
    p = criar_produto()
    with pytest.raises(RegraNegocioError):
        inv.registrar_entrada(p.id, 1, "xyz", admin)


def test_movimentacao_registra_auditoria(admin, criar_produto):
    p = criar_produto()
    mov = inv.registrar_entrada(p.id, 4, "compra", admin, observacao="NF 123")
    assert mov.usuario_id == admin.id
    assert mov.data_hora is not None
    assert mov.tipo == "compra" and mov.natureza == "entrada"
    assert mov.quantidade == 4 and mov.saldo_apos == 4
    assert mov.product_id == p.id


def test_saldo_bate_com_historico(admin, criar_produto):
    p = criar_produto()
    for q in (10, 5, 8):
        inv.registrar_entrada(p.id, q, "compra", admin)
    inv.registrar_saida(p.id, 6, "venda", admin)
    inv.registrar_saida(p.id, 2, "perda", admin)
    assert inv.recalcular_saldo(p.id) == inv.saldo_produto(p.id) == Decimal("15")


def test_ponto_de_pedido_gera_alerta(admin, criar_produto):
    p = criar_produto()  # ponto de pedido = 10
    inv.registrar_entrada(p.id, 15, "compra", admin)
    assert not inv.verificar_ponto_de_pedido(p)
    assert Alert.query.filter_by(product_id=p.id, resolvido=False).count() == 0
    inv.registrar_saida(p.id, 5, "venda", admin)  # 10 == ponto de pedido
    assert inv.verificar_ponto_de_pedido(p)
    alerta = Alert.query.filter_by(product_id=p.id, tipo="estoque_baixo", resolvido=False).one()
    assert alerta.nivel == "alto"
    assert p.quantidade_sugerida == Decimal("40")  # máximo 50 - atual 10


def test_alerta_resolvido_apos_reposicao(admin, criar_produto):
    p = criar_produto()
    assert Alert.query.filter_by(product_id=p.id, tipo="sem_estoque", resolvido=False).count() == 1
    inv.registrar_entrada(p.id, 30, "compra", admin)
    assert Alert.query.filter_by(product_id=p.id, resolvido=False).count() == 0
    assert Alert.query.filter_by(product_id=p.id, tipo="sem_estoque", resolvido=True).count() == 1


def test_lote_obrigatorio_e_fefo(admin, criar_produto):
    p = criar_produto(controla_lote="on", controla_validade="on")
    with pytest.raises(RegraNegocioError, match="lote"):
        inv.registrar_entrada(p.id, 5, "compra", admin, validade=date.today() + timedelta(days=60))
    with pytest.raises(RegraNegocioError, match="validade"):
        inv.registrar_entrada(p.id, 5, "compra", admin, lote="L1")
    inv.registrar_entrada(p.id, 5, "compra", admin, lote="L-LONGE", validade=date.today() + timedelta(days=90))
    inv.registrar_entrada(p.id, 5, "compra", admin, lote="L-PERTO", validade=date.today() + timedelta(days=10))
    movs = inv.registrar_saida(p.id, 7, "venda", admin)  # FEFO: 5 do L-PERTO + 2 do L-LONGE
    assert [(m.lote.numero, m.quantidade) for m in movs] == [("L-PERTO", 5), ("L-LONGE", 2)]
    perto = Lote.query.filter_by(numero="L-PERTO").one()
    longe = Lote.query.filter_by(numero="L-LONGE").one()
    assert perto.quantidade == 0 and longe.quantidade == 3
    assert p.estoque_atual == 3
    assert [m.quantidade for m in longe.movimentacoes] == [5, 2]  # histórico do lote


def test_saida_de_lote_especifico_insuficiente(admin, criar_produto):
    p = criar_produto(controla_lote="on")
    inv.registrar_entrada(p.id, 2, "compra", admin, lote="A")
    inv.registrar_entrada(p.id, 8, "compra", admin, lote="B")
    lote_a = Lote.query.filter_by(numero="A").one()
    with pytest.raises(EstoqueInsuficienteError):
        inv.registrar_saida(p.id, 3, "perda", admin, lote_id=lote_a.id)
    assert p.estoque_atual == 10


def test_lote_com_validade_divergente_e_bloqueado(admin, criar_produto):
    p = criar_produto(controla_lote="on", controla_validade="on")
    inv.registrar_entrada(p.id, 1, "compra", admin, lote="X", validade=date(2030, 1, 1))
    with pytest.raises(RegraNegocioError, match="já existe com validade"):
        inv.registrar_entrada(p.id, 1, "compra", admin, lote="X", validade=date(2031, 1, 1))


def test_numero_de_serie(admin, criar_produto):
    p = criar_produto(controla_serie="on", estoque_minimo="0", ponto_pedido="0", estoque_maximo="0")
    with pytest.raises(RegraNegocioError, match="número"):
        inv.registrar_entrada(p.id, 2, "compra", admin, numeros_serie="SN1")
    inv.registrar_entrada(p.id, 3, "compra", admin, numeros_serie="sn1, SN2\nSN3")
    with pytest.raises(RegraNegocioError, match="já estão no estoque"):
        inv.registrar_entrada(p.id, 1, "compra", admin, numeros_serie="SN2")
    with pytest.raises(RegraNegocioError, match="não encontrado"):
        inv.registrar_saida(p.id, 1, "venda", admin, numeros_serie="SN9")
    inv.registrar_saida(p.id, 1, "venda", admin, numeros_serie="SN2")
    sn2 = SerialNumber.query.filter_by(numero="SN2").one()
    assert sn2.status == "saiu" and sn2.saida is not None and sn2.entrada is not None
    assert p.estoque_atual == 2
    assert SerialNumber.query.filter_by(status="em_estoque").count() == 2


def test_validade_sem_lote_gera_lote_automatico(admin, criar_produto):
    p = criar_produto(controla_validade="on")
    val = date.today() + timedelta(days=100)
    inv.registrar_entrada(p.id, 4, "compra", admin, validade=val)
    inv.registrar_entrada(p.id, 6, "compra", admin, validade=val)
    lote = Lote.query.filter_by(product_id=p.id).one()
    assert lote.numero == f"VAL-{val:%Y%m%d}" and lote.quantidade == 10


def test_produto_inativo_nao_movimenta(admin, criar_produto, db):
    p = criar_produto()
    p.ativo = False
    db.session.commit()
    with pytest.raises(RegraNegocioError, match="inativo"):
        inv.registrar_entrada(p.id, 1, "compra", admin)


def test_lote_vencido_nao_e_vendido(admin, criar_produto):
    p = criar_produto(controla_lote="on", controla_validade="on")
    inv.registrar_entrada(p.id, 4, "compra", admin, lote="VELHO", validade=date.today() - timedelta(days=2))
    inv.registrar_entrada(p.id, 3, "compra", admin, lote="NOVO", validade=date.today() + timedelta(days=60))
    movs = inv.registrar_saida(p.id, 2, "venda", admin)  # FEFO pula o lote vencido
    assert [m.lote.numero for m in movs] == ["NOVO"]
    with pytest.raises(EstoqueInsuficienteError, match="VENCIDOS"):
        inv.registrar_saida(p.id, 3, "venda", admin)
    velho = Lote.query.filter_by(numero="VELHO").one()
    with pytest.raises(RegraNegocioError, match="vencido"):
        inv.registrar_saida(p.id, 1, "venda", admin, lote_id=velho.id)
    inv.registrar_saida(p.id, 4, "perda", admin, lote_id=velho.id)  # descarte permitido
    assert p.estoque_atual == 1
