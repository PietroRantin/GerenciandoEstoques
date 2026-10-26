"""Roteiro de aceitação executado num navegador real (Chromium via Playwright).

Pré-requisito: sistema rodando com dados de demonstração.
Uso: python scripts/teste_aceitacao_navegador.py [http://127.0.0.1:5000]
"""
import os
import sys
import time
from datetime import date, timedelta

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"
SKU = f"TESTE{int(time.time()) % 100000}"
passos = []


def passo(descricao):
    passos.append(descricao)
    print(f"  [{len(passos):02d}] OK - {descricao}")


def flash(pagina):
    return pagina.locator(".alert").first.inner_text()


with sync_playwright() as pw:
    exe = os.environ.get("CHROMIUM_PATH")
    nav = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
    pg = nav.new_page(viewport={"width": 1280, "height": 900})
    pg.on("dialog", lambda d: d.accept())

    pg.goto(BASE + "/login")
    pg.fill("#email", "admin@estoque.local"); pg.fill("#senha", "admin123"); pg.click("button[type=submit]")
    expect(pg.locator("h1")).to_contain_text("Olá"); passo("Fazer login")

    pg.click("text=Produtos"); expect(pg.locator("h1")).to_contain_text("Produtos"); passo("Abrir Produtos")

    pg.click("text=Cadastrar produto")
    pg.fill("#nome", "Biscoito recheado 130g (teste)"); pg.fill("#sku", SKU); pg.fill("#preco_custo", "2,10")
    pg.fill("#preco_venda", "3,99"); pg.fill("#estoque_minimo", "3"); pg.fill("#ponto_pedido", "5"); pg.fill("#estoque_maximo", "20")
    pg.click("button:has-text('Cadastrar produto')")
    assert "cadastrado" in flash(pg); passo("Cadastrar produto")

    pg.click("text=Registrar entrada")
    pg.fill("#quantidade", "12"); pg.click("button:has-text('Registrar entrada')")
    assert "Estoque atual: 12" in flash(pg); passo("Registrar entrada")
    expect(pg.locator(".kpi .valor").first).to_contain_text("12"); passo("Verificar estoque (12)")

    pg.goto(BASE + "/vendas/nova")
    pg.fill("#busca-venda", SKU.lower()); pg.press("#busca-venda", "Enter")
    pg.locator(".item-qtd").first.fill("4")
    expect(pg.locator("#total-venda")).to_contain_text("15,96")
    pg.click("button:has-text('Confirmar venda')")
    assert "registrada" in flash(pg); passo("Registrar venda (leitor de código + total calculado)")

    pg.goto(BASE + f"/estoque?q={SKU}")
    expect(pg.locator("tbody tr").first).to_contain_text("8 un"); passo("Verificar redução do estoque (8)")

    pg.goto(BASE + "/saida")
    pg.fill(".filtro-produto", SKU.lower()); pg.press(".filtro-produto", "Enter")
    expect(pg.locator("#info-produto")).to_contain_text("8 un")
    pg.fill("#quantidade", "9")
    expect(pg.locator("#aviso-qtd")).to_contain_text("Estoque insuficiente")
    pg.click("button:has-text('Registrar saída')"); passo("Tentar saída maior que o estoque")
    assert "Estoque insuficiente. Não é possível realizar esta saída." in flash(pg); passo("Confirmar bloqueio")

    pg.goto(BASE + f"/produtos?q={SKU}"); pg.click("text=Editar")
    pg.fill("#ponto_pedido", "10"); pg.click("button:has-text('Salvar alterações')"); passo("Alterar ponto de pedido para 10")
    pg.goto(BASE + "/alertas"); expect(pg.locator("#reposicao")).to_contain_text("Biscoito recheado"); passo("Confirmar alerta de reposição")

    pg.goto(BASE + "/entrada")
    pg.fill(".filtro-produto", "iogurte-170g"); pg.press(".filtro-produto", "Enter")
    expect(pg.locator(".campo-lote").first).to_be_visible()
    pg.fill("#quantidade", "5"); pg.fill("#lote", f"L{SKU}")
    pg.fill("#validade", (date.today() + timedelta(days=6)).isoformat())
    pg.click("button:has-text('Registrar entrada')"); assert "Entrada registrada" in flash(pg)
    passo("Cadastrar lote com validade próxima (campos de lote aparecem sozinhos)")
    pg.goto(BASE + "/alertas/validade"); expect(pg.locator("table")).to_contain_text(f"L{SKU}"); passo("Confirmar alerta de validade")

    pg.goto(BASE + "/curva-abc"); expect(pg.locator("table")).to_contain_text("Biscoito recheado"); passo("Consultar Curva ABC")
    pg.goto(BASE + "/relatorios/estoque"); expect(pg.locator("table")).to_contain_text(SKU); passo("Consultar relatório")
    pg.goto(BASE + "/movimentacoes"); expect(pg.locator("tbody tr").first).to_contain_text("Iogurte"); passo("Consultar histórico")

    pg.click("button:has-text('Sair')"); expect(pg.locator("h1")).to_contain_text("Estoque Fácil"); passo("Fazer logout")

    nav.close()
print(f"\nRoteiro de aceitação: {len(passos)} passos aprovados.")
