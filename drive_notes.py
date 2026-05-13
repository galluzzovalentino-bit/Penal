#!/usr/bin/env python3
"""Generador de apuntes desde Google Drive usando Claude AI.

Lee archivos pendientes de una carpeta de Drive, genera apuntes
con Claude y los envía por email. Los archivos procesados se mueven
a una subcarpeta 'Procesados' automáticamente.

Configuración (variables de entorno o archivo .env):
  DRIVE_FOLDER_ID      ID de la carpeta de Drive con la bibliografía
  GMAIL_USER           Tu dirección de Gmail
  GMAIL_APP_PASSWORD   Contraseña de aplicación de Gmail (no la normal)
  EMAIL_TO             Destinatario de los apuntes

Uso:
  python drive_notes.py                        # procesa archivos pendientes
  python drive_notes.py --folder FOLDER_ID     # especifica carpeta de Drive
  python drive_notes.py --email tu@email.com   # especifica destinatario
  python drive_notes.py --dry-run              # muestra qué se procesaría
"""

import argparse
import base64
import io
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import markdown
from docx import Document
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive"]

SUPPORTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "application/vnd.google-apps.document": "gdoc",
    "text/plain": "text",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

NOTE_PROMPT = """\
Eres un asistente académico experto. Analiza el siguiente documento y genera \
apuntes completos y bien organizados en español.

Los apuntes deben incluir:
1. **Título y tema principal**
2. **Ideas clave** (lista con los conceptos más importantes)
3. **Resumen por secciones** (si el documento tiene estructura)
4. **Conceptos y términos importantes** (definiciones breves)
5. **Conclusiones**

Usa formato Markdown. Sé conciso pero completo: el objetivo es poder estudiar \
solo con estos apuntes.\
"""


def get_drive_service():
    """Autentica con Google Drive y retorna el servicio."""
    creds = None
    token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                print(
                    f"Error: No se encontró '{credentials_path}'.\n"
                    "Descárgalo desde: Google Cloud Console → APIs & Services → Credentials\n"
                    "Guárdalo en la misma carpeta que este script.",
                    file=sys.stderr,
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def get_or_create_processed_folder(service, parent_id: str) -> str:
    """Retorna el ID de la subcarpeta 'Procesados', creándola si no existe."""
    query = (
        f"'{parent_id}' in parents"
        " and name = 'Procesados'"
        " and mimeType = 'application/vnd.google-apps.folder'"
        " and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    folder_meta = {
        "name": "Procesados",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=folder_meta, fields="id").execute()
    return folder["id"]


def list_pending_files(service, folder_id: str) -> tuple[list[dict], str]:
    """Lista archivos pendientes en la carpeta y retorna también el ID de 'Procesados'."""
    processed_folder_id = get_or_create_processed_folder(service, folder_id)
    query = (
        f"'{folder_id}' in parents"
        " and trashed = false"
        " and mimeType != 'application/vnd.google-apps.folder'"
    )
    results = (
        service.files()
        .list(q=query, fields="files(id, name, mimeType)", pageSize=50)
        .execute()
    )
    files = results.get("files", [])
    return [f for f in files if f["mimeType"] in SUPPORTED_MIME_TYPES], processed_folder_id


def download_file(service, file_id: str, mime_type: str) -> bytes:
    """Descarga un archivo. Los Google Docs se exportan como texto plano."""
    if mime_type == "application/vnd.google-apps.document":
        request = service.files().export_media(fileId=file_id, mimeType="text/plain")
    else:
        request = service.files().get_media(fileId=file_id)

    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def extract_docx_text(content: bytes) -> str:
    """Extrae texto de un archivo .docx."""
    doc = Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def build_claude_content(file_name: str, mime_type: str, content: bytes) -> list:
    """Construye el contenido del mensaje para Claude según el tipo de archivo."""
    file_type = SUPPORTED_MIME_TYPES[mime_type]
    intro = f"El siguiente es el documento '{file_name}'. Por favor genera los apuntes.\n\n"

    if file_type == "pdf":
        return [
            {"type": "text", "text": intro},
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(content).decode("utf-8"),
                },
            },
        ]

    if file_type == "image":
        return [
            {"type": "text", "text": intro},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": base64.standard_b64encode(content).decode("utf-8"),
                },
            },
        ]

    if file_type == "docx":
        text = extract_docx_text(content)
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

    return [{"type": "text", "text": f"{intro}{text}"}]


def generate_notes(file_name: str, mime_type: str, content: bytes) -> str:
    """Llama a Claude para generar apuntes del archivo."""
    client = anthropic.Anthropic()
    message_content = build_claude_content(file_name, mime_type, content)
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=NOTE_PROMPT,
        messages=[{"role": "user", "content": message_content}],
    )
    return response.content[0].text


def send_email(subject: str, body_md: str, to_addr: str) -> None:
    """Envía los apuntes por email en formato HTML (generado desde Markdown)."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    from_addr = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    body_html = markdown.markdown(body_md, extensions=["extra", "toc"])
    html_full = f"""\
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: Georgia, serif; max-width: 800px; margin: 40px auto; color: #222; line-height: 1.6; }}
  h1, h2, h3 {{ color: #1a1a2e; }}
  code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
  hr {{ border: none; border-top: 1px solid #ddd; margin: 24px 0; }}
  blockquote {{ border-left: 4px solid #ccc; margin-left: 0; padding-left: 16px; color: #555; }}
</style>
</head><body>{body_html}</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(body_md, "plain", "utf-8"))
    msg.attach(MIMEText(html_full, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(from_addr, password)
        server.sendmail(from_addr, to_addr, msg.as_string())


def move_to_processed(service, file_id: str, parent_id: str, processed_id: str) -> None:
    """Mueve el archivo a la subcarpeta 'Procesados'."""
    service.files().update(
        fileId=file_id,
        addParents=processed_id,
        removeParents=parent_id,
        fields="id, parents",
    ).execute()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera apuntes desde archivos en Google Drive usando Claude AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--folder",
        default=os.getenv("DRIVE_FOLDER_ID"),
        help="ID de la carpeta de Google Drive",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("EMAIL_TO"),
        help="Email destinatario de los apuntes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra qué archivos se procesarían sin generar apuntes ni enviar email",
    )
    args = parser.parse_args()

    if not args.folder:
        print("Error: especifica --folder o define DRIVE_FOLDER_ID en .env", file=sys.stderr)
        sys.exit(1)
    if not args.email and not args.dry_run:
        print("Error: especifica --email o define EMAIL_TO en .env", file=sys.stderr)
        sys.exit(1)

    print("Conectando con Google Drive...")
    service = get_drive_service()
    files, processed_folder_id = list_pending_files(service, args.folder)

    if not files:
        print("No hay archivos pendientes de procesar.")
        return

    print(f"Archivos encontrados: {len(files)}")
    for f in files:
        print(f"  - {f['name']}  ({f['mimeType']})")

    if args.dry_run:
        print("\n[dry-run] No se procesará nada.")
        return

    errors = []
    for file_info in files:
        name = file_info["name"]
        fid = file_info["id"]
        mime = file_info["mimeType"]
        print(f"\nProcesando: {name}")

        try:
            print("  Descargando...")
            content = download_file(service, fid, mime)

            print("  Generando apuntes con Claude...")
            notes = generate_notes(name, mime, content)

            subject = f"Apuntes: {name}"
            body = f"# Apuntes generados automáticamente\n\n**Fuente:** {name}\n\n---\n\n{notes}"

            print(f"  Enviando email a {args.email}...")
            send_email(subject, body, args.email)

            print("  Moviendo a 'Procesados'...")
            move_to_processed(service, fid, args.folder, processed_folder_id)

            print(f"  OK: {name}")
        except Exception as e:
            print(f"  ERROR en '{name}': {e}", file=sys.stderr)
            errors.append((name, str(e)))

    if errors:
        print(f"\nErrores en {len(errors)} archivo(s):")
        for name, err in errors:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print(f"\nTodos los archivos procesados correctamente.")


if __name__ == "__main__":
    main()
