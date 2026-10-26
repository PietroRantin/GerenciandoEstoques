"""Regras de estoque — ÚNICO ponto do sistema que altera saldos.

Toda entrada/saída passa por aqui. Cada operação:
  1. valida os dados (produto, quantidade, lote, série);
  2. altera o saldo com um UPDATE atômico condicionado (nunca fica negativo,
     mesmo com dois usuários registrando saídas ao mesmo tempo);
  3. grava a movimentação (usuário, data/hora, tipo, quantidade, saldo após);
  4. atualiza os alertas do produto.
As telas (entrada, saída, vendas) apenas chamam estas funções.
"""
import re
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import case, func, update

from ..extensions import db
from ..models import InventoryMovement, Lote, Product, SerialNumber
from ..models.movement import TIPOS_ENTRADA, TIPOS_SAIDA
from ..utils.datas import agora, hoje
from ..utils.parsing import ValorInvalido, parse_decimal
from . import alert_service
from .errors import EstoqueInsuficienteError, RegraNegocioError

MSG_ESTOQUE_INSUFICIENTE = "Estoque insuficiente. Não é possível realizar esta saída."
TIPOS_SEM_VENCIDOS = ("venda", "consumo")
CASAS = Decimal("0.001")


# ---- Auxiliares -----------------------------------------------------------
def _produto(product_id) -> Product:
    produto = db.session.get(Product, int(product_id)) if str(product_id or "").isdigit() else None
    if produto is None:
        raise RegraNegocioError("Produto não encontrado. Selecione um produto da lista.")
    if not produto.ativo:
        raise RegraNegocioError(f"O produto \"{produto.nome}\" está inativo e não pode ser movimentado.")
    return produto


def _quantidade(valor, produto: Product) -> Decimal:
    try:
        quantidade = parse_decimal(valor, "a quantidade")
    except ValorInvalido as exc:
        raise RegraNegocioError(str(exc))
    if quantidade <= 0:
        raise RegraNegocioError("A quantidade deve ser maior que zero.")
    if quantidade != quantidade.quantize(CASAS):
        raise RegraNegocioError("Use no máximo 3 casas decimais na quantidade.")
    if quantidade > Decimal("1000000"):
        raise RegraNegocioError("Quantidade muito alta. Confira o valor digitado.")
    if (produto.controla_serie or produto.unidade == "un") and quantidade != quantidade.to_integral_value():
        raise RegraNegocioError("Este produto é contado por unidade. Informe uma quantidade inteira.")
    return quantidade.quantize(CASAS)


def _valor_unitario(valor):
    if valor in (None, ""):
        return None
    try:
        numero = parse_decimal(valor, "o valor unitário", casas=2)
    except ValorInvalido as exc:
        raise RegraNegocioError(str(exc))
    if numero < 0:
        raise RegraNegocioError("O valor unitário não pode ser negativo.")
    return numero


def _series(texto) -> list[str]:
    if not texto:
        return []
    if isinstance(texto, (list, tuple)):
        itens = texto
    else:
        itens = re.split(r"[,;\n\r]+", texto)
    series = [s.strip().upper() for s in itens if s and s.strip()]
    duplicadas = {s for s in series if series.count(s) > 1}
    if duplicadas:
        raise RegraNegocioError(f"Número de série repetido: {', '.join(sorted(duplicadas))}.")
    return series


def _alterar_saldo_produto(produto: Product, delta: Decimal) -> Decimal:
    """UPDATE atômico. Para saídas, só altera se houver saldo suficiente."""
    stmt = (
        update(Product)
        .where(Product.id == produto.id)
        .values(estoque_atual=func.round(Product.estoque_atual + delta, 3))
        .execution_options(synchronize_session=False)
    )
    if delta < 0:
        stmt = stmt.where(Product.estoque_atual >= -delta)
    resultado = db.session.execute(stmt)
    if resultado.rowcount != 1:
        raise EstoqueInsuficienteError(MSG_ESTOQUE_INSUFICIENTE)
    db.session.refresh(produto, ["estoque_atual"])
    return Decimal(produto.estoque_atual)


def _alterar_saldo_lote(lote: Lote, delta: Decimal) -> None:
    stmt = (
        update(Lote)
        .where(Lote.id == lote.id)
        .values(quantidade=func.round(Lote.quantidade + delta, 3))
        .execution_options(synchronize_session=False)
    )
    if delta < 0:
        stmt = stmt.where(Lote.quantidade >= -delta)
    if db.session.execute(stmt).rowcount != 1:
        raise EstoqueInsuficienteError(
            f"Estoque insuficiente no lote {lote.numero}. Não é possível realizar esta saída."
        )
    db.session.refresh(lote, ["quantidade"])


def _commit_ou_rollback(commit: bool):
    if commit:
        db.session.commit()


# ---- Consultas ------------------------------------------------------------
def saldo_produto(product_id: int) -> Decimal:
    """Consulta de saldo (RNF-001): leitura direta e indexada pela chave primária."""
    valor = db.session.query(Product.estoque_atual).filter(Product.id == product_id).scalar()
    return Decimal(valor or 0)


def recalcular_saldo(product_id: int) -> Decimal:
    """Saldo calculado a partir do histórico de movimentações (auditoria)."""
    total = db.session.query(
        func.coalesce(func.sum(case((InventoryMovement.natureza == "entrada", InventoryMovement.quantidade),
                                    else_=-InventoryMovement.quantidade)), 0)
    ).filter(InventoryMovement.product_id == product_id).scalar()
    return Decimal(str(total)).quantize(CASAS)


def verificar_estoque_insuficiente(produto: Product, quantidade) -> bool:
    """True quando NÃO há saldo para a saída pretendida."""
    return Decimal(produto.estoque_atual or 0) < Decimal(str(quantidade))


def verificar_ponto_de_pedido(produto: Product) -> bool:
    """True quando o produto atingiu ou ficou abaixo do ponto de pedido."""
    return produto.precisa_reposicao


def lotes_disponiveis(produto: Product):
    """Lotes com saldo, na ordem de saída sugerida (vence primeiro, sai primeiro)."""
    return (
        Lote.query.filter(Lote.product_id == produto.id, Lote.quantidade > 0)
        .order_by(Lote.validade.is_(None), Lote.validade, Lote.criado_em, Lote.id)
        .all()
    )


def series_disponiveis(produto: Product):
    return (
        SerialNumber.query.filter_by(product_id=produto.id, status="em_estoque")
        .order_by(SerialNumber.criado_em, SerialNumber.id)
        .all()
    )


# ---- Operações ------------------------------------------------------------
def registrar_entrada(product_id, quantidade, tipo, usuario, lote=None, validade=None,
                      numeros_serie=None, valor_unitario=None, observacao=None,
                      data_hora: datetime | None = None, commit=True) -> InventoryMovement:
    produto = _produto(product_id)
    if tipo not in TIPOS_ENTRADA:
        raise RegraNegocioError("Escolha o tipo de entrada.")
    qtd = _quantidade(quantidade, produto)
    valor = _valor_unitario(valor_unitario)
    observacao = (observacao or "").strip()[:255] or None
    numero_lote = (lote or "").strip().upper() or None
    if validade is not None and not isinstance(validade, date):
        raise RegraNegocioError("Data de validade inválida.")

    lote_obj = None
    series = []
    if produto.controla_serie:
        series = _series(numeros_serie)
        if len(series) != int(qtd):
            raise RegraNegocioError(
                f"Informe {int(qtd)} número(s) de série — um para cada unidade. Foram informados {len(series)}."
            )
        existentes = SerialNumber.query.filter(SerialNumber.product_id == produto.id,
                                               SerialNumber.numero.in_(series),
                                               SerialNumber.status == "em_estoque").all()
        if existentes:
            raise RegraNegocioError(
                "Estes números de série já estão no estoque: " + ", ".join(s.numero for s in existentes) + "."
            )
    elif produto.usa_lote:
        if produto.controla_lote and not numero_lote:
            raise RegraNegocioError("Informe o número do lote (está impresso na embalagem).")
        if produto.controla_validade and validade is None:
            raise RegraNegocioError("Informe a data de validade deste produto.")
        if not numero_lote:
            numero_lote = f"VAL-{validade:%Y%m%d}" if validade else "SEM-LOTE"
        lote_obj = Lote.query.filter_by(product_id=produto.id, numero=numero_lote).first()
        if lote_obj is None:
            lote_obj = Lote(product_id=produto.id, numero=numero_lote, validade=validade, quantidade=0)
            db.session.add(lote_obj)
            db.session.flush()
        elif validade and lote_obj.validade and lote_obj.validade != validade:
            raise RegraNegocioError(
                f"O lote {numero_lote} já existe com validade {lote_obj.validade:%d/%m/%Y}. "
                "Confira a data ou use outro número de lote."
            )
        elif validade and not lote_obj.validade:
            lote_obj.validade = validade
        _alterar_saldo_lote(lote_obj, qtd)

    try:
        saldo = _alterar_saldo_produto(produto, qtd)
        mov = InventoryMovement(
            product_id=produto.id, natureza="entrada", tipo=tipo, quantidade=qtd, saldo_apos=saldo,
            lote_id=lote_obj.id if lote_obj else None,
            validade=lote_obj.validade if lote_obj else None,
            numero_serie=", ".join(series) or None, valor_unitario=valor,
            usuario_id=usuario.id, data_hora=data_hora or agora(), observacao=observacao,
        )
        db.session.add(mov)
        db.session.flush()
        for numero in series:
            serie = SerialNumber.query.filter_by(product_id=produto.id, numero=numero).first()
            if serie is None:
                serie = SerialNumber(product_id=produto.id, numero=numero)
                db.session.add(serie)
            serie.status = "em_estoque"
            serie.entrada_mov_id = mov.id
            serie.saida_mov_id = None
        alert_service.sincronizar_alertas_estoque(produto)
        if lote_obj is not None:
            alert_service.sincronizar_alertas_lote(lote_obj)
        _commit_ou_rollback(commit)
        return mov
    except Exception:
        if commit:
            db.session.rollback()
        raise


def registrar_saida(product_id, quantidade, tipo, usuario, lote_id=None, numeros_serie=None,
                    valor_unitario=None, observacao=None, sale_id=None,
                    data_hora: datetime | None = None, commit=True,
                    selecionar_series_automaticamente=False) -> list[InventoryMovement]:
    """Registra uma saída. Retorna as movimentações geradas (uma por lote envolvido)."""
    produto = _produto(product_id)
    if tipo not in TIPOS_SAIDA:
        raise RegraNegocioError("Escolha o tipo de saída.")
    qtd = _quantidade(quantidade, produto)
    valor = _valor_unitario(valor_unitario)
    observacao = (observacao or "").strip()[:255] or None
    momento = data_hora or agora()

    # Verificação prévia com mensagem clara (a garantia final é o UPDATE atômico).
    if verificar_estoque_insuficiente(produto, qtd):
        raise EstoqueInsuficienteError(
            f"{MSG_ESTOQUE_INSUFICIENTE} Disponível de \"{produto.nome}\": "
            f"{_fmt(produto.estoque_atual)} {produto.unidade}; solicitado: {_fmt(qtd)} {produto.unidade}."
        )

    try:
        # Define de onde sai a quantidade: [(lote, qtd)] ou séries
        alocacao: list[tuple[Lote | None, Decimal]] = []
        series_obj: list[SerialNumber] = []
        if produto.controla_serie:
            series = _series(numeros_serie)
            if not series and selecionar_series_automaticamente:
                series_obj = series_disponiveis(produto)[: int(qtd)]
            else:
                if len(series) != int(qtd):
                    raise RegraNegocioError(
                        f"Informe {int(qtd)} número(s) de série que estão saindo. Foram informados {len(series)}."
                    )
                series_obj = SerialNumber.query.filter(SerialNumber.product_id == produto.id,
                                                       SerialNumber.numero.in_(series)).all()
                encontrados = {s.numero for s in series_obj if s.status == "em_estoque"}
                faltando = [s for s in series if s not in encontrados]
                if faltando:
                    raise RegraNegocioError(
                        "Número(s) de série não encontrado(s) no estoque deste produto: " + ", ".join(faltando) + "."
                    )
            if len(series_obj) != int(qtd):
                raise EstoqueInsuficienteError(MSG_ESTOQUE_INSUFICIENTE)
            alocacao = [(None, qtd)]
        elif produto.usa_lote:
            # Produto vencido não pode ser vendido nem consumido; só sai como perda/devolução/ajuste.
            bloquear_vencidos = tipo in TIPOS_SEM_VENCIDOS
            dia = momento.date()
            if lote_id:
                lote = db.session.get(Lote, int(lote_id)) if str(lote_id).isdigit() else None
                if lote is None or lote.product_id != produto.id:
                    raise RegraNegocioError("Lote não encontrado para este produto.")
                if bloquear_vencidos and lote.validade and lote.validade < dia:
                    raise RegraNegocioError(
                        f"O lote {lote.numero} está vencido ({lote.validade:%d/%m/%Y}) e não pode ser vendido "
                        "ou consumido. Registre a saída como \"Perda / quebra / vencido\"."
                    )
                if Decimal(lote.quantidade) < qtd:
                    raise EstoqueInsuficienteError(
                        f"Estoque insuficiente no lote {lote.numero} (disponível: {_fmt(lote.quantidade)}). "
                        "Não é possível realizar esta saída."
                    )
                alocacao = [(lote, qtd)]
            else:
                restante = qtd
                vencido = Decimal(0)
                for lote in lotes_disponiveis(produto):  # FEFO: vence primeiro, sai primeiro
                    if bloquear_vencidos and lote.validade and lote.validade < dia:
                        vencido += Decimal(lote.quantidade)
                        continue
                    usar = min(restante, Decimal(lote.quantidade))
                    alocacao.append((lote, usar))
                    restante -= usar
                    if restante <= 0:
                        break
                if restante > 0:
                    if vencido > 0:
                        raise EstoqueInsuficienteError(
                            f"{MSG_ESTOQUE_INSUFICIENTE} Há {_fmt(vencido)} {produto.unidade} de \"{produto.nome}\" "
                            "em lotes VENCIDOS, que não podem ser vendidos. Registre a perda desses lotes."
                        )
                    raise EstoqueInsuficienteError(MSG_ESTOQUE_INSUFICIENTE)
        else:
            alocacao = [(None, qtd)]

        movimentos = []
        for lote, parcela in alocacao:
            if lote is not None:
                _alterar_saldo_lote(lote, -parcela)
            saldo = _alterar_saldo_produto(produto, -parcela)
            mov = InventoryMovement(
                product_id=produto.id, natureza="saida", tipo=tipo, quantidade=parcela, saldo_apos=saldo,
                lote_id=lote.id if lote else None, validade=lote.validade if lote else None,
                numero_serie=", ".join(s.numero for s in series_obj) or None,
                valor_unitario=valor, usuario_id=usuario.id, data_hora=momento,
                observacao=observacao, sale_id=sale_id,
            )
            db.session.add(mov)
            db.session.flush()
            movimentos.append(mov)
            if lote is not None:
                alert_service.sincronizar_alertas_lote(lote)
        for serie in series_obj:
            serie.status = "saiu"
            serie.saida_mov_id = movimentos[0].id
        alert_service.sincronizar_alertas_estoque(produto)
        _commit_ou_rollback(commit)
        return movimentos
    except Exception:
        if commit:
            db.session.rollback()
        raise


def _fmt(valor) -> str:
    from ..utils.formatos import qtd
    return qtd(valor)


def produto_dados_api(produto: Product) -> dict:
    """Dados usados pelos formulários (lotes e séries disponíveis)."""
    return {
        "id": produto.id,
        "nome": produto.nome,
        "sku": produto.sku,
        "unidade": produto.unidade,
        "estoque_atual": float(produto.estoque_atual or 0),
        "preco_venda": float(produto.preco_venda or 0),
        "preco_custo": float(produto.preco_custo or 0),
        "ponto_pedido": float(produto.ponto_pedido or 0),
        "controla_lote": produto.controla_lote,
        "controla_validade": produto.controla_validade,
        "controla_serie": produto.controla_serie,
        "lotes": [
            {"id": l.id, "numero": l.numero, "quantidade": float(l.quantidade),
             "validade": l.validade.strftime("%d/%m/%Y") if l.validade else None,
             "vencido": bool(l.validade and l.validade < hoje())}
            for l in lotes_disponiveis(produto)
        ] if produto.usa_lote else [],
        "series": [s.numero for s in series_disponiveis(produto)] if produto.controla_serie else [],
    }
