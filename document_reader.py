#!/usr/bin/env python3
"""
Extrae texto de documentos PDF, Word (.docx), PowerPoint (.pptx) y texto plano.
"""

from __future__ import annotations

import sys
from pathlib import Path


def read_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        sys.exit("Falta pdfplumber. Ejecutá: pip install pdfplumber")

    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[Página {i}]\n{text}")
    return "\n\n".join(pages)


def read_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError:
        sys.exit("Falta python-docx. Ejecutá: pip install python-docx")

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                paragraphs.append(row_text)
    return "\n\n".join(paragraphs)


def read_pptx(path: Path) -> str:
    try:
        from pptx import Presentation
    except ImportError:
        sys.exit("Falta python-pptx. Ejecutá: pip install python-pptx")

    prs = Presentation(str(path))
    slides = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = para.text.strip()
                    if t:
                        texts.append(t)
        if texts:
            slides.append(f"[Diapositiva {i}]\n" + "\n".join(texts))
    return "\n\n".join(slides)


def read_txt(path: Path) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    sys.exit(f"No se pudo leer '{path}' con ninguna codificación conocida.")


READERS = {
    ".pdf":  read_pdf,
    ".docx": read_docx,
    ".doc":  read_docx,
    ".pptx": read_pptx,
    ".ppt":  read_pptx,
    ".txt":  read_txt,
    ".md":   read_txt,
    ".csv":  read_txt,
}


def read_document(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        sys.exit(f"Archivo no encontrado: {p}")
    ext = p.suffix.lower()
    reader = READERS.get(ext)
    if reader is None:
        sys.exit(f"Formato no soportado: '{ext}'. Soportados: {', '.join(READERS)}")
    return reader(p)


def read_multiple(paths: list[str | Path]) -> dict[str, str]:
    """Devuelve {nombre_archivo: texto_extraido} para cada archivo."""
    result = {}
    for path in paths:
        p = Path(path)
        print(f"  Leyendo {p.name}...", file=sys.stderr)
        result[p.name] = read_document(p)
    return result
