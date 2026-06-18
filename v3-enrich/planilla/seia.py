"""SEIA (Servicio de Evaluación de Impacto Ambiental) → titular + representante legal.

A diferencia de los demás proveedores de la v3 (APIs de pago), el SEIA es un
registro **público y gratuito** de proyectos ambientales en Chile. La ficha de
cada expediente publica los *Antecedentes del titular*: razón social, domicilio,
teléfono y e-mail del **titular** y de su **representante legal**. Para los
listados de proyectos solares (el caso de uso de la v3) eso son contactos
nominados reales sin costo de API.

Flujo (no requiere clave):
  1. Buscar el expediente por titular (o por nombre de proyecto) en el buscador
     público → JSON con el expediente, su comuna, estado y URL de ficha.
  2. Elegir la mejor coincidencia (match exacto de titular; desempate por comuna
     y por presentación más reciente, que suele traer el contacto vigente).
  3. Descargar la ficha y leer las secciones "Titular" y "Representante Legal".

El sitio responde en ISO-8859-1, así que las respuestas se decodifican en latin-1
antes de parsearlas. La función pública es ``buscar``.
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from . import config

_BUSCAR = "https://seia.sea.gob.cl/busqueda/buscarProyectoResumenAction.php"
_ENCODING = "ISO-8859-1"
_UA = "planilla-v3 enriquecimiento de leads (contacto SEIA publico)"

_session = requests.Session()
_session.headers.update({"User-Agent": _UA})


@dataclass
class FichaSEIA:
    """Datos públicos del titular y su representante legal en el SEIA."""

    titular: str = ""
    titular_email: str = ""
    titular_telefono: str = ""
    rep_legal: str = ""
    rep_email: str = ""
    rep_telefono: str = ""
    expediente: str = ""  # URL de la ficha (trazabilidad)
    expediente_nombre: str = ""


def _norm(texto: object) -> str:
    """minúsculas, sin acentos y sin espacios sobrantes — para comparar nombres."""
    s = str(texto or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


# ─── 1. Búsqueda de expedientes ───────────────────────────────────────────────


def _buscar_expedientes(titular: str = "", nombre: str = "", limit: int = 20) -> list[dict]:
    """Consulta el buscador público y devuelve la lista de expedientes (JSON)."""
    if not (titular or nombre):
        return []
    datos = {
        "nombre": nombre,
        "titular": titular,
        "folio": "",
        "selectRegion": "",
        "selectComuna": "",
        "tipoPresentacion": "",
        "projectStatus": "",
        "offset": 1,
        "limit": limit,
    }
    # El SEIA lee el formulario como ISO-8859-1: si mandáramos UTF-8 (lo que hace
    # requests por defecto), los nombres con tilde ("Gamboína") no harían match.
    cuerpo = urlencode(datos, encoding=_ENCODING, errors="replace")
    cabeceras = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        resp = _session.post(_BUSCAR, data=cuerpo, headers=cabeceras, timeout=30)
        resp.raise_for_status()
        resp.encoding = _ENCODING
        payload = resp.json()
    except (requests.RequestException, ValueError):
        return []
    filas = payload.get("data") if isinstance(payload, dict) else None
    return filas or []


def _coincide(fila: dict, objetivo: str, exacto: bool) -> bool:
    """¿La fila corresponde al nombre buscado? Compara con titular y proyecto.

    El buscador del SEIA hace substring ("Andina Solar 1" también trae "10",
    "13"…), por eso exigimos igualdad o, como mucho, que un nombre contenga al
    otro ("Catemu Solar" ↔ "Catemu Solar SpA"). Así evitamos quedarnos con una
    empresa distinta sólo porque comparte una palabra.
    """
    if not objetivo:
        return False
    campos = (_norm(fila.get("TITULAR")), _norm(fila.get("EXPEDIENTE_NOMBRE")))
    if exacto:
        return objetivo in campos
    return any(c and (objetivo in c or c in objetivo) for c in campos)


def _elegir(filas: list[dict], nombre: str, comuna: str = "") -> dict | None:
    """Elige el expediente más representativo del nombre buscado.

    Prioriza el match exacto (titular o nombre de proyecto); si no hay, acepta
    sólo nombres compatibles. Desempata por misma comuna y, por último, por la
    presentación más reciente (que suele traer el contacto vigente).
    """
    if not filas:
        return None
    objetivo = _norm(nombre)
    candidatos = [f for f in filas if _coincide(f, objetivo, exacto=True)]
    if not candidatos:
        candidatos = [f for f in filas if _coincide(f, objetivo, exacto=False)]
    if not candidatos:
        return None

    if comuna:
        c = _norm(comuna)
        mismos = [f for f in candidatos if _norm(f.get("COMUNA_NOMBRE")) == c]
        if mismos:
            candidatos = mismos

    def _fecha(f: dict) -> int:
        try:
            return int(f.get("FECHA_PRESENTACION") or 0)
        except (TypeError, ValueError):
            return 0

    candidatos.sort(key=_fecha, reverse=True)
    return candidatos[0]


# ─── 2. Lectura de la ficha ───────────────────────────────────────────────────


# Marcadores que el SEIA usa como "campo vacío" y que sólo ensucian la planilla
# (p. ej. "SN"/"S/N" = sin número en teléfono/fax).
_BASURA = {".", "-", "--", "sn", "s/n", "s.n", "na", "n/a", "no tiene", "0", "00"}


def _valor_celda(div) -> str:
    """Texto de la celda-valor de la ficha: e-mail (mailto) o texto plano.

    Descarta celdas sin contenido real (sólo puntuación, o marcadores de "vacío"
    como "." o "SN" que el SEIA deja en teléfono/fax).
    """
    a = div.find("a", href=True)
    if a and a["href"].lower().startswith("mailto:"):
        valor = _limpiar(a.get_text()) or _limpiar(a["href"][7:])
    else:
        valor = _limpiar(div.get_text())
    if not re.search(r"[^\W_]", valor) or _norm(valor) in _BASURA:
        return ""
    return valor


def _limpiar(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def _parsear_ficha(html: str) -> dict[str, dict[str, str]]:
    """Devuelve {sección_normalizada: {etiqueta: valor}} del acordeón de contactos."""
    soup = BeautifulSoup(html, "html.parser")
    contenedor = soup.find(id="accordionContact")
    secciones: dict[str, dict[str, str]] = {}
    if not contenedor:
        return secciones
    for item in contenedor.select(".accordion-item"):
        boton = item.select_one(".accordion-button")
        titulo = _norm(boton.get_text()) if boton else ""
        if not titulo:
            continue
        datos: dict[str, str] = {}
        for fila in item.select(".sg-row-file-description"):
            celdas = fila.find_all("div", recursive=False)
            if len(celdas) < 2:
                continue
            etiqueta = _norm(celdas[0].get_text())
            if etiqueta:
                datos[etiqueta] = _valor_celda(celdas[1])
        secciones[titulo] = datos
    return secciones


def _descargar_ficha(url: str) -> str:
    try:
        resp = _session.get(url, timeout=30)
        resp.raise_for_status()
        resp.encoding = _ENCODING
        return resp.text
    except requests.RequestException:
        return ""


# ─── API pública ──────────────────────────────────────────────────────────────


def buscar(nombre: str, comuna: str = "") -> FichaSEIA | None:
    """Busca la empresa en el SEIA y devuelve su titular + representante legal.

    Args:
        nombre: razón social / titular del proyecto (la columna "Empresa").
        comuna: opcional, para desambiguar titulares con varios proyectos.

    Devuelve None si no hay coincidencia o si el sitio no responde.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        return None

    filas = _buscar_expedientes(titular=nombre)
    if not filas:  # algunos listados traen el nombre del proyecto, no del titular
        filas = _buscar_expedientes(nombre=nombre)
    exp = _elegir(filas, nombre, comuna)
    if not exp:
        return None

    if config.SEIA_PAUSA_SEG:
        time.sleep(config.SEIA_PAUSA_SEG)

    url_ficha = exp.get("EXPEDIENTE_URL_FICHA") or ""
    secciones = _parsear_ficha(_descargar_ficha(url_ficha)) if url_ficha else {}
    titular = secciones.get("titular", {})
    rep = secciones.get("representante legal", {})

    return FichaSEIA(
        titular=titular.get("nombre") or _limpiar(exp.get("TITULAR")),
        titular_email=titular.get("e-mail", ""),
        titular_telefono=titular.get("telefono", ""),
        rep_legal=rep.get("nombre", ""),
        rep_email=rep.get("e-mail", ""),
        rep_telefono=rep.get("telefono", ""),
        expediente=url_ficha,
        expediente_nombre=_limpiar(exp.get("EXPEDIENTE_NOMBRE")),
    )
