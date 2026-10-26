# Roteiro de teste manual de aceitação

**Pré-condição:** `python -m seed.seed` e `python run.py`; abrir http://localhost:5000.
Este mesmo roteiro está automatizado em `scripts/teste_aceitacao_navegador.py` (Chromium real).

| # | Ação | Resultado esperado | Resultado obtido |
|---|---|---|---|
| 1 | Entrar com `admin@estoque.local` / `admin123` | Painel "Olá, Maria!" com cartões, alertas e gráfico | ✅ |
| 2 | Menu **Produtos** | Lista paginada com busca, filtros e situação de cada produto | ✅ |
| 3 | **Cadastrar produto**: "Biscoito recheado 130g", SKU `BISC-130`, custo 2,10, venda 3,99, mín. 3, ponto 5, máx. 20 | "Produto cadastrado!" e página do produto com estoque 0 | ✅ |
| 4 | **Registrar entrada** de 12 un (tipo Compra) | "Entrada registrada: +12 un ... Estoque atual: 12 un" | ✅ |
| 5 | Ver o produto / menu **Estoque** | Estoque atual = 12 | ✅ |
| 6 | **Nova venda**: digitar `bisc-130` + Enter, quantidade 4 | Total R$ 15,96; "Venda nº … registrada" | ✅ |
| 7 | Menu **Estoque**, buscar o produto | Estoque = 8 | ✅ |
| 8 | **Registrar saída** de 9 un (tipo Perda) | Aviso vermelho já no formulário; ao enviar: | ✅ |
| 9 | Confirmar bloqueio | "Estoque insuficiente. Não é possível realizar esta saída." e estoque continua 8 | ✅ |
| 10 | **Editar** o produto: ponto de pedido = 10 | "Alterações salvas." | ✅ |
| 11 | Menu **Alertas** | Produto aparece em "Produtos que precisam de reposição" com sugestão de compra 12 (20 − 8) | ✅ |
| 12 | **Registrar entrada** do "Iogurte natural 170g": lote e validade aparecem sozinhos; validade daqui a 6 dias | "Entrada registrada" | ✅ |
| 13 | **Alertas › Produtos próximos do vencimento** | Lote aparece como "Vence em breve" | ✅ |
| 14 | Menu **Curva ABC** | Cartões A/B/C e tabela com participação e acumulado | ✅ |
| 15 | **Relatórios › Estoque** (e Exportar CSV) | Relatório com o produto; CSV abre no Excel | ✅ |
| 16 | **Estoque › Histórico** | Movimentações com data/hora, usuário, tipo, quantidade e saldo após | ✅ |
| 17 | **Sair** | Volta para a tela de login; páginas internas exigem login | ✅ |

## Testes extras recomendados

| Ação | Esperado |
|---|---|
| Entrar como `operador@estoque.local` e abrir Relatórios/Usuários | "Acesso não permitido" (403) |
| Cadastrar produto com SKU já existente | Mensagem "Já existe um produto com este código/SKU" no campo |
| Tentar vender produto cujo único lote está vencido | Venda bloqueada informando que há lotes vencidos |
| Em **Alertas › vencimento**, clicar "Dar baixa (perda)" em um lote vencido | Saída de perda daquele lote; alerta some |
| Abrir o sistema no celular (`HOST=0.0.0.0 python run.py`) | Menu recolhível, botões grandes, venda em blocos empilhados |
