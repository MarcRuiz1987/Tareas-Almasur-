#!/usr/bin/env python3
"""
Scraping de empresas logísticas en Google Maps
Genera CSV con: nombre, teléfono, dirección, calificación, reseñas, sitio web, link Maps

Uso:
    python scrape_leads_logistica.py
    python scrape_leads_logistica.py --ciudad "Montevideo" --max 30

Requisitos:
    uv pip install "scrapling[all]"
    scrapling install
"""

import csv
import re
import time
import argparse
from pathlib import Path
from scrapling.fetchers import StealthyFetcher, StealthySession

# ─── Configuración ───────────────────────────────────────────────────────────

DEFAULT_CIUDAD = "Santiago de Chile"
DEFAULT_MAX    = 50
MIN_RESENAS    = 3

MAPS_BASE = "https://www.google.com/maps/search/"

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _safe_text(el):
    return el.text.strip() if el else ""

def _safe_attr(el, attr):
    return (el.attrib.get(attr) or "").strip() if el else ""

def _clean_phone(raw: str) -> str:
    raw = re.sub(r"[Tt]el[eé]fono[:\s]*", "", raw, flags=re.I)
    raw = re.sub(r"[Pp]hone[:\s]*", "", raw)
    raw = re.sub(r"[^+\d\s\-\(\)]", "", raw)
    return raw.strip()

def _clean_reviews(raw: str) -> int:
    nums = re.sub(r"[^\d]", "", raw)
    return int(nums) if nums else 0

def _output_path(ciudad: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", ciudad.lower()).strip("-")
    filename = f"leads-operaciones-logistica-{slug}.csv"
    return Path.home() / "Desktop" / filename

# ─── Acciones de página (Playwright) ─────────────────────────────────────────

def _action_scroll_and_collect(urls_out: list, target: int = 70):
    """
    page_action para la página de búsqueda de Google Maps.
    Acepta cookies, hace scroll en el feed y recoge las URLs de fichas.
    """
    def action(page):
        page.wait_for_timeout(2500)

        # Aceptar consentimiento de cookies / RGPD
        consent_texts = ["Aceptar todo", "Accept all", "Aceitar tudo", "Tout accepter"]
        for text in consent_texts:
            try:
                btn = page.get_by_text(text, exact=True).first
                btn.click(timeout=1500)
                page.wait_for_timeout(1000)
                break
            except Exception:
                pass

        # Cerrar posibles diálogos extra
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        except Exception:
            pass

        # Scroll del feed de resultados para cargar ≥ target fichas
        for i in range(20):
            try:
                feed = page.locator('div[role="feed"]')
                if feed.count() == 0:
                    break
                feed.evaluate("(el) => el.scrollBy(0, 900)")
                page.wait_for_timeout(1600)

                links = page.locator('a[href*="/maps/place/"]').all()
                current_urls = {lk.get_attribute("href") for lk in links
                                if (lk.get_attribute("href") or "").startswith("http")}
                if len(current_urls) >= target:
                    break
            except Exception:
                pass

        # Recopilar URLs únicas
        links = page.locator('a[href*="/maps/place/"]').all()
        seen = set()
        for lk in links:
            href = lk.get_attribute("href") or ""
            if "/maps/place/" in href and href not in seen:
                seen.add(href)
                urls_out.append(href)

        print(f"  → {len(urls_out)} fichas encontradas en el panel")

    return action


def _action_extract_detail(storage: dict):
    """
    page_action para la ficha individual de un negocio.
    Extrae teléfono y sitio web antes de que Scrapling capture el HTML.
    """
    def action(page):
        page.wait_for_timeout(2000)
        storage["final_url"] = page.url

        # ── Teléfono ──────────────────────────────────────────────────────
        phone_selectors = [
            '[data-item-id*="phone"]',
            'button[aria-label*="Teléfono"]',
            'button[aria-label*="Phone"]',
            '[data-tooltip*="Copiar número"]',
        ]
        for sel in phone_selectors:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    label = el.get_attribute("aria-label") or ""
                    if not label:
                        label = el.inner_text()
                    phone = _clean_phone(label)
                    if re.search(r"\d{5,}", phone):
                        storage["telefono"] = phone
                        break
            except Exception:
                pass

        # ── Sitio web ─────────────────────────────────────────────────────
        web_selectors = [
            'a[data-item-id="authority"]',
            'a[aria-label*="Sitio web"]',
            'a[aria-label*="Website"]',
        ]
        for sel in web_selectors:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    storage["sitio_web"] = el.get_attribute("href") or ""
                    break
            except Exception:
                pass

    return action

# ─── Parseo del HTML (Scrapling) ──────────────────────────────────────────────

def _parse_detail_page(page_html, storage: dict) -> dict:
    """Extrae campos de la ficha de negocio ya cargada."""
    record = {
        "nombre":       "",
        "telefono":     storage.get("telefono", ""),
        "direccion":    "",
        "calificacion": "",
        "resenas":      0,
        "sitio_web":    storage.get("sitio_web", ""),
        "maps_url":     storage.get("final_url", ""),
    }

    # Nombre
    for sel in ["h1.DUwDvf", "h1[data-attrid='title']", "h1"]:
        el = page_html.css_first(sel)
        if el:
            record["nombre"] = el.text.strip()
            break

    # Calificación  (buscar patrón "4.3" o "4,3")
    for sel in [
        "div.F7nice span[aria-hidden='true']",
        "span.MW4etd",
        "span[aria-hidden='true']",
    ]:
        el = page_html.css_first(sel)
        if el:
            t = el.text.strip()
            if re.match(r"^\d[,\.]\d$", t):
                record["calificacion"] = t.replace(",", ".")
                break

    # Reseñas  (buscar el span con aria-label que contenga "reseña" o un número entre paréntesis)
    for sel in [
        "div.F7nice span[aria-label]",
        "button[jsaction*='pane.rating'] span[aria-label]",
        "span[aria-label*='reseña']",
        "span[aria-label*='review']",
    ]:
        el = page_html.css_first(sel)
        if el:
            label = _safe_attr(el, "aria-label") or el.text
            n = _clean_reviews(label)
            if n > 0:
                record["resenas"] = n
                break

    # Si no encontramos reseñas con aria-label, buscar el texto "(1.234)"
    if record["resenas"] == 0:
        for el in page_html.css("span"):
            m = re.search(r"\((\d[\d\.,]+)\)", el.text or "")
            if m:
                n = _clean_reviews(m.group(1))
                if n > 0:
                    record["resenas"] = n
                    break

    # Dirección
    for sel in [
        'button[data-item-id*="address"] span.Io6YTe',
        'button[data-item-id*="laddr"] span',
        '[data-item-id*="address"]',
    ]:
        el = page_html.css_first(sel)
        if el:
            addr = el.text.strip()
            if len(addr) > 5:
                record["direccion"] = addr
                break

    return record

# ─── Flujo principal ──────────────────────────────────────────────────────────

def scrape(ciudad: str, max_leads: int) -> list:
    query = f"empresas logísticas {ciudad}"
    search_url = MAPS_BASE + query.replace(" ", "+")

    print(f"\n{'='*60}")
    print(f"  Scrapling — Leads logística")
    print(f"  Ciudad  : {ciudad}")
    print(f"  Objetivo: {max_leads} leads (mín. {MIN_RESENAS} reseñas)")
    print(f"{'='*60}\n")

    # ── Paso 1: Recopilar URLs del panel de búsqueda ──────────────────
    print("[1/3] Abriendo Google Maps y cargando resultados...")
    business_urls: list = []

    StealthyFetcher().fetch(
        search_url,
        headless=False,          # visible → puedes resolver CAPTCHA si aparece
        network_idle=True,
        page_action=_action_scroll_and_collect(business_urls, target=max_leads + 25),
        wait=1000,
    )

    if not business_urls:
        print("  ✗ No se encontraron fichas. Verifica la conexión y que Google Maps cargó.")
        return []

    # ── Paso 2: Visitar cada ficha ────────────────────────────────────
    print(f"\n[2/3] Extrayendo detalles de fichas...")
    leads = []

    with StealthySession(headless=False) as session:
        for i, url in enumerate(business_urls[: max_leads * 2], 1):
            storage: dict = {"telefono": "", "sitio_web": "", "final_url": url}
            try:
                detail = session.fetch(
                    url,
                    network_idle=True,
                    page_action=_action_extract_detail(storage),
                    wait=1000,
                )

                record = _parse_detail_page(detail, storage)

                # Filtrar sin nombre o menos reseñas del mínimo
                if not record["nombre"]:
                    print(f"  [{i:>2}] ✗ sin nombre — {url[:55]}")
                    continue
                if record["resenas"] < MIN_RESENAS:
                    print(f"  [{i:>2}] ✗ {record['nombre'][:40]:<40} "
                          f"— {record['resenas']} reseñas (< {MIN_RESENAS})")
                    continue

                leads.append(record)
                print(f"  [{i:>2}] ✓ {record['nombre'][:40]:<40} "
                      f"| {record['calificacion']}★ | {record['resenas']:>5} reseñas "
                      f"| {'📞' if record['telefono'] else '  '} "
                      f"| {'🌐' if record['sitio_web'] else '  '}")

                if len(leads) >= max_leads:
                    print(f"\n  → Objetivo de {max_leads} leads alcanzado.")
                    break

                time.sleep(1.2)   # pausa educada entre requests

            except Exception as e:
                print(f"  [{i:>2}] ✗ Error: {e!s:.80}")
                continue

    return leads


def deduplicate(leads: list) -> list:
    seen = set()
    unique = []
    for lead in leads:
        key = re.sub(r"\s+", " ", lead["nombre"].lower()).strip()
        if key not in seen:
            seen.add(key)
            unique.append(lead)
    return unique


def save_csv(leads: list, ciudad: str) -> Path:
    output = _output_path(ciudad)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Deduplicar y ordenar por reseñas desc
    unique = deduplicate(leads)
    unique.sort(key=lambda x: x["resenas"], reverse=True)

    campos = ["nombre", "telefono", "direccion", "calificacion", "resenas", "sitio_web", "maps_url"]
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(unique)

    return output, unique


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scraping leads logística desde Google Maps")
    parser.add_argument("--ciudad", default=DEFAULT_CIUDAD, help="Ciudad de búsqueda")
    parser.add_argument("--max",    type=int, default=DEFAULT_MAX, help="Máximo de leads")
    args = parser.parse_args()

    leads = scrape(args.ciudad, args.max)
    if not leads:
        print("\n✗ No se obtuvieron leads.")
        return

    output, saved = save_csv(leads, args.ciudad)

    print(f"\n{'='*60}")
    print(f"  ✅  {len(saved)} leads guardados en:")
    print(f"      {output}")
    print(f"{'='*60}")
    print(f"\n  Preview (top 5 por reseñas):")
    for r in saved[:5]:
        print(f"    {r['nombre'][:38]:<38} | {r['calificacion']}★ "
              f"| {r['resenas']:>5} reseñas | {r['telefono']}")


if __name__ == "__main__":
    main()
