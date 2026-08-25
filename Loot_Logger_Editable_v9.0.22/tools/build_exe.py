#!/usr/bin/env python3
"""Rebuild Loot Logger from the editable frontend files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from patch_loot_logger import repack_payload, unpack_payload


EDITABLE_INLINE_SCRIPTS = (0, 1, 10)


def numbered_files(directory: Path, prefix: str, suffix: str) -> list[Path]:
    files = list(directory.glob(f"{prefix}-*{suffix}"))
    return sorted(files, key=lambda path: int(path.stem.split("-")[-1]))


def replace_inline_scripts(html: str, source_dir: Path) -> str:
    matches = list(re.finditer(r"<script(?:\s[^>]*)?>(.*?)</script>", html, re.S))
    replacements: list[tuple[int, int, str]] = []
    for index in EDITABLE_INLINE_SCRIPTS:
        path = source_dir / f"inline-{index}.js"
        if index >= len(matches) or not path.exists():
            raise RuntimeError(f"editable inline script is missing: {path.name}")
        replacements.append((*matches[index].span(1), path.read_text(encoding="utf-8")))
    for start, end, replacement in reversed(replacements):
        html = html[:start] + replacement + html[end:]
    return html


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: build_exe.py TEMPLATE.exe SOURCE_DIR OUTPUT.exe")

    template_path = Path(sys.argv[1])
    source_dir = Path(sys.argv[2])
    output_path = Path(sys.argv[3])
    binary = template_path.read_bytes()
    html_start = binary.find(b"<!DOCTYPE html>")
    close = binary.find(b"</body></html>", html_start)
    if html_start < 0 or close < 0:
        raise RuntimeError("embedded frontend was not found in the template")
    slot_end = close + len(b"</body></html>")
    while slot_end < len(binary) and binary[slot_end] == 0x20:
        slot_end += 1
    slot_length = slot_end - html_start

    html = (source_dir / "embedded.html").read_text(encoding="utf-8")
    html = replace_inline_scripts(html, source_dir)
    payload, packed_length, capacity = unpack_payload(html)

    pre_files = numbered_files(source_dir, "pre", ".js")
    style_files = numbered_files(source_dir, "style", ".css")
    payload["pre"] = [path.read_text(encoding="utf-8") for path in pre_files]
    payload["styles"] = [path.read_text(encoding="utf-8") for path in style_files]
    payload["js"] = (source_dir / "app.js").read_text(encoding="utf-8")
    html, compressed_length = repack_payload(html, payload, packed_length, capacity)

    encoded_html = html.encode("utf-8")
    if len(encoded_html) > slot_length:
        raise RuntimeError(
            f"frontend exceeds the executable slot by {len(encoded_html) - slot_length} bytes"
        )
    replacement = encoded_html + b" " * (slot_length - len(encoded_html))
    rebuilt = binary[:html_start] + replacement + binary[slot_end:]
    if len(rebuilt) != len(binary) or rebuilt[:2] != b"MZ":
        raise RuntimeError("rebuilt Windows executable failed layout validation")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(rebuilt)
    print(
        json.dumps(
            {
                "output": str(output_path),
                "file_size": len(rebuilt),
                "html_spare": slot_length - len(encoded_html),
                "payload_spare": capacity - compressed_length,
                "pre_scripts": len(pre_files),
                "styles": len(style_files),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
