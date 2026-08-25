#!/usr/bin/env python3
"""Extract the packed frontend payload from a Loot Logger executable."""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path


ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%()+,-.:=?@[]^_`{|}~"


def decode_base85(data: str) -> bytes:
    if len(data) % 5:
        raise ValueError(f"packed data length is not divisible by 5: {len(data)}")
    indexes = {char: index for index, char in enumerate(ALPHABET)}
    output = bytearray()
    for offset in range(0, len(data), 5):
        value = 0
        for char in data[offset : offset + 5]:
            value = value * 85 + indexes[char]
        output.extend(value.to_bytes(4, "big"))
    return bytes(output)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: unpack_loot_logger.py INPUT.exe OUTPUT_DIR")

    exe_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    binary = exe_path.read_bytes()
    start = binary.find(b"<!DOCTYPE html>")
    close = binary.find(b"</body></html>", start)
    if start < 0 or close < 0:
        raise SystemExit("embedded HTML was not found")
    end = close + len(b"</body></html>")
    html = binary[start:end].decode("utf-8")

    style_parts = [
        match.group(1)
        for match in re.finditer(r"/\*LL835PACK:\d+:\d+:([^*]*)\*/", html)
    ]
    script_parts = {
        int(match.group(1)): match.group(2)
        for match in re.finditer(
            r"window\.__ll832Parts\[([0-9]+)\]='([^']*)'", html
        )
    }
    packed = "".join(style_parts) + "".join(
        script_parts[index] for index in sorted(script_parts)
    )

    loader_match = re.search(r"b\.slice\(0,([0-9]+)\)", html)
    if not loader_match:
        raise SystemExit("compressed payload length was not found")
    compressed_length = int(loader_match.group(1))
    raw = gzip.decompress(decode_base85(packed)[:compressed_length])
    payload = json.loads(raw)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "embedded.html").write_text(html, encoding="utf-8")
    inline_scripts = [
        match.group(1)
        for match in re.finditer(r"<script(?:\s[^>]*)?>(.*?)</script>", html, re.S)
    ]
    for index, script in enumerate(inline_scripts):
        (output_dir / f"inline-{index}.js").write_text(script, encoding="utf-8")
    (output_dir / "payload.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    for index, script in enumerate(payload.get("pre", [])):
        (output_dir / f"pre-{index}.js").write_text(script, encoding="utf-8")
    (output_dir / "app.js").write_text(payload["js"], encoding="utf-8")
    for index, style in enumerate(payload.get("styles", [])):
        (output_dir / f"style-{index}.css").write_text(style, encoding="utf-8")

    print(
        json.dumps(
            {
                "html_start": start,
                "html_end": end,
                "html_length": end - start,
                "compressed_length": compressed_length,
                "packed_length": len(packed),
                "payload_keys": sorted(payload),
                "scripts": len(payload.get("pre", [])),
                "inline_scripts": len(inline_scripts),
                "styles": len(payload.get("styles", [])),
                "app_js_length": len(payload["js"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
