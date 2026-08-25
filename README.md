# Loot Logger recovered editable files

This folder was recovered from `Loot Logger Optimized v9.0.07.exe`, a native Windows x86-64 Go executable.

## What is editable

- `frontend/index.html` is the unpacked, developer-friendly entry page.
- `frontend/styles/app.css` contains the decompressed CSS.
- `frontend/scripts/app.js` contains the decompressed application JavaScript.
- `frontend/scripts/inline-*.js` and `pre-*.js` contain the remaining scripts.
- `assets/` contains 7 valid PNG resources recovered from the executable.
- `backend-recovery/` contains the recoverable Go source-file map, function/type names,
  API routes, JSON tags, and build settings.
- `tools/extract_loot_logger.py` can repeat the extraction against another copy of the EXE.
- `tools/patch_bank_stability_v906.py` reproduces the earlier Bank Compare and refresh update.
- `tools/patch_extra_color_v907.py` reproduces the v9.0.07 dedicated Extra-status colour update.
- `EXTRA_COLOR.md` documents the status colour separation.
- `BANK_STABILITY.md` documents scroll preservation, render throttling, and Extra deposits.
- The included historical patch scripts reproduce the earlier performance, icon, runtime,
  Options, and visual updates.

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

- EXE SHA-256: `ed8297a64d6aef3a51d7d02431ddff9bf6d0a87ef33c873af1812b99e8344c33`
- Recovered Go function names: 482
- Recovered Go type/name entries: 230
- Recovered project source filenames: 19
- Recovered JSON tags: 146
- Recovered API route strings: 22

## Version

The executable, interface, diagnostics, metadata, and editable frontend report `v9.0.07`
(or `9.0.07` where a leading `v` is not used).
