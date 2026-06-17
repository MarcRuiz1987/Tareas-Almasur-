"""Exportación de leads a CSV y Excel.

Mantiene el formato utf-8-sig de la v1 (`save_csv`) para que el CSV abra bien en
Excel en español. El Excel es opcional (requiere openpyxl).
"""

from __future__ import annotations

import csv
from pathlib import Path

from .models import Empresa

CAMPOS = [
    "nombre",
    "rubro",
    "comuna",
    "descripcion",
    "sector",
    "tamano_estimado",
    "nombre_contacto",
    "cargo_contacto",
    "email",
    "telefono",
    "sitio_web",
    "ajuste_icp",
    "score_icp",
    "razon_icp",
    "score",
]


def _fila(e: Empresa) -> dict:
    c = e.contacto_principal
    return {
        "nombre": e.nombre,
        "rubro": e.rubro,
        "comuna": e.comuna,
        "descripcion": e.descripcion,
        "sector": e.sector,
        "tamano_estimado": e.tamano_estimado,
        "nombre_contacto": c.nombre if c else "",
        "cargo_contacto": c.cargo if c else "",
        "email": c.email if c else "",
        "telefono": (c.telefono if c and c.telefono else e.telefono),
        "sitio_web": e.sitio_web,
        "ajuste_icp": e.ajuste_icp,
        "score_icp": e.score_icp,
        "razon_icp": e.razon_icp,
        "score": e.score,
    }


def a_csv(empresas: list[Empresa], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS)
        writer.writeheader()
        for e in empresas:
            writer.writerow(_fila(e))
    return path


def a_excel(empresas: list[Empresa], path: str | Path) -> Path:
    from openpyxl import Workbook

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.append(CAMPOS)
    for e in empresas:
        fila = _fila(e)
        ws.append([fila[c] for c in CAMPOS])
    wb.save(path)
    return path
