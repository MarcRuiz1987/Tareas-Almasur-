"""Orquestador de la v3: recorre la planilla y rellena las celdas vacías.

Para cada empresa (fila con nombre), y según los grupos de campos pedidos:
  - rut   → ``rut.buscar_rut``
  - web   → ``lugar.resolver`` (sitio web, dominio, teléfono, dirección)
  - contactos → ``contactos.mejor_contacto`` (nombre, cargo, email, tel, linkedin)
  - seia  → ``seia.buscar`` (titular + representante legal con contacto, gratis)

Sólo escribe en celdas vacías (salvo ``sobrescribir``). El dominio se necesita
para los contactos: si la planilla no lo trae, se deriva del sitio web (Places)
o del e-mail del SEIA (el del desarrollador madre de la SPV).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import config, contactos, lugar, rut, seia
from .lugar import dominio_de_email, dominio_de_url
from .sheet import Planilla


@dataclass
class Resumen:
    filas: int = 0
    con_rut: int = 0
    con_web: int = 0
    con_contacto: int = 0
    con_seia: int = 0
    celdas_escritas: int = 0


def _dominio_para_contactos(pl: Planilla, fila: list) -> str:
    """Mejor dominio para buscar contactos: celda 'dominio' → sitio web → e-mail SEIA.

    Para las SPV sin web propia, el dominio del desarrollador madre viene en el
    e-mail del representante legal (o del titular) publicado en el SEIA.
    """
    dom = str(pl.valor(fila, "dominio") or "").strip()
    if dom:
        return dom
    dom = dominio_de_url(str(pl.valor(fila, "sitio_web") or ""))
    if dom:
        return dom
    return dominio_de_email(
        str(pl.valor(fila, "seia_rep_email") or pl.valor(fila, "seia_titular_email") or "")
    )


def completar_planilla(
    entrada: str | Path,
    salida: str | Path,
    campos: set[str] | None = None,
    limite: int | None = None,
    sobrescribir: bool = False,
    checkpoint_cada: int | None = None,
    progreso=print,
) -> Resumen:
    """Completa ``entrada`` y guarda el resultado en ``salida``.

    Args:
        campos: subconjunto de {"rut", "web", "contactos"} (por defecto todos).
        limite: nº máximo de filas a procesar (None = todas).
        sobrescribir: si True, reemplaza también celdas ya llenas.
        checkpoint_cada: si se indica, guarda la planilla cada N filas (además
            de al final), para no perder el avance ante una interrupción. Como
            sólo se rellenan celdas vacías, re-correr sobre la salida reanuda.
    """
    campos = campos or set(config.GRUPOS_CAMPOS)
    pl = Planilla.cargar(entrada)
    if "empresa" not in pl.mapa:
        raise ValueError(
            "La planilla no tiene una columna de empresa reconocible "
            f"(encabezados: {pl.encabezados}). Renómbrala a 'Empresa'."
        )

    res = Resumen()
    filas = pl.filas if limite is None else pl.filas[:limite]
    total = len(filas)

    for n, fila in enumerate(filas, 1):
        nombre = str(pl.valor(fila, "empresa") or "").strip()
        if not nombre:
            continue
        res.filas += 1
        progreso(f"[{n}/{total}] {nombre[:50]}")
        comuna = str(pl.valor(fila, "comuna") or "").strip()

        # ── RUT ──────────────────────────────────────────────────────────────
        if "rut" in campos and (sobrescribir or pl.vacia(fila, "rut")):
            valor = rut.buscar_rut(nombre)
            if pl.set(fila, "rut", valor, sobrescribir):
                res.celdas_escritas += 1

        # ── Web / teléfono / dirección ───────────────────────────────────────
        necesita_web = "web" in campos and any(
            sobrescribir or pl.vacia(fila, c)
            for c in ("sitio_web", "dominio", "telefono", "direccion")
        )
        # Sólo recurrimos a Places por el dominio si no lo hay por otra vía
        # (celda, sitio web o e-mail del SEIA) — así no gastamos búsquedas de más.
        necesita_dominio = (
            "contactos" in campos
            and config.GOOGLE_PLACES_API_KEY
            and not _dominio_para_contactos(pl, fila)
        )
        if necesita_web or necesita_dominio:
            ficha = lugar.resolver(nombre, comuna)
            for c in ("sitio_web", "dominio", "telefono", "direccion"):
                if "web" in campos and pl.set(fila, c, ficha[c], sobrescribir):
                    res.celdas_escritas += 1
            # Aseguramos el dominio en la celda aunque no se pidiera "web".
            if necesita_dominio and pl.vacia(fila, "dominio"):
                pl.set(fila, "dominio", ficha["dominio"], sobrescribir=False)

        # ── SEIA: titular + representante legal con contacto (público) ────────
        if "seia" in campos and any(
            sobrescribir or pl.vacia(fila, c) for c in config.GRUPOS_CAMPOS["seia"]
        ):
            ficha = seia.buscar(nombre, comuna)
            if ficha:
                escritos = [
                    pl.set(fila, "seia_titular", ficha.titular, sobrescribir),
                    pl.set(fila, "seia_titular_email", ficha.titular_email, sobrescribir),
                    pl.set(fila, "seia_titular_telefono", ficha.titular_telefono, sobrescribir),
                    pl.set(fila, "seia_titular_direccion", ficha.titular_direccion, sobrescribir),
                    pl.set(fila, "seia_rep_legal", ficha.rep_legal, sobrescribir),
                    pl.set(fila, "seia_rep_email", ficha.rep_email, sobrescribir),
                    pl.set(fila, "seia_rep_telefono", ficha.rep_telefono, sobrescribir),
                    pl.set(fila, "seia_rep_direccion", ficha.rep_direccion, sobrescribir),
                    pl.set(fila, "seia_expediente", ficha.expediente, sobrescribir),
                ]
                res.celdas_escritas += sum(escritos)

        # ── Contactos ────────────────────────────────────────────────────────
        # No gastar la búsqueda (de pago) si la fila ya trae un contacto: así
        # re-correr —p. ej. tras un checkpoint— no vuelve a cobrar en Hunter.
        ya_tiene_contacto = not pl.vacia(fila, "email") or not pl.vacia(fila, "contacto")
        if "contactos" in campos and (sobrescribir or not ya_tiene_contacto):
            dominio = _dominio_para_contactos(pl, fila)
            if dominio:
                # Dejar el dominio en la planilla (trazabilidad), aunque venga del SEIA.
                if pl.set(fila, "dominio", dominio, sobrescribir=False):
                    res.celdas_escritas += 1
                c = contactos.mejor_contacto(dominio, nombre)
                if c:
                    escritos = [
                        pl.set(fila, "contacto", c.nombre, sobrescribir),
                        pl.set(fila, "cargo", c.cargo, sobrescribir),
                        pl.set(fila, "email", c.email, sobrescribir),
                        pl.set(fila, "telefono_contacto", c.telefono, sobrescribir),
                        pl.set(fila, "linkedin", c.linkedin, sobrescribir),
                    ]
                    res.celdas_escritas += sum(escritos)

        # Conteos de cobertura (estado final de la fila).
        if not pl.vacia(fila, "rut"):
            res.con_rut += 1
        if not pl.vacia(fila, "sitio_web") or not pl.vacia(fila, "dominio"):
            res.con_web += 1
        if not pl.vacia(fila, "email") or not pl.vacia(fila, "contacto"):
            res.con_contacto += 1
        if not pl.vacia(fila, "seia_rep_legal") or not pl.vacia(fila, "seia_titular"):
            res.con_seia += 1

        # Guardado periódico: no perder el avance ante una interrupción.
        if checkpoint_cada and n % checkpoint_cada == 0:
            pl.guardar(salida)
            progreso(f"    · checkpoint guardado ({n}/{total})")

    pl.guardar(salida)
    return res
