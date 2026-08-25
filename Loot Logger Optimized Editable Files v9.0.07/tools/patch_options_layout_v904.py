#!/usr/bin/env python3
"""Use the empty Options column and bump Loot Logger v9.0.03 to v9.0.04."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def once(text: str, before: str, after: str) -> str:
    count = text.count(before)
    if count != 1:
        raise RuntimeError(f"Expected one target, found {count}: {before[:100]!r}")
    return text.replace(before, after)


def section(text: str, title: str) -> str:
    marker = f'<section class="settings-card'
    heading = f'<h3>{title}</h3>'
    heading_at = text.index(heading)
    start = text.rfind(marker, 0, heading_at)
    end = text.index('</section>', heading_at) + len('</section>')
    return text[start:end]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: patch_options_layout_v904.py INPUT.exe OUTPUT.exe")
    source, destination = map(Path, sys.argv[1:])
    executable = source.read_bytes()
    html_start = executable.find(b'<!DOCTYPE html><html lang="en"')
    html_end = executable.find(b"</html>", html_start) + len(b"</html>")
    if html_start < 0 or html_end < len(b"</html>"):
        raise RuntimeError("Packed HTML payload not found")
    original_html = executable[html_start:html_end]
    html = original_html.decode("utf-8")

    interface = section(html, "Interface")
    roster = section(html, "Bank compare roster")
    categories = section(html, "Item categories")
    sorting = section(html, "Sorting and display filters")
    current = interface + roster + categories + sorting
    right_column = (
        '<div class=settings-stack>'
        + categories.replace('class="settings-card wide"', 'class="settings-card"', 1)
        + sorting.replace('class="settings-card wide"', 'class="settings-card"', 1)
        + '</div>'
    )
    html = once(html, current, interface + right_column + roster)

    html = once(
        html,
        'Appearance, capture filters, roster and layout. Changes save automatically after a short delay.',
        'Appearance, filters, roster and layout. Press Save options when finished.',
    )

    layout_css = (
        '<style>.settings-stack{display:grid;gap:15px}'
        '.settings-stack .category-grid{grid-template-columns:repeat(2,1fr)}'
        '@media(max-width:1000px){.settings-stack .category-grid{grid-template-columns:1fr}}'
        '</style>'
    )
    html = once(
        html,
        '<style>.bank-player{content-visibility:auto}</style>',
        layout_css + '<style>.bank-player{content-visibility:auto}</style>',
    )

    # Keep the searchable Help manual consistent with the manual-save behavior.
    bootstrap_tail = (
        ".replace('Host and other-player source toggles',"
        "'Host and other-player loot always enabled')"
    )
    bootstrap_new = bootstrap_tail + (
        ".replace('Options save automatically after a short delay; Save options forces an "
        "immediate commit','Changes remain unsaved until Save options is pressed')"
        ".replace('Automatic option saving','Manual option saving')"
    )
    html = once(html, bootstrap_tail, bootstrap_new)

    html = html.replace("9.0.03", "9.0.04")
    if "v9.0.03" in html:
        raise RuntimeError("Stale frontend version remains")

    delta = len(html.encode()) - len(original_html)
    marker = html.rfind("</body></html>")
    padding = len(html[:marker]) - len(html[:marker].rstrip(" "))
    if delta > padding:
        raise RuntimeError(f"Packed payload needs {delta - padding} more bytes")
    if delta > 0:
        html = html[: marker - delta] + html[marker:]
    elif delta < 0:
        html = html[:marker] + " " * -delta + html[marker:]
    packed_html = html.encode()
    if len(packed_html) != len(original_html):
        raise RuntimeError("Embedded HTML size changed")

    patched = executable[:html_start] + packed_html + executable[html_end:]
    if patched.count(b"9.0.03") != 1:
        raise RuntimeError(f"Expected one backend version, found {patched.count(b'9.0.03')}")
    patched = patched.replace(b"9.0.03", b"9.0.04")
    if len(patched) != len(executable):
        raise RuntimeError("Executable size changed")
    destination.write_bytes(patched)
    print(f"input_sha256={hashlib.sha256(executable).hexdigest()}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")
    print("version=v9.0.04")
    print("options_right_column=item_categories,sorting_display")
    print("bank_roster=full_width")
    print(f"payload_headroom={padding - delta}")
    print(f"executable_bytes={len(patched)}")


if __name__ == "__main__":
    main()
