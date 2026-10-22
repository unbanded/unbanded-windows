# Unbanded Patcher (BAND for Windows)

![Unbanded Patcher logo](logo.png)

> Adaptation of [**Unbanded**](https://github.com/unbanded/Unbanded) for the **BAND desktop (Windows)** client.

Self-contained repository: everything lives in this folder. The sole interface is `main.py`
(Tkinter GUI + patching core). Launch with `python main.py` or `run.bat`.

## What it does

Unbanded is a userscript that enhances the BAND experience. The desktop (PC) build of BAND is an
Electron app, so the userscript cannot be injected by a browser extension. This patcher takes the
compiled `unbanded.user.js` and injects it into the BAND desktop app's `app.asar`, forcing BAND
mode and adding a desktop header injection branch.

## How it works

BAND desktop is an Electron app (`main: js/main.js`, `nodeIntegration: true`). The patcher:

1. Reads the original `resources/app.asar` (read-only).
2. Extracts it to a temp working directory.
3. Strips the Tampermonkey `==UserScript==` header from `unbanded.user.js` and wraps the code in
   a safe IIFE with `unsafeWindow` / `GM_info` shims.
4. Writes it as `unbanded-injected.js` inside the asar.
5. Injects `<script src="unbanded-injected.js"></script>` into `main.html`.
6. Repacks into a new asar at the output path (or in place, with `.bak` backup).

> Note: injection targets the Electron **app.asar**, not the `.exe` binary.
> PE/binary injection is intentionally avoided (fragile, version-specific).
> This mirrors Vencord's approach (userscript + desktop asar injector).

## Features

- Injects `unbanded-injected.js` into `app.asar` and registers it in `main.html`
- Forces `isBand = true` and the `desktopNav` branch
- GUI (`main.py`) with:
  - Auto-detection of the BAND desktop installation
  - Live path validation badges
  - Patch / Verify / Unpatch tabs
  - Backup management (restore / delete)
  - Light & dark theme (dark by default)
  - Persisted configuration
  - Keyboard shortcuts (`Ctrl+Enter` run, `Esc` cancel, `F5` refresh backups)
- In-place or output-directory patching
- Auto-downloads `unbanded.user.js` from GitHub releases next to `main.py` on startup

## Usage

### GUI

```bash
python main.py        # or double-click run.bat
```

1. Set the **Source directory** (folder containing the original BAND `resources/app.asar`).
   Default: `C:\Program Files\BAND`.
2. Set the **Userscript** path (`unbanded.user.js`). Auto-downloaded next to `main.py` if missing.
3. Set the **Target app directory** (installed BAND app, optional) or an **Output directory**.
   Output default: `%USERPROFILE%\Downloads`.
4. Click **Patch**.

> The GUI is the only interface — there is no separate CLI. Patching runs in-process via
> `main.py`. In-place target is optional (empty by default); when used it creates
> `resources\app.asar.bak` before overwriting.

### Unpatch

Use the **Unpatch** tab in the GUI, or restore `resources/app.asar.bak` (created during
in-place patching) / `app.asar.patched.bak`.

## Project layout

```
.
├── main.py             # Tkinter GUI + patching core (sole interface)
├── run.bat             # Windows launcher for the GUI
├── .gitignore
├── LICENSE             # MIT
└── unbanded.user.js    # Auto-downloaded (gitignored)
```

## Limitation

The Unbanded userscript targets the web client (`band.us`). The desktop client renders a different
(Angular) UI, so DOM-dependent features need a desktop adapter rewrite; the injection mechanism
itself is fully functional.

## Demo mode fix

The BAND desktop client is an Angular/Electron app, not band.us. The userscript normally detects
this and enters "demo mode" (showing only a demo banner). The patcher now forces `isBand = true`
in the injected payload so the userscript runs in full mode on the desktop client.

This avoids having to maintain a separate desktop adapter rewrite of the userscript: the same
upstream userscript can be injected as-is, so new Unbanded releases land faster and with less
drift between web and desktop.

## Safety

- Original files are only **read**, never written.
- In-place patching creates `resources/app.asar.bak` before overwriting.
- Re-running is idempotent (injection checks for existing `unbanded-injected.js`).

## License

[MIT](LICENSE) — see `LICENSE`.

