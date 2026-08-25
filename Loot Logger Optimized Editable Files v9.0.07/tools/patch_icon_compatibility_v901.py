#!/usr/bin/env python3
"""Add eager, dual-endpoint Albion item icons and bump v9.0.00 to v9.0.01."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def replace_exact(text: str, before: str, after: str) -> str:
    count = text.count(before)
    if count != 1:
        raise RuntimeError(f"Expected one icon renderer, found {count}")
    return text.replace(before, after)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: patch_icon_compatibility_v901.py INPUT.exe OUTPUT.exe")
    source, destination = map(Path, sys.argv[1:])
    executable = source.read_bytes()
    html_start = executable.find(b'<!DOCTYPE html><html lang="en"')
    html_end = executable.find(b"</html>", html_start) + len(b"</html>")
    if html_start < 0 or html_end < len(b"</html>"):
        raise RuntimeError("Packed HTML payload not found")
    original_html = executable[html_start:html_end]
    html = original_html.decode("utf-8")

    before = """function N(rp){const pk=String(rp?.image_url||'').trim();if(pk)return pk;const id=String(rp?.item_id||'').trim();if(!id)return '';if(/^(?:SIM_|TEST_|UNKNOWN_)/i.test(id))return'';return'https://render.albiononline.com/v1/item/'+encodeURIComponent(id).replace(/%40/gi,'@')+'.png';}function sh(Hs){const Mt=N(Hs);return Mt?`<img loading=\"lazy\" src=\"${Qa(Mt)}\" alt=\"\" onerror=\"this.replaceWith(Object.assign(document.createElement('span'),{className:'fallback-icon',textContent:'◈'}))\">`:'<span class=\"fallback-icon\">◈</span>';}"""
    after = """function N(i){let u=String(i?.image_url||'').trim(),d=String(i?.item_id||'').trim();return u||(d&&!/^(SIM_|TEST_|UNKNOWN_)/i.test(d)?'https://render.albiononline.com/v1/item/'+encodeURI(d)+'.png':'')}function sh(i){let u=N(i);return u?`<img src=\"${Qa(u)}\" onerror=\"this.src.includes('render.')?this.src=this.src.replace('render.albiononline.com/v1/item/','gameinfo.albiononline.com/api/gameinfo/items/').replace('.png','@0.png'):this.replaceWith('◈')\">`:'<span class=fallback-icon>◈</span>';}"""
    html = replace_exact(html, before, after)
    html = html.replace("9.0.00", "9.0.01")
    if "9.0.00" in html:
        raise RuntimeError("Stale frontend version remains")

    delta = len(html.encode()) - len(original_html)
    if delta > 0:
        suffix = "</body></html>"
        marker = html.rfind(suffix)
        padding = len(html[:marker]) - len(html[:marker].rstrip(" "))
        if padding < delta:
            raise RuntimeError(f"Packed payload needs {delta - padding} more bytes")
        html = html[: marker - delta] + html[marker:]
    elif delta < 0:
        html = html.replace("</body></html>", " " * -delta + "</body></html>")
    packed_html = html.encode()
    if len(packed_html) != len(original_html):
        raise RuntimeError("Embedded HTML size changed")

    patched = executable[:html_start] + packed_html + executable[html_end:]
    if patched.count(b"9.0.00") != 1:
        raise RuntimeError(f"Expected one backend version, found {patched.count(b'9.0.00')}")
    patched = patched.replace(b"9.0.00", b"9.0.01")
    if len(patched) != len(executable):
        raise RuntimeError("Executable size changed")
    destination.write_bytes(patched)
    print(f"input_sha256={hashlib.sha256(executable).hexdigest()}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")
    print("version=v9.0.01")
    print("icon_loading=eager")
    print("icon_fallback=gameinfo.albiononline.com")
    print(f"payload_headroom={-delta}")
    print(f"executable_bytes={len(patched)}")


if __name__ == "__main__":
    main()
