# Loot Logger Optimized v9.0.22 — Editable Source

This package contains the exact editable frontend used by the included v9.0.22 Windows executable.

Additional loot logger files always use smart merge. Events with the same looter, item, and loot source inside a rolling 60-second window count only once, both within one file and across multiple files.

Bank Compare View all uses the same compact item spacing as the normal view. Resolving one item updates its card, player counters, and summaries in place without an immediate full redraw or vertical scroll jump.

## Main editable files

- `source/app.js` — main extended application logic
- `source/inline-1.js` — core Loot Logger interface and behavior
- `source/inline-0.js` and `source/inline-10.js` — startup/theme helpers
- `source/pre-*.js` — scripts loaded before the main application
- `source/style-*.css` — interface styles
- `source/embedded.html` — complete embedded page and HTML structure
- `source/payload.json` — readable snapshot of the packed frontend payload

The generated `inline-2.js` through `inline-9.js` files contain packed transport data. Edit `app.js`, `pre-*.js`, or `style-*.css` instead of those generated parts.

## Rebuild the EXE

Requirements:

- Python 3
- `libdeflate.so.0` (Linux package: `libdeflate0`)

From the package directory, run:

```bash
python3 tools/build_exe.py \
  "template/Loot Logger Optimized v9.0.22.exe" \
  source \
  "Loot Logger Custom.exe"
```

The frontend is stored in a fixed-size section of the executable. If a change is too large, the build script reports how many bytes exceed the available space.

Before rebuilding, JavaScript files can be checked with:

```bash
for file in source/inline-0.js source/inline-1.js source/inline-10.js source/pre-*.js source/app.js; do
  node --check "$file"
done
```
