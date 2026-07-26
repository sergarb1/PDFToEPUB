"""
PDFToEPUB_common — Shared pipeline for PDF → Markdown/EPUB OCR conversion.

All three scripts (LightOnOCR, GLM-OCR, PP-OCRv6) import this module
for CLI parsing, the OCR loop, resume support, and EPUB output.
"""

import argparse
import gc
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from pdf2image import convert_from_path

# ── Explicit line buffering so progress lines are visible ──────────────
sys.stdout.reconfigure(line_buffering=True)


# ── Bilingual messages ─────────────────────────────────────────────────

MSG = {
    "en": {
        "err_pdf_not_found": "ERROR: PDF not found: {}",
        "err_pandoc": "pandoc error: {}",
        "out": "Out",
        "dpi": "DPI",
        "max_h": "MaxH",
        "loading_model": "Loading model...",
        "loaded": "Loaded in {:.1f}s",
        "converting_pdf": "Converting PDF to images...",
        "pages": "Pages",
        "resuming": "Resuming: {} pages already done",
        "page_fmt": "[{}/{}] {:6.1f}s  {:4d} chars  ETA: {:.0f}s",
        "err_page": "[{}/{}] ERROR: {}",
        "done": "Done! {:.0f}s total  ({:.1f}s/page)",
        "converting_epub": "Converting to EPUB...",
        "epub_ok": "EPUB: {}",
        "cpu_mode": "CPU mode enabled",
        "warn_layout": "Warning: no layout detection – tables/figures will be flat text.",
        "note_raw": "NOTE: this engine outputs raw text without layout structure.",
    },
    "es": {
        "err_pdf_not_found": "ERROR: PDF no encontrado: {}",
        "err_pandoc": "Error de pandoc: {}",
        "out": "Salida",
        "dpi": "DPI",
        "max_h": "AltMax",
        "loading_model": "Cargando modelo...",
        "loaded": "Cargado en {:.1f}s",
        "converting_pdf": "Convirtiendo PDF a imágenes...",
        "pages": "Páginas",
        "resuming": "Reanudando: {} páginas ya procesadas",
        "page_fmt": "[{}/{}] {:6.1f}s  {:4d} chars  ETA: {:.0f}s",
        "err_page": "[{}/{}] ERROR: {}",
        "done": "¡Completado! {:.0f}s total  ({:.1f}s/página)",
        "converting_epub": "Convirtiendo a EPUB...",
        "epub_ok": "EPUB: {}",
        "cpu_mode": "Modo CPU activado",
        "warn_layout": "Aviso: sin detección de diseño – tablas/figuras serán texto plano.",
        "note_raw": "NOTA: este motor extrae texto plano sin estructura de diseño.",
    },
}


def _(key, lang="en"):
    return MSG.get(lang, MSG["en"]).get(key, key)


# ── Config dataclass ────────────────────────────────────────────────────


@dataclass
class PipelineConfig:
    pdf_path: str
    output_path: str | None = None
    dpi: int = 200
    max_h: int = 768
    first_page: int | None = None
    last_page: int | None = None
    resume: bool = False
    cpu: bool = False
    lang: str = "en"
    epub: bool = True
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    engine: str = "lighton"
    reload_every: int = 0  # 0 = never reload
    context_window: int = 5  # how many previous pages to feed as context


# ── Shared helpers ──────────────────────────────────────────────────────


def setup_logging():
    import logging
    import warnings
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("accelerate").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message=".*model of type.*to instantiate a model of type.*")


def safe_empty_cache():
    try:
        import torch
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def reload_model(cfg, load_model_fn):
    """Unload current model from GPU and reload fresh."""
    import torch
    gc.collect()
    safe_empty_cache()
    return load_model_fn(cfg)


def resolve_device(cpu=False):
    """Return ``"cuda"`` or ``"cpu"`` based on availability and flag."""
    if cpu:
        return "cpu"
    try:
        import torch
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if torch.cuda.is_available():
                return "cuda"
    except Exception:
        pass
    return "cpu"


# ── CLI parser ──────────────────────────────────────────────────────────


def build_parser(description="PDF → Markdown/EPUB"):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("pdf", help="Input PDF file | Archivo PDF de entrada")
    parser.add_argument("-o", "--output", help="Output path (.md or .epub)")
    parser.add_argument("--dpi", type=int, default=200, help="Image DPI (default 200)")
    parser.add_argument(
        "--max-h", type=int, default=768, dest="max_h",
        help="Max image height, lower = less VRAM (default 768)",
    )
    parser.add_argument("--first-page", type=int, dest="first_page", help="First page")
    parser.add_argument("--last-page", type=int, dest="last_page", help="Last page")
    parser.add_argument("--cpu", action="store_true", help="Run on CPU (no GPU required)")
    parser.add_argument("--resume", action="store_true", help="Resume from existing output")
    parser.add_argument("--lang", default="en", choices=["en", "es"],
                        help="Interface language (en/es, default en)")
    parser.add_argument("--no-epub", action="store_true", dest="no_epub",
                        help="Skip EPUB, output Markdown only | Solo Markdown, sin EPUB")
    parser.add_argument("--reload-every", type=int, default=0, dest="reload_every",
                        help="Reload model every N pages to prevent quality decay (0 = never)")
    parser.add_argument("--context-window", type=int, default=5, dest="context_window",
                        help="Feed last N pages as context to the model (0 = no context, default 5)")
    parser.add_argument("--title", help="Book title | Título del libro")
    parser.add_argument("--author", action="append", help="Author (repeatable)")
    return parser


def parse_config(args) -> PipelineConfig:
    return PipelineConfig(
        pdf_path=args.pdf,
        output_path=args.output,
        dpi=args.dpi,
        max_h=getattr(args, "max_h", 768),
        first_page=args.first_page,
        last_page=args.last_page,
        resume=args.resume,
        cpu=args.cpu,
        lang=args.lang,
        epub=not getattr(args, "no_epub", False),
        title=args.title,
        authors=args.author or [],
        engine=getattr(args, "engine", "lighton"),
        reload_every=getattr(args, "reload_every", 0),
        context_window=getattr(args, "context_window", 5),
    )


# ── EPUB conversion ─────────────────────────────────────────────────────


def to_epub(md_path, title=None, authors=None, lang="en"):
    epub_path = Path(md_path).with_suffix(".epub")
    cmd = ["pandoc", md_path, "-o", str(epub_path), "-f", "markdown"]
    if title:
        cmd += ["--metadata", f"title={title}"]
    for a in (authors or []):
        cmd += ["--metadata", f"author={a}"]
    print(f"\n{_('converting_epub', lang)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(_("err_pandoc", lang).format(r.stderr))
        return None
    print(_("epub_ok", lang).format(epub_path))
    return str(epub_path)


# ── Main pipeline ───────────────────────────────────────────────────────


def run_pipeline(cfg: PipelineConfig, load_model_fn, ocr_page_fn):
    """Generic OCR pipeline.

    Parameters
    ----------
    cfg : PipelineConfig
        All runtime settings.
    load_model_fn : callable
        ``(cfg) -> (processor, model)``
    ocr_page_fn : callable
        ``(processor, model, pil_image, cfg) -> str``
    """
    pdf_path = Path(cfg.pdf_path).resolve()
    if not pdf_path.exists():
        print(_("err_pdf_not_found", cfg.lang).format(pdf_path))
        sys.exit(1)

    if cfg.output_path is None:
        output_path = pdf_path.with_suffix(".md")
    else:
        output_path = Path(cfg.output_path)
        if output_path.suffix == ".epub":
            output_path = output_path.with_suffix(".md")

    print(f"PDF:  {pdf_path}")
    print(f"{_('out', cfg.lang)}:  {output_path}")

    if cfg.cpu:
        print(_("cpu_mode", cfg.lang))

    if hasattr(load_model_fn, "_needs_max_h") or cfg.first_page or cfg.last_page:
        print(f"{_('dpi', cfg.lang)}:  {cfg.dpi}", end="")
        if hasattr(load_model_fn, "_needs_max_h"):
            print(f"  {_('max_h', cfg.lang)}: {cfg.max_h}")
        else:
            print()

    # ── Resume ──────────────────────────────────────────────────
    existing_pages = set()
    if cfg.resume and output_path.exists():
        content = output_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("## Page "):
                try:
                    n = int(line.split()[2])
                    existing_pages.add(n)
                except (IndexError, ValueError):
                    pass
        if existing_pages:
            print(_("resuming", cfg.lang).format(len(existing_pages)))
        skip_until = max(existing_pages) if existing_pages else 0
    else:
        skip_until = (cfg.first_page or 1) - 1 if cfg.first_page else 0

    # ── Load model ──────────────────────────────────────────────
    print(f"\n{_('loading_model', cfg.lang)}")
    t0 = time.time()
    processor, model = load_model_fn(cfg)
    print(_("loaded", cfg.lang).format(time.time() - t0))

    # ── Rasterise PDF ───────────────────────────────────────────
    print(_("converting_pdf", cfg.lang))
    kwargs = {"dpi": cfg.dpi}
    if cfg.first_page is not None:
        kwargs["first_page"] = cfg.first_page
    if cfg.last_page is not None:
        kwargs["last_page"] = cfg.last_page

    pages = convert_from_path(str(pdf_path), **kwargs)
    offset = (cfg.first_page or 1) - 1
    total = len(pages)
    print(f"{_('pages', cfg.lang)}: {total}\n")

    # ── OCR loop ────────────────────────────────────────────────
    all_text = []
    if cfg.resume and output_path.exists():
        all_text.append(output_path.read_text(encoding="utf-8").rstrip() + "\n")

    ocr_start = time.time()
    pages_processed = 0
    prev_pages = []  # rolling window of previous page texts for context
    context_window = max(0, cfg.context_window)

    for i, page in enumerate(pages, 1):
        page_num = offset + i
        if cfg.resume and page_num <= skip_until:
            continue

        # Reload model if --reload-every is set
        if cfg.reload_every > 0 and pages_processed > 0 and pages_processed % cfg.reload_every == 0:
            print("  Reloading model to clear accumulated state...")
            processor, model = load_model_fn(cfg)

        # Build context from previous pages (skip if too short to be useful)
        prev_text = ""
        if prev_pages:
            combined = [p for p in prev_pages if len(p.strip()) > 20]
            if combined:
                prev_text = "\n\n".join(combined)

        page_start = time.time()
        try:
            text = ocr_page_fn(processor, model, page, cfg, prev_text=prev_text)
            all_text.append(f"## Page {page_num}\n\n{text}\n")
            pages_processed += 1
            elapsed = time.time() - page_start
            rate = (time.time() - ocr_start) / max(pages_processed, 1)
            eta = rate * (total - pages_processed)
            chars = len(text)
            print(
                _("page_fmt", cfg.lang).format(
                    page_num, total + offset, elapsed, chars, eta
                )
            )
        except Exception as e:
            print(_("err_page", cfg.lang).format(page_num, total + offset, e))
            all_text.append(f"## Page {page_num}\n\n*[OCR failed: {e}]*\n")
            pages_processed += 1
            text = ""

        # Update rolling context window
        if context_window > 0 and text.strip():
            prev_pages.append(text)
            if len(prev_pages) > context_window:
                prev_pages.pop(0)

        gc.collect()
        safe_empty_cache()

    # ── Save ────────────────────────────────────────────────────
    md = "".join(all_text)
    output_path.write_text(md, encoding="utf-8")

    total_time = time.time() - ocr_start
    avg = total_time / max(pages_processed, 1)
    print(f"\n{_('done', cfg.lang).format(total_time, avg)}")
    return str(output_path)
