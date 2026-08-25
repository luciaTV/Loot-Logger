#!/usr/bin/env python3
"""Patch the embedded Loot Logger frontend without changing the PE layout."""

from __future__ import annotations

import ctypes
import gzip
import json
import re
import sys
from pathlib import Path

from unpack_loot_logger import ALPHABET, decode_base85


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def encode_base85(data: bytes) -> str:
    if len(data) % 4:
        raise ValueError("base85 input length must be divisible by four")
    result: list[str] = []
    for offset in range(0, len(data), 4):
        value = int.from_bytes(data[offset : offset + 4], "big")
        digits = [""] * 5
        for index in range(4, -1, -1):
            value, remainder = divmod(value, 85)
            digits[index] = ALPHABET[remainder]
        result.extend(digits)
    return "".join(result)


def gzip_libdeflate(data: bytes) -> bytes:
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
    if not compressor:
        raise RuntimeError("could not allocate libdeflate compressor")
    try:
        source = ctypes.create_string_buffer(data)
        bound = library.libdeflate_gzip_compress_bound(compressor, len(data))
        destination = ctypes.create_string_buffer(bound)
        size = library.libdeflate_gzip_compress(
            compressor, source, len(data), destination, bound
        )
        if not size:
            raise RuntimeError("libdeflate compression failed")
        return destination.raw[:size]
    finally:
        library.libdeflate_free_compressor(compressor)


def packed_parts(html: str) -> tuple[list[re.Match[str]], list[re.Match[str]]]:
    styles = list(
        re.finditer(r"/\*LL835PACK:\d+:\d+:([^*]*)\*/", html)
    )
    scripts = sorted(
        re.finditer(r"window\.__ll832Parts\[([0-9]+)\]='([^']*)'", html),
        key=lambda match: int(match.group(1)),
    )
    if not styles or not scripts:
        raise RuntimeError("packed frontend parts were not found")
    return styles, scripts


def unpack_payload(html: str) -> tuple[dict[str, object], int, int]:
    styles, scripts = packed_parts(html)
    packed = "".join(match.group(1) for match in styles) + "".join(
        match.group(2) for match in scripts
    )
    length_match = re.search(r"b\.slice\(0,([0-9]+)\)", html)
    if not length_match:
        raise RuntimeError("compressed payload length was not found")
    compressed_length = int(length_match.group(1))
    decoded = decode_base85(packed)
    return json.loads(gzip.decompress(decoded[:compressed_length])), len(packed), len(decoded)


def patch_core(html: str) -> str:
    html = replace_once(
        html,
        "function D(){if(!j)return;const z=",
        "function D(){if(!j)return;const y=scrollY,z=",
        "capture vertical scroll before the main refresh",
    )
    html = replace_once(
        html,
        "else if(z==='loot'&&n-(D.l||0)>1000)D.l=n,fa()}function sa",
        "else if(z==='loot'&&n-(D.l||0)>1000)D.l=n,fa();requestAnimationFrame(()=>scrollTo(0,y))}function sa",
        "restore vertical scroll after the main refresh",
    )
    resolve_start = html.find("if(b.dataset.resolveBankPlayer){let n=")
    resolve_end = html.find(
        "e.stopPropagation();const k=S(b.dataset.proIgnore)", resolve_start
    )
    if resolve_start < 0 or resolve_end < 0:
        raise RuntimeError("legacy Resolve user handler was not found")
    html = (
        html[:resolve_start]
        + "if(b.dataset.resolveBankPlayer){window.__llResolveBankUser?.(b.dataset.resolveBankPlayer);return}"
        + html[resolve_end:]
    )
    html = replace_once(
        html,
        "const va0=va;va=function(force=false){const signature=bankRenderSignature();",
        "const va0=va;va=function(force=false){let y=scrollY;const signature=bankRenderSignature();",
        "capture vertical scroll before direct bank redraws",
    )
    html = replace_once(
        html,
        "p.bankSort,p.filters,Object.keys(p.prices||{}).length,h]",
        "p.bankSort,p.filters,[...p.resolved].sort(),Object.keys(p.prices||{}).length,h]",
        "include manual resolution state in the bank render signature",
    )
    html = replace_once(
        html,
        "if(t)t.textContent=`${C.rows||0} rows · ${n} files`}};const vb0=vb;",
        "if(t)t.textContent=`${C.rows||0} rows · ${n} files`}requestAnimationFrame(()=>scrollTo(0,y))};const vb0=vb;",
        "restore vertical scroll after direct bank redraws",
    )
    return html


def patch_app(app: str) -> str:
    validation_start = app.find("function renderValidation(){")
    validation_end = app.find("function sessionEvents", validation_start)
    if validation_start < 0 or validation_end < 0:
        raise RuntimeError("hidden validation renderer was not found")
    app = (
        app[:validation_start]
        + "function renderValidation(){return[]}"
        + app[validation_end:]
    )
    app = replace_once(
        app,
        "return t.native||[j?.session_id||'current',N(t.p),N(t.i?.item_id||t.i?.item_name),Number(t.i?.bank_enchantment||ench(t.i)||0)].join('|')",
        "return t.native||[N(t.p),N(t.i?.item_id||t.i?.item_name),Number(t.i?.bank_enchantment||ench(t.i)||0)].join('|')",
        "use the native three-part resolution key",
    )
    app = replace_once(
        app,
        "function refreshBank80(){try{lastBankRenderSignature=''}catch{}try{j=w(j)}catch{}try{D()}catch{}try{va(true)}catch{}try{renderBank80()}catch{}}",
        "function refreshBank80(){let y=scrollY;try{lastBankRenderSignature=''}catch{}try{j=w(j)}catch{}try{va(true)}catch{}try{renderBank80()}catch{}requestAnimationFrame(()=>scrollTo(0,y))}",
        "avoid duplicate bank rendering and retain vertical scroll",
    )

    resolver = (
        "function resolveBankUser80(name){let p=owa(Sa(j?.settings||{},j?.game||{})).find(x=>N(x.name)===N(name)),"
        "a=(p?.items||[]).map(i=>({p:p.name,i,k:key(p.name,i),itemType:N(i.item_id||i.item_name)}))"
        ".filter(t=>/^(missing|partial|different|extra|resolved)$/.test(bankEdits[t.k]?.status||t.i.bank_status)),"
        "on=a.some(t=>(bankEdits[t.k]?.status||t.i.bank_status)!=='resolved');"
        "setBankTargets80(a,on?'resolved':'reset',on?'Resolved user — treated as deposited':'')}\n"
    )
    app = replace_once(
        app,
        "\nfunction showAllPlayers80(){",
        "\n" + resolver + "function showAllPlayers80(){",
        "add complete Resolve user state transition",
    )
    app = replace_once(
        app,
        "window.__llSetBankTargets=setBankTargets80;window.ALL80API=",
        "window.__llSetBankTargets=setBankTargets80;window.__llResolveBankUser=resolveBankUser80;window.ALL80API=",
        "expose the Resolve user state transition",
    )
    return app


def repack_payload(html: str, payload: dict[str, object], packed_length: int, capacity: int) -> tuple[str, int]:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    compressed = gzip_libdeflate(raw)
    if len(compressed) > capacity:
        raise RuntimeError(
            f"patched payload is {len(compressed)} bytes but capacity is {capacity}"
        )
    padded = compressed + bytes(capacity - len(compressed))
    encoded = encode_base85(padded)
    if len(encoded) != packed_length:
        raise RuntimeError("repacked base85 length changed")

    styles, scripts = packed_parts(html)
    matches: list[tuple[re.Match[str], int]] = [
        *((match, 1) for match in styles),
        *((match, 2) for match in scripts),
    ]
    cursor = 0
    replacements: list[tuple[int, int, str]] = []
    for match, group_index in matches:
        start, end = match.span(group_index)
        length = end - start
        replacements.append((start, end, encoded[cursor : cursor + length]))
        cursor += length
    if cursor != len(encoded):
        raise RuntimeError("packed part lengths do not cover the payload")
    for start, end, replacement in reversed(replacements):
        html = html[:start] + replacement + html[end:]

    html = replace_once(
        html,
        re.search(r"b\.slice\(0,[0-9]+\)", html).group(0),
        f"b.slice(0,{len(compressed)})",
        "update compressed payload length",
    )
    return html, len(compressed)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_loot_logger.py INPUT.exe OUTPUT.exe")

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    binary = input_path.read_bytes()
    html_start = binary.find(b"<!DOCTYPE html>")
    close = binary.find(b"</body></html>", html_start)
    if html_start < 0 or close < 0:
        raise RuntimeError("embedded frontend was not found")
    slot_end = close + len(b"</body></html>")
    while slot_end < len(binary) and binary[slot_end] == 0x20:
        slot_end += 1
    original_slot_length = slot_end - html_start
    html = binary[html_start:slot_end].decode("utf-8").rstrip(" ")

    payload, packed_length, capacity = unpack_payload(html)
    html = patch_core(html)
    payload["js"] = patch_app(str(payload["js"]))
    html, compressed_length = repack_payload(
        html, payload, packed_length, capacity
    )
    html = replace_once(html, "'9.0.12'", "'9.0.13'", "bump frontend version")

    encoded_html = html.encode("utf-8")
    if len(encoded_html) > original_slot_length:
        raise RuntimeError(
            f"patched HTML exceeds its PE slot by {len(encoded_html) - original_slot_length} bytes"
        )
    replacement = encoded_html + b" " * (original_slot_length - len(encoded_html))
    patched = binary[:html_start] + replacement + binary[slot_end:]
    if len(patched) != len(binary) or patched[:2] != b"MZ":
        raise RuntimeError("PE layout validation failed")

    verify_html = patched[html_start:slot_end].decode("utf-8").rstrip(" ")
    verify_payload, verify_packed_length, verify_capacity = unpack_payload(verify_html)
    if verify_payload["js"] != payload["js"]:
        raise RuntimeError("repacked application JavaScript did not round-trip")
    if (verify_packed_length, verify_capacity) != (packed_length, capacity):
        raise RuntimeError("packed payload geometry changed")
    required = [
        "window.__llResolveBankUser=resolveBankUser80",
        "[...p.resolved].sort()",
        "requestAnimationFrame(()=>scrollTo(0,y))",
        "function renderValidation(){return[]}",
        "'9.0.13'",
    ]
    for marker in required:
        if marker not in verify_html and marker not in str(verify_payload["js"]):
            raise RuntimeError(f"verification marker is missing: {marker}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(patched)
    print(
        json.dumps(
            {
                "output": str(output_path),
                "file_size": len(patched),
                "html_slot": original_slot_length,
                "html_used": len(encoded_html),
                "html_spare": original_slot_length - len(encoded_html),
                "payload_capacity": capacity,
                "payload_compressed": compressed_length,
                "payload_spare": capacity - compressed_length,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
