"""RNF-001 / RNF-003: consulta de saldo em até 2 segundos com alto volume."""
import random
import time
from datetime import datetime, timedelta

import pytest

from app.models import InventoryMovement, Product
from app.services import inventory_service as inv
from app.services import product_service

N_PRODUTOS = 1500        # ~45x o catálogo de demonstração (folga para crescimento de 50%)
N_MOVIMENTOS = 100_000


@pytest.mark.performance
def test_consulta_de_saldo_com_alto_volume(db, admin):
    agora = datetime.now()
    db.session.execute(Product.__table__.insert(), [
        {"sku": f"P{i:05d}", "nome": f"Produto {i}", "unidade": "un", "preco_custo": 1, "preco_venda": 2,
         "estoque_atual": 0, "estoque_minimo": 0, "estoque_maximo": 0, "ponto_pedido": 0, "controla_lote": False,
         "controla_validade": False, "controla_serie": False, "ativo": True, "criado_em": agora,
         "atualizado_em": agora} for i in range(N_PRODUTOS)])
    rng = random.Random(1)
    db.session.execute(InventoryMovement.__table__.insert(), [
        {"product_id": rng.randint(1, N_PRODUTOS), "natureza": "entrada", "tipo": "compra", "quantidade": 1,
         "saldo_apos": 1, "usuario_id": admin.id, "data_hora": agora - timedelta(minutes=i)}
        for i in range(N_MOVIMENTOS)])
    db.session.commit()

    alvo = N_PRODUTOS // 2
    inicio = time.perf_counter()
    for _ in range(100):
        inv.saldo_produto(alvo)
    por_consulta = (time.perf_counter() - inicio) / 100
    assert por_consulta < 2.0

    inicio = time.perf_counter()
    inv.recalcular_saldo(alvo)  # soma das movimentações (auditoria)
    assert time.perf_counter() - inicio < 2.0

    inicio = time.perf_counter()
    pagina = product_service.buscar_produtos("Produto 7").paginate(page=1, per_page=20, error_out=False)
    assert pagina.total > 0 and time.perf_counter() - inicio < 2.0

    # Registrar uma movimentação continua rápido com o histórico cheio
    inicio = time.perf_counter()
    for _ in range(50):
        inv.registrar_entrada(alvo, 1, "compra", admin)
    assert (time.perf_counter() - inicio) / 50 < 0.5
    print(f"\n  saldo: {por_consulta * 1000:.3f} ms/consulta com {N_MOVIMENTOS} movimentações")
