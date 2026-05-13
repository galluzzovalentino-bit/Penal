#!/usr/bin/env python3
"""
Interfaz web del sistema de apuntes automáticos.
Ejecutar con: streamlit run app.py
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
import anthropic

from document_reader import read_document, READERS
from pdf_tools import _parse_page_spec


def get_api_key() -> str | None:
    """Lee la API key desde Streamlit secrets, variable de entorno o sidebar."""
    # 1. Streamlit Cloud secrets
    try:
        key = st.secrets["ANTHROPIC_API_KEY"]
        if key:
            return key
    except (KeyError, FileNotFoundError, AttributeError):
        pass
    # 2. Variable de entorno local
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    # 3. Ingreso manual en sidebar
    key = st.session_state.get("manual_api_key", "")
    return key if key else None

# ─── Configuración de página ──────────────────────────────────────────────────

st.set_page_config(
    page_title="Apuntes IA",
    page_icon="📚",
    layout="centered",
)

st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        padding: 0.75rem;
        font-size: 1.1rem;
        border-radius: 10px;
    }
    .stTextArea textarea {
        font-size: 1rem;
    }
    .result-box {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        border-left: 4px solid #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

# ─── Helpers ──────────────────────────────────────────────────────────────────

STYLE_PROMPTS = {
    "Detallado 📝": (
        "detallado",
        "Generá apuntes académicos extremadamente detallados y completos. "
        "Usá títulos (##), subtítulos (###), listas con viñetas, definiciones en negrita, "
        "ejemplos concretos y resaltá los conceptos clave. "
        "El objetivo es que alguien pueda estudiar únicamente con estos apuntes.",
    ),
    "Esquema 🗂️": (
        "esquema",
        "Armá un esquema jerárquico con todos los temas, subtemas, definiciones y puntos clave. "
        "Usá numeración (1., 1.1., 1.1.1.) para mostrar la jerarquía claramente.",
    ),
    "Resumen 📄": (
        "resumen",
        "Hacé un resumen ejecutivo claro y conciso de los puntos más importantes, "
        "sin perder conceptos clave. Máximo 30% de la extensión original.",
    ),
    "Flashcards 🃏": (
        "flashcards",
        "Generá tarjetas de estudio en formato: **Pregunta:** ... / **Respuesta:** ... "
        "Cubrí todos los conceptos importantes del material.",
    ),
    "Mapa conceptual 🗺️": (
        "mapa",
        "Creá un mapa conceptual en texto usando indentación y flechas (→) para mostrar "
        "relaciones entre conceptos. Incluí todos los temas principales y sus conexiones.",
    ),
}

ACCEPTED_EXTENSIONS = list(READERS.keys())


def save_uploaded(uploaded_file) -> tuple[Path, str]:
    suffix = Path(uploaded_file.name).suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.read())
    tmp.flush()
    tmp.close()  # cerrar antes de que otra librería abra el mismo archivo
    return Path(tmp.name), uploaded_file.name


def generate_notes_stream(docs: dict[str, str], instruction: str, style_prompt: str, api_key: str, model: str = "claude-sonnet-4-6"):
    parts = [
        "Sos un experto en didáctica y síntesis académica. Tu tarea es generar apuntes de estudio.",
        f"\n## Instrucción del usuario\n{instruction}" if instruction else "",
        f"\n## Estilo de apuntes\n{style_prompt}",
        "\n## Material bibliográfico\n",
    ]
    for filename, text in docs.items():
        truncated = text[:80_000] if len(text) > 80_000 else text
        parts.append(f"### Documento: {filename}\n{truncated}\n")
    parts.append(
        "\n---\nGenerá los apuntes completos según la instrucción y el estilo. "
        "Sé exhaustivo, preciso y académicamente riguroso."
    )
    prompt = "\n".join(p for p in parts if p)

    client = anthropic.Anthropic(api_key=api_key)
    with client.messages.stream(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            yield chunk


# ─── Tabs ─────────────────────────────────────────────────────────────────────

# ─── Sidebar: API Key ────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Configuración")
    _key = get_api_key()
    if not _key:
        manual_key = st.text_input(
            "API Key de Anthropic",
            type="password",
            placeholder="sk-ant-...",
            help="Obtené tu key en console.anthropic.com",
        )
        if manual_key:
            st.session_state["manual_api_key"] = manual_key
        st.warning("Ingresá tu API Key para usar la app.")
    else:
        # Mostramos solo los primeros y últimos caracteres para confirmar que se leyó
        masked = _key[:8] + "..." + _key[-4:] if len(_key) > 12 else "***"
        st.success(f"API Key configurada ✓\n`{masked}`")

    st.divider()
    st.markdown("**Modelo**")
    model = st.selectbox(
        "Modelo Claude",
        options=[
            "claude-sonnet-4-6",
            "claude-opus-4-5",
            "claude-haiku-4-5-20251001",
        ],
        index=0,
        label_visibility="collapsed",
    )
    st.caption("Sonnet: balance ideal. Opus: más detallado. Haiku: más rápido.")

    st.divider()
    st.markdown("**Formatos soportados**")
    st.markdown("PDF · Word · PowerPoint · TXT")
    st.divider()
    st.markdown("Creado con [Claude](https://anthropic.com) + Streamlit")

# ─── Título ───────────────────────────────────────────────────────────────────

st.title("📚 Apuntes con IA")
st.caption("Subí tu bibliografía y generá apuntes al instante.")

tab_notas, tab_pdf = st.tabs(["✏️ Generar Apuntes", "📄 Herramientas PDF"])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — GENERAR APUNTES
# ════════════════════════════════════════════════════════════════════════════════

with tab_notas:
    st.subheader("1. Subí tus documentos")
    uploaded_files = st.file_uploader(
        "PDF, Word, PowerPoint o texto",
        type=[e.lstrip(".") for e in ACCEPTED_EXTENSIONS],
        accept_multiple_files=True,
        key="docs_uploader",
    )

    st.subheader("2. Instrucciones")
    instruction = st.text_area(
        "¿Qué apuntes necesitás?",
        placeholder="Ej: Armá apuntes para rendir Derecho Penal. Enfocate en los elementos del delito y la autoría.",
        height=120,
    )

    st.subheader("3. Estilo")
    style_label = st.radio(
        "Elegí el formato",
        options=list(STYLE_PROMPTS.keys()),
        horizontal=True,
    )

    st.divider()

    if st.button("🚀 Generar Apuntes", type="primary", disabled=not uploaded_files):
        api_key = get_api_key()
        if not api_key:
            st.error("Primero ingresá tu API Key en el panel izquierdo.")
            st.stop()
        if not uploaded_files:
            st.warning("Primero subí al menos un documento.")
        else:
            docs = {}
            with st.spinner("Leyendo documentos..."):
                for uf in uploaded_files:
                    tmp_path, original_name = save_uploaded(uf)
                    try:
                        docs[original_name] = read_document(tmp_path)
                    except (SystemExit, ValueError, Exception) as e:
                        st.error(f"Error leyendo **{original_name}**: {e}")
                        st.stop()

            total = sum(len(t) for t in docs.values())
            st.info(f"Leídos {len(docs)} documento(s) — {total:,} caracteres en total.")

            _, style_prompt = STYLE_PROMPTS[style_label]

            st.subheader("📝 Tus apuntes")
            result_container = st.empty()
            collected = []

            for chunk in generate_notes_stream(docs, instruction, style_prompt, api_key, model):
                collected.append(chunk)
                result_container.markdown("".join(collected))

            notes_text = "".join(collected)
            st.success("¡Apuntes generados!")

            st.download_button(
                label="⬇️ Descargar apuntes (.md)",
                data=notes_text.encode("utf-8"),
                file_name="apuntes.md",
                mime="text/markdown",
            )


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — HERRAMIENTAS PDF
# ════════════════════════════════════════════════════════════════════════════════

with tab_pdf:
    st.subheader("¿Qué querés hacer?")
    operacion = st.radio(
        "Operación",
        ["✂️ Dividir PDF", "📌 Extraer páginas", "🔗 Fusionar PDFs", "🔄 Rotar páginas"],
        horizontal=False,
    )

    # ── DIVIDIR ──────────────────────────────────────────────────────────────
    if operacion == "✂️ Dividir PDF":
        st.markdown("**Subí el PDF y definí los rangos de páginas para cada parte.**")
        pdf_file = st.file_uploader("PDF a dividir", type=["pdf"], key="split_up")

        if pdf_file:
            from pypdf import PdfReader, PdfWriter
            import io

            tmp_path, _ = save_uploaded(pdf_file)
            reader = PdfReader(str(tmp_path))
            total_pages = len(reader.pages)
            st.info(f"El PDF tiene **{total_pages} páginas**.")

            rangos_raw = st.text_input(
                "Rangos de páginas (uno por línea o separados por coma)",
                placeholder="1-10\n11-20\n21-30",
            )
            rangos_input = st.text_area(
                "O escribilos acá (un rango por línea)",
                height=120,
                placeholder="1-10\n11-20\n21",
            )
            rangos = [r.strip() for r in rangos_input.strip().splitlines() if r.strip()]

            if st.button("✂️ Dividir", type="primary", disabled=not rangos):
                for i, rango in enumerate(rangos, 1):
                    try:
                        indices = _parse_page_spec(rango, total_pages)
                    except SystemExit as e:
                        st.error(str(e))
                        continue
                    writer = PdfWriter()
                    for idx in indices:
                        writer.add_page(reader.pages[idx])
                    buf = io.BytesIO()
                    writer.write(buf)
                    buf.seek(0)
                    st.download_button(
                        label=f"⬇️ Descargar Parte {i} (páginas {rango})",
                        data=buf,
                        file_name=f"parte_{i}_pags_{rango.replace('-','_')}.pdf",
                        mime="application/pdf",
                        key=f"split_dl_{i}",
                    )
                st.success("¡Partes generadas!")

    # ── EXTRAER ───────────────────────────────────────────────────────────────
    elif operacion == "📌 Extraer páginas":
        st.markdown("**Subí el PDF e indicá qué páginas querés extraer.**")
        pdf_file = st.file_uploader("PDF de origen", type=["pdf"], key="extract_up")

        if pdf_file:
            from pypdf import PdfReader, PdfWriter
            import io

            tmp_path, _ = save_uploaded(pdf_file)
            reader = PdfReader(str(tmp_path))
            total_pages = len(reader.pages)
            st.info(f"El PDF tiene **{total_pages} páginas**.")

            pages_spec = st.text_input(
                "Páginas a extraer",
                placeholder="Ej: 1,3,5-10,15",
            )

            if st.button("📌 Extraer", type="primary", disabled=not pages_spec):
                try:
                    indices = _parse_page_spec(pages_spec, total_pages)
                except SystemExit as e:
                    st.error(str(e))
                    st.stop()

                writer = PdfWriter()
                for idx in indices:
                    writer.add_page(reader.pages[idx])
                buf = io.BytesIO()
                writer.write(buf)
                buf.seek(0)
                st.download_button(
                    label=f"⬇️ Descargar páginas extraídas ({len(indices)} págs.)",
                    data=buf,
                    file_name="paginas_extraidas.pdf",
                    mime="application/pdf",
                )
                st.success(f"Extraídas {len(indices)} página(s).")

    # ── FUSIONAR ──────────────────────────────────────────────────────────────
    elif operacion == "🔗 Fusionar PDFs":
        st.markdown("**Subí varios PDFs y se fusionarán en el orden en que los subas.**")
        pdf_files = st.file_uploader(
            "PDFs a fusionar (en orden)",
            type=["pdf"],
            accept_multiple_files=True,
            key="merge_up",
        )

        if pdf_files:
            st.write(f"PDFs a fusionar en este orden:")
            for i, f in enumerate(pdf_files, 1):
                st.write(f"  {i}. {f.name}")

            if st.button("🔗 Fusionar", type="primary"):
                from pypdf import PdfReader, PdfWriter
                import io

                writer = PdfWriter()
                total = 0
                for uf in pdf_files:
                    tmp_path, _ = save_uploaded(uf)
                    reader = PdfReader(str(tmp_path))
                    for page in reader.pages:
                        writer.add_page(page)
                    total += len(reader.pages)

                buf = io.BytesIO()
                writer.write(buf)
                buf.seek(0)
                st.download_button(
                    label=f"⬇️ Descargar PDF fusionado ({total} págs.)",
                    data=buf,
                    file_name="fusionado.pdf",
                    mime="application/pdf",
                )
                st.success(f"Fusionados {len(pdf_files)} archivos ({total} páginas).")

    # ── ROTAR ─────────────────────────────────────────────────────────────────
    elif operacion == "🔄 Rotar páginas":
        st.markdown("**Rotá páginas de un PDF.**")
        pdf_file = st.file_uploader("PDF a rotar", type=["pdf"], key="rotate_up")

        if pdf_file:
            from pypdf import PdfReader, PdfWriter
            import io

            tmp_path, _ = save_uploaded(pdf_file)
            reader = PdfReader(str(tmp_path))
            total_pages = len(reader.pages)
            st.info(f"El PDF tiene **{total_pages} páginas**.")

            angle = st.select_slider(
                "Ángulo de rotación",
                options=[90, 180, 270],
                value=90,
            )
            pages_spec = st.text_input(
                "Páginas a rotar (dejá vacío para rotar todas)",
                placeholder="Ej: 1,3,5-10",
            )

            if st.button("🔄 Rotar", type="primary"):
                target = (
                    set(_parse_page_spec(pages_spec, total_pages))
                    if pages_spec.strip()
                    else set(range(total_pages))
                )
                writer = PdfWriter()
                for i, page in enumerate(reader.pages):
                    if i in target:
                        page.rotate(angle)
                    writer.add_page(page)
                buf = io.BytesIO()
                writer.write(buf)
                buf.seek(0)
                st.download_button(
                    label=f"⬇️ Descargar PDF rotado",
                    data=buf,
                    file_name="rotado.pdf",
                    mime="application/pdf",
                )
                st.success(f"Rotadas {len(target)} página(s) {angle}°.")
