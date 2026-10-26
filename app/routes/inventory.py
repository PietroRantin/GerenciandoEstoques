from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Category, InventoryMovement, Lote, Product, SerialNumber, User
from ..models.inventory import STATUS_SERIE
from ..models.movement import TIPOS_ENTRADA, TIPOS_SAIDA
from ..services import alert_service, inventory_service, product_service, report_service
from ..services.errors import RegraNegocioError
from ..utils.datas import hoje
from ..utils.formatos import qtd
from ..utils.parsing import ValorInvalido, parse_date, parse_int

bp = Blueprint("inventory", __name__)


def _produtos_ativos():
    return Product.query.filter_by(ativo=True).order_by(Product.nome).all()


@bp.route("/estoque")
@login_required
def estoque():
    termo = request.args.get("q", "").strip()
    categoria_id = parse_int(request.args.get("categoria"))
    situacao = request.args.get("situacao", "")
    pagina = product_service.buscar_produtos(termo, categoria_id, situacao).paginate(
        page=parse_int(request.args.get("page"), 1), per_page=current_app.config["ITENS_POR_PAGINA"],
        error_out=False)
    return render_template("inventory/stock.html", pagina=pagina, termo=termo, categoria_id=categoria_id,
                           situacao=situacao, categorias=Category.query.order_by(Category.nome).all())


@bp.route("/entrada", methods=["GET", "POST"])
@login_required
def entrada():
    dados = request.form if request.method == "POST" else {"produto_id": request.args.get("produto", "")}
    if request.method == "POST":
        try:
            try:
                validade = parse_date(request.form.get("validade"), "a data de validade")
            except ValorInvalido as exc:
                raise RegraNegocioError(str(exc))
            mov = inventory_service.registrar_entrada(
                request.form.get("produto_id"), request.form.get("quantidade"), request.form.get("tipo"),
                current_user, lote=request.form.get("lote"), validade=validade,
                numeros_serie=request.form.get("numeros_serie"), valor_unitario=request.form.get("valor_unitario"),
                observacao=request.form.get("observacao"),
            )
            produto = mov.produto
            flash(f"Entrada registrada: +{qtd(mov.quantidade)} {produto.unidade} de \"{produto.nome}\". "
                  f"Estoque atual: {qtd(produto.estoque_atual)} {produto.unidade}.", "success")
            if validade and validade < hoje():
                flash("Atenção: a validade informada já passou. Este lote aparece como VENCIDO nos alertas.",
                      "warning")
            if request.form.get("continuar"):
                return redirect(url_for("inventory.entrada"))
            return redirect(url_for("products.detalhe", produto_id=produto.id))
        except RegraNegocioError as exc:
            db.session.rollback()
            flash(exc.mensagem, "danger")
            return render_template("inventory/entry.html", produtos=_produtos_ativos(), tipos=TIPOS_ENTRADA,
                                   dados=dados), 422
    return render_template("inventory/entry.html", produtos=_produtos_ativos(), tipos=TIPOS_ENTRADA, dados=dados)


@bp.route("/saida", methods=["GET", "POST"])
@login_required
def saida():
    dados = request.form if request.method == "POST" else {"produto_id": request.args.get("produto", ""),
                                                            "lote_id": request.args.get("lote", "")}
    if request.method == "POST":
        try:
            movs = inventory_service.registrar_saida(
                request.form.get("produto_id"), request.form.get("quantidade"), request.form.get("tipo"),
                current_user, lote_id=request.form.get("lote_id") or None,
                numeros_serie=request.form.get("numeros_serie"), valor_unitario=request.form.get("valor_unitario"),
                observacao=request.form.get("observacao"),
            )
            produto = movs[0].produto
            total = sum(m.quantidade for m in movs)
            lotes = ", ".join(m.lote.numero for m in movs if m.lote)
            flash(f"Saída registrada: -{qtd(total)} {produto.unidade} de \"{produto.nome}\""
                  + (f" (lote {lotes})" if lotes else "")
                  + f". Estoque atual: {qtd(produto.estoque_atual)} {produto.unidade}.", "success")
            if inventory_service.verificar_ponto_de_pedido(produto):
                flash(f"\"{produto.nome}\" atingiu o ponto de pedido. Ele foi adicionado à lista de reposição.",
                      "warning")
            if request.form.get("continuar"):
                return redirect(url_for("inventory.saida"))
            return redirect(url_for("products.detalhe", produto_id=produto.id))
        except RegraNegocioError as exc:
            db.session.rollback()
            flash(exc.mensagem, "danger")
            return render_template("inventory/exit.html", produtos=_produtos_ativos(), tipos=TIPOS_SAIDA,
                                   dados=dados), 422
    return render_template("inventory/exit.html", produtos=_produtos_ativos(), tipos=TIPOS_SAIDA, dados=dados)


@bp.route("/movimentacoes")
@login_required
def movimentacoes():
    erros = []
    try:
        inicio = parse_date(request.args.get("inicio"), "a data inicial")
        fim = parse_date(request.args.get("fim"), "a data final")
    except ValorInvalido as exc:
        erros.append(str(exc))
        inicio = fim = None
    filtros = dict(inicio=inicio, fim=fim, product_id=parse_int(request.args.get("produto")),
                   natureza=request.args.get("natureza") or None, tipo=request.args.get("tipo") or None,
                   usuario_id=parse_int(request.args.get("usuario")))
    for erro in erros:
        flash(erro, "warning")
    pagina = report_service.relatorio_movimentacoes(**filtros).paginate(
        page=parse_int(request.args.get("page"), 1), per_page=30, error_out=False)
    return render_template("inventory/movements.html", pagina=pagina, filtros=filtros, args=request.args,
                           produtos=Product.query.order_by(Product.nome).all(),
                           usuarios=User.query.order_by(User.nome).all(),
                           tipos={**{k: v for k, v in TIPOS_SAIDA.items()}, **TIPOS_ENTRADA})


@bp.route("/lotes")
@login_required
def lotes():
    termo = request.args.get("q", "").strip()
    query = Lote.query.join(Product).options(db.contains_eager(Lote.produto))
    if termo:
        like = f"%{termo}%"
        query = query.filter(db.or_(Lote.numero.ilike(like), Product.nome.ilike(like), Product.sku.ilike(like)))
    if not request.args.get("todos"):
        query = query.filter(Lote.quantidade > 0)
    pagina = query.order_by(Lote.validade.is_(None), Lote.validade, Product.nome).paginate(
        page=parse_int(request.args.get("page"), 1), per_page=30, error_out=False)
    return render_template("inventory/lots.html", pagina=pagina, termo=termo, todos=request.args.get("todos"),
                           status_validade=alert_service.status_validade,
                           info=alert_service.STATUS_VALIDADE_INFO)


@bp.route("/lotes/<int:lote_id>")
@login_required
def lote_detalhe(lote_id):
    lote = db.session.get(Lote, lote_id) or abort(404)
    movimentos = (lote.movimentacoes.options(db.joinedload(InventoryMovement.usuario))
                  .order_by(InventoryMovement.data_hora.desc(), InventoryMovement.id.desc()).all())
    status = alert_service.status_validade(lote.validade)
    return render_template("inventory/lot_detail.html", lote=lote, movimentos=movimentos,
                           status=alert_service.STATUS_VALIDADE_INFO[status])


@bp.route("/series")
@login_required
def series():
    termo = request.args.get("q", "").strip()
    query = SerialNumber.query.join(Product).options(db.contains_eager(SerialNumber.produto))
    if termo:
        like = f"%{termo}%"
        query = query.filter(db.or_(SerialNumber.numero.ilike(like), Product.nome.ilike(like)))
    status = request.args.get("status", "")
    if status in STATUS_SERIE:
        query = query.filter(SerialNumber.status == status)
    pagina = query.order_by(Product.nome, SerialNumber.numero).paginate(
        page=parse_int(request.args.get("page"), 1), per_page=30, error_out=False)
    return render_template("inventory/serials.html", pagina=pagina, termo=termo, status=status,
                           status_opcoes=STATUS_SERIE)


@bp.route("/series/<int:serie_id>")
@login_required
def serie_detalhe(serie_id):
    serie = db.session.get(SerialNumber, serie_id) or abort(404)
    return render_template("inventory/serial_detail.html", serie=serie)
