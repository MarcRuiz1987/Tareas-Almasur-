#!/usr/bin/env python3
"""Servidor MCP de la v2 — herramientas conversacionales para Claude Desktop.

Expone el pipeline como herramientas que puedes invocar por chat: buscar empresas,
describirlas, enriquecer contactos, cargar tus clientes, construir el ICP y
calificar leads. Misma filosofía que el setup de Scrapling de la v1
(ver ../v1-scraping/scrapling-mcp-setup.md).

Ejecutar:
    python mcp_server.py            # stdio (Claude Desktop)

Registro en Claude Desktop (claude_desktop_config.json):
    {
      "mcpServers": {
        "leadgen": {
          "command": "python",
          "args": ["/ruta/a/v2-leadgen/mcp_server.py"]
        }
      }
    }
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from leadgen import config, describe, discovery, enrich, icp
from leadgen.models import Empresa

mcp = FastMCP("leadgen")


@mcp.tool()
def buscar_empresas(rubro: str, comuna: str, maximo: int = 20) -> list[dict]:
    """Busca empresas de un rubro en una comuna (Google Places). Devuelve fichas básicas."""
    nombre, query = config.resolver_rubro(rubro)
    empresas = discovery.buscar_empresas(query, comuna, nombre, maximo)
    return [e.to_dict() for e in empresas]


@mcp.tool()
def describir_empresa(nombre: str, sitio_web: str) -> dict:
    """Genera una descripción estructurada de la empresa a partir de su sitio web."""
    e = Empresa(nombre=nombre, sitio_web=sitio_web)
    describe.describir(e)
    return {
        "descripcion": e.descripcion,
        "sector": e.sector,
        "tamano_estimado": e.tamano_estimado,
        "senales": e.senales,
    }


@mcp.tool()
def enriquecer_contactos(nombre: str, dominio: str, sitio_web: str = "") -> list[dict]:
    """Descubre (Hunter) y enriquece (FullEnrich) contactos de la empresa."""
    e = Empresa(nombre=nombre, dominio=dominio, sitio_web=sitio_web or f"https://{dominio}")
    enrich.enriquecer_empresa(e)
    return [c.to_dict() for c in e.contactos]


@mcp.tool()
def cargar_clientes(csv_path: str) -> list[str]:
    """Lee la lista de nombres de clientes desde un CSV."""
    return icp.cargar_clientes(csv_path)


@mcp.tool()
def construir_icp(csv_path: str, usar_cache: bool = True) -> dict:
    """Construye (o carga del caché) el Perfil de Cliente Ideal desde tus clientes."""
    nombres = icp.cargar_clientes(csv_path)
    perfil, _ = icp.construir_o_cargar_icp(nombres, usar_cache=usar_cache)
    return perfil.model_dump()


@mcp.tool()
def calificar_lead(
    nombre: str, descripcion: str, sector: str, tamano: str, csv_clientes: str
) -> dict:
    """Califica si una empresa encaja con el ICP construido desde tus clientes."""
    nombres = icp.cargar_clientes(csv_clientes)
    perfil, ejemplos = icp.construir_o_cargar_icp(nombres)
    e = Empresa(nombre=nombre, descripcion=descripcion, sector=sector, tamano_estimado=tamano)
    icp.calificar(e, perfil, ejemplos)
    return {"ajuste": e.ajuste_icp, "score_icp": e.score_icp, "razon": e.razon_icp}


if __name__ == "__main__":
    mcp.run()
