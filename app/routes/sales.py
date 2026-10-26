from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Product, Sale
from ..models.sale import FORMAS_PAGAMENTO
from ..services import sales_service
from ..services.errors import RegraNegocioError
from ..utils.formatos import brl
from ..utils.parsing import ValorInvalido, parse_date, parse_int

bp = Blueprint("sales", __name__)


@bp.route("/vendas")
@login_required
def listar():
    from datetime import datetime, time
    query = Sale.query.options(db.joinedload(Sale.usuario))
    try:
        inicio = parse_date(request.args.get("inicio"), "a data inicial")
        fim = parse_date(request.args.get("fim"), "a data final")
    except ValorInvalido as exc:
        flash(str(exc), "warning")
        inicio = fim = None
    if inicio:
        query = query.filter(Sale.data_hora >= datetime.combine(inicio, time.min))
    if fim:
        query = query.filter(Sale.data_hora <= datetime.combine(fim, time.max))
    pagina = query.order_by(Sale.data_hora.desc(), Sale.id.desc()).paginate(
        page=parse_int(request.args.get("page"), 1), per_page=20, error_out=False)
    p_inicio, p_fim = sales_service.periodo(30)
    return render_template("sales/list.html", pagina=pagina, args=request.args,
                           resumo=sales_service.resumo_vendas(p_inicio, p_fim))


def _itens_do_form(form):
    produtos = form.getlist("item_produto")
    quantidades = form.getlist("item_quantidade")
    precos = form.getlist("item_preco")
    itens = []
    for i, produto_id in enumerate(produtos):
        itens.append({"product_id": produto_id,
                      "quantidade": quantidades[i] if i < len(quantidades) else "",
                      "preco_unitario": precos[i] if i < len(precos) else ""})
    return itens


@bp.route("/vendas/nova", methods=["GET", "POST"])
@login_required
def nova():
    produtos = Product.query.filter_by(ativo=True).order_by(Product.nome).all()
    itens = [{"product_id": request.args.get("produto", ""), "quantidade": "1", "preco_unitario": ""}]
    if request.method == "POST":
        itens = _itens_do_form(request.form)
        try:
            venda = sales_service.registrar_venda(itens, current_user,
                                                  forma_pagamento=request.form.get("forma_pagamento"),
                                                  observacao=request.form.get("observacao"))
            flash(f"Venda nº {venda.id} registrada: {brl(venda.valor_total)}. O estoque já foi atualizado.",
                  "success")
            return redirect(url_for("sales.detalhe", venda_id=venda.id))
        except RegraNegocioError as exc:
            flash(exc.mensagem + " Nenhum item foi baixado do estoque.", "danger")
            return render_template("sales/form.html", produtos=produtos, itens=itens or [{}],
                                   formas=FORMAS_PAGAMENTO, dados=request.form), 422
    return render_template("sales/form.html", produtos=produtos, itens=itens, formas=FORMAS_PAGAMENTO, dados={})


@bp.route("/vendas/<int:venda_id>")
@login_required
def detalhe(venda_id):
    venda = db.session.get(Sale, venda_id) or abort(404)
    return render_template("sales/detail.html", venda=venda)
