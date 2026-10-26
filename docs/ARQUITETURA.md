# Arquitetura e banco de dados

## Visão geral

Aplicação web monolítica em camadas — escolhida por ser simples de instalar (um único processo
Python + um arquivo SQLite), adequada a um pequeno comércio e fácil de manter.

```mermaid
flowchart LR
    U[Comerciante / Operador<br>computador, tablet ou celular] -->|HTTP| R
    subgraph Aplicação Flask
      R[routes/<br>telas e validação de acesso] --> S[services/<br>REGRAS DE NEGÓCIO]
      R --> T[templates/ + static/<br>HTML, CSS, JS]
      S --> M[models/<br>SQLAlchemy ORM]
    end
    M --> DB[(SQLite<br>ou PostgreSQL)]
    CLI[CLI: seed, verificar-saldos,<br>db upgrade] --> S
```

| Camada | Responsabilidade | Não faz |
|---|---|---|
| `routes/` | Recebe a requisição, verifica login/perfil, chama o serviço, mostra mensagem | Não calcula estoque |
| `services/` | Todas as regras: saldo, bloqueio, lotes (FEFO), alertas, vendas, Curva ABC, relatórios | Não conhece HTML |
| `models/` | Estrutura das tabelas e propriedades de leitura (situação, sugestão de compra) | Não altera saldo |
| `templates/`, `static/` | Apresentação e conforto de uso (busca, máscara, avisos) | Não decide regras — o servidor sempre revalida |

**Regra central:** somente `services/inventory_service.py` altera saldos. Entrada, saída e venda
chamam as mesmas funções (`registrar_entrada`, `registrar_saida`), evitando regras duplicadas.

## Decisões técnicas

| Decisão | Motivo |
|---|---|
| Flask (e não FastAPI/SPA) | Menos código e menos dependências para entregar telas HTML rapidamente |
| Bootstrap embutido em `static/vendor` | Funciona sem internet — comum em pequenos comércios |
| Gráficos em HTML/CSS (sem biblioteca JS) | Leves, acessíveis (tabela de valores junto) e offline |
| Saldo em `produtos.estoque_atual` alterado por `UPDATE ... SET estoque = estoque - q WHERE estoque >= q` | Consulta instantânea (RNF-001) e impossibilidade de saldo negativo mesmo com dois usuários simultâneos |
| Movimentações imutáveis + `recalcular_saldo` | Auditoria (RNF-005) e prova de integridade (comando `verificar-saldos`) |
| Alertas persistidos e resolvidos automaticamente | Histórico de quando o problema surgiu e quando foi resolvido |
| Parâmetros de negócio em `config.DEFAULT_SETTINGS` + tabela `configuracoes` | Limites ABC e janelas de validade em um único lugar, editáveis pela tela |
| Flask-Migrate (Alembic) com `render_as_batch` | Evolução do banco compatível com SQLite e PostgreSQL |
| Valores monetários `Numeric(12,2)`, quantidades `Numeric(12,3)` + `Decimal` | Evita erros de arredondamento de `float`; permite kg/litro fracionados |

## Modelo entidade-relacionamento

```mermaid
erDiagram
    usuarios ||--o{ movimentacoes : registra
    usuarios ||--o{ vendas : realiza
    categorias ||--o{ produtos : agrupa
    produtos ||--o{ lotes : possui
    produtos ||--o{ numeros_serie : possui
    produtos ||--o{ movimentacoes : "tem histórico"
    produtos ||--o{ venda_itens : "é vendido em"
    produtos ||--o{ alertas : gera
    lotes ||--o{ movimentacoes : rastreia
    lotes ||--o{ alertas : "validade"
    vendas ||--|{ venda_itens : contém
    vendas ||--o{ movimentacoes : "baixa estoque"
    movimentacoes ||--o{ numeros_serie : "entrada/saída"

    usuarios {
        int id PK
        string nome
        string email UK
        string senha_hash
        string perfil
        bool ativo
        datetime criado_em
    }
    categorias {
        int id PK
        string nome UK
        string descricao
    }
    produtos {
        int id PK
        string sku UK
        string codigo_barras UK
        string nome
        text descricao
        int categoria_id FK
        string unidade
        decimal preco_custo
        decimal preco_venda
        decimal estoque_atual
        decimal estoque_minimo
        decimal estoque_maximo
        decimal ponto_pedido
        bool controla_lote
        bool controla_validade
        bool controla_serie
        bool ativo
        datetime criado_em
        datetime atualizado_em
    }
    lotes {
        int id PK
        int product_id FK
        string numero
        date validade
        decimal quantidade
        datetime criado_em
    }
    numeros_serie {
        int id PK
        int product_id FK
        string numero
        string status
        int entrada_mov_id FK
        int saida_mov_id FK
    }
    movimentacoes {
        int id PK
        int product_id FK
        string natureza
        string tipo
        decimal quantidade
        decimal saldo_apos
        int lote_id FK
        text numero_serie
        date validade
        decimal valor_unitario
        int usuario_id FK
        datetime data_hora
        string observacao
        int sale_id FK
    }
    vendas {
        int id PK
        int usuario_id FK
        datetime data_hora
        decimal valor_total
        string forma_pagamento
        string observacao
    }
    venda_itens {
        int id PK
        int sale_id FK
        int product_id FK
        decimal quantidade
        decimal preco_unitario
        decimal subtotal
    }
    alertas {
        int id PK
        int product_id FK
        int lote_id FK
        string tipo
        string mensagem
        string nivel
        bool resolvido
        datetime criado_em
        datetime resolvido_em
    }
    configuracoes {
        string chave PK
        string valor
    }
```

Índices relevantes: `produtos.sku`, `produtos.codigo_barras`, `produtos.nome`, `movimentacoes(product_id, data_hora)`,
`movimentacoes(data_hora)`, `lotes.validade`, `vendas.data_hora`, `alertas(resolvido, tipo)`.

## Casos de uso

Baseado no diagrama da proposta, detalhado por perfil:

```mermaid
flowchart LR
    A((Administrador))
    O((Operador))
    subgraph Sistema Estoque Fácil
      UC1[Gerenciar produtos e categorias]
      UC2[Configurar níveis de estoque]
      UC3[Registrar entrada]
      UC4[Registrar saída]
      UC5[Registrar venda]
      UC6[Controlar lote, validade e nº de série]
      UC7[Consultar saldo e histórico]
      UC8[Receber alertas de estoque e validade]
      UC9[Classificar produtos — Curva ABC]
      UC10[Consultar relatórios / exportar CSV]
      UC11[Gerenciar usuários e configurações]
    end
    A --- UC1 & UC2 & UC9 & UC10 & UC11
    A --- UC3 & UC4 & UC5 & UC7 & UC8
    O --- UC3 & UC4 & UC5 & UC7 & UC8
    UC3 -. inclui .-> UC6
    UC4 -. inclui .-> UC6
    UC5 -. inclui .-> UC4
```

## Fluxo de uma saída de estoque (venda, perda, consumo...)

```mermaid
flowchart TD
    A[Usuário informa produto e quantidade] --> B{Produto existe e está ativo?}
    B -- não --> X1[Mensagem: produto não encontrado / inativo]
    B -- sim --> C{Quantidade válida? > 0, inteira se 'un'}
    C -- não --> X2[Mensagem explicando o formato]
    C -- sim --> D{Saldo suficiente?}
    D -- não --> X3["Estoque insuficiente. Não é possível realizar esta saída." + disponível]
    D -- sim --> E{Produto usa lote?}
    E -- sim --> F[Escolhe lotes: o informado ou FEFO<br>vence primeiro sai primeiro, sem vencidos em vendas]
    E -- não --> G
    F --> G[UPDATE atômico do saldo<br>WHERE saldo >= quantidade]
    G -- falhou --> X3
    G -- ok --> H[Grava movimentação: usuário, data/hora, tipo, quantidade, saldo após]
    H --> I[Atualiza alertas: sem estoque / ponto de pedido / validade]
    I --> J[Commit — ou rollback de tudo em caso de erro]
    J --> K[Mensagem de sucesso com o novo saldo]
```

## Fluxo de desenvolvimento e implantação

```mermaid
flowchart LR
    A[Requisito] --> B[Implementar serviço + tela] --> C[Teste automatizado pytest] --> D{Todos os testes passam?}
    D -- não --> B
    D -- sim --> E[Commit semântico no Git<br>feat/fix/test/docs] --> F[Push para o GitHub]
    F --> G[Implantação: pip install -r requirements.txt<br>python run.py — aplica migrations]
    G --> H[Seed de demonstração + roteiro de aceitação]
```

## Segurança

- Senhas com hash (`werkzeug.security`, PBKDF2/scrypt); usuário desativado não entra.
- Sessão com expiração (8 h), cookies `HttpOnly`/`SameSite=Lax`; logout via POST.
- Proteção CSRF em todos os formulários (Flask-WTF).
- Controle de acesso por perfil (`@admin_required`); operador recebe 403 nas áreas administrativas.
- Redirecionamento pós-login só para URLs internas (evita *open redirect*).
- Consultas via ORM (sem SQL concatenado) — proteção contra SQL injection; Jinja2 escapa HTML (XSS).
- Erros internos registrados em log e exibidos ao usuário como mensagem amigável.
