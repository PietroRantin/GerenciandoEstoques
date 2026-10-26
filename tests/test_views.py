"""Testes de interface (fluxo HTTP completo, como o usuário faz no navegador)."""
from datetime import date, timedelta

from app.models import Alert, Category, InventoryMovement, Product, Sale


def _produto_form(**extra):
    dados = {"nome": "Arroz 5kg", "sku": "arroz-5", "codigo_barras": "789100", "unidade": "un",
             "preco_custo": "20,00", "preco_venda": "1.027,90", "estoque_minimo": "5", "ponto_pedido": "8",
             "estoque_maximo": "30"}
    dados.update(extra)
    return dados


def test_roteiro_de_aceitacao_completo(client_admin):
    """Reproduz o roteiro de teste manual (docs/ROTEIRO_TESTE_MANUAL.md)."""
    # Cadastrar produto
    r = client_admin.post("/produtos/novo", data=_produto_form())
    assert r.status_code == 302
    p = Product.query.filter_by(sku="ARROZ-5").one()
    assert str(p.preco_venda) == "1027.90"
    # Registrar entrada
    r = client_admin.post("/entrada", data={"produto_id": p.id, "tipo": "compra", "quantidade": "20"},
                          follow_redirects=True)
    assert "Entrada registrada" in r.get_data(as_text=True)
    assert "Estoque atual: 20" in r.get_data(as_text=True)
    # Registrar venda e ver redução
    r = client_admin.post("/vendas/nova", data={"item_produto": [p.id], "item_quantidade": ["3"],
                                                 "item_preco": [""], "forma_pagamento": "pix"}, follow_redirects=True)
    assert "registrada" in r.get_data(as_text=True)
    assert p.estoque_atual == 17
    # Saída maior que o estoque é bloqueada
    r = client_admin.post("/saida", data={"produto_id": p.id, "tipo": "perda", "quantidade": "18"})
    assert r.status_code == 422
    assert "Estoque insuficiente. Não é possível realizar esta saída." in r.get_data(as_text=True)
    assert p.estoque_atual == 17
    # Alterar ponto de pedido e confirmar alerta
    r = client_admin.post(f"/produtos/{p.id}/editar", data=_produto_form(sku="ARROZ-5", ponto_pedido="20", ativo="on"))
    assert r.status_code == 302
    assert Alert.query.filter_by(product_id=p.id, tipo="estoque_baixo", resolvido=False).count() == 1
    assert "Arroz 5kg" in client_admin.get("/alertas").get_data(as_text=True)
    # Lote com validade próxima → alerta de validade
    r = client_admin.post("/produtos/novo", data=_produto_form(nome="Iogurte", sku="IOG", codigo_barras="",
                                                                controla_lote="on", controla_validade="on"))
    iog = Product.query.filter_by(sku="IOG").one()
    validade = (date.today() + timedelta(days=5)).isoformat()
    r = client_admin.post("/entrada", data={"produto_id": iog.id, "tipo": "compra", "quantidade": "6",
                                            "lote": "L77", "validade": validade})
    assert r.status_code == 302
    pagina = client_admin.get("/alertas/validade").get_data(as_text=True)
    assert "L77" in pagina and "Iogurte" in pagina
    # Curva ABC, relatório e histórico
    assert "Classe A" in client_admin.get("/curva-abc").get_data(as_text=True)
    assert "Arroz 5kg" in client_admin.get("/relatorios/estoque").get_data(as_text=True)
    historico = client_admin.get(f"/movimentacoes?produto={p.id}").get_data(as_text=True)
    assert "Ana Admin" in historico and "Venda" in historico
    # Logout
    assert client_admin.post("/logout").status_code == 302


def test_sku_e_codigo_de_barras_duplicados(client_admin):
    client_admin.post("/produtos/novo", data=_produto_form())
    r = client_admin.post("/produtos/novo", data=_produto_form(nome="Outro"))
    texto = r.get_data(as_text=True)
    assert r.status_code == 422
    assert "Já existe um produto com este código/SKU" in texto
    assert "Este código de barras já pertence" in texto
    assert Product.query.count() == 1


def test_validacoes_de_produto(client_admin):
    r = client_admin.post("/produtos/novo", data=_produto_form(nome="", preco_venda="abc", estoque_maximo="2",
                                                                ponto_pedido="1"))
    texto = r.get_data(as_text=True)
    assert r.status_code == 422
    assert "Informe o nome do produto." in texto
    assert "inválido" in texto
    assert Product.query.count() == 0


def test_estoque_nao_editavel_pelo_cadastro(client_admin):
    client_admin.post("/produtos/novo", data=_produto_form(estoque_atual="999"))
    assert Product.query.one().estoque_atual == 0


def test_excluir_produto_sem_e_com_historico(client_admin):
    client_admin.post("/produtos/novo", data=_produto_form())
    client_admin.post("/produtos/novo", data=_produto_form(sku="B", codigo_barras="", nome="B"))
    a = Product.query.filter_by(sku="ARROZ-5").one()
    b = Product.query.filter_by(sku="B").one()
    client_admin.post("/entrada", data={"produto_id": a.id, "tipo": "compra", "quantidade": "1"})
    client_admin.post(f"/produtos/{b.id}/excluir")
    assert Product.query.filter_by(sku="B").first() is None
    r = client_admin.post(f"/produtos/{a.id}/excluir", follow_redirects=True)
    assert "DESATIVADO" in r.get_data(as_text=True)
    assert Product.query.filter_by(sku="ARROZ-5").one().ativo is False
    assert InventoryMovement.query.count() == 1  # histórico preservado


def test_categoria_com_produtos_nao_e_excluida(client_admin):
    client_admin.post("/categorias", data={"nome": "Bebidas"})
    cat = Category.query.filter_by(nome="Bebidas").one()
    client_admin.post("/produtos/novo", data=_produto_form(categoria_id=cat.id))
    r = client_admin.post(f"/categorias/{cat.id}/excluir", follow_redirects=True)
    assert "possui produtos" in r.get_data(as_text=True)
    r = client_admin.post("/categorias", data={"nome": "bebidas"})
    assert "Já existe a categoria" in r.get_data(as_text=True)


def test_venda_bloqueada_mostra_mensagem_e_nao_grava(client_admin):
    client_admin.post("/produtos/novo", data=_produto_form())
    p = Product.query.one()
    r = client_admin.post("/vendas/nova", data={"item_produto": [p.id], "item_quantidade": ["2"], "item_preco": [""]})
    assert r.status_code == 422
    assert "Estoque insuficiente" in r.get_data(as_text=True)
    assert Sale.query.count() == 0


def test_operador_registra_movimento_e_auditoria(client_operador, operador, db):
    from app.services import product_service
    p = product_service.criar_produto(_produto_form())
    r = client_operador.post("/entrada", data={"produto_id": p.id, "tipo": "compra", "quantidade": "4"})
    assert r.status_code == 302
    mov = InventoryMovement.query.one()
    assert mov.usuario_id == operador.id


def test_exportacao_csv(client_admin):
    client_admin.post("/produtos/novo", data=_produto_form())
    for url in ("/relatorios/estoque", "/relatorios/movimentacoes", "/relatorios/vendas", "/relatorios/validade",
                "/curva-abc"):
        r = client_admin.get(url + "?formato=csv")
        assert r.status_code == 200 and r.mimetype == "text/csv"
    assert "Arroz 5kg" in client_admin.get("/relatorios/estoque?formato=csv").get_data(as_text=True)


def test_api_produto_e_paginas_de_erro(client_admin):
    client_admin.post("/produtos/novo", data=_produto_form())
    p = Product.query.one()
    dados = client_admin.get(f"/api/produtos/{p.id}").get_json()
    assert dados["sku"] == "ARROZ-5" and dados["estoque_atual"] == 0
    r = client_admin.get("/produtos/9999")
    assert r.status_code == 404 and "Página não encontrada" in r.get_data(as_text=True)


def test_configuracoes_validam_limites(client_admin):
    r = client_admin.post("/configuracoes", data={"abc_limite_a": "90", "abc_limite_b": "80"}, follow_redirects=True)
    assert "limite da classe A deve ser menor" in r.get_data(as_text=True)
    r = client_admin.post("/configuracoes", data={"validade_alerta_dias": "45", "nome_loja": "Mercearia do Zé"},
                          follow_redirects=True)
    assert "Configurações salvas" in r.get_data(as_text=True) and "Mercearia do Zé" in r.get_data(as_text=True)




def test_todas_as_paginas_renderizam(client_admin, admin):
    from app.services import inventory_service, product_service, sales_service
    p = product_service.criar_produto(_produto_form(controla_lote="on", controla_validade="on"))
    s = product_service.criar_produto(_produto_form(sku="S", codigo_barras="", nome="Fone", controla_serie="on"))
    inventory_service.registrar_entrada(p.id, 10, "compra", admin, lote="L1", validade=date.today())
    inventory_service.registrar_entrada(s.id, 1, "compra", admin, numeros_serie="X1")
    venda = sales_service.registrar_venda([{"product_id": p.id, "quantidade": 2}], admin)
    for url in ["/", "/?dias=7", "/produtos", f"/produtos/{p.id}", f"/produtos/{s.id}", f"/produtos/{p.id}/editar",
                "/produtos/novo", "/categorias", "/estoque", "/entrada", "/saida", "/movimentacoes", "/lotes",
                "/lotes/1", "/series", "/series/1", "/vendas", "/vendas/nova", f"/vendas/{venda.id}", "/alertas",
                "/alertas/validade", "/curva-abc", "/relatorios", "/relatorios/estoque", "/relatorios/movimentacoes",
                "/relatorios/vendas", "/relatorios/validade", "/usuarios", "/usuarios/novo", "/configuracoes"]:
        r = client_admin.get(url)
        assert r.status_code == 200, url
        assert "Algo deu errado" not in r.get_data(as_text=True), url


def test_csrf_bloqueia_formulario_sem_token(app, admin):
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        c = app.test_client()
        r = c.post("/login", data={"email": "admin@teste.com", "senha": "senha123"})
        assert r.status_code == 302 and "/login" not in r.headers.get("Location", "/") or r.status_code == 302
        assert c.get("/").status_code == 302  # não logou: requisição sem token foi rejeitada
    finally:
        app.config["WTF_CSRF_ENABLED"] = False
