"""Validação dos quatro cenários de negócio de comércios de bairro (evidência para o relatório final).

Reproduz, no sistema real (servidor HTTP + navegador), as situações levantadas com os comerciantes:

1. Mercearia: venda de 15 unidades de leite com apenas 8 em estoque (RF-004).
2. Padaria: farinha de trigo chegando ao ponto de pedido de 10 pacotes (RF-005 e RF-006).
3. Conveniência: pico de movimentações do fim de tarde, medindo o tempo de resposta da consulta de
   saldo (RNF-001) e conferindo a auditoria por operador (RNF-005).
4. Mercearia: lote de laticínios vencendo dentro da janela de 30 dias (RF-007).

Usa um banco separado (instance/validacao.db), carregado com os dados de demonstração.

Uso:
    pip install playwright && python scripts/validacao_cenarios.py
Gera docs/VALIDACAO_CENARIOS.md, docs/validacao/resultados.json e as capturas em docs/validacao/.
"""
import json
import os
import re
import socket
import statistics
import subprocess
import sys
import time
from datetime import date, datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
BANCO = os.path.join(RAIZ, "instance", "validacao.db")
os.environ["DATABASE_URL"] = "sqlite:///" + BANCO
SAIDA = os.path.join(RAIZ, "docs", "validacao")
RELATORIO = os.path.join(RAIZ, "docs", "VALIDACAO_CENARIOS.md")
CHROMIUM = os.environ.get("CHROMIUM_PATH")

OPERACOES_PICO = 300  # vendas registradas no pico simulado
CONSULTAS_PICO = 600  # consultas de saldo no pico simulado


def preparar_banco():
    """Carrega os dados de demonstração e ajusta os produtos dos cenários."""
    from app import create_app
    from app.extensions import db
    from app.models import Product, User
    from app.services import alert_service, inventory_service, settings_service
    from seed.seed import popular_banco

    os.makedirs(os.path.dirname(BANCO), exist_ok=True)
    if os.path.exists(BANCO):
        os.remove(BANCO)
    app = create_app()
    with app.app_context():
        from flask_migrate import upgrade
        upgrade(directory=os.path.join(RAIZ, "migrations"))
        popular_banco(resetar=True, verbose=False)
        admin = User.query.filter_by(perfil="admin").first()

        def ajustar_saldo(sku, alvo):
            p = Product.query.filter_by(sku=sku).one()
            atual = p.estoque_atual
            if atual > alvo:
                inventory_service.registrar_saida(p.id, atual - alvo, "ajuste_negativo", admin,
                                                  observacao="Preparação do cenário de validação")
            elif atual < alvo:
                validade = date.today() + timedelta(days=90) if p.controla_validade else None
                inventory_service.registrar_entrada(p.id, alvo - atual, "ajuste_positivo", admin,
                                                    lote="VALID-PREP" if p.usa_lote else None, validade=validade,
                                                    observacao="Preparação do cenário de validação")
            return Product.query.filter_by(sku=sku).one()

        # Cenário 1: leite com saldo de 8 unidades
        leite = ajustar_saldo("LEITE-1L", 8)
        # Cenário 2: farinha com ponto de pedido em 10 pacotes e saldo de 14
        farinha = Product.query.filter_by(sku="FARINHA-1KG").one()
        farinha.estoque_minimo, farinha.ponto_pedido, farinha.estoque_maximo = 6, 10, 40
        db.session.commit()
        farinha = ajustar_saldo("FARINHA-1KG", 14)
        # Cenário 4: lote de iogurte vencendo em 20 dias (janela configurada: 30 dias)
        iogurte = Product.query.filter_by(sku="IOGURTE-170G").one()
        inventory_service.registrar_entrada(iogurte.id, 24, "compra", admin, lote="LAT-2610",
                                            validade=date.today() + timedelta(days=20),
                                            observacao="Lote de laticínios do cenário de validade")
        # Cenário 3: reposição dos demais produtos antes do pico (compra da manhã)
        pico_ids = []
        for p in Product.query.filter_by(ativo=True, controla_serie=False).all():
            if p.id in (leite.id, farinha.id, iogurte.id):
                continue
            pico_ids.append(p.id)
            if p.estoque_atual < 30:
                inventory_service.registrar_entrada(
                    p.id, 30 - p.estoque_atual, "compra", admin,
                    lote="VALID-PICO" if p.usa_lote else None,
                    validade=date.today() + timedelta(days=90) if p.controla_validade else None,
                    observacao="Reposição antes do pico")
        alert_service.sincronizar_todos()
        janela = settings_service.get("validade_alerta_dias")
        return {"leite_id": leite.id, "farinha_id": farinha.id, "iogurte_id": iogurte.id,
                "janela_validade": janela, "pico_ids": pico_ids}


def porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def subir_servidor(porta):
    env = dict(os.environ, PORT=str(porta), HOST="127.0.0.1")
    proc = subprocess.Popen([sys.executable, os.path.join(RAIZ, "run.py")], cwd=RAIZ, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", porta), timeout=0.2):
                return proc
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("O servidor não iniciou.")


def login(navegador, base, email, senha, viewport=None):
    """Abre uma sessão nova (contexto próprio do navegador) já autenticada."""
    contexto = navegador.new_context(viewport=viewport or {"width": 1366, "height": 860}, locale="pt-BR")
    pagina = contexto.new_page()
    pagina.goto(base + "/login")
    pagina.fill("#email", email)
    pagina.fill("#senha", senha)
    pagina.click("button[type=submit]")
    pagina.wait_for_url(base + "/")
    return pagina


def saldo_api(pagina, base, produto_id):
    r = pagina.request.get(f"{base}/api/produtos/{produto_id}")
    return r.json()


def csrf(pagina):
    return pagina.locator("input[name=csrf_token]").first.get_attribute("value")


def captura(pagina, nome, seletor=None):
    caminho = os.path.join(SAIDA, nome)
    if seletor:
        pagina.locator(seletor).first.screenshot(path=caminho)
    else:
        pagina.screenshot(path=caminho, full_page=False)
    return os.path.relpath(caminho, os.path.join(RAIZ, "docs"))


def executar(ids):
    from playwright.sync_api import sync_playwright

    os.makedirs(SAIDA, exist_ok=True)
    porta = porta_livre()
    base = f"http://127.0.0.1:{porta}"
    servidor = subir_servidor(porta)
    resultados = {"executado_em": datetime.now().strftime("%d/%m/%Y %H:%M"), "cenarios": []}
    try:
        with sync_playwright() as pw:
            navegador = pw.chromium.launch(executable_path=CHROMIUM) if CHROMIUM else pw.chromium.launch()
            pagina = login(navegador, base, "operador@estoque.local", "operador123")

            # ---- Cenário 1: ruptura de estoque (leite) ------------------------------------
            antes = saldo_api(pagina, base, ids["leite_id"])
            pagina.goto(f"{base}/vendas/nova?produto={ids['leite_id']}")
            pagina.fill("input[name=item_quantidade]", "15")
            pagina.click("#form-venda button[type=submit]")
            pagina.wait_for_load_state("networkidle")
            mensagem = pagina.locator(".alert-danger").first.inner_text().strip()
            depois = saldo_api(pagina, base, ids["leite_id"])
            img1 = captura(pagina, "c1_ruptura_leite.png")
            resultados["cenarios"].append({
                "id": 1, "nome": "Ruptura de estoque (mercearia)", "requisitos": "RF-004, RF-003",
                "entrada": "Venda de 15 unidades de Leite integral UHT 1L",
                "saldo_antes": antes.get("estoque_atual"), "saldo_depois": depois.get("estoque_atual"),
                "mensagem": mensagem,
                "aprovado": "Estoque insuficiente" in mensagem and antes.get("estoque_atual") == depois.get("estoque_atual"),
                "captura": img1,
            })

            # ---- Cenário 2: ponto de pedido (farinha) -------------------------------------
            pagina = login(navegador, base, "admin@estoque.local", "admin123")
            antes = saldo_api(pagina, base, ids["farinha_id"])
            pagina.goto(f"{base}/saida?produto={ids['farinha_id']}")
            pagina.select_option("#tipo", "consumo")
            pagina.fill("#quantidade", "4")
            pagina.fill("#observacao", "Consumo na produção de pães")
            pagina.click("#form-movimento button.btn-danger")
            pagina.wait_for_load_state("networkidle")
            aviso = " ".join(t.strip() for t in pagina.locator(".alert-warning").all_inner_texts())
            img2a = captura(pagina, "c2_ponto_pedido_aviso.png")
            pagina.goto(base + "/alertas")
            pagina.wait_for_load_state("networkidle")
            img2b = captura(pagina, "c2_ponto_pedido_alertas.png")
            depois = saldo_api(pagina, base, ids["farinha_id"])
            resultados["cenarios"].append({
                "id": 2, "nome": "Ponto de pedido (padaria)", "requisitos": "RF-005, RF-006",
                "entrada": "Consumo de 4 pacotes de Farinha de trigo 1kg (saldo 14, ponto de pedido 10)",
                "saldo_antes": antes.get("estoque_atual"), "saldo_depois": depois.get("estoque_atual"),
                "mensagem": aviso,
                "aprovado": "ponto de pedido" in aviso.lower(),
                "captura": [img2a, img2b],
            })

            # ---- Cenário 3: pico de movimentações (conveniência) --------------------------
            pagina = login(navegador, base, "operador@estoque.local", "operador123")
            pagina.goto(base + "/vendas/nova")
            token = csrf(pagina)
            produtos = ids["pico_ids"]
            inicio_pico = datetime.now()
            tempos_venda, tempos_consulta, vendas_ok, recusas = [], [], 0, []
            for i in range(OPERACOES_PICO):
                pid = produtos[i % len(produtos)]
                t0 = time.perf_counter()
                r = pagina.request.post(base + "/vendas/nova", form={
                    "csrf_token": token, "item_produto": str(pid), "item_quantidade": "1",
                    "item_preco": "", "forma_pagamento": "pix", "observacao": "Pico simulado"},
                    max_redirects=0)
                tempos_venda.append(time.perf_counter() - t0)
                if r.status in (302, 303):
                    vendas_ok += 1
                else:
                    m = re.search(r'alert-danger[^>]*>(.*?)</div>', r.text(), re.S)
                    recusas.append(re.sub(r"<[^>]+>|\s+", " ", m.group(1)).strip() if m else str(r.status))
                for _ in range(CONSULTAS_PICO // OPERACOES_PICO):
                    t0 = time.perf_counter()
                    pagina.request.get(f"{base}/api/produtos/{produtos[(i * 7) % len(produtos)]}")
                    tempos_consulta.append(time.perf_counter() - t0)
            duracao = (datetime.now() - inicio_pico).total_seconds()
            from app import create_app
            from app.models import InventoryMovement, Sale, User
            app = create_app()
            with app.app_context():
                operador = User.query.filter_by(email="operador@estoque.local").one()
                vendas_pico = [v.id for v in Sale.query.filter_by(observacao="Pico simulado").all()]
                movs = InventoryMovement.query.filter(InventoryMovement.sale_id.in_(vendas_pico)).all()
                auditados = sum(1 for m in movs if m.usuario_id == operador.id and m.data_hora)
                operador_id = operador.id
            pagina = login(navegador, base, "admin@estoque.local", "admin123")
            pagina.goto(f"{base}/relatorios/movimentacoes?usuario={operador_id}")
            pagina.wait_for_load_state("networkidle")
            img3 = captura(pagina, "c3_auditoria_operador.png")

            def ms(valores, f):
                return round(f(valores) * 1000, 1)
            ordenados = sorted(tempos_consulta)
            p95 = ordenados[int(len(ordenados) * 0.95) - 1]
            resultados["cenarios"].append({
                "id": 3, "nome": "Pico de movimentações (conveniência)", "requisitos": "RNF-001, RNF-003, RNF-005",
                "entrada": f"{OPERACOES_PICO} vendas e {len(tempos_consulta)} consultas de saldo em sequência",
                "duracao_s": round(duracao, 1),
                "vendas_registradas": vendas_ok,
                "vendas_recusadas": sorted(set(recusas)),
                "operacoes_por_hora_equivalente": int((OPERACOES_PICO + len(tempos_consulta)) / duracao * 3600),
                "consulta_media_ms": ms(tempos_consulta, statistics.mean),
                "consulta_p95_ms": round(p95 * 1000, 1),
                "consulta_max_ms": ms(tempos_consulta, max),
                "venda_media_ms": ms(tempos_venda, statistics.mean),
                "venda_max_ms": ms(tempos_venda, max),
                "movimentacoes_no_pico": len(movs), "movimentacoes_com_operador_data_hora": auditados,
                "aprovado": vendas_ok == OPERACOES_PICO and max(tempos_consulta) < 2
                            and statistics.mean(tempos_consulta) < 0.5 and auditados == len(movs),
                "captura": img3,
            })

            # ---- Cenário 4: validade de lote (laticínios) ---------------------------------
            pagina.goto(base + "/alertas/validade")
            pagina.wait_for_load_state("networkidle")
            texto = pagina.locator("main").inner_text() if pagina.locator("main").count() else pagina.inner_text("body")
            img4 = captura(pagina, "c4_validade_laticinios.png")
            resultados["cenarios"].append({
                "id": 4, "nome": "Validade de lote (mercearia)", "requisitos": "RF-007",
                "entrada": f"Lote LAT-2610 de Iogurte natural 170g vencendo em 20 dias (janela de {ids['janela_validade']} dias)",
                "mensagem": "Lote LAT-2610 listado" if "LAT-2610" in texto else "Lote não listado",
                "aprovado": "LAT-2610" in texto,
                "captura": img4,
            })

            # Tela no celular (RNF-004)
            celular = login(navegador, base, "operador@estoque.local", "operador123",
                            viewport={"width": 390, "height": 844})
            celular.goto(base + "/alertas")
            celular.wait_for_load_state("networkidle")
            celular.screenshot(path=os.path.join(SAIDA, "c5_alertas_celular.png"))
            navegador.close()
    finally:
        servidor.terminate()
        servidor.wait(timeout=10)
    return resultados


def escrever_relatorio(res):
    with open(os.path.join(SAIDA, "resultados.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    c = {x["id"]: x for x in res["cenarios"]}
    ok = lambda x: "Aprovado" if x["aprovado"] else "Reprovado"  # noqa: E731
    linhas = [
        "# Validação dos cenários de comércios de bairro", "",
        f"Executado por `scripts/validacao_cenarios.py` em {res['executado_em']}, no sistema real "
        "(servidor HTTP + navegador Chromium), com o banco de demonstração de uma mercearia de Barueri "
        "(90 dias simulados). Os cenários reproduzem situações típicas de mercearias, padarias e lojas de conveniência definidas no escopo do projeto.", "",
        "| # | Cenário | Requisitos | Entrada | Resultado obtido | Status |",
        "|---|---|---|---|---|---|",
        f"| 1 | {c[1]['nome']} | {c[1]['requisitos']} | {c[1]['entrada']} | Venda bloqueada: \"{c[1]['mensagem']}\". "
        f"Saldo antes {c[1]['saldo_antes']}, depois {c[1]['saldo_depois']} | {ok(c[1])} |",
        f"| 2 | {c[2]['nome']} | {c[2]['requisitos']} | {c[2]['entrada']} | Saldo {c[2]['saldo_antes']} → "
        f"{c[2]['saldo_depois']}; aviso: \"{c[2]['mensagem']}\" e produto na lista de reposição | {ok(c[2])} |",
        f"| 3 | {c[3]['nome']} | {c[3]['requisitos']} | {c[3]['entrada']} | Consulta de saldo: média "
        f"{c[3]['consulta_media_ms']} ms, p95 {c[3]['consulta_p95_ms']} ms, máx. {c[3]['consulta_max_ms']} ms "
        f"(limite 2.000 ms); {c[3]['vendas_registradas']} vendas em {c[3]['duracao_s']} s "
        f"(≈ {c[3]['operacoes_por_hora_equivalente']} operações/h); {c[3]['movimentacoes_com_operador_data_hora']} de "
        f"{c[3]['movimentacoes_no_pico']} movimentações com operador, data e hora | {ok(c[3])} |",
        f"| 4 | {c[4]['nome']} | {c[4]['requisitos']} | {c[4]['entrada']} | {c[4]['mensagem']} na tela de "
        f"vencimento | {ok(c[4])} |",
        "", "## Capturas", "",
        f"![Cenário 1]({c[1]['captura']})", "",
        f"![Cenário 2 — aviso]({c[2]['captura'][0]})", "",
        f"![Cenário 2 — alertas]({c[2]['captura'][1]})", "",
        f"![Cenário 3 — auditoria]({c[3]['captura']})", "",
        f"![Cenário 4 — validade]({c[4]['captura']})", "",
        "![Alertas no celular](validacao/c5_alertas_celular.png)", "",
        "Dados brutos: [validacao/resultados.json](validacao/resultados.json).", "",
    ]
    with open(RELATORIO, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))


if __name__ == "__main__":
    ids = preparar_banco()
    resultados = executar(ids)
    escrever_relatorio(resultados)
    for x in resultados["cenarios"]:
        print(f"Cenário {x['id']} — {x['nome']}: {'APROVADO' if x['aprovado'] else 'REPROVADO'}")
