"""Perfil de Cliente Ideal (ICP) y calificación de empresas candidatas.

Esta es la pieza que retroalimenta la herramienta con la cartera de clientes
actuales:

  1. Se lee la lista de clientes (sólo nombres).
  2. Cada cliente se resuelve a dominio (Google Places) y se describe (Claude).
     El resultado se cachea en clients/icp_profile.json para no re-pagar.
  3. Claude resume el conjunto en un perfil ICP.
  4. Cada empresa candidata se califica contra el ICP (si / quizas / no + score).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from . import config, discovery, llm
from .describe import describir
from .models import Empresa


def cargar_clientes(csv_path: str | Path) -> list[str]:
    """Lee nombres de clientes desde un CSV (una columna 'nombre' o la primera)."""
    nombres: list[str] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return []
    # Detectar encabezado
    encabezado = [c.strip().lower() for c in rows[0]]
    if "nombre" in encabezado:
        idx = encabezado.index("nombre")
        data = rows[1:]
    else:
        idx = 0
        # si la primera fila no parece encabezado, incluirla
        data = rows if encabezado[0] not in ("empresa", "cliente") else rows[1:]
    for row in data:
        if row and row[idx].strip():
            nombres.append(row[idx].strip())
    return nombres


def _perfilar_clientes(nombres: list[str]) -> list[dict]:
    """Resuelve cada cliente a dominio y lo describe. Devuelve dicts perfilados."""
    perfilados: list[dict] = []
    for nombre in nombres:
        try:
            empresa = discovery.resolver_dominio_de_nombre(nombre)
        except Exception:
            empresa = None
        if empresa is None:
            perfilados.append({"nombre": nombre, "descripcion": "", "sector": "", "tamano_estimado": ""})
            continue
        empresa.nombre = nombre
        describir(empresa)
        perfilados.append(
            {
                "nombre": nombre,
                "descripcion": empresa.descripcion,
                "sector": empresa.sector,
                "tamano_estimado": empresa.tamano_estimado,
                "senales": empresa.senales,
            }
        )
    return perfilados


def construir_o_cargar_icp(
    nombres: list[str], usar_cache: bool = True
) -> tuple[llm.PerfilICP, list[dict]]:
    """Devuelve (perfil_icp, ejemplos_clientes). Cachea en clients/icp_profile.json."""
    if usar_cache and config.ICP_CACHE.exists():
        cache = json.loads(config.ICP_CACHE.read_text(encoding="utf-8"))
        return llm.PerfilICP(**cache["perfil"]), cache["clientes"]

    clientes = _perfilar_clientes(nombres)
    perfil = llm.construir_perfil_icp(clientes)

    config.CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    config.ICP_CACHE.write_text(
        json.dumps({"perfil": perfil.model_dump(), "clientes": clientes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return perfil, clientes


def calificar(empresa: Empresa, perfil: llm.PerfilICP, ejemplos: list[dict]) -> Empresa:
    """Califica una empresa contra el ICP y rellena ajuste_icp / score_icp / razon_icp."""
    try:
        cal = llm.calificar_empresa(empresa.to_dict(), perfil, ejemplos)
    except Exception:
        return empresa
    empresa.ajuste_icp = cal.ajuste
    empresa.score_icp = cal.score_icp
    empresa.razon_icp = cal.razon
    return empresa
