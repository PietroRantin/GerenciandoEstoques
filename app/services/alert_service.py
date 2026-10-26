"""Alertas de reposição e de validade.

Regras:
  * Sem estoque: saldo <= 0                         -> nível crítico
  * Reposição:   saldo <= ponto de pedido           -> nível alto
  * Vencido:     validade < hoje (lote com saldo)   -> nível crítico
  * Vencendo:    validade <= hoje + N dias          -> alto (até X dias) / médio
As janelas N e X são configuráveis (Configurações).
"""
from datetime import date, timedelta
from decimal import Decimal

from ..extensions import db
from ..models import Alert, Lote, Product
from ..utils.datas import agora, hoje as _hoje
from . import settings_service


# ---- Validade -----------------------------------------------------------
def status_validade(validade: date | None, hoje: date | None = None,
                    janela: int | None = None, critico: int | None = None):
    """Retorna 'vencido', 'critico', 'atencao' ou None."""
    if validade is None:
        return None
    hoje = hoje or _hoje()
    janela = settings_service.get("validade_alerta_dias") if janela is None else janela
    critico = settings_service.get("validade_critico_dias") if critico is None else critico
    dias = (validade - hoje).days
    if dias < 0:
        return "vencido"
    if dias <= critico:
        return "critico"
    if dias <= janela:
        return "atencao"
    return None


STATUS_VALIDADE_INFO = {
    "vencido": ("Vencido", "danger"),
    "critico": ("Vence em breve", "warning"),
    "atencao": ("Atenção", "info"),
    None: ("OK", "success"),
}


def verificar_validade(lote: Lote, hoje: date | None = None) -> str | None:
    return status_validade(lote.validade, hoje)


ORDENACOES_VALIDADE = {
    "validade": (Lote.validade, Lote.id),
    "produto": (Product.nome, Lote.validade),
    "quantidade": (Lote.quantidade.desc(), Lote.validade),
    "lote": (Lote.numero, Lote.validade),
}


def lotes_vencendo(hoje: date | None = None, janela: int | None = None, ordenar="validade",
                   incluir_vencidos=True):
    """Query dos lotes com saldo que vencem dentro da janela (e os já vencidos)."""
    hoje = hoje or _hoje()
    janela = settings_service.get("validade_alerta_dias") if janela is None else janela
    query = (
        Lote.query.join(Product)
        .options(db.contains_eager(Lote.produto))
        .filter(Lote.quantidade > 0, Lote.validade.isnot(None), Product.ativo.is_(True),
                Lote.validade <= hoje + timedelta(days=janela))
    )
    if not incluir_vencidos:
        query = query.filter(Lote.validade >= hoje)
    return query.order_by(*ORDENACOES_VALIDADE.get(ordenar, ORDENACOES_VALIDADE["validade"]))


def contagem_validade(hoje: date | None = None) -> dict:
    hoje = hoje or _hoje()
    lotes = lotes_vencendo(hoje).all()
    vencidos = [l for l in lotes if l.validade < hoje]
    return {"vencidos": len(vencidos), "vencendo": len(lotes) - len(vencidos),
            "produtos_vencidos": len({l.product_id for l in vencidos}),
            "produtos_vencendo": len({l.product_id for l in lotes if l.validade >= hoje})}


# ---- Reposição ----------------------------------------------------------
def produtos_para_repor():
    """Produtos ativos com saldo <= ponto de pedido (mais urgentes primeiro)."""
    return (
        Product.query.filter(Product.ativo.is_(True), Product.estoque_atual <= Product.ponto_pedido)
        .order_by((Product.estoque_atual > 0), Product.estoque_atual - Product.ponto_pedido, Product.nome)
    )


# ---- Sincronização dos alertas -------------------------------------------
def _abrir_ou_atualizar(product_id, tipo, nivel, mensagem, lote_id=None):
    alerta = Alert.query.filter_by(product_id=product_id, lote_id=lote_id, tipo=tipo, resolvido=False).first()
    if alerta is None:
        db.session.add(Alert(product_id=product_id, lote_id=lote_id, tipo=tipo, nivel=nivel, mensagem=mensagem))
    else:
        alerta.nivel = nivel
        alerta.mensagem = mensagem


def _resolver(product_id, tipos, lote_id=None, todos_lotes=False):
    query = Alert.query.filter(Alert.product_id == product_id, Alert.tipo.in_(tipos), Alert.resolvido.is_(False))
    if not todos_lotes:
        query = query.filter(Alert.lote_id.is_(None) if lote_id is None else Alert.lote_id == lote_id)
    for alerta in query:
        alerta.resolvido = True
        alerta.resolvido_em = agora()


def sincronizar_alertas_estoque(produto: Product) -> None:
    """Chamado após qualquer movimentação ou alteração do produto."""
    from ..utils.formatos import qtd
    if not produto.ativo:
        _resolver(produto.id, ["sem_estoque", "estoque_baixo", "vencido", "vencendo"], todos_lotes=True)
        return
    estoque = Decimal(produto.estoque_atual or 0)
    if estoque <= 0:
        _resolver(produto.id, ["estoque_baixo"])
        _abrir_ou_atualizar(produto.id, "sem_estoque", "critico", f"{produto.nome} está sem estoque.")
    elif estoque <= Decimal(produto.ponto_pedido or 0):
        _resolver(produto.id, ["sem_estoque"])
        _abrir_ou_atualizar(
            produto.id, "estoque_baixo", "alto",
            f"{produto.nome}: restam {qtd(estoque)} {produto.unidade} "
            f"(ponto de pedido: {qtd(produto.ponto_pedido)}). Sugestão de compra: "
            f"{qtd(produto.quantidade_sugerida)} {produto.unidade}.",
        )
    else:
        _resolver(produto.id, ["sem_estoque", "estoque_baixo"])


def sincronizar_alertas_lote(lote: Lote, hoje: date | None = None) -> None:
    status = status_validade(lote.validade, hoje) if Decimal(lote.quantidade or 0) > 0 else None
    nome = lote.produto.nome if lote.produto else "Produto"
    if status == "vencido":
        _resolver(lote.product_id, ["vencendo"], lote.id)
        _abrir_ou_atualizar(lote.product_id, "vencido", "critico",
                            f"{nome} (lote {lote.numero}) venceu em {lote.validade:%d/%m/%Y}. Retire da venda.",
                            lote.id)
    elif status in ("critico", "atencao"):
        _resolver(lote.product_id, ["vencido"], lote.id)
        dias = (lote.validade - (hoje or _hoje())).days
        quando = "hoje" if dias == 0 else f"em {dias} dia(s)"
        _abrir_ou_atualizar(lote.product_id, "vencendo", "alto" if status == "critico" else "medio",
                            f"{nome} (lote {lote.numero}) vence {quando} ({lote.validade:%d/%m/%Y}).", lote.id)
    else:
        _resolver(lote.product_id, ["vencido", "vencendo"], lote.id)


def sincronizar_todos(hoje: date | None = None, commit=True) -> None:
    """Revisa todos os alertas (a validade muda com a passagem dos dias)."""
    for produto in Product.query.all():
        sincronizar_alertas_estoque(produto)
    lotes_com_alerta = {a.lote_id for a in Alert.query.filter(Alert.lote_id.isnot(None), Alert.resolvido.is_(False))}
    janela = settings_service.get("validade_alerta_dias")
    limite = (hoje or _hoje()) + timedelta(days=janela)
    candidatos = Lote.query.filter(
        db.or_(Lote.id.in_(lotes_com_alerta),
               db.and_(Lote.quantidade > 0, Lote.validade.isnot(None), Lote.validade <= limite))
    ).all()
    for lote in candidatos:
        sincronizar_alertas_lote(lote, hoje)
    if commit:
        db.session.commit()


def alertas_abertos():
    return (
        Alert.query.filter_by(resolvido=False)
        .options(db.joinedload(Alert.produto), db.joinedload(Alert.lote))
        .order_by(db.case((Alert.nivel == "critico", 0), (Alert.nivel == "alto", 1), else_=2), Alert.criado_em.desc())
    )
