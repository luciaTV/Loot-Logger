#!/usr/bin/env python3
"""Preserve player position, suppress redundant renders, and retain bank-only extras."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def once(text: str, before: str, after: str) -> str:
    count = text.count(before)
    if count != 1:
        raise RuntimeError(f"Expected one target, found {count}: {before[:100]!r}")
    return text.replace(before, after)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: patch_bank_stability_v906.py INPUT.exe OUTPUT.exe")
    source, destination = map(Path, sys.argv[1:])
    executable = source.read_bytes()
    html_start = executable.find(b'<!DOCTYPE html><html lang="en"')
    html_end = executable.find(b"</html>", html_start) + len(b"</html>")
    if html_start < 0 or html_end < len(b"</html>"):
        raise RuntimeError("Packed HTML payload not found")
    original_html = executable[html_start:html_end]
    html = original_html.decode("utf-8")

    # Restore the same document scroll offset immediately after a player-only rerender.
    html = once(
        html,
        "ab();fa()}));Yd.querySelectorAll('[data-fp]'",
        "ab();let y=scrollY;fa();scroll(0,y)}));Yd.querySelectorAll('[data-fp]'",
    )
    html = once(
        html,
        "ya();va()}));Ad.querySelectorAll('[data-bfp]'",
        "ya();let y=scrollY;va();scroll(0,y)}));Ad.querySelectorAll('[data-bfp]'",
    )

    # Coalesce bursty updates and make the fallback state poll less intrusive.
    html = once(
        html,
        "setTimeout(()=>{Xc.t=0;D()},150)",
        "setTimeout(()=>{Xc.t=0;D()},500)",
    )
    html = once(html, "setInterval(rj,10000)", "setInterval(rj,30000)")
    html = once(
        html,
        "events.addEventListener('state',lr=>{if(window.AlbionTestMode?.active)return;j=w(JSON.parse(lr.data));Xc();});",
        "events.addEventListener('state',lr=>{if(window.AlbionTestMode?.active)return;let v=JSON.parse(lr.data),q=[v.total_quantity,v.unique_items,v.bank?.imported_at,v.capture?.state]+'';if(q===events._s)return;events._s=q;j=w(v);Xc();});",
    )

    # Bank-only rows are Extra even when a custom tracked roster does not include the depositor.
    html = once(
        html,
        "function wa(x){const l=x||[],r=window.__llRoster;if(r)return l.filter(r);if(!C?.players)return l;return l.filter(p=>C.players[y(p.name)])}",
        "function wa(x){const l=x||[],r=window.__llRoster;if(r)return l.filter(p=>r(p)||p.items?.some(i=>i.is_bank_only));if(!C?.players)return l;return l.filter(p=>C.players[y(p.name)])}",
    )
    html = once(
        html,
        "function Fd($j){const ae=j?.settings||{};if(!yb($j)||!ae.show_loot_toasts)return false;const xp=String(j?.game?.character||'');const Bk=xp&&String($j.looted_by||'').toLowerCase()===xp.toLowerCase();return wb(ae,G($j));}",
        "function Fd(x){return yb(x)&&j?.settings?.show_loot_toasts&&wb(j.settings,G(x))}",
    )

    # Reclaim eight harmless whitespace bytes so the packed resource remains fixed-size.
    html = once(html, "test(Qh)   &&", "test(Qh) &&")
    html = once(html, "</script>   <style>.settings-stack", "</script><style>.settings-stack")
    html = once(html, ";;", ";")
    if html.count("} function") != 3 or "} \nfunction" not in html:
        raise RuntimeError("Expected whitespace-minification targets")
    html = html.replace("} function", "}function")
    html = html.replace("} \nfunction", "};function", 1)

    html = html.replace("9.0.05", "9.0.06")
    if "9.0.05" in html:
        raise RuntimeError("Stale frontend version remains")

    delta = len(html.encode("utf-8")) - len(original_html)
    marker = html.rfind("</body></html>")
    padding = len(html[:marker]) - len(html[:marker].rstrip(" "))
    if delta > padding:
        raise RuntimeError(f"Packed payload needs {delta - padding} more bytes")
    if delta > 0:
        html = html[: marker - delta] + html[marker:]
    elif delta < 0:
        html = html[:marker] + " " * -delta + html[marker:]
    packed_html = html.encode("utf-8")
    if len(packed_html) != len(original_html):
        raise RuntimeError("Embedded HTML size changed")

    patched = executable[:html_start] + packed_html + executable[html_end:]
    if patched.count(b"9.0.05") != 1:
        raise RuntimeError(
            f"Expected one backend version, found {patched.count(b'9.0.05')}"
        )
    patched = patched.replace(b"9.0.05", b"9.0.06")
    if len(patched) != len(executable):
        raise RuntimeError("Executable size changed")
    destination.write_bytes(patched)

    print(f"input_sha256={hashlib.sha256(executable).hexdigest()}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")
    print("version=v9.0.06")
    print("collapse_scroll=preserved")
    print("state_render=change_only,500ms_coalescing")
    print("fallback_poll_seconds=30")
    print("bank_only_deposits=extra")
    print(f"payload_headroom={padding - delta}")
    print(f"executable_bytes={len(patched)}")


if __name__ == "__main__":
    main()
