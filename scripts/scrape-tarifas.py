#!/usr/bin/env python3
"""Rate shopping de tarifas PÚBLICAS (vista de cliente) en Booking.com y Expedia.

Sin login, sin extranet: navega la página pública del hotel con Playwright y captura la
tarifa que vería un huésped, para las fechas/ocupaciones de config/tarifas-publicas.yaml.
Escribe un CSV en reports/YYYY-MM-DD-tarifas.csv.

USO RESPONSABLE: estos sitios tienen detección de automatización (captcha, bloqueos,
límites de tasa). El script respeta las pausas configuradas y, si detecta bloqueo, marca
la fila como 'bloqueado' y continúa. Úsalo a baja frecuencia y conforme a los términos de
cada sitio. Es para monitoreo legítimo de tarifas propias/de mercado.

Dependencias: playwright (+ 'playwright install chromium'), PyYAML.

Uso:
    python scripts/scrape-tarifas.py
    python scripts/scrape-tarifas.py --config config/tarifas-publicas.yaml --salida reports
    python scripts/scrape-tarifas.py --headful   # ver el navegador (debug)
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("Falta 'PyYAML'. Instala con: pip install -r scripts/requirements.txt")

try:
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sys.exit(
        "Falta 'playwright'. Instala con: pip install -r scripts/requirements.txt && "
        "playwright install chromium"
    )

TZ = ZoneInfo("America/Santiago")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
CAMPOS = [
    "plataforma", "hotel", "propio", "check_in", "check_out",
    "ocupacion", "habitacion", "tarifa", "moneda", "url", "estado",
]


def _sep(url: str) -> str:
    return "&" if "?" in url else "?"


def url_booking(base: str, ci: date, co: date, ad: int, ni: int, hab: int) -> str:
    p = (
        f"checkin={ci:%Y-%m-%d}&checkout={co:%Y-%m-%d}"
        f"&group_adults={ad}&group_children={ni}&no_rooms={hab}"
    )
    return base + _sep(base) + p


def url_expedia(base: str, ci: date, co: date, ad: int, ni: int, hab: int) -> str:
    # Expedia acepta chkin/chkout en la URL de información del hotel.
    p = f"chkin={ci:%Y-%m-%d}&chkout={co:%Y-%m-%d}&adults={ad}&rooms={hab}"
    return base + _sep(base) + p


# Selectores best-effort. Los sitios cambian su DOM con frecuencia: si dejan de
# funcionar, hay que actualizar esta lista (revisar con --headful).
SELECTORES_PRECIO = {
    "booking": [
        "[data-testid='price-and-discounted-price']",
        "span.prco-valign-middle-helper",
        ".bui-price-display__value",
    ],
    "expedia": [
        "[data-test-id='price-summary'] .uitk-text",
        "div[data-stid='price-summary'] span",
        ".uitk-type-500",
    ],
}
PATRON_PRECIO = re.compile(r"[\d][\d.,]{2,}")
SENALES_BLOQUEO = ("captcha", "are you a robot", "unusual traffic", "verifica que eres")


def extraer_precio(page, plataforma: str) -> str | None:
    for sel in SELECTORES_PRECIO.get(plataforma, []):
        try:
            el = page.query_selector(sel)
            if el:
                txt = (el.inner_text() or "").strip()
                m = PATRON_PRECIO.search(txt)
                if m:
                    return m.group(0)
        except Exception:
            continue
    return None


def es_bloqueo(page) -> bool:
    try:
        cuerpo = (page.inner_text("body") or "").lower()
    except Exception:
        return False
    return any(s in cuerpo for s in SENALES_BLOQUEO)


def consultar(page, plataforma: str, url: str, pausa: int, reintentos: int) -> tuple[str, str]:
    """Devuelve (tarifa, estado). estado ∈ {ok, sin_precio, bloqueado, error, timeout}."""
    for intento in range(reintentos + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)  # dejar que cargue precio (JS)
            if es_bloqueo(page):
                return "", "bloqueado"
            precio = extraer_precio(page, plataforma)
            if precio:
                return precio, "ok"
            if intento < reintentos:
                time.sleep(pausa)
                continue
            return "", "sin_precio"
        except PWTimeout:
            if intento < reintentos:
                time.sleep(pausa)
                continue
            return "", "timeout"
        except Exception:
            if intento < reintentos:
                time.sleep(pausa)
                continue
            return "", "error"
    return "", "error"


def cargar_config(ruta: Path) -> dict:
    if not ruta.is_file():
        sys.exit(f"No se encontró el archivo de config: {ruta}")
    data = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    if not data.get("hoteles"):
        sys.exit(
            f"'{ruta}' no tiene hoteles configurados. Descomenta/agrega entradas en "
            "'hoteles:' antes de ejecutar."
        )
    return data


def construir_filas(cfg: dict) -> list[dict]:
    """Expande la matriz hoteles × plataformas × fechas × ocupaciones."""
    c = cfg.get("consulta", {})
    moneda = c.get("moneda", "CLP")
    offsets = c.get("offsets_dias", [7])
    noches = int(c.get("noches", 1))
    ocupaciones = c.get("ocupaciones", [{"adultos": 2, "ninos": 0, "habitaciones": 1}])
    hoy = datetime.now(TZ).date()

    builders = {"booking": url_booking, "expedia": url_expedia}
    filas = []
    for hotel in cfg["hoteles"]:
        for plataforma, base in (hotel.get("plataformas") or {}).items():
            if not base or plataforma not in builders:
                continue
            for off in offsets:
                ci = hoy + timedelta(days=int(off))
                co = ci + timedelta(days=noches)
                for ocu in ocupaciones:
                    ad = int(ocu.get("adultos", 2))
                    ni = int(ocu.get("ninos", 0))
                    hab = int(ocu.get("habitaciones", 1))
                    url = builders[plataforma](base, ci, co, ad, ni, hab)
                    filas.append(
                        {
                            "plataforma": plataforma,
                            "hotel": hotel.get("nombre", hotel.get("id", "")),
                            "propio": "si" if hotel.get("propio") else "no",
                            "check_in": f"{ci:%Y-%m-%d}",
                            "check_out": f"{co:%Y-%m-%d}",
                            "ocupacion": f"{ad}A{ni}N x{hab}",
                            "habitacion": "",
                            "tarifa": "",
                            "moneda": moneda,
                            "url": url,
                            "estado": "",
                        }
                    )
    return filas


def main() -> None:
    parser = argparse.ArgumentParser(description="Rate shopping público Booking/Expedia.")
    parser.add_argument("--config", default="config/tarifas-publicas.yaml")
    parser.add_argument("--salida", default="reports", help="Carpeta de salida.")
    parser.add_argument("--headful", action="store_true", help="Mostrar el navegador.")
    args = parser.parse_args()

    cfg = cargar_config(Path(args.config))
    pausa = int(cfg.get("consulta", {}).get("pausa_segundos", 8))
    reintentos = int(cfg.get("consulta", {}).get("reintentos", 2))
    filas = construir_filas(cfg)
    if not filas:
        sys.exit("No hay consultas que ejecutar (revisa URLs por plataforma en la config).")

    print(f"Consultas a realizar: {len(filas)} (pausa {pausa}s entre cada una)")
    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=not args.headful)
        ctx = navegador.new_context(
            user_agent=UA,
            locale=cfg.get("consulta", {}).get("idioma", "es-CL"),
        )
        page = ctx.new_page()
        for i, fila in enumerate(filas, 1):
            tarifa, estado = consultar(page, fila["plataforma"], fila["url"], pausa, reintentos)
            fila["tarifa"], fila["estado"] = tarifa, estado
            marca = tarifa or estado
            print(f"  [{i}/{len(filas)}] {fila['plataforma']:8} {fila['hotel'][:30]:30} "
                  f"{fila['check_in']} -> {marca}")
            if i < len(filas):
                time.sleep(pausa)
        navegador.close()

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    hoy = datetime.now(TZ).date()
    destino = salida / f"{hoy:%Y-%m-%d}-tarifas.csv"
    with destino.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)
    ok = sum(1 for x in filas if x["estado"] == "ok")
    print(f"\nListo: {ok}/{len(filas)} con tarifa. CSV → {destino}")


if __name__ == "__main__":
    main()
