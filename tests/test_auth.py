"""Autenticação, sessão e perfis."""
import pytest

from app.models import User


def test_usuario_valido_entra(client, admin):
    r = client.post("/login", data={"email": "ADMIN@teste.com", "senha": "senha123"})
    assert r.status_code == 302
    assert client.get("/").status_code == 200


def test_usuario_invalido_e_bloqueado(client, admin):
    r = client.post("/login", data={"email": "admin@teste.com", "senha": "errada"})
    assert r.status_code == 401
    assert "E-mail ou senha incorretos" in r.get_data(as_text=True)
    assert client.get("/").status_code == 302


def test_usuario_desativado_nao_entra(client, admin, db):
    admin.ativo = False
    db.session.commit()
    assert client.post("/login", data={"email": "admin@teste.com", "senha": "senha123"}).status_code == 401


@pytest.mark.parametrize("url", ["/", "/produtos", "/entrada", "/saida", "/estoque", "/vendas", "/alertas",
                                 "/curva-abc", "/relatorios", "/usuarios", "/configuracoes", "/movimentacoes",
                                 "/api/produtos/1"])
def test_paginas_protegidas_exigem_login(client, url):
    r = client.get(url)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_senha_armazenada_com_hash(admin):
    assert admin.senha_hash != "senha123" and admin.check_senha("senha123")


def test_logout(client_admin):
    r = client_admin.post("/logout")
    assert r.status_code == 302
    assert client_admin.get("/").status_code == 302


def test_redirecionamento_externo_bloqueado(client, admin):
    r = client.post("/login?next=https://malicioso.com", data={"email": "admin@teste.com", "senha": "senha123"})
    assert r.headers["Location"].endswith("/")


@pytest.mark.parametrize("url", ["/produtos/novo", "/relatorios", "/curva-abc", "/usuarios", "/configuracoes",
                                 "/categorias"])
def test_operador_nao_acessa_areas_de_admin(client_operador, url):
    assert client_operador.get(url).status_code == 403


@pytest.mark.parametrize("url", ["/", "/produtos", "/entrada", "/saida", "/estoque", "/vendas", "/vendas/nova",
                                 "/alertas", "/alertas/validade", "/movimentacoes", "/lotes", "/series"])
def test_operador_acessa_operacao(client_operador, url):
    assert client_operador.get(url).status_code == 200


def test_manter_um_admin(client_admin, admin, db):
    r = client_admin.post(f"/usuarios/{admin.id}/editar", data={"nome": "Ana", "email": "admin@teste.com",
                                                                 "perfil": "operador", "ativo": "on"})
    assert r.status_code == 422
    assert db.session.get(User, admin.id).perfil == "admin"


def test_admin_cria_usuario(client_admin):
    r = client_admin.post("/usuarios/novo", data={"nome": "Carlos", "email": "carlos@teste.com", "perfil": "operador",
                                                   "senha": "abc123", "senha_confirmacao": "abc123", "ativo": "on"})
    assert r.status_code == 302
    assert User.query.filter_by(email="carlos@teste.com").one().check_senha("abc123")
