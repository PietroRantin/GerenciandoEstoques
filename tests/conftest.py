from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import Category, User
from app.services import product_service


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()
        _db.engine.dispose()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def admin(db):
    u = User(nome="Ana Admin", email="admin@teste.com", perfil="admin", ativo=True)
    u.set_senha("senha123")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def operador(db):
    u = User(nome="Otávio Operador", email="operador@teste.com", perfil="operador", ativo=True)
    u.set_senha("senha123")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def categoria(db):
    c = Category(nome="Mercearia")
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture
def criar_produto(db, categoria):
    contador = {"n": 0}

    def _criar(**extra):
        contador["n"] += 1
        dados = {
            "nome": f"Produto {contador['n']}", "sku": f"SKU-{contador['n']}", "unidade": "un",
            "preco_custo": "5,00", "preco_venda": "10,00", "estoque_minimo": "5",
            "ponto_pedido": "10", "estoque_maximo": "50", "categoria_id": str(categoria.id),
        }
        dados.update({k: v for k, v in extra.items()})
        return product_service.criar_produto(dados)

    return _criar


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, email, senha="senha123"):
    return client.post("/login", data={"email": email, "senha": senha}, follow_redirects=False)


@pytest.fixture
def client_admin(client, admin):
    _login(client, admin.email)
    return client


@pytest.fixture
def client_operador(client, operador):
    _login(client, operador.email)
    return client


def D(valor) -> Decimal:
    return Decimal(str(valor))
