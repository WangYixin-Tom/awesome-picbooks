#!/usr/bin/env python3
"""
Picture-book OCR pipeline:
1) list and naturally sort images in a book directory
2) run Vision OCR (Swift script) once
3) build plain story text with page headers
4) build page-turn narration text

This script is intentionally deterministic and reusable so the skill does not need
to rewrite OCR scripts each run.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff"}


def natural_key(name: str):
    parts = re.split(r"(\d+)", name)
    key = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.lower())
    return key


def list_images(book_dir: Path) -> List[Path]:
    files = [
        p
        for p in book_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]
    return sorted(files, key=lambda p: natural_key(p.name))


def parse_swift_output(raw: str) -> Dict[str, str]:
    """Parse output format from vision_ocr.swift.

    ===FILE===\t<abs_path>
    <ocr text>
    ===END===
    """
    out: Dict[str, str] = {}
    current_file = None
    buf: List[str] = []

    for line in raw.splitlines():
        if line.startswith("===FILE===\t"):
            current_file = line.split("\t", 1)[1].strip()
            buf = []
            continue

        if line.strip() == "===END===":
            if current_file is not None:
                out[current_file] = "\n".join(buf).strip()
            current_file = None
            buf = []
            continue

        if current_file is not None:
            buf.append(line.rstrip())

    return out


def normalize_ocr_text(text: str) -> str:
    if not text or text.strip() == "[OCR_EMPTY]":
        return "[本页无文字]"

    lines = [ln.strip() for ln in text.splitlines()]

    # trim leading/trailing empty lines
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()

    # collapse repeated blank lines
    compact: List[str] = []
    prev_empty = False
    for ln in lines:
        is_empty = ln == ""
        if is_empty and prev_empty:
            continue
        compact.append(ln)
        prev_empty = is_empty

    result = "\n".join(compact).strip()
    return result if result else "[本页无文字]"


def write_plain(path: Path, page_texts: List[str]) -> None:
    chunks: List[str] = []
    for idx, text in enumerate(page_texts, start=1):
        chunks.append(f"第 {idx} 页")
        chunks.append(text)
        chunks.append("")
    path.write_text("\n".join(chunks).rstrip() + "\n", encoding="utf-8")


def write_page_turn(path: Path, page_texts: List[str], page_turn_text: str) -> None:
    body = f"\n\n{page_turn_text}\n\n".join(page_texts)
    path.write_text(body.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reusable OCR pipeline for picture books")
    parser.add_argument("--book-dir", required=True, help="Book image directory")
    parser.add_argument("--plain-out", required=True, help="Output path: plain story text")
    parser.add_argument("--turn-out", required=True, help="Output path: page-turn version")
    parser.add_argument(
        "--page-turn-text",
        default="请翻到下一页。",
        help="Page-turn prompt text (default: 请翻到下一页。)",
    )
    parser.add_argument(
        "--swift-script",
        default=str(Path(__file__).with_name("vision_ocr.swift")),
        help="Path to vision_ocr.swift",
    )
    parser.add_argument(
        "--raw-ocr-out",
        default="",
        help="Optional path to save raw OCR output",
    )
    parser.add_argument(
        "--meta-out",
        default="",
        help="Optional path to save metadata JSON",
    )
    parser.add_argument(
        "--dedupe-consecutive",
        action="store_true",
        help="Remove consecutive pages whose normalized OCR text is exactly identical",
    )

    args = parser.parse_args()

    book_dir = Path(args.book_dir).expanduser().resolve()
    plain_out = Path(args.plain_out).expanduser().resolve()
    turn_out = Path(args.turn_out).expanduser().resolve()
    swift_script = Path(args.swift_script).expanduser().resolve()

    if not book_dir.exists() or not book_dir.is_dir():
        raise SystemExit(f"book dir not found: {book_dir}")
    if not swift_script.exists():
        raise SystemExit(f"swift script not found: {swift_script}")

    images = list_images(book_dir)
    if not images:
        raise SystemExit(f"no image files found in: {book_dir}")

    cmd = ["swift", str(swift_script), *[str(p) for p in images]]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"swift OCR failed with code {proc.returncode}")

    raw = proc.stdout
    if args.raw_ocr_out:
        raw_path = Path(args.raw_ocr_out).expanduser().resolve()
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw, encoding="utf-8")

    file_to_text = parse_swift_output(raw)

    page_texts: List[str] = []
    original_pages = []
    for idx, img in enumerate(images, start=1):
        ocr_text = normalize_ocr_text(file_to_text.get(str(img), ""))
        page_texts.append(ocr_text)
        original_pages.append({"index": idx, "image": str(img), "text": ocr_text})

    removed_duplicates = []
    if args.dedupe_consecutive:
        deduped = []
        deduped_meta = []
        for page in original_pages:
            if deduped and deduped[-1] == page["text"]:
                removed_duplicates.append(page)
                continue
            deduped.append(page["text"])
            deduped_meta.append(page)
        page_texts = deduped
        original_pages = deduped_meta

    plain_out.parent.mkdir(parents=True, exist_ok=True)
    turn_out.parent.mkdir(parents=True, exist_ok=True)

    write_plain(plain_out, page_texts)
    write_page_turn(turn_out, page_texts, args.page_turn_text)

    meta = {
        "book_dir": str(book_dir),
        "image_count": len(images),
        "page_count": len(page_texts),
        "page_turn_count": max(0, len(page_texts) - 1),
        "first_image": images[0].name,
        "last_image": images[-1].name,
        "plain_out": str(plain_out),
        "turn_out": str(turn_out),
        "dedupe_consecutive": args.dedupe_consecutive,
        "removed_duplicates": [
            {"original_index": p["index"], "image": p["image"]} for p in removed_duplicates
        ],
    }

    if args.meta_out:
        meta_path = Path(args.meta_out).expanduser().resolve()
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
