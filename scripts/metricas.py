"""Métricas simples do projeto (qualidade + controle de configuração).

Uso: python scripts/metricas.py  -> imprime e grava docs/METRICAS.md
"""
import os
import re
import subprocess
from datetime import date

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def contar(pasta, extensoes):
    arquivos, linhas = 0, 0
    for base, dirs, nomes in os.walk(os.path.join(RAIZ, pasta)):
        dirs[:] = [d for d in dirs if d not in ("vendor", "__pycache__")]
        for nome in nomes:
            if nome.endswith(extensoes):
                arquivos += 1
                with open(os.path.join(base, nome), encoding="utf-8") as f:
                    linhas += sum(1 for linha in f if linha.strip())
    return arquivos, linhas


def rodar(cmd):
    return subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True).stdout


def main():
    py_app = contar("app", (".py",))
    html = contar("app/templates", (".html",))
    css_js = contar("app/static", (".css", ".js"))
    py_test = contar("tests", (".py",))
    saida = rodar(["python", "-m", "pytest", "-o", "addopts=", "-q", "-p", "no:cacheprovider", "--cov=app", "--cov-report=term"])
    resumo = re.search(r"(\d+) passed(?:, (\d+) failed)?", saida)
    aprovados = int(resumo.group(1)) if resumo else 0
    falhas = int(resumo.group(2) or 0) if resumo else 0
    cobertura = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", saida)
    commits = rodar(["git", "log", "--oneline"]).strip().splitlines()
    tipos = {}
    for c in commits:
        m = re.match(r"\w+ (\w+)(\(.+\))?:", c)
        if m:
            tipos[m.group(1)] = tipos.get(m.group(1), 0) + 1
    rotas = len(re.findall(r"@bp\.route", "".join(open(os.path.join(RAIZ, "app/routes", f), encoding="utf-8").read()
                                                  for f in os.listdir(os.path.join(RAIZ, "app/routes")) if f.endswith(".py"))))
    testes = len(re.findall(r"^def test_", "".join(open(os.path.join(RAIZ, "tests", f), encoding="utf-8").read()
                                                    for f in os.listdir(os.path.join(RAIZ, "tests")) if f.endswith(".py")),
                            re.M))

    md = f"""# Métricas do projeto

Gerado automaticamente por `scripts/metricas.py` em {date.today():%d/%m/%Y}.

| Métrica | Valor |
|---|---|
| Arquivos Python da aplicação (`app/`) | {py_app[0]} ({py_app[1]} linhas não vazias) |
| Templates HTML | {html[0]} ({html[1]} linhas) |
| CSS/JS próprios (sem bibliotecas) | {css_js[0]} ({css_js[1]} linhas) |
| Arquivos de teste | {py_test[0]} ({py_test[1]} linhas) |
| Rotas (telas/endpoints) | {rotas} |
| Funções de teste | {testes} |
| Casos de teste executados (com parametrizações) | {aprovados + falhas} |
| Testes aprovados | {aprovados} |
| Testes com falha | {falhas} |
| Cobertura de código (`app/`) | {cobertura.group(1) + '%' if cobertura else 'n/d'} |
| Commits | {len(commits)} |
| Commits por tipo | {', '.join(f'{k}: {v}' for k, v in sorted(tipos.items()))} |
"""
    with open(os.path.join(RAIZ, "docs", "METRICAS.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
