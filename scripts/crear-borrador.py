#!/usr/bin/env python3
"""Crea un correo como BORRADOR en Outlook vía Microsoft Graph. NUNCA lo envía.

Usa el flujo client-credentials (app-only) con MSAL, de modo que funciona en
sesiones desatendidas (programadas). Crea el mensaje con POST /users/{mailbox}/messages,
que lo deja en la carpeta "Borradores" con isDraft=true. No se llama jamás a /sendMail.

Permiso de aplicación requerido en Entra ID: Mail.ReadWrite (con consentimiento de
administrador). Ver README para el paso a paso del registro de aplicación.

Variables de entorno (cargar como secretos del environment, NO commitear):
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, MAILBOX

Ejemplos de uso:
    # Cuerpo y destinatarios por argumentos:
    python crear-borrador.py \
        --asunto "Informe diario de ventas — 2026-06-07" \
        --para gerencia@ialmasur.cl --cc marcelo.ruiz@ialmasur.cl \
        --cuerpo-archivo reports/2026-06-07-ventas.html --formato html \
        --adjunto reports/2026-06-07-tarifas.xlsx

    # Cuerpo por stdin:
    cat cuerpo.md | python crear-borrador.py --asunto "Hola" --para x@y.cl --formato markdown
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

import requests

try:
    import msal
except ImportError:  # pragma: no cover
    sys.exit("Falta la dependencia 'msal'. Instala con: pip install -r scripts/requirements.txt")

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = ["https://graph.microsoft.com/.default"]


def _env(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        sys.exit(f"Falta la variable de entorno {nombre}. Cárgala como secreto del environment.")
    return valor


def obtener_token() -> str:
    tenant = _env("TENANT_ID")
    app = msal.ConfidentialClientApplication(
        client_id=_env("CLIENT_ID"),
        client_credential=_env("CLIENT_SECRET"),
        authority=f"https://login.microsoftonline.com/{tenant}",
    )
    resultado = app.acquire_token_for_client(scopes=SCOPE)
    if "access_token" not in resultado:
        sys.exit(
            "No se pudo obtener token de Graph: "
            f"{resultado.get('error')} — {resultado.get('error_description')}"
        )
    return resultado["access_token"]


def _markdown_a_html(texto: str) -> str:
    """Conversión mínima markdown -> HTML para no requerir dependencias extra.

    Para reportes con formato rico, pasar el cuerpo directamente como --formato html.
    """
    lineas = []
    for linea in texto.splitlines():
        s = linea.rstrip()
        if s.startswith("### "):
            lineas.append(f"<h3>{s[4:]}</h3>")
        elif s.startswith("## "):
            lineas.append(f"<h2>{s[3:]}</h2>")
        elif s.startswith("# "):
            lineas.append(f"<h1>{s[2:]}</h1>")
        elif s.startswith("- "):
            lineas.append(f"<li>{s[2:]}</li>")
        elif s == "":
            lineas.append("<br>")
        else:
            lineas.append(f"<p>{s}</p>")
    return "\n".join(lineas)


def _recipients(direcciones: list[str]) -> list[dict]:
    return [{"emailAddress": {"address": d}} for d in direcciones if d]


def _adjuntos(rutas: list[str]) -> list[dict]:
    items = []
    for ruta in rutas:
        p = Path(ruta)
        if not p.is_file():
            sys.exit(f"Adjunto no encontrado: {ruta}")
        contenido = base64.b64encode(p.read_bytes()).decode("ascii")
        items.append(
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": p.name,
                "contentBytes": contenido,
            }
        )
    return items


def crear_borrador(args: argparse.Namespace) -> dict:
    if args.cuerpo_archivo:
        cuerpo = Path(args.cuerpo_archivo).read_text(encoding="utf-8")
    elif args.cuerpo:
        cuerpo = args.cuerpo
    else:
        cuerpo = sys.stdin.read()

    if args.formato == "markdown":
        content_type, content = "HTML", _markdown_a_html(cuerpo)
    elif args.formato == "html":
        content_type, content = "HTML", cuerpo
    else:
        content_type, content = "Text", cuerpo

    mensaje: dict = {
        "subject": args.asunto,
        "body": {"contentType": content_type, "content": content},
        "toRecipients": _recipients(args.para),
    }
    if args.cc:
        mensaje["ccRecipients"] = _recipients(args.cc)
    if args.adjunto:
        mensaje["attachments"] = _adjuntos(args.adjunto)

    token = obtener_token()
    mailbox = _env("MAILBOX")
    # POST /messages crea el mensaje como BORRADOR (isDraft=true). No envía.
    resp = requests.post(
        f"{GRAPH}/users/{mailbox}/messages",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=mensaje,
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        sys.exit(f"Error creando borrador ({resp.status_code}): {resp.text}")
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea un borrador en Outlook (no envía).")
    parser.add_argument("--asunto", required=True)
    parser.add_argument("--para", nargs="+", required=True, help="Destinatarios To (uno o más).")
    parser.add_argument("--cc", nargs="*", default=[], help="Destinatarios CC (opcional).")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--cuerpo", help="Cuerpo del correo como texto.")
    grupo.add_argument("--cuerpo-archivo", help="Ruta a un archivo con el cuerpo.")
    parser.add_argument("--formato", choices=["text", "html", "markdown"], default="markdown")
    parser.add_argument("--adjunto", nargs="*", default=[], help="Rutas de archivos a adjuntar.")
    args = parser.parse_args()

    creado = crear_borrador(args)
    web_link = creado.get("webLink", "")
    print("Borrador creado en Outlook (NO enviado).")
    print(f"  id: {creado.get('id', '')}")
    if web_link:
        print(f"  abrir: {web_link}")


if __name__ == "__main__":
    main()
