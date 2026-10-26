"""Dados de demonstração: simula ~90 dias de operação de uma mercearia em Barueri-SP.

Todo o histórico é gerado pelos MESMOS serviços usados pelas telas
(entradas, vendas, perdas), então saldos, lotes, alertas e auditoria são
consistentes. A geração é determinística (semente fixa).

Uso:
    python -m seed.seed            # apaga e recria os dados
    flask --app run seed
"""
import os
import random
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.extensions import db  # noqa: E402
from app.models import Category, Lote, Product, User  # noqa: E402
from app.services import alert_service, inventory_service, product_service, sales_service  # noqa: E402
from app.services.errors import RegraNegocioError  # noqa: E402

DIAS = 90
SEMENTE = 42

USUARIOS = [
    ("Maria Aparecida (Administradora)", "admin@estoque.local", "admin123", "admin"),
    ("João Pereira (Operador)", "operador@estoque.local", "operador123", "operador"),
]

CATEGORIAS = {
    "Mercearia": "Grãos, massas, enlatados e itens secos",
    "Bebidas": "Refrigerantes, sucos, água e cervejas",
    "Laticínios e frios": "Leite, iogurtes, queijos e frios",
    "Padaria": "Pães e bolos",
    "Hortifrúti": "Frutas, legumes e verduras",
    "Higiene pessoal": "Sabonetes, cremes dentais e papel higiênico",
    "Limpeza": "Produtos de limpeza doméstica",
    "Acessórios": "Pilhas, carregadores e eletrônicos simples",
}

# nome, sku, código de barras, categoria, unidade, custo, venda, mínimo, ponto, máximo,
# validade_dias (None = sem validade), lote, série, popularidade, cenário final
PRODUTOS = [
    ("Arroz branco tipo 1 5kg", "ARROZ-5KG", "7896006711117", "Mercearia", "un", "19.90", "27.90", 8, 12, 40, None, False, False, 8, "normal"),
    ("Feijão carioca 1kg", "FEIJAO-1KG", "7896006744115", "Mercearia", "un", "6.20", "8.99", 8, 12, 40, None, False, False, 8, "normal"),
    ("Açúcar refinado 1kg", "ACUCAR-1KG", "7896032501010", "Mercearia", "un", "3.80", "5.49", 6, 10, 30, None, False, False, 5, "normal"),
    ("Café torrado e moído 500g", "CAFE-500G", "7896089012345", "Mercearia", "un", "14.50", "21.90", 6, 10, 30, None, False, False, 7, "baixo"),
    ("Óleo de soja 900ml", "OLEO-900ML", "7891107101621", "Mercearia", "un", "5.90", "8.49", 6, 10, 30, None, False, False, 6, "baixo"),
    ("Macarrão espaguete 500g", "MACARRAO-500G", "7896005800027", "Mercearia", "un", "3.20", "4.99", 6, 10, 30, None, False, False, 5, "normal"),
    ("Farinha de trigo 1kg", "FARINHA-1KG", "7896005030028", "Mercearia", "un", "4.10", "5.99", 4, 6, 20, None, False, False, 3, "normal"),
    ("Sal refinado 1kg", "SAL-1KG", "7896110100012", "Mercearia", "un", "1.50", "2.79", 3, 5, 15, None, False, False, 1, "normal"),
    ("Refrigerante cola 2L", "REFRI-COLA-2L", "7894900011517", "Bebidas", "un", "6.50", "10.99", 10, 15, 48, None, False, False, 9, "normal"),
    ("Água mineral 500ml", "AGUA-500ML", "7896065200016", "Bebidas", "un", "0.90", "2.50", 12, 20, 72, None, False, False, 10, "normal"),
    ("Cerveja lata 350ml", "CERVEJA-350ML", "7891149103102", "Bebidas", "un", "2.80", "4.99", 24, 36, 120, 180, True, False, 9, "normal"),
    ("Suco de laranja integral 1L", "SUCO-LAR-1L", "7896000522017", "Bebidas", "un", "5.20", "8.90", 4, 6, 20, 120, True, False, 3, "vencendo"),
    ("Energético 250ml", "ENERGETICO-250", "7898124590011", "Bebidas", "un", "4.90", "8.99", 4, 6, 24, None, False, False, 3, "zerado"),
    ("Leite integral UHT 1L", "LEITE-1L", "7898080640017", "Laticínios e frios", "un", "4.20", "5.99", 12, 18, 60, 120, True, False, 9, "normal"),
    ("Iogurte natural 170g", "IOGURTE-170G", "7891025101079", "Laticínios e frios", "un", "1.90", "3.49", 6, 10, 30, 30, True, False, 4, "vencendo"),
    ("Queijo muçarela fatiado", "MUCARELA-KG", "2000000000015", "Laticínios e frios", "kg", "32.00", "49.90", 1, 2, 6, 45, True, False, 5, "normal"),
    ("Presunto cozido fatiado", "PRESUNTO-KG", "2000000000022", "Laticínios e frios", "kg", "25.00", "39.90", 1, 2, 5, 30, True, False, 4, "normal"),
    ("Requeijão cremoso 200g", "REQUEIJAO-200G", "7891000100011", "Laticínios e frios", "un", "4.80", "7.99", 3, 5, 15, 60, True, False, 1, "vencido"),
    ("Manteiga com sal 200g", "MANTEIGA-200G", "7896051111012", "Laticínios e frios", "un", "8.50", "12.99", 3, 5, 15, 90, True, False, 2, "normal"),
    ("Pão francês", "PAO-FRANCES-KG", None, "Padaria", "kg", "9.00", "16.90", 2, 3, 10, None, False, False, 10, "normal"),
    ("Pão de forma tradicional", "PAO-FORMA", "7896002300018", "Padaria", "un", "6.80", "9.99", 4, 6, 15, 12, True, False, 4, "vencido"),
    ("Bolo de fubá caseiro", "BOLO-FUBA", None, "Padaria", "un", "8.00", "14.90", 1, 2, 6, 6, False, False, 2, "normal"),
    ("Banana prata", "BANANA-KG", None, "Hortifrúti", "kg", "3.50", "6.99", 3, 5, 15, None, False, False, 6, "normal"),
    ("Tomate", "TOMATE-KG", None, "Hortifrúti", "kg", "4.50", "8.99", 2, 4, 12, None, False, False, 5, "baixo"),
    ("Sabonete 90g", "SABONETE-90G", "7891024134702", "Higiene pessoal", "un", "1.50", "2.99", 6, 10, 36, None, False, False, 4, "normal"),
    ("Creme dental 90g", "CREME-DENTAL-90", "7891528038114", "Higiene pessoal", "un", "3.20", "5.49", 4, 8, 24, None, False, False, 3, "normal"),
    ("Papel higiênico 12 rolos", "PAPEL-HIG-12", "7896110005478", "Higiene pessoal", "un", "14.00", "21.90", 4, 6, 20, None, False, False, 4, "baixo"),
    ("Detergente 500ml", "DETERGENTE-500", "7891022100013", "Limpeza", "un", "1.80", "2.99", 6, 10, 36, None, False, False, 4, "normal"),
    ("Sabão em pó 1kg", "SABAO-PO-1KG", "7891150028014", "Limpeza", "un", "9.50", "14.90", 3, 5, 15, None, False, False, 3, "zerado"),
    ("Água sanitária 1L", "AGUA-SANIT-1L", "7896098900011", "Limpeza", "un", "2.60", "4.49", 4, 6, 20, None, False, False, 3, "normal"),
    ("Pilha alcalina AA (2 un)", "PILHA-AA-2", "7891155000017", "Acessórios", "un", "6.00", "10.99", 3, 5, 15, None, False, False, 1, "normal"),
    ("Carregador USB-C", "CARREG-USBC", "7899000000017", "Acessórios", "un", "18.00", "39.90", 1, 2, 6, None, False, True, 1, "normal"),
    ("Fone de ouvido bluetooth", "FONE-BT", "7899000000024", "Acessórios", "un", "45.00", "89.90", 1, 1, 4, None, False, True, 1, "normal"),
]


def _momento(dia: date, hora: int, minuto: int = 0) -> datetime:
    return datetime.combine(dia, time(hora, minuto))


class Simulador:
    def __init__(self, admin, operador):
        self.rng = random.Random(SEMENTE)
        self.admin, self.operador = admin, operador
        self.hoje = date.today()
        self.agora = datetime.now()
        self.info = {}
        self.serie_seq = 0

    def comprar(self, produto: Product, dia: date, quantidade=None, validade=None, lote=None, hora=8):
        quantidade = quantidade or (Decimal(produto.estoque_maximo) - Decimal(produto.estoque_atual))
        if quantidade <= 0:
            return
        if produto.unidade == "un":
            quantidade = int(quantidade)
        dados = self.info[produto.id]
        kwargs = {}
        if produto.controla_serie:
            series = []
            for _ in range(int(quantidade)):
                self.serie_seq += 1
                series.append(f"{produto.sku[:4]}{self.serie_seq:05d}")
            kwargs["numeros_serie"] = ",".join(series)
        if produto.usa_lote:
            validade = validade or (dia + timedelta(days=dados["validade_dias"]))
            kwargs["validade"] = validade
            kwargs["lote"] = lote or f"L{dia:%y%m%d}"
        inventory_service.registrar_entrada(
            produto.id, quantidade, "compra", self.admin, valor_unitario=produto.preco_custo,
            observacao=f"NF {self.rng.randint(1000, 99999)} - fornecedor", data_hora=_momento(dia, hora), **kwargs)

    def descartar_vencidos(self, dia: date):
        vencidos = Lote.query.filter(Lote.quantidade > 0, Lote.validade < dia).all()
        for lote in vencidos:
            inventory_service.registrar_saida(lote.product_id, lote.quantidade, "perda", self.operador,
                                              lote_id=lote.id, observacao="Descarte: produto vencido",
                                              data_hora=_momento(dia, 7, 30))

    def quantidade_venda(self, produto):
        if produto.unidade == "kg":
            return Decimal(str(round(self.rng.uniform(0.2, 1.5), 3)))
        return self.rng.choice([1, 1, 1, 2, 2, 3])

    def vender(self, dia: date, ativos: list[Product], pesos: list[int]):
        n = self.rng.randint(7, 13) + (4 if dia.weekday() >= 5 else 0)
        horarios = sorted(_momento(dia, self.rng.randint(8, 20), self.rng.randint(0, 59)) for _ in range(n))
        for momento in horarios:
            if momento > self.agora:
                break
            escolhidos = {p.id: p for p in self.rng.choices(ativos, weights=pesos, k=self.rng.randint(1, 3))}
            itens = [{"product_id": p.id, "quantidade": self.quantidade_venda(p)} for p in escolhidos.values()]
            usuario = self.operador if self.rng.random() < 0.7 else self.admin
            forma = self.rng.choice(["pix", "pix", "dinheiro", "debito", "credito", "fiado"])
            try:
                sales_service.registrar_venda(itens, usuario, forma_pagamento=forma, data_hora=momento)
            except RegraNegocioError:
                # Falta de estoque de algum item: o cliente leva só o que tem
                itens = [i for i in itens if Decimal(str(i["quantidade"])) <= escolhidos[int(i["product_id"])].estoque_atual]
                if itens:
                    try:
                        sales_service.registrar_venda(itens, usuario, forma_pagamento=forma, data_hora=momento)
                    except RegraNegocioError:
                        pass

    def executar(self, produtos: list[Product]):
        inicio = self.hoje - timedelta(days=DIAS)
        for p in produtos:  # estoque inicial
            self.comprar(p, inicio)
        pesos = [self.info[p.id]["popularidade"] for p in produtos]
        for d in range(DIAS - 1, -1, -1):
            dia = self.hoje - timedelta(days=d)
            if d >= 6:
                self.descartar_vencidos(dia)
            for p in produtos:
                cenario = self.info[p.id]["cenario"]
                congelado = cenario in ("baixo", "zerado") and d < 18  # deixou de repor
                if not congelado and p.estoque_atual <= p.ponto_pedido and dia.weekday() != 6:
                    self.comprar(p, dia)
            self.vender(dia, produtos, pesos)
            if d % 9 == 0:  # pequenas ocorrências do dia a dia
                p = self.rng.choice(produtos)
                if p.estoque_atual >= 1 and not p.controla_serie:
                    try:
                        inventory_service.registrar_saida(p.id, 1, self.rng.choice(["perda", "consumo"]), self.operador,
                                                          observacao="Embalagem danificada / uso da loja",
                                                          data_hora=_momento(dia, 18))
                    except RegraNegocioError:
                        pass

    def ajustar_cenarios(self, produtos: list[Product]):
        """Garante situações claras para a demonstração."""
        hoje = self.hoje
        hora = max(min(self.agora.hour, 21), 8) if self.agora.hour >= 8 else None
        momento = _momento(hoje, hora, 0) if hora is not None else self.agora - timedelta(minutes=5)
        for p in produtos:
            cenario = self.info[p.id]["cenario"]
            atual = Decimal(p.estoque_atual)
            if cenario == "baixo":
                alvo = max(Decimal(1), (Decimal(p.ponto_pedido) / 2).quantize(Decimal(1)))
                if atual < alvo:
                    self.comprar(p, hoje - timedelta(days=1), quantidade=alvo - atual)
                elif atual > alvo:
                    self._vender_ate(p, atual - alvo, momento)
            elif cenario == "zerado" and atual > 0:
                self._vender_ate(p, atual, momento)
            elif cenario == "vencendo":
                self.comprar(p, hoje - timedelta(days=12), quantidade=4, validade=hoje + timedelta(days=4),
                             lote=f"PROMO{hoje:%m%d}")
                self.comprar(p, hoje - timedelta(days=5), quantidade=6, validade=hoje + timedelta(days=21),
                             lote=f"L{hoje:%y%m}B")
            elif cenario == "vencido":
                self.comprar(p, hoje - timedelta(days=20), quantidade=3, validade=hoje - timedelta(days=3),
                             lote=f"V{hoje:%y%m}X")

    def _vender_ate(self, produto, quantidade, momento):
        try:
            sales_service.registrar_venda([{"product_id": produto.id, "quantidade": quantidade}], self.operador,
                                          forma_pagamento="pix", data_hora=momento)
        except RegraNegocioError:
            inventory_service.registrar_saida(produto.id, quantidade, "ajuste_negativo", self.admin,
                                              observacao="Ajuste após contagem", data_hora=momento)


def popular_banco(resetar=True, verbose=True):
    if resetar:
        db.drop_all()
        db.create_all()
    from app.services.user_service import criar_usuario_inicial
    usuarios = [criar_usuario_inicial(*u) for u in USUARIOS]
    admin, operador = usuarios
    for i, u in enumerate(usuarios):  # datas de criação no passado
        u.criado_em = datetime.now() - timedelta(days=DIAS + 5 - i)
    categorias = {}
    for nome, descricao in CATEGORIAS.items():
        categorias[nome] = Category.query.filter_by(nome=nome).first() or product_service.salvar_categoria(
            {"nome": nome, "descricao": descricao})

    sim = Simulador(admin, operador)
    produtos = []
    for (nome, sku, barras, cat, un, custo, venda, minimo, ponto, maximo, val_dias, lote, serie, pop,
         cenario) in PRODUTOS:
        if Product.query.filter_by(sku=sku).first():
            continue
        p = product_service.criar_produto({
            "nome": nome, "sku": sku, "codigo_barras": barras or "", "categoria_id": categorias[cat].id,
            "unidade": un, "preco_custo": custo, "preco_venda": venda, "estoque_minimo": minimo,
            "ponto_pedido": ponto, "estoque_maximo": maximo, "controla_lote": "on" if lote else "",
            "controla_validade": "on" if val_dias else "", "controla_serie": "on" if serie else "",
            "descricao": f"{nome} — produto de demonstração.",
        })
        p.criado_em = p.atualizado_em = datetime.now() - timedelta(days=DIAS + 1)
        sim.info[p.id] = {"validade_dias": val_dias, "popularidade": pop, "cenario": cenario}
        produtos.append(p)
    db.session.commit()

    if verbose:
        print(f"Simulando {DIAS} dias de operação para {len(produtos)} produtos...")
    sim.executar(produtos)
    sim.ajustar_cenarios(produtos)
    alert_service.sincronizar_todos()

    if verbose:
        from app.models import InventoryMovement, Sale
        print(f"  Produtos: {Product.query.count()} | Movimentações: {InventoryMovement.query.count()} | "
              f"Vendas: {Sale.query.count()} | Lotes: {Lote.query.count()}")
        print("  Login administrador: admin@estoque.local / admin123")
        print("  Login operador:      operador@estoque.local / operador123")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    from app import create_app
    app = create_app()
    with app.app_context():
        from flask_migrate import upgrade
        upgrade()
        popular_banco(resetar=True)
