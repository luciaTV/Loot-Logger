#!/usr/bin/env python3
"""Add dependency warnings and bump Loot Logger v9.0.01 to v9.0.02."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def once(text: str, before: str, after: str) -> str:
    if text.count(before) != 1:
        raise RuntimeError(f"Expected one match, found {text.count(before)}: {before[:80]!r}")
    return text.replace(before, after)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: patch_runtime_requirements_v902.py INPUT.exe OUTPUT.exe")
    source, destination = map(Path, sys.argv[1:])
    executable = source.read_bytes()
    html_start = executable.find(b'<!DOCTYPE html><html lang="en"')
    html_end = executable.find(b"</html>", html_start) + len(b"</html>")
    if html_start < 0 or html_end < len(b"</html>"):
        raise RuntimeError("Packed HTML payload not found")
    original_html = executable[html_start:html_end]
    html = original_html.decode("utf-8")

    # Apply these small edits after the packed application is decompressed. This lets the
    # original highly-optimized gzip stream remain byte-for-byte intact.
    old_transform = ".replaceAll('8.3.70','9.0.01')"
    new_transform = (
        ".replaceAll('8.3.70','9.0.02')"
        ".replace('incompatible)/i','incompatible|old|outdated)/i')"
        ".replace('could not be started or loaded','is missing, incompatible, or outdated')"
    )
    html = once(html, old_transform, new_transform)

    # WebView2 cannot show an HTML warning when it is completely absent, so the native
    # startup dialog handles that case. Once a runtime launches, its Edge major version is
    # available in the user agent and can be checked before normal use.
    old_tail = "h(j.js)})()"
    new_tail = (
        "h(j.js);let v=+(navigator.userAgent.match(/Edg\\/(\\d+)/)?.[1]||0);"
        "v&&v<109&&confirm('WebView2 '+v+' is outdated. Update Microsoft Edge WebView2, "
        "then restart Loot Logger.\\n\\nOpen download page?')&&"
        "open('https://developer.microsoft.com/microsoft-edge/webview2','_blank')})()"
    )
    html = once(html, old_tail, new_tail)

    # Reclaim fixed-payload space from optional background-timer presentation only.
    for before, after in (
        (' aria-label="Background change interval"', ''),
        (' aria-label="Background change interval unit"', ''),
        (' step=1', ''),
        (';align-items:center;padding-top:10px;margin-top:2px;border-top:1px solid var(--line)', ''),
        ('.llbg-auto-label{display:flex;align-items:center;gap:9px;min-width:0;color:var(--text)}',
         '.llbg-auto-label{display:flex;gap:9px}'),
        ('.llbg-auto-label input{accent-color:var(--gold);width:16px;height:16px}',
         '.llbg-auto-label input{accent-color:var(--gold)}'),
        ('.llbg-auto-label span{display:flex;flex-direction:column;min-width:0}',
         '.llbg-auto-label span{display:grid}'),
        ('width:100%;height:31px;box-sizing:border-box;', ''),
        ('.llbg-auto-label small{color:var(--muted);font-size:9px}',
         '.llbg-auto-label small{font-size:9px}'),
        ('border-radius:8px;background:var(--panel2);color:var(--text);padding:4px 7px}',
         'background:var(--panel2);color:var(--text);padding:4px}'),
    ):
        html = once(html, before, after)

    html = html.replace("9.0.01", "9.0.02")
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
    old_native = (
        b"Microsoft Edge WebView2 Runtime was not found. Install or repair the Evergreen "
        b"WebView2 Runtime and start the logger again"
    )
    new_native = (
        b"Microsoft Edge WebView2 Runtime is missing or damaged. Install or update Evergreen "
        b"WebView2, then restart the Loot Logger."
    )
    if len(old_native) != len(new_native) or patched.count(old_native) != 1:
        raise RuntimeError("Native WebView2 startup message was not uniquely patchable")
    patched = patched.replace(old_native, new_native)
    if patched.count(b"9.0.01") != 1:
        raise RuntimeError(f"Expected one backend version, found {patched.count(b'9.0.01')}")
    patched = patched.replace(b"9.0.01", b"9.0.02")
    if len(patched) != len(executable):
        raise RuntimeError("Executable size changed")
    destination.write_bytes(patched)
    print(f"input_sha256={hashlib.sha256(executable).hexdigest()}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")
    print("version=v9.0.02")
    print("npcap_warning=missing,incompatible,outdated")
    print("webview2_minimum_major=109")
    print(f"executable_bytes={len(patched)}")


if __name__ == "__main__":
    main()
