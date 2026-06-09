#!/usr/bin/env python3
"""
Generador de leads para Procentro — bodegas Santiago de Chile
Busca empresas en Google Maps (7 rubros) + enriquece con email y contacto nominado

Uso:
    python procentro_leads.py                        # todos los rubros, 50 leads c/u
    python procentro_leads.py --max 30               # 30 leads por rubro
    python procentro_leads.py --rubro logistica      # solo un rubro
    python procentro_leads.py --solo-empresas        # sin enriquecimiento (más rápido)
    python procentro_leads.py --sin-linkedin         # solo enriquecer desde web

Requisitos:
    uv pip install "scrapling[all]"
    scrapling install
"""

import csv
import re
import time
import argparse
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

from scrapling.fetchers import Fetcher, StealthyFetcher, StealthySession

# ─── Rubros objetivo de Procentro ────────────────────────────────────────────

RUBROS = [
    ("Logística",        "empresa logística Santiago Chile"),
    ("E-commerce",       "ecommerce tienda online bodega Santiago"),
    ("Distribución",     "distribuidora Santiago Chile"),
    ("Importadores",     "importadora Santiago Chile"),
    ("Manufactura",      "manufactura liviana Santiago Chile"),
    ("Exportadores",     "exportadora Santiago Chile"),
    ("Serv. Técnicos",   "servicios técnicos industriales Santiago"),
]

RUBRO_SLUGS = {
    "logistica":     "Logística",
    "ecommerce":     "E-commerce",
    "distribucion":  "Distribución",
    "importadores":  "Importadores",
    "manufactura":   "Manufactura",
    "exportadores":  "Exportadores",
    "tecnicos":      "Serv. Técnicos",
}

# ─── Configuración ───────────────────────────────────────────────────────────

DEFAULT_MAX = 50
MIN_RESENAS = 3
MAPS_BASE   = "https://www.google.com/maps/search/"

CONTACT_PATHS   = ["/contacto", "/contact", "/nosotros", "/equipo", "/about", "/team", "/quienes-somos"]
CARGO_KEYWORDS  = ["gerente", "jefe", "supervisor", "director", "encargado", "manager", "coordinador"]
LINKEDIN_CARGOS = (
    '"gerente de operaciones" OR "jefe de logística" OR '
    '"supervisor de bodega" OR "gerente comercial" OR '
    '"jefe de distribución" OR "gerente de logística" OR '
    '"director de operaciones" OR "jefe de bodega"'
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _clean_phone(raw: str) -> str:
    raw = re.sub(r"[Tt]el[eé]fono[:\s]*|[Pp]hone[:\s]*", "", raw)
    return re.sub(r"[^+\d\s\-\(\)]", "", raw).strip()

def _clean_reviews(raw: str) -> int:
    nums = re.sub(r"[^\d]", "", raw)
    return int(nums) if nums else 0

def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.lower()).strip()

def _output_path() -> Path:
    today = date.today().isoformat()
    return Path.home() / "Desktop" / f"leads-procentro-santiago-{today}.csv"

def _score(lead: dict) -> int:
    s = 0
    if lead.get("nombre_contacto"): s += 35
    if lead.get("email"):           s += 25
    if lead.get("telefono"):        s += 15
    if lead.get("sitio_web"):       s +=  5
    reviews = lead.get("resenas") or 0
    if   reviews >= 50: s += 10
    elif reviews >= 10: s +=  5
    try:
        if float(lead.get("calificacion") or 0) >= 4.0: s += 5
    except (ValueError, TypeError):
        pass
    return s

# ─── Fase 1 — Google Maps ─────────────────────────────────────────────────────

def _action_scroll_and_collect(urls_out: list, target: int):
    """page_action: acepta cookies, scroll del feed, recolecta URLs de fichas."""
    def action(page):
        page.wait_for_timeout(2500)

        for text in ["Aceptar todo", "Accept all", "Aceitar tudo", "Tout accepter"]:
            try:
                page.get_by_text(text, exact=True).first.click(timeout=1500)
                page.wait_for_timeout(800)
                break
            except Exception:
                pass
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
        except Exception:
            pass

        for _ in range(20):
            try:
                feed = page.locator('div[role="feed"]')
                if feed.count() == 0:
                    break
                feed.evaluate("(el) => el.scrollBy(0, 900)")
                page.wait_for_timeout(1500)
                count = sum(
                    1 for lk in page.locator('a[href*="/maps/place/"]').all()
                    if "/maps/place/" in (lk.get_attribute("href") or "")
                )
                if count >= target:
                    break
            except Exception:
                pass

        seen: set = set()
        for lk in page.locator('a[href*="/maps/place/"]').all():
            href = lk.get_attribute("href") or ""
            if "/maps/place/" in href and href not in seen:
                seen.add(href)
                urls_out.append(href)
        print(f"    → {len(urls_out)} fichas cargadas")

    return action


def _action_extract_detail(storage: dict):
    """page_action: extrae teléfono y sitio web desde la ficha abierta."""
    def action(page):
        page.wait_for_timeout(2000)
        storage["final_url"] = page.url

        for sel in ['[data-item-id*="phone"]', 'button[aria-label*="Teléfono"]', 'button[aria-label*="Phone"]']:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    label = el.get_attribute("aria-label") or el.inner_text()
                    phone = _clean_phone(label)
                    if re.search(r"\d{5,}", phone):
                        storage["telefono"] = phone
                        break
            except Exception:
                pass

        for sel in ['a[data-item-id="authority"]', 'a[aria-label*="Sitio web"]', 'a[aria-label*="Website"]']:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    storage["sitio_web"] = el.get_attribute("href") or ""
                    break
            except Exception:
                pass

    return action


def _parse_detail(html, storage: dict, rubro: str) -> dict:
    record = {
        "nombre_empresa":   "",
        "rubro":            rubro,
        "nombre_contacto":  "",
        "cargo_contacto":   "",
        "telefono":         storage.get("telefono", ""),
        "email":            "",
        "direccion":        "",
        "calificacion":     "",
        "resenas":          0,
        "sitio_web":        storage.get("sitio_web", ""),
        "maps_url":         storage.get("final_url", ""),
        "score":            0,
    }

    for sel in ["h1.DUwDvf", "h1"]:
        el = html.css_first(sel)
        if el and el.text.strip():
            record["nombre_empresa"] = el.text.strip()
            break

    for sel in ["div.F7nice span[aria-hidden='true']", "span.MW4etd"]:
        el = html.css_first(sel)
        if el:
            t = el.text.strip()
            if re.match(r"^\d[,\.]\d$", t):
                record["calificacion"] = t.replace(",", ".")
                break

    for sel in ["div.F7nice span[aria-label]", "span[aria-label*='reseña']", "span[aria-label*='review']"]:
        el = html.css_first(sel)
        if el:
            n = _clean_reviews((el.attrib.get("aria-label") or "") + (el.text or ""))
            if n > 0:
                record["resenas"] = n
                break
    if record["resenas"] == 0:
        for el in html.css("span"):
            m = re.search(r"\((\d[\d\.,]+)\)", el.text or "")
            if m:
                n = _clean_reviews(m.group(1))
                if n > 0:
                    record["resenas"] = n
                    break

    for sel in ['button[data-item-id*="address"] span.Io6YTe', 'button[data-item-id*="laddr"] span']:
        el = html.css_first(sel)
        if el and len(el.text.strip()) > 5:
            record["direccion"] = el.text.strip()
            break

    return record


def scrape_maps_rubro(rubro_name: str, query: str, max_leads: int) -> list:
    print(f"\n  [{rubro_name}] Buscando en Google Maps...")
    url = MAPS_BASE + quote_plus(query)
    urls: list = []

    try:
        StealthyFetcher().fetch(
            url,
            headless=False,
            network_idle=True,
            page_action=_action_scroll_and_collect(urls, target=max_leads + 20),
            wait=2,
        )
    except Exception as e:
        print(f"    ✗ Error al cargar Maps: {e}")
        return []

    leads = []
    with StealthySession(headless=False) as session:
        for i, biz_url in enumerate(urls[: max_leads * 2], 1):
            storage: dict = {"telefono": "", "sitio_web": "", "final_url": biz_url}
            try:
                detail = session.fetch(
                    biz_url,
                    network_idle=True,
                    page_action=_action_extract_detail(storage),
                    wait=2,
                )
                record = _parse_detail(detail, storage, rubro_name)

                if not record["nombre_empresa"]:
                    continue
                if record["resenas"] < MIN_RESENAS:
                    continue

                leads.append(record)
                print(f"    [{i:>2}] ✓ {record['nombre_empresa'][:45]:<45} "
                      f"{record['calificacion']}★ ({record['resenas']} reseñas)")

                if len(leads) >= max_leads:
                    break
                time.sleep(1.0)

            except Exception as e:
                print(f"    [{i:>2}] ✗ {e!s:.70}")
                continue

    return leads

# ─── Fase 2A — Enriquecimiento desde sitio web ───────────────────────────────

def _extract_contact_from_html(html) -> tuple[str, str, str]:
    """Retorna (email, nombre_contacto, cargo) desde el HTML de una página."""
    email = nombre = cargo = ""

    for el in html.css('a[href^="mailto:"]'):
        addr = el.attrib.get("href", "").replace("mailto:", "").split("?")[0].strip()
        if EMAIL_RE.match(addr) and "noreply" not in addr and "example" not in addr:
            email = addr
            break

    if not email:
        for el in html.css("p, span, li, td"):
            m = EMAIL_RE.search(el.text or "")
            if m and "noreply" not in m.group() and "example" not in m.group():
                email = m.group()
                break

    full_text = html.text or ""
    for kw in CARGO_KEYWORDS:
        pattern = (
            rf"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){{1,3}})"
            rf"\s*[,\-–]?\s*({kw}[a-záéíóúñ\s]{{2,30}})"
        )
        m = re.search(pattern, full_text, re.IGNORECASE)
        if m:
            nombre = m.group(1).strip()
            cargo  = m.group(2).strip().title()
            break

    return email, nombre, cargo


def enrich_from_website(website: str) -> dict:
    result = {"email": "", "nombre_contacto": "", "cargo_contacto": ""}
    if not website:
        return result

    fetcher = Fetcher()
    pages_to_try = [website] + [website.rstrip("/") + p for p in CONTACT_PATHS]

    for url in pages_to_try:
        try:
            page = fetcher.get(url, timeout=10)
            if not page or page.status not in (200,):
                continue
            email, nombre, cargo = _extract_contact_from_html(page)
            if email and not result["email"]:
                result["email"] = email
            if nombre and not result["nombre_contacto"]:
                result["nombre_contacto"] = nombre
                result["cargo_contacto"]  = cargo
            if result["email"] and result["nombre_contacto"]:
                break
            time.sleep(0.4)
        except Exception:
            continue

    return result

# ─── Fase 2B — Contacto nominado vía Google → LinkedIn ───────────────────────

def find_linkedin_contact(empresa: str) -> tuple[str, str]:
    """
    Busca en Google perfiles LinkedIn públicos del personal de la empresa.
    No requiere cuenta LinkedIn.
    Retorna (nombre, cargo) o ("", "").
    """
    query = f'site:linkedin.com/in "{empresa}" ({LINKEDIN_CARGOS}) Chile'
    url   = "https://www.google.com/search?q=" + quote_plus(query)

    try:
        page = Fetcher().get(url, timeout=15)
        if not page or page.status != 200:
            return "", ""

        for el in page.css("h3"):
            text = el.text.strip()
            m = re.match(
                r"^([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})"
                r"\s*[\-–|]\s*(.+?)(?:\s*[\|]|\s*-\s*LinkedIn)",
                text, re.IGNORECASE,
            )
            if m:
                nombre = m.group(1).strip()
                cargo  = m.group(2).strip()
                if any(kw in cargo.lower() for kw in CARGO_KEYWORDS):
                    return nombre, cargo

    except Exception:
        pass

    return "", ""

# ─── Dedup + Scoring + CSV ────────────────────────────────────────────────────

def deduplicate(leads: list) -> list:
    seen: set = set()
    unique = []
    for lead in leads:
        key = _normalize(lead["nombre_empresa"])
        if key not in seen:
            seen.add(key)
            unique.append(lead)
    return unique


def save_csv(leads: list) -> Path:
    output = _output_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    campos = [
        "nombre_empresa", "rubro", "nombre_contacto", "cargo_contacto",
        "telefono", "email", "direccion", "calificacion", "resenas",
        "sitio_web", "maps_url", "score",
    ]
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(leads)
    return output

# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generador de leads Procentro")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX,
                        help=f"Leads por rubro (default {DEFAULT_MAX})")
    parser.add_argument("--rubro", type=str, default=None,
                        help=f"Rubro único: {', '.join(RUBRO_SLUGS)}")
    parser.add_argument("--solo-empresas", action="store_true",
                        help="Solo Fase 1 — sin enriquecimiento de contactos")
    parser.add_argument("--sin-linkedin", action="store_true",
                        help="Fase 2A solo — enriquecer desde web, sin buscar LinkedIn")
    args = parser.parse_args()

    rubros = RUBROS
    if args.rubro:
        nombre = RUBRO_SLUGS.get(args.rubro.lower())
        if not nombre:
            print(f"Rubro desconocido: '{args.rubro}'. Opciones: {', '.join(RUBRO_SLUGS)}")
            return
        rubros = [(n, q) for n, q in RUBROS if n == nombre]

    print(f"\n{'='*65}")
    print(f"  Procentro — Generador de Leads")
    print(f"  Rubros  : {', '.join(n for n, _ in rubros)}")
    print(f"  Máximo  : {args.max} leads/rubro  |  mín. {MIN_RESENAS} reseñas")
    modo = "solo empresas" if args.solo_empresas else ("web+linkedin" if not args.sin_linkedin else "solo web")
    print(f"  Modo    : {modo}")
    print(f"{'='*65}\n")

    # ── Fase 1 ────────────────────────────────────────────────────────
    print("[ FASE 1 ] Descubrimiento en Google Maps")
    all_leads: list = []
    for rubro_name, query in rubros:
        leads = scrape_maps_rubro(rubro_name, query, args.max)
        all_leads.extend(leads)
        print(f"  → {len(leads)} leads de [{rubro_name}]")

    all_leads = deduplicate(all_leads)
    print(f"\n  Total único: {len(all_leads)} empresas")

    # ── Fase 2A ───────────────────────────────────────────────────────
    if not args.solo_empresas:
        with_web = [l for l in all_leads if l.get("sitio_web")]
        print(f"\n[ FASE 2A ] Enriquecimiento desde web ({len(with_web)} empresas con sitio)")
        for i, lead in enumerate(with_web, 1):
            enriched = enrich_from_website(lead["sitio_web"])
            lead.update({k: v for k, v in enriched.items() if v})
            found = []
            if lead.get("email"):           found.append("email")
            if lead.get("nombre_contacto"): found.append(lead["nombre_contacto"])
            if found:
                print(f"  [{i:>3}/{len(with_web)}] {lead['nombre_empresa'][:40]:<40} → {', '.join(found)}")

        # ── Fase 2B ───────────────────────────────────────────────────
        if not args.sin_linkedin:
            sin_contacto = [l for l in all_leads if not l.get("nombre_contacto")]
            print(f"\n[ FASE 2B ] LinkedIn vía Google ({len(sin_contacto)} empresas sin contacto)")
            for i, lead in enumerate(sin_contacto, 1):
                nombre, cargo = find_linkedin_contact(lead["nombre_empresa"])
                if nombre:
                    lead["nombre_contacto"] = nombre
                    lead["cargo_contacto"]  = cargo
                    print(f"  [{i:>3}] {lead['nombre_empresa'][:40]:<40} → {nombre} ({cargo})")
                time.sleep(1.5)

    # ── Scoring + export ──────────────────────────────────────────────
    for lead in all_leads:
        lead["score"] = _score(lead)
    all_leads.sort(key=lambda x: x["score"], reverse=True)

    output = save_csv(all_leads)

    con_tel      = sum(1 for l in all_leads if l.get("telefono"))
    con_email    = sum(1 for l in all_leads if l.get("email"))
    con_contacto = sum(1 for l in all_leads if l.get("nombre_contacto"))

    print(f"\n{'='*65}")
    print(f"  ✅  {len(all_leads)} leads guardados en:")
    print(f"      {output}")
    print(f"\n  Resumen de cobertura:")
    print(f"    Con teléfono  : {con_tel}")
    print(f"    Con email     : {con_email}")
    print(f"    Con contacto  : {con_contacto}")
    print(f"{'='*65}")
    print(f"\n  Top 5 leads (score más alto):")
    for r in all_leads[:5]:
        contacto = f"{r['nombre_contacto']} — {r['cargo_contacto']}" if r.get("nombre_contacto") else "sin contacto"
        print(f"    [{r['score']:>3}pts] {r['nombre_empresa'][:35]:<35} | {contacto}")


if __name__ == "__main__":
    main()
