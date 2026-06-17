"""Orquestador del pipeline de la v2 (fases 1→5)."""

from __future__ import annotations

import re

from . import config, describe, discovery, enrich, icp, score
from .llm import PerfilICP
from .models import Empresa


def _normalizar(nombre: str) -> str:
    return re.sub(r"\s+", " ", nombre.lower()).strip()


def deduplicar(empresas: list[Empresa]) -> list[Empresa]:
    """Quita empresas repetidas por nombre (portado de la v1)."""
    vistas: set[str] = set()
    unicas: list[Empresa] = []
    for e in empresas:
        clave = e.dominio or _normalizar(e.nombre)
        if clave not in vistas:
            vistas.add(clave)
            unicas.append(e)
    return unicas


def generar_leads(
    rubro_slug: str,
    comunas: list[str] | None = None,
    max_por_comuna: int = config.DEFAULT_MAX,
    clientes_csv: str | None = None,
    progreso=print,
) -> list[Empresa]:
    """Corre el pipeline completo y devuelve los leads calificados y ordenados.

    Args:
        rubro_slug: rubro a buscar (clave de config.RUBROS).
        comunas: zonas a barrer (por defecto config.COMUNAS_DEFAULT).
        max_por_comuna: tope de empresas por comuna.
        clientes_csv: ruta al CSV de clientes para construir el ICP (opcional).
        progreso: callable para reportar avance (por defecto print).
    """
    rubro_nombre, rubro_query = config.resolver_rubro(rubro_slug)
    comunas = comunas or config.COMUNAS_DEFAULT

    # ── Fase 1: descubrimiento ────────────────────────────────────────────
    progreso(f"[1/5] Descubriendo '{rubro_nombre}' en {len(comunas)} comunas...")
    empresas: list[Empresa] = []
    for comuna in comunas:
        encontradas = discovery.buscar_empresas(
            rubro_query, comuna, rubro_nombre, max_por_comuna
        )
        empresas.extend(encontradas)
        progreso(f"    {comuna}: {len(encontradas)} empresas")
    empresas = deduplicar(empresas)
    progreso(f"    Total único: {len(empresas)} empresas")

    # ── Fase 2: descripción ───────────────────────────────────────────────
    progreso(f"[2/5] Describiendo empresas con sitio web...")
    for e in empresas:
        describe.describir(e)

    # ── Fase 3: contactos ─────────────────────────────────────────────────
    progreso(f"[3/5] Descubriendo y enriqueciendo contactos...")
    for e in empresas:
        enrich.enriquecer_empresa(e)

    # ── Fase 4: ICP ───────────────────────────────────────────────────────
    perfil: PerfilICP | None = None
    ejemplos: list[dict] = []
    if clientes_csv:
        progreso(f"[4/5] Construyendo ICP desde clientes y calificando...")
        nombres = icp.cargar_clientes(clientes_csv)
        perfil, ejemplos = icp.construir_o_cargar_icp(nombres)
        for e in empresas:
            icp.calificar(e, perfil, ejemplos)
    else:
        progreso("[4/5] Sin CSV de clientes: se omite la calificación ICP.")

    # ── Fase 5: scoring + orden ───────────────────────────────────────────
    progreso("[5/5] Calculando score y ordenando...")
    for e in empresas:
        score.score(e)
    empresas.sort(key=lambda e: e.score, reverse=True)
    return empresas
