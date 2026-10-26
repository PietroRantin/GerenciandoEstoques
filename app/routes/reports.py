from datetime import timedelta

from flask import Blueprint, flash, render_template, request
from flask_login import login_required

from ..models import Category, Product, User
from ..models.movement import TIPOS_ENTRADA, TIPOS_SAIDA
from ..services import abc_service, alert_service, report_service, sales_service, settings_service
from ..utils.datas import hoje
from ..utils.decorators import admin_required
from ..utils.exportacao import csv_response
from ..utils.formatos import brl, data_br, datahora_br, numero_br, pct, qtd
from ..utils.parsing import ValorInvalido, parse_date, parse_int

bp = Blueprint("reports", __name__)


def _periodo_args(padrao_dias=30):
    try:
        inicio = parse_date(request.args.get("inicio"), "a data inicial")
        fim = parse_date(request.args.get("fim"), "a data final")
    except ValorInvalido as exc:
        flash(str(exc), "warning")
        inicio = fim = None
    fim = fim or hoje()
    inicio = inicio or (fim - timedelta(days=padrao_dias - 1))
    if inicio > fim:
        flash("A data inicial é depois da data final. As datas foram invertidas.", "warning")
        inicio, fim = fim, inicio
    return inicio, fim


def _csv():
    return request.args.get("formato") == "csv"


@bp.route("/relatorios")
@admin_required
def index():
    return render_template("reports/index.html")


@bp.route("/relatorios/estoque")
@admin_required
def estoque():
    categoria_id = parse_int(request.args.get("categoria"))
    situacao = request.args.get("situacao", "")
    produtos = report_service.relatorio_estoque(categoria_id, situacao).all()
    if _csv():
        return csv_response("relatorio_estoque",
                            ["Produto", "Código/SKU", "Código de barras", "Categoria", "Unidade", "Estoque atual",
                             "Mínimo", "Máximo", "Ponto de pedido", "Situação", "Custo unitário", "Valor em estoque"],
                            [[p.nome, p.sku, p.codigo_barras, p.categoria.nome if p.categoria else "", p.unidade,
                              qtd(p.estoque_atual), qtd(p.estoque_minimo), qtd(p.estoque_maximo), qtd(p.ponto_pedido),
                              p.situacao[0], numero_br(p.preco_custo), numero_br(p.valor_estoque)] for p in produtos])
    total = sum(p.valor_estoque for p in produtos)
    return render_template("reports/stock.html", produtos=produtos, total=total, categoria_id=categoria_id,
                           situacao=situacao, categorias=Category.query.order_by(Category.nome).all())


@bp.route("/relatorios/movimentacoes")
@admin_required
def movimentacoes():
    inicio, fim = _periodo_args()
    filtros = dict(inicio=inicio, fim=fim, product_id=parse_int(request.args.get("produto")),
                   natureza=request.args.get("natureza") or None, tipo=request.args.get("tipo") or None,
                   usuario_id=parse_int(request.args.get("usuario")))
    query = report_service.relatorio_movimentacoes(**filtros)
    if _csv():
        return csv_response("relatorio_movimentacoes",
                            ["Data/hora", "Produto", "Código/SKU", "Operação", "Tipo", "Quantidade", "Saldo após",
                             "Lote", "Validade", "Nº série", "Valor unitário", "Usuário", "Observação"],
                            [[datahora_br(m.data_hora), m.produto.nome, m.produto.sku,
                              "Entrada" if m.natureza == "entrada" else "Saída", m.tipo_nome, qtd(m.quantidade),
                              qtd(m.saldo_apos), m.lote.numero if m.lote else "",
                              data_br(m.validade) if m.validade else "", m.numero_serie or "",
                              numero_br(m.valor_unitario) if m.valor_unitario is not None else "",
                              m.usuario.nome, m.observacao or ""] for m in query])
    pagina = query.paginate(page=parse_int(request.args.get("page"), 1), per_page=50, error_out=False)
    return render_template("reports/movements.html", pagina=pagina, filtros=filtros, args=request.args,
                           produtos=Product.query.order_by(Product.nome).all(),
                           usuarios=User.query.order_by(User.nome).all(),
                           tipos={**TIPOS_SAIDA, **TIPOS_ENTRADA})


@bp.route("/relatorios/vendas")
@admin_required
def vendas():
    inicio, fim = _periodo_args()
    product_id = parse_int(request.args.get("produto"))
    linhas = report_service.relatorio_vendas(inicio, fim, product_id)
    ini, fi = report_service.intervalo(inicio, fim)
    resumo = sales_service.resumo_vendas(ini, fi)
    if _csv():
        return csv_response("relatorio_vendas",
                            ["Produto", "Código/SKU", "Quantidade vendida", "Nº de vendas", "Faturamento"],
                            [[p.nome, p.sku, qtd(q), n, numero_br(f)] for p, q, f, n in linhas])
    return render_template("reports/sales.html", linhas=linhas, resumo=resumo, inicio=inicio, fim=fim,
                           product_id=product_id, produtos=Product.query.order_by(Product.nome).all(),
                           grafico=sales_service.vendas_por_dia(ini, fi) if (fim - inicio).days <= 62 else None)


@bp.route("/relatorios/validade")
@admin_required
def validade():
    situacao = request.args.get("situacao", "")
    ordenar = request.args.get("ordenar", "validade")
    linhas = report_service.relatorio_validade(situacao, ordenar)
    info = alert_service.STATUS_VALIDADE_INFO
    if _csv():
        return csv_response("relatorio_validade",
                            ["Lote", "Produto", "Código/SKU", "Quantidade", "Validade", "Dias para vencer", "Situação"],
                            [[l.numero, l.produto.nome, l.produto.sku, qtd(l.quantidade), data_br(l.validade),
                              (l.validade - hoje()).days, info[s][0]] for l, s in linhas])
    return render_template("reports/expiry.html", linhas=linhas, info=info, situacao=situacao, ordenar=ordenar,
                           hoje=hoje())


@bp.route("/curva-abc")
@admin_required
def curva_abc():
    padrao = settings_service.get("abc_periodo_dias")
    inicio, fim = _periodo_args(padrao)
    ini, fi = report_service.intervalo(inicio, fim)
    resultado = abc_service.calcular_curva_abc(ini, fi)
    if _csv():
        return csv_response("curva_abc",
                            ["Posição", "Produto", "Código/SKU", "Categoria", "Quantidade vendida", "Faturamento",
                             "Participação %", "Participação acumulada %", "Classe"],
                            [[l["posicao"], l["produto"].nome, l["produto"].sku,
                              l["produto"].categoria.nome if l["produto"].categoria else "", qtd(l["quantidade"]),
                              numero_br(l["faturamento"]), numero_br(l["participacao"]),
                              numero_br(l["acumulado"]), l["classe"]] for l in resultado["linhas"]])
    return render_template("reports/abc.html", r=resultado, inicio=inicio, fim=fim, brl=brl, pct=pct)
