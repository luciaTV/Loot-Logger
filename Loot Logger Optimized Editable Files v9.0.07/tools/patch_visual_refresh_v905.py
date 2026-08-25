#!/usr/bin/env python3
"""Apply the v9.0.05 visual refresh to the packed Loot Logger executable."""

from __future__ import annotations

import ctypes
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

BASE85 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%()+,-.:=?@[]^_`{|}~"


def decode85(value: str) -> bytes:
    table = {character: index for index, character in enumerate(BASE85)}
    output = bytearray()
    for offset in range(0, len(value), 5):
        number = 0
        for character in value[offset : offset + 5]:
            number = number * 85 + table[character]
        output.extend(number.to_bytes(4, "big"))
    return bytes(output)


def encode85(value: bytes) -> str:
    if len(value) % 4:
        raise RuntimeError("Base85 input must be divisible by four")
    output: list[str] = []
    for offset in range(0, len(value), 4):
        number = int.from_bytes(value[offset : offset + 4], "big")
        digits = [""] * 5
        for index in range(4, -1, -1):
            number, digit = divmod(number, 85)
            digits[index] = BASE85[digit]
        output.extend(digits)
    return "".join(output)


def libdeflate_gzip(value: bytes) -> bytes:
    library = ctypes.CDLL("libdeflate.so.0")
    library.libdeflate_alloc_compressor.argtypes = [ctypes.c_int]
    library.libdeflate_alloc_compressor.restype = ctypes.c_void_p
    library.libdeflate_gzip_compress_bound.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    library.libdeflate_gzip_compress_bound.restype = ctypes.c_size_t
    library.libdeflate_gzip_compress.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_size_t,
    ]
    library.libdeflate_gzip_compress.restype = ctypes.c_size_t
    library.libdeflate_free_compressor.argtypes = [ctypes.c_void_p]
    compressor = library.libdeflate_alloc_compressor(12)
    try:
        capacity = library.libdeflate_gzip_compress_bound(compressor, len(value))
        source = ctypes.create_string_buffer(value)
        destination = ctypes.create_string_buffer(capacity)
        size = library.libdeflate_gzip_compress(
            compressor, source, len(value), destination, capacity
        )
        if not size:
            raise RuntimeError("libdeflate could not compress the frontend")
        return destination.raw[:size]
    finally:
        library.libdeflate_free_compressor(compressor)


def remove_decorative_svg_rules(css: str) -> tuple[str, int]:
    pattern = re.compile(r"[^{}]+\{[^{}]*background-image:url\(\"data:image/svg\+xml[^{}]*\}")
    matches = list(pattern.finditer(css))
    if len(matches) != 5:
        raise RuntimeError(f"Expected five decorative SVG rules, found {len(matches)}")
    removed = sum(len(match.group()) for match in matches)
    css = pattern.sub("", css)
    obsolete = (
        r'html\[data-theme\]:not\(\[data-theme="light"\]\):not\(\[data-theme="dark"\]\)body\{[^{}]*\}',
        r'@media\(max-width:1280px\)\{html\[data-theme\]body\{[^{}]*\}\}',
        r'@media\(max-width:980px\)\{html\[data-theme\]body\{[^{}]*\}\}',
    )
    for expression in obsolete:
        css, count = re.subn(expression, "", css)
        if count != 1:
            raise RuntimeError(f"Expected one obsolete theme rule, found {count}")
    return css, removed


def replace_slots(text: str, encoded: str) -> str:
    style_pattern = re.compile(
        r"(?P<prefix><style>\s*/\*LL835PACK:\d+:\d+:)(?P<data>[^*]*)(?P<suffix>\*/\s*</style>)",
        re.DOTALL,
    )
    part_pattern = re.compile(
        r"(?P<prefix>window\.__ll832Parts\[\d+\]=')(?P<data>[^']*)(?P<suffix>')",
        re.DOTALL,
    )
    style_slots = list(style_pattern.finditer(text))
    part_slots = sorted(
        part_pattern.finditer(text),
        key=lambda match: int(re.search(r"\[(\d+)\]", match.group("prefix")).group(1)),
    )
    logical_slots = [*style_slots, *part_slots]
    lengths = [len(match.group("data")) for match in logical_slots]
    if sum(lengths) != len(encoded):
        raise RuntimeError("Packed slot capacity changed")
    cursor = 0
    replacements: dict[tuple[int, int], str] = {}
    for match, length in zip(logical_slots, lengths):
        replacements[(match.start("data"), match.end("data"))] = encoded[cursor : cursor + length]
        cursor += length
    slots = sorted(logical_slots, key=lambda match: match.start("data"))
    output: list[str] = []
    previous = 0
    for match in slots:
        output.append(text[previous : match.start("data")])
        output.append(replacements[(match.start("data"), match.end("data"))])
        previous = match.end("data")
    output.append(text[previous:])
    return "".join(output)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: patch_visual_refresh_v905.py INPUT.exe OUTPUT.exe REFRESH.css")
    source, destination, css_path = map(Path, sys.argv[1:])
    executable = source.read_bytes()
    html_start = executable.find(b'<!DOCTYPE html><html lang="en"')
    html_end = executable.find(b"</html>", html_start) + len(b"</html>")
    if html_start < 0 or html_end < len(b"</html>"):
        raise RuntimeError("Packed HTML payload not found")
    original_html = executable[html_start:html_end]
    html = original_html.decode("utf-8")

    style_payloads = re.findall(
        r"<style>\s*/\*LL835PACK:\d+:\d+:([^*]*)\*/\s*</style>", html, re.DOTALL
    )
    part_payloads = {
        int(index): value
        for index, value in re.findall(
            r"window\.__ll832Parts\[(\d+)\]='([^']*)'", html, re.DOTALL
        )
    }
    encoded = "".join(style_payloads) + "".join(
        part_payloads[index] for index in sorted(part_payloads)
    )
    decoded = decode85(encoded)
    length_match = re.search(r"b\.slice\(0,(\d+)\)", html)
    if not length_match:
        raise RuntimeError("Compressed payload length not found")
    old_compressed_length = int(length_match.group(1))
    payload = json.loads(gzip.decompress(decoded[:old_compressed_length]).decode("utf-8"))

    payload["styles"][-1], removed = remove_decorative_svg_rules(payload["styles"][-1])
    refresh = css_path.read_text(encoding="utf-8").strip().replace("\n", "")
    payload["styles"].append(refresh)
    payload_text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    payload_text = payload_text.replace("9.0.04", "9.0.05")
    compressed = libdeflate_gzip(payload_text.encode("utf-8"))
    if len(compressed) > len(decoded):
        raise RuntimeError(
            f"Compressed frontend exceeds capacity by {len(compressed) - len(decoded)} bytes"
        )
    padded = compressed + bytes(len(decoded) - len(compressed))
    html = replace_slots(html, encode85(padded))
    html = html.replace(
        f"b.slice(0,{old_compressed_length})", f"b.slice(0,{len(compressed)})", 1
    )
    html = html.replace("9.0.04", "9.0.05")
    if len(html.encode("utf-8")) != len(original_html):
        raise RuntimeError("Embedded HTML size changed")

    patched = executable[:html_start] + html.encode("utf-8") + executable[html_end:]
    if patched.count(b"9.0.04") != 1:
        raise RuntimeError(
            f"Expected one backend version, found {patched.count(b'9.0.04')}"
        )
    patched = patched.replace(b"9.0.04", b"9.0.05")
    if len(patched) != len(executable):
        raise RuntimeError("Executable size changed")
    destination.write_bytes(patched)

    print(f"input_sha256={hashlib.sha256(executable).hexdigest()}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")
    print("version=v9.0.05")
    print(f"visual_css_bytes={len(refresh.encode('utf-8'))}")
    print(f"decorative_svg_bytes_removed={removed}")
    print(f"compressed_frontend_bytes={len(compressed)}")
    print(f"compressed_capacity_bytes={len(decoded)}")
    print(f"executable_bytes={len(patched)}")


if __name__ == "__main__":
    main()
