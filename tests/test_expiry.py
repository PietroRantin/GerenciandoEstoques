"""RF-007: alertas de validade."""
from datetime import date, timedelta

from app.models import Alert, Lote
from app.services import alert_service
from app.services import inventory_service as inv
from app.services import settings_service


def _entrada_com_validade(admin, produto, dias, lote):
    inv.registrar_entrada(produto.id, 5, "compra", admin, lote=lote, validade=date.today() + timedelta(days=dias))
    return Lote.query.filter_by(numero=lote).one()


def test_status_validade_niveis():
    hoje = date(2026, 10, 1)
    assert alert_service.status_validade(date(2026, 9, 30), hoje, 30, 7) == "vencido"
    assert alert_service.status_validade(date(2026, 10, 1), hoje, 30, 7) == "critico"
    assert alert_service.status_validade(date(2026, 10, 8), hoje, 30, 7) == "critico"
    assert alert_service.status_validade(date(2026, 10, 20), hoje, 30, 7) == "atencao"
    assert alert_service.status_validade(date(2026, 10, 31), hoje, 30, 7) == "atencao"
    assert alert_service.status_validade(date(2026, 11, 1), hoje, 30, 7) is None
    assert alert_service.status_validade(None, hoje) is None


def test_produto_vencido_gera_alerta(admin, criar_produto):
    p = criar_produto(controla_lote="on", controla_validade="on")
    lote = _entrada_com_validade(admin, p, -3, "VENC")
    alerta = Alert.query.filter_by(lote_id=lote.id, resolvido=False).one()
    assert alerta.tipo == "vencido" and alerta.nivel == "critico"


def test_produto_dentro_da_janela_gera_alerta(admin, criar_produto):
    p = criar_produto(controla_lote="on", controla_validade="on")
    critico = _entrada_com_validade(admin, p, 5, "L5")
    atencao = _entrada_com_validade(admin, p, 25, "L25")
    a1 = Alert.query.filter_by(lote_id=critico.id, resolvido=False).one()
    a2 = Alert.query.filter_by(lote_id=atencao.id, resolvido=False).one()
    assert (a1.tipo, a1.nivel) == ("vencendo", "alto")
    assert (a2.tipo, a2.nivel) == ("vencendo", "medio")
    assert {l.numero for l in alert_service.lotes_vencendo()} == {"L5", "L25"}


def test_produto_distante_da_validade_nao_gera_alerta(admin, criar_produto):
    p = criar_produto(controla_lote="on", controla_validade="on")
    lote = _entrada_com_validade(admin, p, 120, "LONGE")
    assert Alert.query.filter_by(lote_id=lote.id).count() == 0
    assert alert_service.lotes_vencendo().count() == 0


def test_janela_configuravel(admin, criar_produto):
    p = criar_produto(controla_lote="on", controla_validade="on")
    _entrada_com_validade(admin, p, 45, "L45")
    assert alert_service.lotes_vencendo().count() == 0
    settings_service.salvar({"validade_alerta_dias": "60"})
    assert alert_service.lotes_vencendo().count() == 1
    alert_service.sincronizar_todos()
    assert Alert.query.filter_by(tipo="vencendo", resolvido=False).count() == 1


def test_alerta_some_quando_lote_zerado(admin, criar_produto):
    p = criar_produto(controla_lote="on", controla_validade="on")
    lote = _entrada_com_validade(admin, p, -1, "VENC")
    inv.registrar_saida(p.id, 5, "perda", admin, lote_id=lote.id)
    assert Alert.query.filter_by(lote_id=lote.id, resolvido=False).count() == 0


def test_sincronizacao_diaria_muda_nivel(admin, criar_produto):
    """Um lote que hoje está 'atenção' passa a 'vencido' com o passar dos dias."""
    p = criar_produto(controla_lote="on", controla_validade="on")
    lote = _entrada_com_validade(admin, p, 20, "L20")
    alert_service.sincronizar_todos(hoje=date.today() + timedelta(days=21))
    alerta = Alert.query.filter_by(lote_id=lote.id, resolvido=False).one()
    assert alerta.tipo == "vencido"
