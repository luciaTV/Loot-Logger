#!/usr/bin/env python3
"""Optimize large Bank Compare inventories and normalize Loot Logger to v9.0.00."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


VERSION = "v9.0.00"


def replace_exact(text: str, before: str, after: str) -> str:
    count = text.count(before)
    if count != 1:
        raise RuntimeError(f"Expected one target, found {count}: {before[:80]!r}")
    return text.replace(before, after)


def replace_range(text: str, start: str, end: str, replacement: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError(f"Expected unique range: {start!r} .. {end!r}")
    left = text.index(start)
    right = text.index(end, left)
    return text[:left] + replacement + text[right:]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: patch_large_item_performance_v9.py INPUT.exe OUTPUT.exe")
    source, destination = map(Path, sys.argv[1:])
    executable = source.read_bytes()
    html_start = executable.find(b'<!DOCTYPE html><html lang="en"')
    html_end = executable.find(b"</html>", html_start) + len(b"</html>")
    if html_start < 0 or html_end < len(b"</html>"):
        raise RuntimeError("Packed HTML payload not found")
    original_html = executable[html_start:html_end]
    html = original_html.decode("utf-8")

    # Build the price lookup once and delegate Bank Compare actions to one handler.
    large_list_bindings = r'''function $b(){if(!j)return;for(const a of ef('#players .player')){const n=a.dataset.player,t=a.querySelector('.player-tools');if(t&&!t.querySelector('[data-pro-select-player]')){const c=E.selectedPlayers.has(n);t.insertAdjacentHTML('afterbegin',`<label class=pro-select><input data-pro-select-player="${L(n)}" type=checkbox ${c?'checked':''}></label>`);t.querySelector('[data-pro-select-player]').onchange=e=>{e.target.checked?E.selectedPlayers.add(n):E.selectedPlayers.delete(n);ea()}}}if(E.priceSettings.enabled){const m=new Map;for(const p of j.players)for(const i of p.items)m.set(p.name+'\x1f'+ld(i),i);for(const a of ef('.item')){if(a.querySelector('.pro-value'))continue;const i=m.get(a.closest('.player')?.dataset.player+'\x1f'+a.dataset.itemKey);if(i){const v=Bc(i),q=+i.quantity||0;a.insertAdjacentHTML('beforeend',v>0?`<div class=pro-value>≈ ${Da(v*q)} silver</div>`:'<div class="pro-value pro-price-missing">Price unavailable</div>')}}}const r9=(k,v,b)=>{let s;for(const p of j.players)for(const i of p.items)if(cj(p.name,i)==k)i.bank_status=s=v?'resolved':i.bank_base_status||(i.is_bank_only?'different':'missing');let c=b.closest('.bank-item');c.className=c.className.replace(/\b(?:matched|partial|missing|extra|different|resolved|ignored|lost)\b/,s);let x=c.querySelector('.bank-state');x.className='bank-state '+s;x.textContent=wc[s]||s;b.textContent=v?'Unresolve':'Resolve'},p=Z('#bankPlayers');if(p&&!p._l)p.onclick=p._l=e=>{const b=e.target.closest('[data-pro-resolve],[data-resolve-bank-player],[data-pro-ignore]');if(!b)return;if(b.dataset.proResolve){e.stopPropagation();const k=b.dataset.proResolve,v=!E.resolved.has(k);E.resolved[v?'add':'delete'](k);ea();r9(k,v,b);Ic();return}if(b.dataset.resolveBankPlayer){const t=[...b.closest('.bank-player').querySelectorAll('.bank-item:not(.matched):not(.ignored):not(.lost) [data-pro-resolve]')],v=!t.every(x=>E.resolved.has(x.dataset.proResolve));for(const x of t){let k=x.dataset.proResolve;E.resolved[v?'add':'delete'](k);r9(k,v,x)}ea();Ic();return}e.stopPropagation();const k=S(b.dataset.proIgnore);E.ignoredItems[E.ignoredItems.has(k)?'delete':'add'](k);ea();j=J(j);D()}}'''
    html = replace_range(html, "function $b(){", "const Me=xb;", large_list_bindings)

    # Index bank rows once instead of scanning every row for every player.
    html = replace_exact(
        html,
        "J=function(xj){if(!xj)return xj;let gh=Qd([...(xj.players||[]),...((xj.bank?.loaded&&C?.sourceRows)?C.sourceRows.map(r=>({name:Lb(r.player),items:[]})):[])]).map(Pc=>{",
        "J=function(xj){if(!xj)return xj;const br={};for(const r of xj.bank?.loaded&&C?.sourceRows||[])(br['$'+S(Lb(r.player))]||=[]).push(r);let gh=Qd([...(xj.players||[]),...Object.values(br).map(a=>({name:a[0].player,items:[]}))]).map(Pc=>{",
    )
    html = replace_exact(
        html,
        "for(const r of C.sourceRows){if(S(Lb(r.player))!==S(Pc.name))continue;",
        "for(const r of br['$'+S(Pc.name)]||[]){",
    )

    # Index a player's items during multi-file projection and calculate totals once.
    html = replace_exact(
        html,
        "M=new Map(P.map(p=>[S(Lb(p.name)),p]));for(const e of Object.values(E)){let q=Math.max(0,Number(e.q||0)),p=M.get(S(Lb(e.player)));if(!p){p={name:e.player,guild:e.guild||'',alliance:e.alliance||'',items:[],total_quantity:0,last_loot:''};P.push(p);M.set(S(Lb(e.player)),p)}",
        "M=new Map(P.map(p=>[S(Lb(p.name)),p]));for(const p of P)p._i=new Map(p.items.map((i,n)=>[Ae(i.item_name)+'|'+xa(i),n]));for(const e of Object.values(E)){let q=Math.max(0,Number(e.q||0)),pk=S(Lb(e.player)),p=M.get(pk);if(!p){p={name:e.player,guild:e.guild||'',alliance:e.alliance||'',items:[],total_quantity:0,last_loot:'',_i:new Map};P.push(p);M.set(pk,p)}",
    )
    html = replace_exact(
        html,
        "let i=(p.items||[]).find(i=>Ae(i.item_name)===Ae(e.item)&&xa(i)==e.enchantment);if(i){",
        "let ik=Ae(e.item)+'|'+e.enchantment,ix=p._i.get(ik),i=ix===undefined?null:p.items[ix];if(i){",
    )
    html = replace_exact(
        html,
        "i.category=G(i);let k=p.items.findIndex(x=>Ae(x.item_name)===Ae(e.item)&&xa(x)==e.enchantment);p.items[k]=i}else{",
        "i.category=G(i);p.items[ix]=i}else{",
    )
    html = replace_exact(
        html,
        "created.category=G(created);created.image_url=N(created);p.items.push(created)}p.total_quantity=p.items.reduce((s,i)=>s+Number(i.quantity||0),0)}return{",
        "created.category=G(created);created.image_url=N(created);p._i.set(ik,p.items.length);p.items.push(created)}}for(const p of P){p.total_quantity=p.items.reduce((s,i)=>s+Number(i.quantity||0),0);delete p._i}return{",
    )

    # Use a bounded rolling signature instead of allocating one giant nested array.
    signature = """let lastBankRenderSignature='';const bankRenderSignature=()=>{let h='';for(const p of j?.players||[])for(const i of p.items||[])h=hs(h+[p.name,i.item_id,i.item_name,i.quantity,i.bank_amount,i.bank_status,i.lost_quantity,i.owed_quantity].join('|'));const p=window.AlbionPro||{};return hs(JSON.stringify([j?.bank?.loaded,j?.bank?.rows,j?.bank?.file_name,C?.rows,gb,ia,jh,[...O].sort(),p.bankSort,p.filters,Object.keys(p.prices||{}).length,h]))};"""
    html = replace_range(html, "let lastBankRenderSignature=''", "const va0=va;", signature)

    # Let Chromium skip layout/paint work for off-screen player inventories.
    html = replace_exact(html, "</body></html>", "<style>.bank-player{content-visibility:auto}</style></body></html>")

    # Normalize versions inside the compressed application source before it is evaluated.
    bootstrap = "await new Response(new Blob([b.slice(0,106041)]).stream().pipeThrough(new DecompressionStream('gzip'))).text()"
    html = replace_exact(html, bootstrap, f"({bootstrap}).replaceAll('8.3.70','9.0.00')")

    html = html.replace("v8.3.83", VERSION).replace("v8.3.80", VERSION)
    stale_ui = re.findall(r"v8\.3\.(?:80|83)", html)
    if stale_ui:
        raise RuntimeError(f"Stale UI versions remain: {stale_ui}")

    delta = len(html.encode()) - len(original_html)
    if delta > 0:
        raise RuntimeError(f"Optimized payload is {delta} bytes too large")
    if delta < 0:
        html = html.replace("</body></html>", " " * -delta + "</body></html>")
    patched_html = html.encode()
    if len(patched_html) != len(original_html):
        raise RuntimeError("Embedded HTML size changed")
    patched = executable[:html_start] + patched_html + executable[html_end:]

    old_backend = b"8.3.73"
    if patched.count(old_backend) != 1:
        raise RuntimeError(f"Expected one backend version, found {patched.count(old_backend)}")
    patched = patched.replace(old_backend, b"9.0.00")
    if len(patched) != len(executable):
        raise RuntimeError("Executable size changed")
    destination.write_bytes(patched)
    print(f"input_sha256={hashlib.sha256(executable).hexdigest()}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")
    print(f"version={VERSION}")
    print(f"payload_headroom={-delta}")
    print(f"executable_bytes={len(patched)}")


if __name__ == "__main__":
    main()
