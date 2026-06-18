#!/usr/bin/env python3
"""Corrida parcial del pipeline SIN las fases que usan Claude.

Ejecuta sólo:
    1. discovery  — Google Places (empresas por rubro + comuna)
    3. enrich     — Hunter (descubrir) → FullEnrich (email + teléfono)
    5. score + export

Se saltan describe (Haiku) e icp (Sonnet), que requieren ANTHROPIC_API_KEY.
Llama a los módulos directamente para evitar el gate del CLI (que exige las 4
claves) y para no importar la capa del LLM (`llm.py`).

Uso:
    python run_sin_claude.py --rubro logistica --max-total 50
    python run_sin_claude.py --rubro logistica --comuna "Pudahuel, Santiago"
"""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

import requests

from leadgen import config, discovery, enrich, export, score
from leadgen.models import Empresa


def _normalizar(nombre: str) -> str:
    return re.sub(r"\s+", " ", nombre.lower()).strip()


def deduplicar(empresas: list[Empresa]) -> list[Empresa]:
    """Quita empresas repetidas por dominio o nombre (igual que pipeline.deduplicar)."""
    vistas: set[str] = set()
    unicas: list[Empresa] = []
    for e in empresas:
        clave = e.dominio or _normalizar(e.nombre)
        if clave not in vistas:
            vistas.add(clave)
            unicas.append(e)
    return unicas


def hunter_estado() -> tuple[bool, str]:
    """Comprueba si Hunter domain-search está operativo (sin gastar crédito si está
    restringido: una cuenta restringida responde 429 antes de cobrar).

    Devuelve (disponible, motivo).
    """
    if not config.HUNTER_API_KEY:
        return False, "sin HUNTER_API_KEY"
    try:
        r = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": "hunter.io", "api_key": config.HUNTER_API_KEY, "limit": 1},
            timeout=20,
        )
    except requests.RequestException as e:
        return False, f"error de red ({type(e).__name__})"
    if r.status_code == 200:
        return True, "ok"
    try:
        errores = r.json().get("errors", [])
        motivo = errores[0].get("id") or errores[0].get("details") if errores else f"HTTP {r.status_code}"
    except Exception:
        motivo = f"HTTP {r.status_code}"
    return False, str(motivo)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline parcial (descubrimiento + contactos) sin fases de Claude"
    )
    parser.add_argument("--rubro", default="logistica", help=f"Rubro: {', '.join(config.RUBROS)}")
    parser.add_argument(
        "--comuna", action="append", dest="comunas",
        help="Comuna (repetible). Por defecto: config.COMUNAS_DEFAULT.",
    )
    parser.add_argument("--max-total", type=int, default=50, help="Tope total de empresas únicas")
    parser.add_argument("--por-comuna", type=int, default=15, help="Máx. empresas a pedir por comuna")
    parser.add_argument("--top-contactos", type=int, default=3, help="Máx. contactos a enriquecer por empresa")
    parser.add_argument("--salida", default=None, help="Ruta del CSV de salida")
    args = parser.parse_args()

    if not config.GOOGLE_PLACES_API_KEY:
        print("✗ Falta GOOGLE_PLACES_API_KEY en .env. Abortando.")
        return

    rubro_nombre, rubro_query = config.resolver_rubro(args.rubro)
    comunas = args.comunas or config.COMUNAS_DEFAULT

    # ── Fase 1: descubrimiento ────────────────────────────────────────────────
    print(f"[1/3] Descubriendo '{rubro_nombre}' en {len(comunas)} comunas (Google Places)...")
    empresas: list[Empresa] = []
    for comuna in comunas:
        if len(deduplicar(empresas)) >= args.max_total:
            break
        try:
            encontradas = discovery.buscar_empresas(rubro_query, comuna, rubro_nombre, args.por_comuna)
        except Exception as e:
            print(f"    {comuna}: ✗ error de descubrimiento ({type(e).__name__}: {e})")
            continue
        empresas.extend(encontradas)
        print(f"    {comuna}: {len(encontradas)} empresas")
    empresas = deduplicar(empresas)[: args.max_total]
    print(f"    Total único: {len(empresas)} empresas")

    # ── Fase 3: contactos (Hunter → FullEnrich) ───────────────────────────────
    hunter_ok, motivo = hunter_estado()
    fe_ok = bool(config.FULLENRICH_API_KEY)
    if not hunter_ok:
        print(
            f"[2/3] Hunter NO disponible ({motivo}); se omite el descubrimiento de "
            f"contactos. Se exportan los datos de Google (incl. teléfono cuando exista)."
        )
    else:
        print(f"[2/3] Descubriendo y enriqueciendo contactos (Hunter ok; FullEnrich={'ok' if fe_ok else 'off'})...")
        for i, e in enumerate(empresas, 1):
            if not e.dominio:
                continue
            try:
                enrich.enriquecer_empresa(e, top_contactos=args.top_contactos)
            except Exception as ex:
                # No abortar el lote por un fallo puntual (timeout, import, API, etc.).
                print(f"    [{i}/{len(empresas)}] {e.nombre[:40]}: ✗ {type(ex).__name__}: {ex}")
                continue
            c = e.contacto_principal
            if c and (c.email or c.telefono):
                print(f"    [{i}/{len(empresas)}] {e.nombre[:40]}: {c.email or '—'} | {c.telefono or '—'}")

    # ── Fase 5: scoring + orden + export ──────────────────────────────────────
    print("[3/3] Calculando score, ordenando y exportando...")
    for e in empresas:
        score.score(e)
    empresas.sort(key=lambda e: e.score, reverse=True)

    salida = Path(args.salida) if args.salida else Path(f"leads-{args.rubro}-{date.today().isoformat()}.csv")
    export.a_csv(empresas, salida)

    con_email = sum(1 for e in empresas if e.contacto_principal and e.contacto_principal.email)
    con_tel = sum(
        1 for e in empresas
        if (e.contacto_principal and e.contacto_principal.telefono) or e.telefono
    )
    print(f"\n✅  {len(empresas)} leads guardados en: {salida}")
    print("\n  Resumen:")
    print(f"    Empresas      : {len(empresas)}")
    print(f"    Con email     : {con_email}")
    print(f"    Con teléfono  : {con_tel}")
    print("\n  Top 5:")
    for e in empresas[:5]:
        c = e.contacto_principal
        contacto = f"{c.nombre} — {c.cargo}" if c and c.nombre else "sin contacto"
        tel = (c.telefono if c and c.telefono else e.telefono) or "—"
        print(f"    [{e.score:>3}] {e.nombre[:32]:<32} | tel {tel:<16} | {contacto}")


if __name__ == "__main__":
    main()
