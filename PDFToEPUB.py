#!/usr/bin/env python3
"""
PDFToEPUB — PDF to Markdown/EPUB with 4 local OCR engines.

Choose the engine that fits your document with --engine:

  lighton (default)  LightOnOCR-2-1B (1B VLM).  Balanced speed/quality.
                     Best overall default.  Produces rich Markdown.
                     ~2 GB VRAM, ~8 s/page.

  glm                GLM-OCR (0.9B VLM).  Highest accuracy for complex layouts.
                     Best for tables, formulas, multi-column, dense docs.
                     ~2.5 GB VRAM, ~5-15 s/page.  94.6 OmniDocBench.

  tesseract          Tesseract (CPU-only classic OCR).
                     Lightweight, always available, basic paragraph detection.
                     ~1-3 s/page on CPU.

Bilingual: --lang es
CPU mode:  --cpu  (ppocrv6 is usable on CPU, VLMs will be slow)
"""

import sys
import warnings
from pathlib import Path

import numpy as np
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import torch
from PIL import Image

from PDFToEPUB_common import (
    PipelineConfig,
    build_parser,
    parse_config,
    resolve_device,
    run_pipeline,
    setup_logging,
    to_epub,
    _,
)

ENGINE_HELP = """\
engine selection — pick the right OCR engine for your document:

  lighton (default)  LightOnOCR-2-1B (1B VLM)
                     Best overall default. Understands document layout
                     (headings, paragraphs, lists). Produces Markdown.
                     Requires GPU. ~2 GB VRAM, ~8 s/page.

  glm                GLM-OCR (0.9B VLM)
                     Highest accuracy (94.6 OmniDocBench #1).
                     Best for tables, formulas, multi-column layouts.
                     Requires GPU. ~2.5 GB VRAM, ~5-15 s/page.

   tesseract          Tesseract (CPU-only classic OCR)
                      Lightweight, always available. Basic layout via
                      page segmentation. Works on any CPU. ~1-3 s/page.

Examples:
  python PDFToEPUB.py doc.pdf                           # lighton (default, MD + EPUB)
  python PDFToEPUB.py doc.pdf --engine glm              # GLM-OCR
  python PDFToEPUB.py doc.pdf --engine ppocrv6 --cpu    # PP-OCRv6 on CPU
  python PDFToEPUB.py doc.pdf --no-epub                 # Markdown only, skip EPUB
  python PDFToEPUB.py doc.pdf --title "Book"            # EPUB with metadata
  python PDFToEPUB.py doc.pdf --first-page 5 --last-page 10
  python PDFToEPUB.py doc.pdf --lang es                 # español
"""


# ═══════════════════════════════════════════════════════════════════════
#  Engine 1: LightOnOCR-2-1B
# ═══════════════════════════════════════════════════════════════════════

def _build_vlm_messages(image, prev_text="", max_prev_chars=600):
    """Build chat messages with optional previous-page context."""
    content = [{"type": "image", "image": image}]
    if prev_text:
        truncated = prev_text[-max_prev_chars:] if len(prev_text) > max_prev_chars else prev_text
        content.append({
            "type": "text",
            "text": f"\nContext from previous page (continue from here):\n{truncated}",
        })
    return [{"role": "user", "content": content}]


def load_lighton(cfg: PipelineConfig):
    from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor
    device = resolve_device(cfg.cpu)
    model_id = "lightonai/LightOnOCR-2-1B"
    processor = LightOnOcrProcessor.from_pretrained(model_id, trust_remote_code=True)
    model = LightOnOcrForConditionalGeneration.from_pretrained(
        model_id, torch_dtype=torch.bfloat16, trust_remote_code=True,
    ).to(device)
    model.eval()
    return processor, model

load_lighton._needs_max_h = True

def ocr_lighton(processor, model, image: Image.Image, cfg: PipelineConfig, prev_text=""):
    ratio = cfg.max_h / image.height
    img = image.resize((int(image.width * ratio), cfg.max_h), Image.LANCZOS)
    device = next(model.parameters()).device
    messages = _build_vlm_messages(img, prev_text)
    inputs = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors="pt",
    )
    inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}
    with torch.no_grad():
        ids = model.generate(
            **inputs, max_new_tokens=2048,
            repetition_penalty=1.1, no_repeat_ngram_size=3,
            do_sample=False,
        )
    text = processor.decode(ids[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    del inputs, ids
    return text


# ═══════════════════════════════════════════════════════════════════════
#  Engine 2: GLM-OCR
# ═══════════════════════════════════════════════════════════════════════

def load_glm(cfg: PipelineConfig):
    from transformers import AutoProcessor, GlmOcrForConditionalGeneration
    device = resolve_device(cfg.cpu)
    model_id = "zai-org/GLM-OCR"
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    model = GlmOcrForConditionalGeneration.from_pretrained(
        model_id, torch_dtype=torch.bfloat16, trust_remote_code=True,
    ).to(device)
    model.eval()
    return processor, model

load_glm._needs_max_h = True

def ocr_glm(processor, model, image: Image.Image, cfg: PipelineConfig, prev_text=""):
    ratio = cfg.max_h / image.height
    img = image.resize((int(image.width * ratio), cfg.max_h), Image.LANCZOS)
    device = next(model.parameters()).device
    messages = _build_vlm_messages(img, prev_text)
    inputs = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors="pt",
    )
    inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}
    with torch.no_grad():
        ids = model.generate(
            **inputs, max_new_tokens=4096, do_sample=False,
        )
    text = processor.decode(ids[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    del inputs, ids
    return text


# ═══════════════════════════════════════════════════════════════════════
#  Engine 3: Tesseract
# ═══════════════════════════════════════════════════════════════════════

LANG_MAP = {"en": "eng", "es": "spa"}

def load_tesseract(cfg: PipelineConfig):
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except ImportError:
        print("ERROR: pytesseract not installed.  Run:  pip install pytesseract")
        sys.exit(1)
    except Exception:
        print("ERROR: tesseract-ocr binary not found.  Run:  sudo apt install tesseract-ocr tesseract-ocr-spa")
        sys.exit(1)
    return None, None

def ocr_tesseract(_processor, _model, image: Image.Image, cfg: PipelineConfig, **kwargs):
    import pytesseract
    lang = LANG_MAP.get(cfg.lang, "eng")
    config = "--psm 3 --oem 3"
    try:
        text = pytesseract.image_to_string(image, lang=lang, config=config)
        return text.strip()
    except Exception as e:
        return f"[Tesseract error: {e}]"


# ═══════════════════════════════════════════════════════════════════════
#  Engine registry
# ═══════════════════════════════════════════════════════════════════════

ENGINES = {
    "lighton":   (load_lighton, ocr_lighton, "LightOnOCR-2-1B"),
    "glm":       (load_glm, ocr_glm, "GLM-OCR"),
    "tesseract": (load_tesseract, ocr_tesseract, "Tesseract"),
}


# ═══════════════════════════════════════════════════════════════════════
#  CLI + main
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = build_parser("PDFToEPUB — PDF to Markdown/EPUB (3 OCR engines)")
    # Replace --engine help so choices show properly
    parser.add_argument(
        "--engine", default="lighton",
        choices=["lighton", "glm", "tesseract"],
        help=f"OCR engine: lighton (default, balanced), glm (accuracy), ppocrv6 (speed), tesseract (CPU).\n\n{ENGINE_HELP}",
    )
    parser.epilog = ENGINE_HELP

    args = parser.parse_args()
    cfg = parse_config(args)
    cfg.engine = args.engine

    setup_logging()

    load_fn, ocr_fn, name = ENGINES[args.engine]

    if args.engine == "tesseract":
        print(_("note_raw", cfg.lang))

    md = run_pipeline(cfg, load_fn, ocr_fn)

    if cfg.epub:
        to_epub(md, title=cfg.title or Path(cfg.pdf_path).stem,
                authors=cfg.authors, lang=cfg.lang)


if __name__ == "__main__":
    main()
