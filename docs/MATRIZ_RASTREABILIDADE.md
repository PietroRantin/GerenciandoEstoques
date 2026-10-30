# Matriz de rastreabilidade

Liga cada requisito da **proposta do projeto** (documento "Proposta de Tema", RF-001 a RF-006 e
RNF-001 a RNF-005) e do **escopo detalhado de desenvolvimento** à funcionalidade, ao código que a
implementa e ao teste que a verifica.

Legenda de testes: `tests/<arquivo>::<teste>`. "Aceitação" = passo do
[roteiro manual](ROTEIRO_TESTE_MANUAL.md), também verificado em `tests/test_views.py::test_roteiro_de_aceitacao_completo`.

## Requisitos funcionais da proposta

| Requisito (proposta) | Funcionalidade | Implementação | Testes | Status |
|---|---|---|---|---|
| **RF-001** Registro, edição e exclusão de produtos (código de barras/SKU, nome, descrição, unidade, preço de venda) | Telas Produtos / Cadastrar / Editar / Excluir, pesquisa e filtros; categorias | `services/product_service.py`, `routes/products.py`, `templates/products/*` | `test_views.py::test_roteiro_de_aceitacao_completo`, `::test_sku_e_codigo_de_barras_duplicados`, `::test_validacoes_de_produto`, `::test_excluir_produto_sem_e_com_historico`, `::test_categoria_com_produtos_nao_e_excluida`; aceitação passos 2–3 | ✅ |
| **RF-002** Registrar entradas (compras) e saídas (vendas, consumo, perdas) | Telas Registrar entrada / Registrar saída / Nova venda | `services/inventory_service.py` (`registrar_entrada`, `registrar_saida`), `services/sales_service.py` | `test_inventory.py::test_entrada_aumenta_saldo`, `::test_saida_diminui_saldo`, `test_sales.py::test_venda_registra_corretamente`; aceitação 4, 6 | ✅ |
| **RF-003** Saldo atualizado em tempo real | Saldo alterado na mesma transação da movimentação; painel, alertas e histórico leem o mesmo dado | `inventory_service._alterar_saldo_produto` (UPDATE atômico) | `test_inventory.py::test_saldo_bate_com_historico`, `test_sales.py::test_venda_reduz_estoque`; aceitação 5, 7 | ✅ |
| **RF-004** Impedir saída com saldo insuficiente, com mensagem de ruptura | Bloqueio com a mensagem "Estoque insuficiente. Não é possível realizar esta saída." + quantidade disponível; aviso imediato no formulário | `inventory_service.registrar_saida` + `UPDATE ... WHERE estoque_atual >= qtd` | `test_inventory.py::test_saida_maior_que_estoque_e_bloqueada`, `::test_saldo_nunca_fica_negativo`, `::test_update_atomico_impede_negativo_mesmo_com_dado_desatualizado`, `test_sales.py::test_venda_acima_do_estoque_e_bloqueada_e_nada_e_baixado`; aceitação 8–9 | ✅ |
| **RF-005** Configurar Mínimo, Máximo e Ponto de Pedido por produto | Campos no cadastro com validação (mín ≤ ponto ≤ máx) | `product_service._validar` | `test_views.py::test_validacoes_de_produto`; aceitação 10 | ✅ |
| **RF-006** Alerta automático ao atingir/ficar abaixo do Ponto de Pedido | Alertas no sistema (badge no menu, painel, página Alertas) com sugestão de compra; resolvidos automaticamente após reposição | `services/alert_service.py` (`sincronizar_alertas_estoque`, `produtos_para_repor`) | `test_inventory.py::test_ponto_de_pedido_gera_alerta`, `::test_alerta_resolvido_apos_reposicao`; aceitação 11 | ✅ (no sistema; e-mail não implementado — ver limitações) |

## Requisitos não funcionais da proposta

| Requisito | Como foi atendido | Evidência | Status |
|---|---|---|---|
| **RNF-001** Consulta de saldo ≤ 2 s | Saldo mantido na tabela de produtos (leitura por chave primária) + índices; listas paginadas e filtradas no banco | `tests/test_performance.py` — ~0,2 ms por consulta com 1.500 produtos e 100.000 movimentações | ✅ |
| **RNF-002** Integridade dos dados / disponibilidade 99,9% | Integridade: transações, UPDATE atômico condicionado, chaves únicas, movimentações imutáveis, comando `verificar-saldos`. Disponibilidade depende da hospedagem | `test_saldo_bate_com_historico`, `flask verificar-saldos` | ✅ integridade / ⚠️ disponibilidade: depende de infraestrutura (fora do escopo) |
| **RNF-003** Altas movimentações por hora sem degradação | Registro de movimentação com índices; teste com histórico de 100 mil registros | `test_performance.py` (registro < 0,5 s com histórico cheio) | ✅ |
| **RNF-004** Interface web responsiva, uso em campo (coletores) | Layout responsivo (computador/tablet/celular), botões ≥ 44 px, busca por código de barras com Enter (leitores USB/Bluetooth funcionam como teclado) | `docs/validacao/c5_alertas_celular.png`, `static/js/app.js`, `static/js/venda.js` | ✅ |
| **RNF-005** Toda alteração de saldo registrada com data, hora e usuário | Tabela `movimentacoes` (usuário, data/hora, tipo, quantidade, saldo após, lote/série); não há edição/exclusão de movimentações; o saldo não é editável no cadastro | `test_inventory.py::test_movimentacao_registra_auditoria`, `test_views.py::test_estoque_nao_editavel_pelo_cadastro`, `::test_operador_registra_movimento_e_auditoria` | ✅ |

## Requisitos do escopo detalhado de desenvolvimento

| Requisito | Implementação | Testes | Status |
|---|---|---|---|
| Curva ABC (limites centralizados e configuráveis) | `services/abc_service.py`, `config.DEFAULT_SETTINGS`, tela Curva ABC | `test_abc.py` (4 testes) | ✅ |
| Lote e número de série (opcionais por produto, histórico) | `models/inventory.py`, telas Lotes/Séries | `test_inventory.py::test_lote_obrigatorio_e_fefo`, `::test_numero_de_serie`, `::test_lote_com_validade_divergente_e_bloqueado` | ✅ |
| Alerta de validade (30 dias configurável; níveis vencido/7/30) | `alert_service.status_validade`, página "Produtos próximos do vencimento" com ordenação | `test_expiry.py` (7 testes); aceitação 12–13 | ✅ |
| Lote vencido não pode ser vendido | FEFO ignora lotes vencidos em vendas/consumo | `test_inventory.py::test_lote_vencido_nao_e_vendido` | ✅ |
| Vendas e indicadores (mais vendidos, faturamento, ticket médio, evolução, giro) | `services/sales_service.py`, painel, relatório de vendas | `test_sales.py::test_indicadores` | ✅ |
| Dashboard acionável | `routes/dashboard.py`, `templates/dashboard.html` | `test_views.py::test_todas_as_paginas_renderizam` | ✅ |
| Relatórios + CSV | `routes/reports.py`, `utils/exportacao.py` | `test_views.py::test_exportacao_csv` | ✅ |
| Autenticação, hash de senha, perfis Admin/Operador | `routes/auth.py`, `utils/decorators.py`, `services/user_service.py` | `test_auth.py` (todos) | ✅ |
| Proteção CSRF e sessão com expiração | Flask-WTF `CSRFProtect`, sessão de 8 h | `test_views.py::test_csrf_bloqueia_formulario_sem_token` | ✅ |
| Mensagens de erro em português, sem detalhes técnicos | `RegraNegocioError`, páginas `erro.html` (403/404/500/erro de banco/sessão expirada) | `test_views.py::test_api_produto_e_paginas_de_erro` | ✅ |
| Dados de demonstração | `seed/seed.py` (33 produtos, 90 dias de operação) | execução do seed + `verificar-saldos` | ✅ |
| Notificações por e-mail (P2) | — | — | ❌ não implementado (P2) |

## Conflitos e lacunas identificados na análise

1. **"Não criar campo de estoque alterável livremente" × "consulta de saldo em até 2 s".** Resolvido mantendo
   `estoque_atual` como *cache* controlado: só o `inventory_service` o altera, sempre junto com a
   movimentação, e `recalcular_saldo` / `flask verificar-saldos` provam que ele bate com o histórico.
2. **Lote, validade e número de série juntos.** Para simplificar a operação, número de série é exclusivo de
   produtos unitários sem lote/validade; produtos só com validade recebem lote automático (`VAL-AAAAMMDD`).
3. **Mudança de controle de lote/série com estoque existente** criaria saldo "sem lote". Regra adotada: só é
   possível mudar esses controles com o estoque zerado.
4. **Exclusão de produto com histórico** apagaria a auditoria (RNF-005). Regra adotada: produto com
   movimentações é desativado, não apagado.
5. **Venda de lote vencido** não estava explícita nos requisitos, mas é proibida na prática (Código de Defesa
   do Consumidor). Implementado bloqueio.

## Numeração usada no relatório final

O relatório final mantém a numeração da proposta enviada (RF-001 a RF-006, RNF-001 a RNF-005) e acrescenta os
requisitos que entraram com a evolução do escopo:

| Requisito | Descrição | Onde está nesta matriz |
|---|---|---|
| **RF-007** | Alerta de lotes a vencer em período configurável (30 dias) | "Alerta de validade" (escopo detalhado) |
| **RF-008** | Rastreamento por lote e número de série nas movimentações | "Lote e número de série" (escopo detalhado) |
| **RF-009** | Classificação dos produtos pela Curva ABC | "Curva ABC" (escopo detalhado) |
| **RNF-006** | Suportar crescimento de 50% em produtos e usuários | `tests/test_performance.py` (1.500 produtos, 100 mil movimentações); PostgreSQL via `DATABASE_URL` |

Os quatro cenários de validação estão em [VALIDACAO_CENARIOS.md](VALIDACAO_CENARIOS.md).
