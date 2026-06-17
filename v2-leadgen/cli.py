#!/usr/bin/env python3
"""CLI de la v2 — corridas masivas de generación de leads.

Uso:
    python cli.py --rubro logistica --comuna "Pudahuel, Santiago" --max 50 \
        --clientes clients/clientes.csv

    python cli.py --rubro ecommerce            # usa las comunas por defecto
    python cli.py --rubro logistica --sin-icp  # sin calificación (no necesita clientes)

Requisitos: copiar .env.example a .env y completar las claves de API.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from leadgen import config, export
from leadgen.pipeline import generar_leads


def main() -> None:
    parser = argparse.ArgumentParser(description="Generador de leads v2 (herramientas de pago)")
    parser.add_argument("--rubro", required=True, help=f"Rubro: {', '.join(config.RUBROS)}")
    parser.add_argument(
        "--comuna",
        action="append",
        dest="comunas",
        help="Comuna a buscar (repetible). Por defecto: las de config.COMUNAS_DEFAULT.",
    )
    parser.add_argument("--max", type=int, default=config.DEFAULT_MAX, help="Máx. empresas por comuna")
    parser.add_argument("--clientes", default=None, help="CSV de clientes para construir el ICP")
    parser.add_argument("--sin-icp", action="store_true", help="No calificar contra el ICP")
    parser.add_argument("--salida", default=None, help="Ruta del CSV de salida")
    parser.add_argument("--excel", action="store_true", help="Exportar también a .xlsx")
    args = parser.parse_args()

    faltan = config.claves_faltantes()
    if faltan:
        print("⚠️  Faltan claves de API en .env:")
        for k in faltan:
            print(f"    - {k.name}  ({k.why})")
        print("Copia .env.example a .env y complétalas. Abortando.\n")
        return

    clientes_csv = None if args.sin_icp else args.clientes

    try:
        leads = generar_leads(
            rubro_slug=args.rubro,
            comunas=args.comunas,
            max_por_comuna=args.max,
            clientes_csv=clientes_csv,
        )
    except ValueError as e:
        print(f"✗ {e}")
        return

    salida = Path(args.salida) if args.salida else Path(f"leads-{args.rubro}-{date.today().isoformat()}.csv")
    export.a_csv(leads, salida)
    print(f"\n✅  {len(leads)} leads guardados en: {salida}")
    if args.excel:
        xlsx = salida.with_suffix(".xlsx")
        export.a_excel(leads, xlsx)
        print(f"    Excel: {xlsx}")

    con_email = sum(1 for e in leads if e.contacto_principal and e.contacto_principal.email)
    encajan = sum(1 for e in leads if e.ajuste_icp == "si")
    print("\n  Resumen:")
    print(f"    Con email     : {con_email}")
    print(f"    Encajan (ICP) : {encajan}")
    print("\n  Top 5:")
    for e in leads[:5]:
        c = e.contacto_principal
        contacto = f"{c.nombre} — {c.cargo}" if c and c.nombre else "sin contacto"
        print(f"    [{e.score:>3}] {e.nombre[:35]:<35} | {e.ajuste_icp or '-':<6} | {contacto}")


if __name__ == "__main__":
    main()
