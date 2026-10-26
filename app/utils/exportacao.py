import csv
import io

from flask import Response


def csv_response(nome_arquivo: str, cabecalho: list[str], linhas) -> Response:
    """Gera CSV compatível com Excel em português (separador ';' e BOM UTF-8)."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";")
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow(["" if v is None else v for v in linha])
    conteudo = "﻿" + buffer.getvalue()
    return Response(conteudo, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={nome_arquivo}.csv"})
