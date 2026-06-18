#!/usr/bin/env python3
"""CLI de la v3 — completar (enriquecer) una planilla de empresas existente.

Uso:
    # completar todo (RUT + web + contactos) sobre una planilla del SEIA
    python cli.py --entrada gtc_leads.xlsx --salida gtc_leads_completa.xlsx

    # sólo algunos grupos de campos
    python cli.py --entrada empresas.xlsx --campos web,contactos

    # probar con las primeras 10 filas
    python cli.py --entrada empresas.xlsx --limite 10

Requisitos: copiar .env.example a .env y completar las claves de API que uses.
La planilla debe tener al menos una columna de empresa ("Empresa" / "Nombre" /
"Razón social"); las columnas que falten se crean automáticamente.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from planilla import config
from planilla.completar import completar_planilla

_DIR = Path(__file__).resolve().parent


def asegurar_env() -> bool:
    """Crea .env desde .env.example la primera vez. Devuelve True si lo acaba de crear."""
    env = _DIR / ".env"
    ejemplo = _DIR / ".env.example"
    if env.exists() or not ejemplo.exists():
        return False
    shutil.copy(ejemplo, env)
    print(f"📝  Creé el archivo de claves: {env}")
    print("    Ábrelo, pega tus claves (al menos GOOGLE_PLACES_API_KEY y HUNTER_API_KEY)")
    print("    y vuelve a correr este comando.\n")
    return True


def main() -> None:
    if asegurar_env():
        return

    parser = argparse.ArgumentParser(description="Completar datos de una planilla de empresas (v3)")
    parser.add_argument("--entrada", required=True, help="Planilla de entrada (.xlsx o .csv)")
    parser.add_argument("--salida", default=None, help="Planilla de salida (por defecto: <entrada>_completa.xlsx)")
    parser.add_argument(
        "--campos",
        default="web,contactos",
        help="Grupos a completar, separados por coma: web, contactos, rut (por defecto: web,contactos)",
    )
    parser.add_argument("--limite", type=int, default=None, help="Máx. de filas a procesar")
    parser.add_argument("--sobrescribir", action="store_true", help="Reemplazar también celdas ya llenas")
    args = parser.parse_args()

    campos = {c.strip().lower() for c in args.campos.split(",") if c.strip()}
    desconocidos = campos - set(config.GRUPOS_CAMPOS)
    if desconocidos:
        print(f"✗ Campos desconocidos: {', '.join(desconocidos)}. Opciones: {', '.join(config.GRUPOS_CAMPOS)}")
        return

    avisos = config.avisos_de_claves(campos)
    if avisos:
        print("⚠️  Faltan claves en .env para algunos campos pedidos:")
        for k in avisos:
            print(f"    - {k.name}  ({k.why})")
        print("    Esos campos quedarán vacíos. Continúa de todos modos...\n")

    salida = Path(args.salida) if args.salida else Path(args.entrada).with_name(
        Path(args.entrada).stem + "_completa.xlsx"
    )

    try:
        res = completar_planilla(
            entrada=args.entrada,
            salida=salida,
            campos=campos,
            limite=args.limite,
            sobrescribir=args.sobrescribir,
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"✗ {e}")
        return

    print(f"\n✅  Planilla completada: {salida}")
    print("\n  Resumen (cobertura final):")
    print(f"    Filas procesadas : {res.filas}")
    print(f"    Celdas escritas  : {res.celdas_escritas}")
    print(f"    Con RUT          : {res.con_rut}")
    print(f"    Con web/dominio  : {res.con_web}")
    print(f"    Con contacto     : {res.con_contacto}")


if __name__ == "__main__":
    main()
