"""Gera screenshots das principais telas (evidência para o relatório acadêmico).

Uso: com o sistema rodando (python run.py) e os dados de demonstração carregados:
    pip install playwright && python scripts/capturar_telas.py [http://127.0.0.1:5000]
Salva em docs/screenshots/.
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"
SAIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "screenshots")
CHROMIUM = os.environ.get("CHROMIUM_PATH")

TELAS = [
    ("01_login", "/login", False),
    ("02_dashboard", "/", True),
    ("03_produtos", "/produtos", True),
    ("04_cadastro_produto", "/produtos/novo", True),
    ("05_estoque", "/estoque", True),
    ("06_entrada", "/entrada?produto=15", True),
    ("07_saida", "/saida?produto=15", True),
    ("08_nova_venda", "/vendas/nova", True),
    ("09_alertas", "/alertas", True),
    ("10_vencimento", "/alertas/validade", True),
    ("11_curva_abc", "/curva-abc", True),
    ("12_relatorios", "/relatorios", True),
    ("13_relatorio_vendas", "/relatorios/vendas", True),
    ("14_historico", "/movimentacoes", True),
    ("15_produto_detalhe", "/produtos/15", True),
    ("16_usuarios", "/usuarios", True),
    ("17_configuracoes", "/configuracoes", True),
]


def main():
    os.makedirs(SAIDA, exist_ok=True)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM) if CHROMIUM else pw.chromium.launch()
        for nome_disp, viewport in (("desktop", {"width": 1366, "height": 900}), ("celular", {"width": 390, "height": 844})):
            pagina = navegador.new_page(viewport=viewport, locale="pt-BR")
            pagina.goto(BASE + "/login")
            pagina.fill("#email", "admin@estoque.local")
            pagina.fill("#senha", "admin123")
            pagina.click("button[type=submit]")
            pagina.wait_for_url(BASE + "/")
            for nome, url, logado in TELAS:
                if nome_disp == "celular" and nome not in ("02_dashboard", "08_nova_venda", "05_estoque", "09_alertas"):
                    continue
                if not logado:
                    continue
                pagina.goto(BASE + url)
                pagina.wait_for_load_state("networkidle")
                pagina.screenshot(path=os.path.join(SAIDA, f"{nome}_{nome_disp}.png"), full_page=True)
            pagina.close()
        pagina = navegador.new_page(viewport={"width": 1366, "height": 768})
        pagina.goto(BASE + "/login")
        pagina.screenshot(path=os.path.join(SAIDA, "01_login_desktop.png"))
        navegador.close()
    print("Screenshots salvos em", SAIDA)


if __name__ == "__main__":
    main()
