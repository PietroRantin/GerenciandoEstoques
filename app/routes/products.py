from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from ..extensions import db
from ..models import Category, InventoryMovement, Lote, Product, SerialNumber
from ..models.product import UNIDADES
from ..services import inventory_service, product_service
from ..services.errors import RegraNegocioError
from ..utils.decorators import admin_required
from ..utils.parsing import parse_int

bp = Blueprint("products", __name__)


def _produto_ou_404(produto_id) -> Product:
    produto = db.session.get(Product, produto_id)
    if produto is None:
        abort(404)
    return produto


@bp.route("/produtos")
@login_required
def listar():
    termo = request.args.get("q", "").strip()
    categoria_id = parse_int(request.args.get("categoria"))
    situacao = request.args.get("situacao", "")
    pagina = product_service.buscar_produtos(termo, categoria_id, situacao).paginate(
        page=parse_int(request.args.get("page"), 1), per_page=current_app.config["ITENS_POR_PAGINA"],
        error_out=False)
    return render_template("products/list.html", pagina=pagina, termo=termo, categoria_id=categoria_id,
                           situacao=situacao, categorias=Category.query.order_by(Category.nome).all())


def _form_context(produto=None, dados=None, erros=None):
    return dict(produto=produto, dados=dados or {}, erros=erros or {}, unidades=UNIDADES,
                categorias=Category.query.order_by(Category.nome).all())


@bp.route("/produtos/novo", methods=["GET", "POST"])
@admin_required
def novo():
    if request.method == "POST":
        try:
            produto = product_service.criar_produto(request.form)
            flash(f"Produto \"{produto.nome}\" cadastrado! Agora registre a primeira entrada de estoque.", "success")
            return redirect(url_for("products.detalhe", produto_id=produto.id))
        except RegraNegocioError as exc:
            db.session.rollback()
            flash(exc.mensagem, "danger")
            return render_template("products/form.html", **_form_context(dados=request.form, erros=exc.erros)), 422
    return render_template("products/form.html", **_form_context())


@bp.route("/produtos/<int:produto_id>")
@login_required
def detalhe(produto_id):
    produto = _produto_ou_404(produto_id)
    movimentos = (InventoryMovement.query.filter_by(product_id=produto.id)
                  .options(db.joinedload(InventoryMovement.usuario), db.joinedload(InventoryMovement.lote))
                  .order_by(InventoryMovement.data_hora.desc(), InventoryMovement.id.desc()).limit(15).all())
    lotes = produto.lotes.filter(Lote.quantidade > 0).order_by(Lote.validade).all() if produto.usa_lote else []
    series = (SerialNumber.query.filter_by(product_id=produto.id, status="em_estoque")
              .order_by(SerialNumber.numero).all() if produto.controla_serie else [])
    return render_template("products/detail.html", produto=produto, movimentos=movimentos,
                           lotes=lotes, series=series)


@bp.route("/produtos/<int:produto_id>/editar", methods=["GET", "POST"])
@admin_required
def editar(produto_id):
    produto = _produto_ou_404(produto_id)
    if request.method == "POST":
        try:
            product_service.atualizar_produto(produto, request.form)
            flash("Alterações salvas.", "success")
            return redirect(url_for("products.detalhe", produto_id=produto.id))
        except RegraNegocioError as exc:
            db.session.rollback()
            flash(exc.mensagem, "danger")
            return render_template("products/form.html",
                                   **_form_context(produto, request.form, exc.erros)), 422
    return render_template("products/form.html", **_form_context(produto))


@bp.route("/produtos/<int:produto_id>/excluir", methods=["POST"])
@admin_required
def excluir(produto_id):
    produto = _produto_ou_404(produto_id)
    nome = produto.nome
    resultado = product_service.excluir_produto(produto)
    if resultado == "desativado":
        flash(f"\"{nome}\" tem histórico de movimentações, por isso foi DESATIVADO (o histórico foi preservado). "
              "Para reativar, edite o produto e marque \"Produto ativo\".", "warning")
    else:
        flash(f"Produto \"{nome}\" excluído.", "success")
    return redirect(url_for("products.listar"))


@bp.route("/api/produtos/<int:produto_id>")
@login_required
def api_produto(produto_id):
    produto = _produto_ou_404(produto_id)
    return jsonify(inventory_service.produto_dados_api(produto))


# ---- Categorias -----------------------------------------------------------
@bp.route("/categorias", methods=["GET", "POST"])
@admin_required
def categorias():
    erros, dados = {}, {}
    if request.method == "POST":
        try:
            categoria = product_service.salvar_categoria(request.form)
            flash(f"Categoria \"{categoria.nome}\" cadastrada.", "success")
            return redirect(url_for("products.categorias"))
        except RegraNegocioError as exc:
            db.session.rollback()
            flash(exc.mensagem, "danger")
            erros, dados = exc.erros, request.form
    lista = Category.query.order_by(Category.nome).all()
    return render_template("products/categories.html", categorias=lista, erros=erros, dados=dados)


@bp.route("/categorias/<int:categoria_id>/editar", methods=["POST"])
@admin_required
def editar_categoria(categoria_id):
    categoria = db.session.get(Category, categoria_id) or abort(404)
    try:
        product_service.salvar_categoria(request.form, categoria)
        flash("Categoria atualizada.", "success")
    except RegraNegocioError as exc:
        db.session.rollback()
        flash(exc.mensagem, "danger")
    return redirect(url_for("products.categorias"))


@bp.route("/categorias/<int:categoria_id>/excluir", methods=["POST"])
@admin_required
def excluir_categoria(categoria_id):
    categoria = db.session.get(Category, categoria_id) or abort(404)
    try:
        product_service.excluir_categoria(categoria)
        flash("Categoria excluída.", "success")
    except RegraNegocioError as exc:
        db.session.rollback()
        flash(exc.mensagem, "danger")
    return redirect(url_for("products.categorias"))
