"""Orquestador de la v3: recorre la planilla y rellena las celdas vacías.

Para cada empresa (fila con nombre), y según los grupos de campos pedidos:
  - rut   → ``rut.buscar_rut``
  - web   → ``lugar.resolver`` (sitio web, dominio, teléfono, dirección)
  - contactos → ``contactos.mejor_contacto`` (nombre, cargo, email, tel, linkedin)

Sólo escribe en celdas vacías (salvo ``sobrescribir``). El dominio se necesita
para los contactos: si la planilla no lo trae, se intenta obtener del grupo "web".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import config, contactos, lugar, rut
from .lugar import dominio_de_url
from .sheet import Planilla


@dataclass
class Resumen:
    filas: int = 0
    con_rut: int = 0
    con_web: int = 0
    con_contacto: int = 0
    celdas_escritas: int = 0


def completar_planilla(
    entrada: str | Path,
    salida: str | Path,
    campos: set[str] | None = None,
    limite: int | None = None,
    sobrescribir: bool = False,
    progreso=print,
) -> Resumen:
    """Completa ``entrada`` y guarda el resultado en ``salida``.

    Args:
        campos: subconjunto de {"rut", "web", "contactos"} (por defecto todos).
        limite: nº máximo de filas a procesar (None = todas).
        sobrescribir: si True, reemplaza también celdas ya llenas.
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
        # También resolvemos el lugar si hace falta el dominio para los contactos.
        necesita_dominio = (
            "contactos" in campos and pl.vacia(fila, "dominio") and config.GOOGLE_PLACES_API_KEY
        )
        if necesita_web or necesita_dominio:
            ficha = lugar.resolver(nombre, comuna)
            for c in ("sitio_web", "dominio", "telefono", "direccion"):
                if "web" in campos and pl.set(fila, c, ficha[c], sobrescribir):
                    res.celdas_escritas += 1
            # Aseguramos el dominio en la celda aunque no se pidiera "web".
            if necesita_dominio and pl.vacia(fila, "dominio"):
                pl.set(fila, "dominio", ficha["dominio"], sobrescribir=False)

        # ── Contactos ────────────────────────────────────────────────────────
        if "contactos" in campos:
            dominio = str(pl.valor(fila, "dominio") or "").strip()
            if not dominio:
                dominio = dominio_de_url(str(pl.valor(fila, "sitio_web") or ""))
            if dominio:
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

    pl.guardar(salida)
    return res
