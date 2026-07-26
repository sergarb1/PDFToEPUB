<!-- headroom:rtk-instructions -->
# PDFToEPUB — Project Stack & Context

## Overview
Single-script PDF → Markdown/EPUB converter with 4 pluggable OCR engines.

| Engine | `--engine` | Type | Params | VRAM | Speed |
|--------|-----------|------|--------|------|-------|
| LightOnOCR-2-1B | `lighton` (default) | VLM end-to-end | 1.0 B | ~2 GB | ~8 s/page |
| GLM-OCR | `glm` | VLM end-to-end | 0.9 B | ~2.5 GB | ~10 s/page |
| PP-OCRv6 | `ppocrv6` | Pipeline det+rec | 34.5 M | ~1 GB | <1 s/page |
| Tesseract | `tesseract` | Classic (LSTM+legacy) | — | 0 (CPU) | ~1.5 s/page |

## Files
```
PDFToEPUB/
├── PDFToEPUB.py            Entry point with --engine flag
├── PDFToEPUB_common.py     Shared pipeline (config, resume, EPUB)
├── README.md               Bilingual docs
├── AGENTS.md               This file
├── requirements.txt        Python dependencies
├── LICENSE                 GPLv3
└── .gitignore
```

## Licenses
- LightOnOCR-2-1B → Apache 2.0
- GLM-OCR → Apache 2.0
- PP-OCRv6 (PaddleOCR) → Apache 2.0
- Our code → GPLv3

## When to use which

| Situation | `--engine` |
|---|---|
| Default good balance | `lighton` (omit flag) |
| Tables, complex layout, best accuracy | `glm` |
| Plain text, speed critical | `ppocrv6` |
| CPU only, no GPU needed, always works | `tesseract` |

## Key Design Decisions

1. **LightOnOCR-2-1B as default**: 1B params, Pixtral + Mistral 3.
   Best balance of speed/quality. Fits in bf16 at ~2 GB VRAM.

2. **GLM-OCR for accuracy**: 0.9B, CogViT + GLM-0.5B. 94.62 OmniDocBench.
   Apache 2.0. ~2.5 GB VRAM.

3. **PP-OCRv6 for speed**: Pipeline OCR, 34.5M params. Beats 235B VLMs
   on pure text. No layout awareness. <1 s/page.

4. **Tesseract for CPU**: Classic OCR, always available, works on any
   machine. Basic paragraph detection. ~1.5 s/page.

5. **Image resizing (max_h=768)**: Full-res A4 pages OOM VLMs.
   Resizing to 768 px keeps patches manageable. Not needed for ppocrv6.

6. **Single script**: `PDFToEPUB.py --engine` dispatches to the right
   backend. Shared pipeline in `PDFToEPUB_common.py`.

7. **EPUB by default**: `--no-epub` to skip. Default produces .md + .epub.

## Commands

```bash
# LightOnOCR (default) → .md + .epub
python PDFToEPUB.py documento.pdf

# GLM-OCR
python PDFToEPUB.py documento.pdf --engine glm

# PP-OCRv6 (requires pip install paddleocr)
python PDFToEPUB.py documento.pdf --engine ppocrv6

# Tesseract (CPU only)
python PDFToEPUB.py documento.pdf --engine tesseract

# Markdown only
python PDFToEPUB.py documento.pdf --no-epub

# CPU mode (ppocrv6 only; VLMs very slow on CPU)
python PDFToEPUB.py documento.pdf --engine ppocrv6 --cpu

# Page range & resume
python PDFToEPUB.py documento.pdf --first-page 10 --last-page 50 --resume

# Spanish
python PDFToEPUB.py documento.pdf --lang es

# Page range & resume
python PDFToEPUB.py documento.pdf --first-page 10 --last-page 50 --resume

# Spanish
python PDFToEPUB.py documento.pdf --lang es
```

## Performance

| Engine | Sparse | Dense | Very dense | Average |
|--------|--------|-------|------------|---------|
| LightOnOCR | 4-7 s | 20-65 s | 60-130 s | ~14 s |
| GLM-OCR | 3-6 s | 15-50 s | 40-100 s | ~10 s |
| PP-OCRv6 | <0.5 s | <1 s | 1-3 s | <1 s |
| Tesseract | 0.5-2 s | 1-3 s | 2-5 s | ~1.5 s |

## Known Issues & Mitigations

| Issue | Mitigation |
|-------|------------|
| OOM on dense pages (VLM only) | Lower `--max-h` (e.g. 512) or `--dpi` (e.g. 150). |
| PP-OCRv6: paddleocr not found | `pip install paddleocr`. Falls back to CPU if GPU fails. |
| GLM-OCR: needs transformers ≥5.3.0 | `pip install "transformers>=5.3.0"`. |
| Tesseract: binary not found | `sudo apt install tesseract-ocr` |
| Tesseract: pytesseract not found | `pip install pytesseract` |
| Pandoc not installed | `sudo apt install pandoc` |
