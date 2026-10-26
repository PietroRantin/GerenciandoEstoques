"""Cadastro de produtos e categorias (validações centralizadas)."""
from decimal import Decimal

from sqlalchemy import func, or_

from ..extensions import db
from ..models import Category, InventoryMovement, Product
from ..models.product import UNIDADES
from ..utils.parsing import ValorInvalido, parse_bool, parse_decimal
from . import alert_service
from .errors import RegraNegocioError

CAMPOS_TEXTO = ("sku", "codigo_barras", "nome", "descricao", "unidade")


def _validar(dados: dict, produto: Product | None = None) -> dict:
    erros = {}
    limpo = {c: (dados.get(c) or "").strip() for c in CAMPOS_TEXTO}
    limpo["sku"] = limpo["sku"].upper()

    if not limpo["nome"]:
        erros["nome"] = "Informe o nome do produto."
    elif len(limpo["nome"]) > 120:
        erros["nome"] = "O nome pode ter no máximo 120 caracteres."
    if not limpo["sku"]:
        erros["sku"] = "Informe o código/SKU (ex.: ARROZ-5KG)."
    elif len(limpo["sku"]) > 50:
        erros["sku"] = "O código/SKU pode ter no máximo 50 caracteres."
    if len(limpo["codigo_barras"]) > 50:
        erros["codigo_barras"] = "O código de barras pode ter no máximo 50 caracteres."
    if limpo["unidade"] not in UNIDADES:
        erros["unidade"] = "Escolha uma unidade de medida da lista."

    # Unicidade
    id_atual = produto.id if produto else None
    if limpo["sku"] and "sku" not in erros:
        existe = Product.query.filter(func.upper(Product.sku) == limpo["sku"], Product.id != id_atual).first()
        if existe:
            erros["sku"] = f"Já existe um produto com este código/SKU ({existe.nome})."
    if limpo["codigo_barras"]:
        existe = Product.query.filter(Product.codigo_barras == limpo["codigo_barras"], Product.id != id_atual).first()
        if existe:
            erros["codigo_barras"] = f"Este código de barras já pertence ao produto \"{existe.nome}\"."
    limpo["codigo_barras"] = limpo["codigo_barras"] or None

    # Categoria
    categoria_id = dados.get("categoria_id") or None
    if categoria_id:
        try:
            categoria_id = int(categoria_id)
        except ValueError:
            categoria_id = None
        if categoria_id is None or db.session.get(Category, categoria_id) is None:
            erros["categoria_id"] = "Categoria inválida."
    limpo["categoria_id"] = categoria_id

    # Valores numéricos
    numericos = {
        "preco_custo": ("o preço de custo", 2),
        "preco_venda": ("o preço de venda", 2),
        "estoque_minimo": ("o estoque mínimo", 3),
        "estoque_maximo": ("o estoque máximo", 3),
        "ponto_pedido": ("o ponto de pedido", 3),
    }
    for campo, (rotulo, casas) in numericos.items():
        try:
            valor = parse_decimal(dados.get(campo), rotulo, obrigatorio=False, casas=casas)
            if valor is None:
                valor = None if campo == "ponto_pedido" else Decimal(0)
            elif valor < 0:
                raise ValorInvalido(f"{rotulo.capitalize()} não pode ser negativo.")
            limpo[campo] = valor
        except ValorInvalido as exc:
            erros[campo] = str(exc)

    if not erros:
        if limpo["preco_venda"] <= 0:
            erros["preco_venda"] = "Informe o preço de venda (maior que zero)."
        minimo, maximo = limpo["estoque_minimo"], limpo["estoque_maximo"]
        if limpo["ponto_pedido"] is None:
            limpo["ponto_pedido"] = minimo
        if maximo > 0 and maximo < minimo:
            erros["estoque_maximo"] = "O estoque máximo deve ser maior ou igual ao mínimo."
        if limpo["ponto_pedido"] < minimo:
            erros["ponto_pedido"] = "O ponto de pedido deve ser maior ou igual ao estoque mínimo."
        elif maximo > 0 and limpo["ponto_pedido"] > maximo:
            erros["ponto_pedido"] = "O ponto de pedido deve ser menor ou igual ao estoque máximo."

    # Rastreabilidade
    for flag in ("controla_lote", "controla_validade", "controla_serie"):
        limpo[flag] = parse_bool(dados.get(flag))
    if limpo["controla_serie"] and (limpo["controla_lote"] or limpo["controla_validade"]):
        erros["controla_serie"] = "Produtos com número de série não usam lote/validade. Escolha apenas uma opção."
    if limpo["controla_serie"] and limpo["unidade"] not in ("un", "cx", "pct", "fd"):
        erros["controla_serie"] = "Número de série só pode ser usado em produtos vendidos por unidade."
    if produto is not None and Decimal(produto.estoque_atual or 0) != 0:
        for flag in ("controla_lote", "controla_validade", "controla_serie"):
            if bool(getattr(produto, flag)) != limpo[flag]:
                erros[flag] = (
                    "Para mudar o controle de lote/validade/série, o estoque deste produto precisa estar zerado."
                )
                break

    limpo["ativo"] = parse_bool(dados.get("ativo", "on")) if produto is not None else True

    if erros:
        raise RegraNegocioError("Corrija os campos destacados e tente novamente.", erros)
    return limpo


def criar_produto(dados: dict) -> Product:
    limpo = _validar(dados)
    produto = Product(**limpo)
    db.session.add(produto)
    db.session.flush()
    alert_service.sincronizar_alertas_estoque(produto)
    db.session.commit()
    return produto


def atualizar_produto(produto: Product, dados: dict) -> Product:
    limpo = _validar(dados, produto)
    for campo, valor in limpo.items():
        setattr(produto, campo, valor)
    db.session.flush()
    alert_service.sincronizar_alertas_estoque(produto)
    db.session.commit()
    return produto


def excluir_produto(produto: Product) -> str:
    """Exclui o produto. Se já tiver histórico, apenas desativa (preserva auditoria)."""
    tem_historico = db.session.query(InventoryMovement.id).filter_by(product_id=produto.id).first() is not None
    if tem_historico:
        produto.ativo = False
        alert_service.sincronizar_alertas_estoque(produto)
        db.session.commit()
        return "desativado"
    from ..models import Alert
    Alert.query.filter_by(product_id=produto.id).delete()
    db.session.delete(produto)
    db.session.commit()
    return "excluido"


def buscar_produtos(termo: str = "", categoria_id=None, situacao: str = "", incluir_inativos=False):
    """Query filtrada no banco (usada nas listas paginadas)."""
    query = Product.query.options(db.joinedload(Product.categoria))
    if not incluir_inativos:
        query = query.filter(Product.ativo.is_(True))
    if termo:
        like = f"%{termo.strip()}%"
        query = query.filter(or_(Product.nome.ilike(like), Product.sku.ilike(like),
                                 Product.codigo_barras.ilike(like), Product.descricao.ilike(like)))
    if categoria_id:
        query = query.filter(Product.categoria_id == categoria_id)
    if situacao == "sem_estoque":
        query = query.filter(Product.estoque_atual <= 0)
    elif situacao == "repor":
        query = query.filter(Product.estoque_atual <= Product.ponto_pedido)
    elif situacao == "normal":
        query = query.filter(Product.estoque_atual > Product.ponto_pedido)
    elif situacao == "inativos":
        query = Product.query.filter(Product.ativo.is_(False))
    return query.order_by(Product.nome)


# ---- Categorias ---------------------------------------------------------
def salvar_categoria(dados: dict, categoria: Category | None = None) -> Category:
    nome = (dados.get("nome") or "").strip()
    descricao = (dados.get("descricao") or "").strip() or None
    if not nome:
        raise RegraNegocioError("Informe o nome da categoria.", {"nome": "Informe o nome da categoria."})
    if len(nome) > 80:
        raise RegraNegocioError("O nome da categoria pode ter no máximo 80 caracteres.")
    existe = Category.query.filter(func.lower(Category.nome) == nome.lower(),
                                   Category.id != (categoria.id if categoria else None)).first()
    if existe:
        raise RegraNegocioError(f"Já existe a categoria \"{existe.nome}\".", {"nome": "Categoria já cadastrada."})
    if categoria is None:
        categoria = Category()
        db.session.add(categoria)
    categoria.nome = nome
    categoria.descricao = descricao
    db.session.commit()
    return categoria


def excluir_categoria(categoria: Category) -> None:
    if categoria.produtos.count() > 0:
        raise RegraNegocioError(
            "Esta categoria possui produtos cadastrados. Mude a categoria desses produtos antes de excluí-la."
        )
    db.session.delete(categoria)
    db.session.commit()
