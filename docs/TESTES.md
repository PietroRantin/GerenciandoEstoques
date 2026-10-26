# Evidências de testes

Executado em 06/10/2026 com Python 3.13.16 — comando `python -m pytest -v --cov=app`.

## Resumo

| Item | Resultado |
|---|---|
| Testes automatizados executados | 94 |
| Aprovados | 94 |
| Falhas | 0 |
| Cobertura de código | 90% |
| Desempenho (RNF-001) | saldo: 0.159 ms/consulta com 100000 movimentações (1.500 produtos) — limite: 2 s |
| Integridade após simular 90 dias (`flask verificar-saldos`) | Todos os saldos conferem com o histórico. |
| Roteiro de aceitação no navegador (`scripts/teste_aceitacao_navegador.py`) | 17 de 17 passos aprovados |

## O que cada arquivo de teste cobre

| Arquivo | Escopo |
|---|---|
| `test_inventory.py` | Entrada aumenta saldo, saída diminui, saída maior que estoque bloqueada, saldo nunca negativo (inclusive com concorrência), quantidades inválidas, kg fracionado, auditoria, ponto de pedido gera alerta, alerta resolvido após reposição, lote/FEFO, lote vencido não é vendido, número de série |
| `test_expiry.py` | Níveis de validade, vencido gera alerta, dentro da janela gera alerta, distante não gera, janela configurável, alerta some com lote zerado, mudança de nível com o passar dos dias |
| `test_sales.py` | Venda registra corretamente, reduz estoque, venda acima do estoque bloqueada sem baixa parcial, mesmo produto em duas linhas, venda vazia/preço inválido, série automática, indicadores |
| `test_abc.py` | Classificação calculada, percentuais coerentes, atualização após vendas, sem vendas |
| `test_auth.py` | Login válido/inválido/desativado, páginas protegidas, hash de senha, logout, redirecionamento seguro, permissões do operador, manter um administrador, cadastro de usuário |
| `test_views.py` | Roteiro de aceitação completo via HTTP, SKU/código de barras duplicados, validações, estoque não editável, exclusão com/sem histórico, categorias, venda bloqueada, auditoria do operador, CSV, API, configurações, CSRF, renderização de todas as páginas |
| `test_performance.py` | Consulta de saldo, recálculo pelo histórico, busca paginada e registro de movimentação com 100 mil movimentações |

## Lista completa

```
tests/test_abc.py::test_classificacao_e_calculada — ✅ aprovado
tests/test_abc.py::test_percentuais_sao_coerentes — ✅ aprovado
tests/test_abc.py::test_classificacao_atualiza_apos_vendas — ✅ aprovado
tests/test_abc.py::test_sem_vendas_tudo_c — ✅ aprovado
tests/test_auth.py::test_usuario_valido_entra — ✅ aprovado
tests/test_auth.py::test_usuario_invalido_e_bloqueado — ✅ aprovado
tests/test_auth.py::test_usuario_desativado_nao_entra — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/produtos] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/entrada] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/saida] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/estoque] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/vendas] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/alertas] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/curva-abc] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/relatorios] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/usuarios] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/configuracoes] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/movimentacoes] — ✅ aprovado
tests/test_auth.py::test_paginas_protegidas_exigem_login[/api/produtos/1] — ✅ aprovado
tests/test_auth.py::test_senha_armazenada_com_hash — ✅ aprovado
tests/test_auth.py::test_logout — ✅ aprovado
tests/test_auth.py::test_redirecionamento_externo_bloqueado — ✅ aprovado
tests/test_auth.py::test_operador_nao_acessa_areas_de_admin[/produtos/novo] — ✅ aprovado
tests/test_auth.py::test_operador_nao_acessa_areas_de_admin[/relatorios] — ✅ aprovado
tests/test_auth.py::test_operador_nao_acessa_areas_de_admin[/curva-abc] — ✅ aprovado
tests/test_auth.py::test_operador_nao_acessa_areas_de_admin[/usuarios] — ✅ aprovado
tests/test_auth.py::test_operador_nao_acessa_areas_de_admin[/configuracoes] — ✅ aprovado
tests/test_auth.py::test_operador_nao_acessa_areas_de_admin[/categorias] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/produtos] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/entrada] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/saida] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/estoque] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/vendas] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/vendas/nova] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/alertas] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/alertas/validade] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/movimentacoes] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/lotes] — ✅ aprovado
tests/test_auth.py::test_operador_acessa_operacao[/series] — ✅ aprovado
tests/test_auth.py::test_manter_um_admin — ✅ aprovado
tests/test_auth.py::test_admin_cria_usuario — ✅ aprovado
tests/test_expiry.py::test_status_validade_niveis — ✅ aprovado
tests/test_expiry.py::test_produto_vencido_gera_alerta — ✅ aprovado
tests/test_expiry.py::test_produto_dentro_da_janela_gera_alerta — ✅ aprovado
tests/test_expiry.py::test_produto_distante_da_validade_nao_gera_alerta — ✅ aprovado
tests/test_expiry.py::test_janela_configuravel — ✅ aprovado
tests/test_expiry.py::test_alerta_some_quando_lote_zerado — ✅ aprovado
tests/test_expiry.py::test_sincronizacao_diaria_muda_nivel — ✅ aprovado
tests/test_inventory.py::test_entrada_aumenta_saldo — ✅ aprovado
tests/test_inventory.py::test_saida_diminui_saldo — ✅ aprovado
tests/test_inventory.py::test_saida_maior_que_estoque_e_bloqueada — ✅ aprovado
tests/test_inventory.py::test_saldo_nunca_fica_negativo — ✅ aprovado
tests/test_inventory.py::test_update_atomico_impede_negativo_mesmo_com_dado_desatualizado — ✅ aprovado
tests/test_inventory.py::test_quantidade_invalida[0] — ✅ aprovado
tests/test_inventory.py::test_quantidade_invalida[-3] — ✅ aprovado
tests/test_inventory.py::test_quantidade_invalida[abc] — ✅ aprovado
tests/test_inventory.py::test_quantidade_invalida[] — ✅ aprovado
tests/test_inventory.py::test_quantidade_invalida[1,5] — ✅ aprovado
tests/test_inventory.py::test_quantidade_fracionada_em_kg — ✅ aprovado
tests/test_inventory.py::test_produto_inexistente_e_tipo_invalido — ✅ aprovado
tests/test_inventory.py::test_movimentacao_registra_auditoria — ✅ aprovado
tests/test_inventory.py::test_saldo_bate_com_historico — ✅ aprovado
tests/test_inventory.py::test_ponto_de_pedido_gera_alerta — ✅ aprovado
tests/test_inventory.py::test_alerta_resolvido_apos_reposicao — ✅ aprovado
tests/test_inventory.py::test_lote_obrigatorio_e_fefo — ✅ aprovado
tests/test_inventory.py::test_saida_de_lote_especifico_insuficiente — ✅ aprovado
tests/test_inventory.py::test_lote_com_validade_divergente_e_bloqueado — ✅ aprovado
tests/test_inventory.py::test_numero_de_serie — ✅ aprovado
tests/test_inventory.py::test_validade_sem_lote_gera_lote_automatico — ✅ aprovado
tests/test_inventory.py::test_produto_inativo_nao_movimenta — ✅ aprovado
tests/test_inventory.py::test_lote_vencido_nao_e_vendido — ✅ aprovado
tests/test_performance.py::test_consulta_de_saldo_com_alto_volume — ✅ aprovado
tests/test_sales.py::test_venda_registra_corretamente — ✅ aprovado
tests/test_sales.py::test_venda_reduz_estoque — ✅ aprovado
tests/test_sales.py::test_venda_acima_do_estoque_e_bloqueada_e_nada_e_baixado — ✅ aprovado
tests/test_sales.py::test_mesmo_produto_em_duas_linhas_respeita_saldo — ✅ aprovado
tests/test_sales.py::test_venda_vazia_e_preco_invalido — ✅ aprovado
tests/test_sales.py::test_venda_produto_com_serie_seleciona_automaticamente — ✅ aprovado
tests/test_sales.py::test_indicadores — ✅ aprovado
tests/test_views.py::test_roteiro_de_aceitacao_completo — ✅ aprovado
tests/test_views.py::test_sku_e_codigo_de_barras_duplicados — ✅ aprovado
tests/test_views.py::test_validacoes_de_produto — ✅ aprovado
tests/test_views.py::test_estoque_nao_editavel_pelo_cadastro — ✅ aprovado
tests/test_views.py::test_excluir_produto_sem_e_com_historico — ✅ aprovado
tests/test_views.py::test_categoria_com_produtos_nao_e_excluida — ✅ aprovado
tests/test_views.py::test_venda_bloqueada_mostra_mensagem_e_nao_grava — ✅ aprovado
tests/test_views.py::test_operador_registra_movimento_e_auditoria — ✅ aprovado
tests/test_views.py::test_exportacao_csv — ✅ aprovado
tests/test_views.py::test_api_produto_e_paginas_de_erro — ✅ aprovado
tests/test_views.py::test_configuracoes_validam_limites — ✅ aprovado
tests/test_views.py::test_todas_as_paginas_renderizam — ✅ aprovado
tests/test_views.py::test_csrf_bloqueia_formulario_sem_token — ✅ aprovado
```
