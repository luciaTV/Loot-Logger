#!/usr/bin/env python3
"""Give over-deposited Extra items a dedicated violet style and bump v9.0.06 to v9.0.07."""

from __future__ import annotations

import hashlib
import gzip
import json
import re
import sys
from pathlib import Path

from patch_visual_refresh_v905 import decode85, encode85, libdeflate_gzip, replace_slots


def once(text: str, before: str, after: str) -> str:
    count = text.count(before)
    if count != 1:
        raise RuntimeError(f"Expected one target, found {count}: {before[:100]!r}")
    return text.replace(before, after)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: patch_extra_color_v907.py INPUT.exe OUTPUT.exe")
    source, destination = map(Path, sys.argv[1:])
    executable = source.read_bytes()
    html_start = executable.find(b'<!DOCTYPE html><html lang="en"')
    html_end = executable.find(b"</html>", html_start) + len(b"</html>")
    if html_start < 0 or html_end < len(b"</html>"):
        raise RuntimeError("Packed HTML payload not found")
    original_html = executable[html_start:html_end]
    html = original_html.decode("utf-8")

    # The badge and the complete item card now use violet exclusively for Extra.
    html = once(
        html,
        ".bank-state.extra{background:#253b57;color:#9cc6ff}",
        ".bank-state.extra{background:#3f2858;color:#d7a8ff}",
    )
    old_cards = (
        "#bankPlayers .bank-item:is(.matched,.resolved){background:linear-gradient(135deg,#183d2a,#11261b)!important;box-shadow:inset 5px 0 #55d68a!important}"
        "#bankPlayers .bank-item.partial,#bankPlayers .bank-item.extra,#bankPlayers .bank-item.different{background:linear-gradient(135deg,#493817,#2b2414)!important;box-shadow:inset 5px 0 #f2c45e!important}"
        "#bankPlayers .bank-item.missing{background:linear-gradient(135deg,#4b2027,#29161a)!important;box-shadow:inset 5px 0 #ef6b79!important}"
    )
    new_cards = (
        ".bank-item:is(.matched,.resolved){background:#173522!important;box-shadow:inset 5px 0 #55d68a!important}"
        ".bank-item:is(.partial,.different){background:linear-gradient(135deg,#493817,#2b2414)!important;box-shadow:inset 5px 0 #f2c45e!important}"
        ".bank-item.extra{background:#2f193b!important;border-color:#b875ff!important;box-shadow:inset 5px 0 #b875ff!important}"
        ".bank-item.missing{background:linear-gradient(135deg,#4b2027,#29161a)!important;box-shadow:inset 5px 0 #ef6b79!important;}"
    )
    if len(old_cards) != len(new_cards):
        raise RuntimeError("Status CSS replacement must remain fixed-size")
    html = once(html, old_cards, new_cards)

    # Keep the original decompressed stylesheet consistent in the light theme.
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
    styles = "\n".join(payload["styles"])
    light_old = 'html[data-theme="light"].bank-state.extra{background:#e8f1ff;color:#245ca7}'
    light_new = 'html[data-theme="light"].bank-state.extra{background:#f0e3ff;color:#7138a8}'
    if styles.count(light_old) != 1:
        raise RuntimeError("Expected base Extra colour rules were not found")
    payload["styles"] = [
        style.replace(light_old, light_new)
        for style in payload["styles"]
    ]
    payload_text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    compressed = libdeflate_gzip(payload_text.encode("utf-8"))
    if len(compressed) > len(decoded):
        raise RuntimeError(
            f"Compressed frontend exceeds capacity by {len(compressed) - len(decoded)} bytes"
        )
    html = replace_slots(html, encode85(compressed + bytes(len(decoded) - len(compressed))))
    html = once(
        html,
        f"b.slice(0,{old_compressed_length})",
        f"b.slice(0,{len(compressed)})",
    )

    html = html.replace("9.0.06", "9.0.07")
    if "9.0.06" in html:
        raise RuntimeError("Stale frontend version remains")
    packed_html = html.encode("utf-8")
    if len(packed_html) != len(original_html):
        raise RuntimeError("Embedded HTML size changed")

    patched = executable[:html_start] + packed_html + executable[html_end:]
    if patched.count(b"9.0.06") != 1:
        raise RuntimeError(
            f"Expected one backend version, found {patched.count(b'9.0.06')}"
        )
    patched = patched.replace(b"9.0.06", b"9.0.07")
    if len(patched) != len(executable):
        raise RuntimeError("Executable size changed")
    destination.write_bytes(patched)

    print(f"input_sha256={hashlib.sha256(executable).hexdigest()}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")
    print("version=v9.0.07")
    print("extra_status=violet")
    print("partial_and_different=yellow")
    print(f"compressed_frontend_bytes={len(compressed)}")
    print(f"compressed_capacity_bytes={len(decoded)}")
    print(f"executable_bytes={len(patched)}")


if __name__ == "__main__":
    main()
