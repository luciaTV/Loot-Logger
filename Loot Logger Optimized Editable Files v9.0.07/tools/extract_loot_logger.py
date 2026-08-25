#!/usr/bin/env python3
"""Recover editable assets and metadata from the Loot Logger Go executable."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

from PIL import Image


BASE85_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%()+,-.:=?@[]^_`{|}~"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def find_embedded_html(binary: bytes) -> bytes:
    candidates: list[bytes] = []
    for match in re.finditer(rb"<!doctype html", binary, flags=re.IGNORECASE):
        end = binary.lower().find(b"</html>", match.start())
        if end < 0:
            continue
        candidate = binary[match.start() : end + len(b"</html>")]
        if b"LL835PACK" in candidate and b"__ll832Parts" in candidate:
            try:
                candidate.decode("utf-8")
            except UnicodeDecodeError:
                continue
            candidates.append(candidate)
    if not candidates:
        raise RuntimeError("The packed Loot Logger HTML payload was not found")
    return max(candidates, key=len)


def decode_base85(data: str) -> bytes:
    if len(data) % 5:
        raise RuntimeError(f"Packed base85 length {len(data)} is not divisible by five")
    table = {character: index for index, character in enumerate(BASE85_ALPHABET)}
    decoded = bytearray()
    for offset in range(0, len(data), 5):
        value = 0
        for character in data[offset : offset + 5]:
            if character not in table:
                raise RuntimeError(f"Unexpected base85 character {character!r}")
            value = value * 85 + table[character]
        decoded.extend(value.to_bytes(4, "big"))
    return bytes(decoded)


def unpack_frontend(packed_html: bytes, frontend: Path) -> tuple[str, str]:
    packed_text = packed_html.decode("utf-8")
    write_text(frontend / "index.packed.html", packed_text)

    style_pattern = re.compile(
        r"<style>\s*/\*LL835PACK:\d+:\d+:([^*]*)\*/\s*</style>", re.DOTALL
    )
    style_payloads = style_pattern.findall(packed_text)
    part_matches = re.findall(
        r"window\.__ll832Parts\[(\d+)\]='([^']*)'", packed_text, flags=re.DOTALL
    )
    if not style_payloads or not part_matches:
        raise RuntimeError("Packed frontend chunks were incomplete")

    script_parts = {int(index): value for index, value in part_matches}
    encoded = "".join(style_payloads) + "".join(
        script_parts[index] for index in sorted(script_parts)
    )
    decoded = decode_base85(encoded)
    length_match = re.search(r"b\.slice\(0,(\d+)\)", packed_text)
    if not length_match:
        raise RuntimeError("Compressed payload length was not found")
    compressed_length = int(length_match.group(1))
    payload = json.loads(gzip.decompress(decoded[:compressed_length]).decode("utf-8"))

    styles = payload.get("styles", [])
    pre_scripts = payload.get("pre", [])
    app_script = payload.get("js", "")
    if not isinstance(styles, list) or not isinstance(pre_scripts, list) or not app_script:
        raise RuntimeError("Unpacked frontend JSON had an unexpected shape")

    app_css = "\n\n".join(styles)
    write_text(frontend / "styles" / "app.css", app_css)
    for index, script in enumerate(pre_scripts):
        write_text(frontend / "scripts" / f"pre-{index:02d}.js", script)
    write_text(frontend / "scripts" / "app.js", app_script)

    replaced_style = False

    def replace_style(_: re.Match[str]) -> str:
        nonlocal replaced_style
        if replaced_style:
            return ""
        replaced_style = True
        return '<link rel="stylesheet" href="styles/app.css">'

    clean_html = style_pattern.sub(replace_style, packed_text)

    script_pattern = re.compile(r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.DOTALL)
    inline_index = 0
    inline_scripts: list[str] = []

    def replace_script(match: re.Match[str]) -> str:
        nonlocal inline_index
        attrs = match.group("attrs")
        body = match.group("body")
        if "src=" in attrs:
            return match.group(0)
        if "DecompressionStream" in body and "__ll832Parts.join" in body:
            tags = [
                f'<script src="scripts/pre-{index:02d}.js"></script>'
                for index in range(len(pre_scripts))
            ]
            tags.append('<script src="scripts/app.js"></script>')
            return "".join(tags)
        if "window.__ll832Parts" in body:
            return ""
        if not body.strip():
            return ""
        filename = f"inline-{inline_index:02d}.js"
        inline_index += 1
        inline_scripts.append(body)
        write_text(frontend / "scripts" / filename, body.strip() + "\n")
        return f'<script{attrs} src="scripts/{filename}"></script>'

    clean_html = script_pattern.sub(replace_script, clean_html)
    clean_html = re.sub(r">\s*<", ">\n<", clean_html).strip() + "\n"
    write_text(frontend / "index.html", clean_html)

    metadata = {
        "packed_html_bytes": len(packed_html),
        "compressed_payload_bytes": compressed_length,
        "css_chunks": len(styles),
        "pre_scripts": len(pre_scripts),
        "inline_scripts": inline_index,
        "app_javascript_bytes": len(app_script.encode("utf-8")),
    }
    write_text(frontend / "unpack-metadata.json", json.dumps(metadata, indent=2) + "\n")
    all_scripts = "\n".join([*pre_scripts, *inline_scripts, app_script])
    return app_css, all_scripts


def extract_pngs(binary: bytes, destination: Path) -> list[dict[str, object]]:
    destination.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    search_at = 0
    sequence = 0
    while True:
        start = binary.find(PNG_SIGNATURE, search_at)
        if start < 0:
            break
        search_at = start + len(PNG_SIGNATURE)
        cursor = start + len(PNG_SIGNATURE)
        valid = True
        while cursor + 12 <= len(binary):
            length = struct.unpack(">I", binary[cursor : cursor + 4])[0]
            chunk_type = binary[cursor + 4 : cursor + 8]
            chunk_end = cursor + 12 + length
            if length > 64 * 1024 * 1024 or chunk_end > len(binary):
                valid = False
                break
            chunk_data = binary[cursor + 8 : cursor + 8 + length]
            expected_crc = struct.unpack(">I", binary[cursor + 8 + length : chunk_end])[0]
            actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
            if actual_crc != expected_crc:
                valid = False
                break
            cursor = chunk_end
            if chunk_type == b"IEND":
                break
        else:
            valid = False
        if not valid or binary[cursor - 8 : cursor - 4] != b"IEND":
            continue
        png = binary[start:cursor]
        digest = hashlib.sha256(png).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        try:
            with Image.open(io.BytesIO(png)) as image:
                width, height = image.size
                mode = image.mode
        except Exception:
            continue
        filename = f"resource-{sequence:02d}-{width}x{height}.png"
        (destination / filename).write_bytes(png)
        records.append(
            {
                "file": filename,
                "offset": start,
                "bytes": len(png),
                "width": width,
                "height": height,
                "mode": mode,
                "sha256": digest,
            }
        )
        sequence += 1
    write_text(destination / "manifest.json", json.dumps(records, indent=2) + "\n")
    return records


def run_strings(executable: Path) -> list[str]:
    result = subprocess.run(
        ["strings", "-a", "-n", "4", str(executable)],
        check=True,
        capture_output=True,
        text=True,
        errors="replace",
    )
    return result.stdout.splitlines()


def write_backend_metadata(
    executable: Path, binary: bytes, frontend_scripts: str, destination: Path
) -> dict[str, int]:
    lines = run_strings(executable)
    destination.mkdir(parents=True, exist_ok=True)

    functions = sorted(
        {
            line
            for line in lines
            if re.fullmatch(
                r"main\.(?:\(\*[A-Za-z_][A-Za-z0-9_]*\)\.)?[A-Za-z_][A-Za-z0-9_.-]*",
                line,
            )
        }
    )
    source_files = sorted(
        {line for line in lines if line.startswith("albionlootlogger/") and line.endswith(".go")}
    )
    type_names = sorted(
        set(re.findall(r"main\.[A-Za-z_][A-Za-z0-9_]*", "\n".join(lines)))
    )
    json_tags = sorted(set(re.findall(r'json:"[^"]+"', "\n".join(lines))))
    build_info = [
        line
        for line in lines
        if line.startswith(("path\t", "mod\t", "dep\t", "build\t"))
    ]
    build_info = list(dict.fromkeys(build_info))

    routes_set: set[str] = set()
    for route in re.findall(r"/api/[A-Za-z0-9_./?=&${}:-]+", frontend_scripts):
        if len(route) >= 160:
            continue
        route = route.rstrip("./")
        if "${" in route:
            route = route[: route.index("${")] + "${…}"
        routes_set.add(route)
    routes = sorted(routes_set)

    write_text(destination / "main-functions.txt", "\n".join(functions) + "\n")
    write_text(destination / "main-types.txt", "\n".join(type_names) + "\n")
    write_text(destination / "project-source-file-map.txt", "\n".join(source_files) + "\n")
    write_text(destination / "json-tags.txt", "\n".join(json_tags) + "\n")
    write_text(destination / "build-info.txt", "\n".join(build_info) + "\n")
    write_text(destination / "api-routes.txt", "\n".join(routes) + "\n")
    return {
        "functions": len(functions),
        "types": len(type_names),
        "source_files": len(source_files),
        "json_tags": len(json_tags),
        "api_routes": len(routes),
    }


def write_readme(
    destination: Path,
    executable: Path,
    binary: bytes,
    backend_counts: dict[str, int],
    png_count: int,
) -> None:
    digest = hashlib.sha256(binary).hexdigest()
    readme = f"""# Loot Logger recovered editable files

This folder was recovered from `{executable.name}`, a native Windows x86-64 Go executable.

## What is editable

- `frontend/index.html` is the unpacked, developer-friendly entry page.
- `frontend/styles/app.css` contains the decompressed CSS.
- `frontend/scripts/app.js` contains the decompressed application JavaScript.
- `frontend/scripts/inline-*.js` and `pre-*.js` contain the remaining scripts.
- `assets/` contains {png_count} valid PNG resources recovered from the executable.
- `backend-recovery/` contains the recoverable Go source-file map, function/type names,
  API routes, JSON tags, and build settings.
- `tools/extract_loot_logger.py` can repeat the extraction against another copy of the EXE.

## Important limitation

The original Go backend source code is not stored in the EXE and cannot be recovered exactly.
The files in `backend-recovery/` are metadata, not compilable Go source. The original backend
handled packet capture, Photon protocol decoding, persistence, lookups, WebView2, and HTTP APIs.
To rebuild a fully working replacement EXE, obtain the original `.go` files or reimplement those
parts using the recovered names and API inventory.

The unpacked frontend can be edited normally, but it expects the Loot Logger HTTP endpoints listed
in `backend-recovery/api-routes.txt`. Opening `frontend/index.html` by itself will not provide the
native capture backend.

## Verification

- Original EXE SHA-256: `{digest}`
- Recovered Go function names: {backend_counts['functions']}
- Recovered Go type/name entries: {backend_counts['types']}
- Recovered project source filenames: {backend_counts['source_files']}
- Recovered JSON tags: {backend_counts['json_tags']}
- Recovered API route strings: {backend_counts['api_routes']}
"""
    write_text(destination / "README.md", readme)
    write_text(destination / "original-exe.sha256", f"{digest}  {executable.name}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    executable = args.executable.resolve()
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / "tools").mkdir()
    shutil.copy2(Path(__file__).resolve(), output / "tools" / Path(__file__).name)

    binary = executable.read_bytes()
    packed_html = find_embedded_html(binary)
    _, frontend_scripts = unpack_frontend(packed_html, output / "frontend")
    pngs = extract_pngs(binary, output / "assets")
    backend_counts = write_backend_metadata(
        executable, binary, frontend_scripts, output / "backend-recovery"
    )
    write_readme(output, executable, binary, backend_counts, len(pngs))
    write_text(
        output / "recovery-summary.json",
        json.dumps(
            {
                "input": executable.name,
                "input_bytes": len(binary),
                "packed_html_bytes": len(packed_html),
                "png_resources": len(pngs),
                **backend_counts,
            },
            indent=2,
        )
        + "\n",
    )


if __name__ == "__main__":
    main()
