#!/usr/bin/env python3
"""Lock loot sources on, stabilize Options editing, and bump v9.0.02 to v9.0.03."""

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
        raise SystemExit("Usage: patch_options_stability_v903.py INPUT.exe OUTPUT.exe")
    source, destination = map(Path, sys.argv[1:])
    executable = source.read_bytes()
    html_start = executable.find(b'<!DOCTYPE html><html lang="en"')
    html_end = executable.find(b"</html>", html_start) + len(b"</html>")
    if html_start < 0 or html_end < len(b"</html>"):
        raise RuntimeError("Packed HTML payload not found")
    original_html = executable[html_start:html_end]
    html = original_html.decode("utf-8")

    loot_sources = (
        '<section class="settings-card"><h3>Loot sources</h3>'
        '<small class=setting-help>Your character and other players.</small>'
        '<div class="setting-list"><label class="setting-row"><span class="setting-copy">'
        '<span class="setting-title">Host character</span></span><span class="toggle">'
        '<input id=optHostLoot type="checkbox"><span class="toggle-track"></span></span></label>'
        '<label class="setting-row"><span class="setting-copy"><span class="setting-title">'
        'Other players</span></span><span class="toggle"><input id=optOtherLoot type="checkbox">'
        '<span class="toggle-track"></span></span></label></div></section>'
    )
    html = once(html, loot_sources, "")

    # Live state can continue updating Loot/Bank/Analytics, but must not rewrite fields while
    # the Options page is open. A forced refresh still occurs after an explicit save/reset.
    html = once(
        html,
        "const z=$('.tab-button.active')?.dataset.tab||'loot',n=Date.now();sa(j.settings||{});",
        "const z=$('.tab-button.active')?.dataset.tab||'loot',n=Date.now();if(z!=='options')sa(j.settings||{});",
    )
    html = once(
        html,
        "$('#optHostLoot').checked=Boolean(Va.include_host_loot);$('#optOtherLoot').checked=Boolean(Va.include_other_loot);",
        "",
    )
    html = once(
        html,
        "include_host_loot:$('#optHostLoot').checked,include_other_loot:$('#optOtherLoot').checked,",
        "include_host_loot:true,include_other_loot:true,",
    )
    html = once(
        html,
        "if(Bk&&!ae.include_host_loot)return false;if(!Bk&&!ae.include_other_loot)return false;",
        "",
    )

    # Mark a form dirty at pointer-down/input time, before a checkbox change can race a state
    # refresh. Saving remains a deliberate click instead of a background timer.
    html = once(
        html,
        "$$('#optionsPanel input, #optionsPanel select, #optionsPanel textarea').forEach(jm=>jm.addEventListener('change',nb));",
        "$('#optionsPanel').addEventListener('pointerdown',nb,true);"
        "$$('#optionsPanel input, #optionsPanel select, #optionsPanel textarea').forEach(jm=>{"
        "jm.addEventListener('input',nb);jm.addEventListener('change',nb)});",
    )
    auto_save = (
        "const sb=Z('#saveSettings');let hn;for(const x of "
        "ef('#optionsPanel input,#optionsPanel select,#optionsPanel textarea'))"
        "x.addEventListener(x.matches('textarea,input[type=text],input[type=number]')?"
        "'input':'change',()=>{if(x.id==='optSmallView'){Ai(x.checked);D()}"
        "clearTimeout(hn);hn=setTimeout(()=>sb?.click(),650)});"
    )
    html = once(html, auto_save, "")

    # Persist the mandatory source settings once if an older profile had either disabled.
    old_state_load = "j=w(await wf.json());Xc();"
    new_state_load = (
        "let v=await wf.json(),s=v.settings||{};"
        "if(!rj.s&&(!s.include_host_loot||!s.include_other_loot)){rj.s=1;"
        "void wl('/api/settings',{...s,include_host_loot:true,include_other_loot:true})"
        ".catch(()=>rj.s=0)}s.include_host_loot=s.include_other_loot=true;j=w(v);Xc();"
    )
    html = once(html, old_state_load, new_state_load)

    # Disable the older compressed 300 ms auto-save hook after decompression.
    bootstrap_tail = (
        ".replace('could not be started or loaded','is missing, incompatible, or outdated')"
    )
    bootstrap_new = bootstrap_tail + (
        ".replace(\"clearTimeout(saveTimer);saveTimer=setTimeout(()=>document.querySelector("
        "'#saveSettings')?.click(),300)\",'')"
        ".replace('Host character and Other players can be enabled independently.',"
        "'Host character and Other players are always enabled.')"
        ".replace('Host and other-player source toggles',"
        "'Host and other-player loot always enabled')"
    )
    html = once(html, bootstrap_tail, bootstrap_new)

    html = html.replace("9.0.02", "9.0.03")
    if "v9.0.02" in html:
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
    if patched.count(b"9.0.02") != 1:
        raise RuntimeError(f"Expected one backend version, found {patched.count(b'9.0.02')}")
    patched = patched.replace(b"9.0.02", b"9.0.03")
    if len(patched) != len(executable):
        raise RuntimeError("Executable size changed")
    destination.write_bytes(patched)
    print(f"input_sha256={hashlib.sha256(executable).hexdigest()}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")
    print("version=v9.0.03")
    print("loot_sources=host_and_other_always_on")
    print("options_autosave=disabled")
    print("options_live_repopulate=disabled_while_open")
    print(f"payload_headroom={-delta}")
    print(f"executable_bytes={len(patched)}")


if __name__ == "__main__":
    main()
