#!/usr/bin/env python3
"""Unbanded Patcher - GUI (tkinter), improved edition."""
import os
import sys
import json
import re
import threading
import queue
import shutil
import tempfile
import subprocess
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
os.chdir(HERE)

ACTIVE_PROCS = []
DEFAULT_SOURCE = r"C:\Program Files\BAND"
DEFAULT_USERSCRIPT = "./unbanded.user.js"
DEFAULT_OUTPUT = os.path.join(os.path.expanduser("~"), "Downloads")
LOGO_PATH = os.path.join(ROOT, "logo.png")
CONFIG_PATH = os.path.join(
    os.environ.get(
        "APPDATA",
        os.path.expanduser("~")),
    "UnbandedPatcher",
    "config.json")
CONFIG_VERSION = 3

LIGHT = {
    "BG": "#f3f4f8",
    "CARD": "#ffffff",
    "ACCENT": "#5b6cff",
    "ACCENT_DARK": "#4353e8",
    "ACCENT_SOFT": "#e8ebff",
    "TEXT": "#1f2333",
    "MUTED": "#6b7280",
    "BORDER": "#e2e5ee",
    "SUCCESS": "#16a34a",
    "ERROR": "#dc2626",
    "WARN": "#d97706",
    "CONSOLE_BG": "#1e1e2e",
    "CONSOLE_FG": "#e4e4ef",
    "CONSOLE_DIM": "#8a8aa0",
    "CONSOLE_CMD": "#9cdcfe",
    "CONSOLE_OK": "#4ade80",
    "CONSOLE_ERR": "#f87171",
    "HEADER_BG": "#5b6cff",
    "HEADER_FG": "#ffffff",
    "HEADER_SUB": "#e8ebff"}
DARK = {
    "BG": "#1a1b26",
    "CARD": "#24283b",
    "ACCENT": "#7aa2f7",
    "ACCENT_DARK": "#5a82d7",
    "ACCENT_SOFT": "#2f334d",
    "TEXT": "#c0caf5",
    "MUTED": "#7f849c",
    "BORDER": "#3b4261",
    "SUCCESS": "#9ece6a",
    "ERROR": "#f7768e",
    "WARN": "#e0af68",
    "CONSOLE_BG": "#16161e",
    "CONSOLE_FG": "#c0caf5",
    "CONSOLE_DIM": "#565f89",
    "CONSOLE_CMD": "#7dcfff",
    "CONSOLE_OK": "#9ece6a",
    "CONSOLE_ERR": "#f7768e",
    "HEADER_BG": "#24283b",
    "HEADER_FG": "#c0caf5",
    "HEADER_SUB": "#7aa2f7"}
P = dict(LIGHT)


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def _parse_userscript_version(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                m = re.search(r"@version\s+(\S+)", line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def fetch_latest_release():
    import urllib.request
    import json as _json
    url = "https://api.github.com/repos/unbanded/Unbanded/releases/latest"
    with urllib.request.urlopen(url, timeout=10) as r:
        data = _json.load(r)
    tag = str(data.get("tag_name", "")).lstrip("v")
    asset_url = None
    for a in data.get("assets", []):
        if a.get("name") == "unbanded.user.js":
            asset_url = a.get("browser_download_url")
    return tag, asset_url


def download_latest_userscript(dest):
    import urllib.request
    tag, url = fetch_latest_release()
    if not url:
        raise RuntimeError("no unbanded.user.js asset in latest release")
    urllib.request.urlretrieve(url, dest)
    return tag


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _e=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw,
            text=self.text,
            bg="#222",
            fg="#fff",
            font=(
                "Segoe UI",
                9),
            padx=8,
            pady=4,
            wraplength=260,
            justify="left").pack()

    def _hide(self, _e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class PatcherGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Unbanded Patcher")
        self.geometry("1000x760")
        self.minsize(880, 640)
        if os.path.exists(LOGO_PATH):
            try:
                self._logo_img = tk.PhotoImage(file=LOGO_PATH)
                self.iconphoto(True, self._logo_img)
            except Exception:
                self._logo_img = None
        self._cfg = load_config()
        self._dark = self._cfg.get("dark", True)
        self._apply_palette()
        self.configure(bg=P["BG"])
        self._running = False
        self._q = queue.Queue()
        self._proc = None
        self._cancel_requested = False
        self._vars = []
        self._path_status = {}
        self._build_styles()
        self._build()
        self._poll_log()
        self._load_history()
        self._bind_shortcuts()
        self.after(200, self._validate_all)
        self.after(500, self._start_userscript_update)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_palette(self):
        global P
        P = dict(DARK if self._dark else LIGHT)

    def _build_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            ".",
            font=(
                "Segoe UI",
                10),
            background=P["BG"],
            foreground=P["TEXT"])
        style.configure("TFrame", background=P["BG"])
        style.configure("Card.TFrame", background=P["CARD"])
        style.configure("TLabel", background=P["BG"], foreground=P["TEXT"])
        style.configure(
            "Card.TLabel",
            background=P["CARD"],
            foreground=P["TEXT"])
        style.configure(
            "Muted.TLabel",
            background=P["BG"],
            foreground=P["MUTED"],
            font=(
                "Segoe UI",
                9))
        style.configure(
            "CardMuted.TLabel",
            background=P["CARD"],
            foreground=P["MUTED"],
            font=(
                "Segoe UI",
                9))
        style.configure(
            "Header.TLabel",
            background=P["HEADER_BG"],
            foreground=P["HEADER_FG"],
            font=(
                "Segoe UI Semibold",
                17))
        style.configure(
            "SubHeader.TLabel",
            background=P["HEADER_BG"],
            foreground=P["HEADER_SUB"],
            font=(
                "Segoe UI",
                10))
        style.configure(
            "TEntry",
            fieldbackground=P["CARD"],
            bordercolor=P["BORDER"],
            lightcolor=P["BORDER"],
            darkcolor=P["BORDER"],
            borderwidth=1,
            relief="flat",
            padding=6)
        style.map(
            "TEntry", bordercolor=[
                ("focus", P["ACCENT"])], lightcolor=[
                ("focus", P["ACCENT"])], darkcolor=[
                ("focus", P["ACCENT"])])
        style.configure(
            "TCheckbutton",
            background=P["CARD"],
            foreground=P["TEXT"],
            font=(
                "Segoe UI",
                10))
        style.map("TCheckbutton", background=[("active", P["CARD"])])
        style.configure(
            "Primary.TButton",
            background=P["ACCENT"],
            foreground="white",
            font=("Segoe UI Semibold", 10),
            borderwidth=0,
            padding=(16, 8),
            relief="flat")
        style.map(
            "Primary.TButton",
            background=[
                ("active", P["ACCENT_DARK"]),
                ("disabled", "#b8bcff")],
            foreground=[("disabled", "#ffffff")])
        style.configure(
            "Secondary.TButton",
            background=P["CARD"],
            foreground=P["TEXT"],
            font=("Segoe UI", 10),
            borderwidth=1,
            padding=(14, 8),
            relief="flat")
        style.map(
            "Secondary.TButton", background=[
                ("active", P["ACCENT_SOFT"])], bordercolor=[
                ("focus", P["ACCENT"])])
        style.configure(
            "Ghost.TButton", background=P["BG"], foreground=P["MUTED"], font=(
                "Segoe UI", 9), borderwidth=0, padding=(
                8, 4), relief="flat")
        style.map("Ghost.TButton", foreground=[("active", P["ACCENT"])])
        style.configure(
            "Browse.TButton",
            background=P["ACCENT_SOFT"],
            foreground=P["ACCENT"],
            font=(
                "Segoe UI Semibold",
                9),
            borderwidth=0,
            padding=(
                10,
                6),
            relief="flat")
        style.map("Browse.TButton", background=[("active", "#d6daff")])
        style.configure("TNotebook", background=P["BG"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=P["CARD"],
            foreground=P["MUTED"],
            padding=(
                14,
                6),
            font=(
                "Segoe UI",
                10))
        style.map(
            "TNotebook.Tab", background=[
                ("selected", P["ACCENT_SOFT"])], foreground=[
                ("selected", P["ACCENT"])])
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=P["CARD"],
            background=P["ACCENT"],
            bordercolor=P["BORDER"],
            lightcolor=P["ACCENT"],
            darkcolor=P["ACCENT"])
        style.configure(
            "Treeview",
            background=P["CARD"],
            foreground=P["TEXT"],
            fieldbackground=P["CARD"],
            bordercolor=P["BORDER"],
            font=(
                "Segoe UI",
                9))
        style.configure(
            "Treeview.Heading",
            background=P["ACCENT_SOFT"],
            foreground=P["TEXT"],
            font=(
                "Segoe UI Semibold",
                9))
        style.map(
            "Treeview", background=[
                ("selected", P["ACCENT_SOFT"])], foreground=[
                ("selected", P["TEXT"])])

    def _build(self):
        header = tk.Frame(self, bg=P["HEADER_BG"], height=86)
        header.pack(fill="x")
        header.pack_propagate(False)
        hinner = tk.Frame(header, bg=P["HEADER_BG"])
        hinner.pack(fill="both", expand=True, padx=24, pady=12)
        left = tk.Frame(hinner, bg=P["HEADER_BG"])
        left.pack(side="left", fill="y")
        tk.Label(
            left,
            text="Unbanded Patcher  ",
            bg=P["HEADER_BG"],
            fg=P["HEADER_FG"],
            font=(
                "Segoe UI Semibold",
                19)).pack(
            anchor="w")
        tk.Label(
            left,
            text="Inject the Unbanded userscript into the BAND desktop (Electron) client",  # noqa: E501
            bg=P["HEADER_BG"],
            fg=P["HEADER_SUB"],
            font=(
                "Segoe UI",
                10)).pack(
            anchor="w")
        right = tk.Frame(hinner, bg=P["HEADER_BG"])
        right.pack(side="right", fill="y")
        self.btn_theme = ttk.Button(
            right,
            text=(
                "\u263E Dark" if not self._dark else "\u2600 Light"),
            style="Ghost.TButton",
            command=self._toggle_theme)
        self.btn_theme.pack(anchor="e")
        tk.Label(
            right,
            text="v1.0.0",
            bg=P["HEADER_BG"],
            fg=P["HEADER_SUB"],
            font=(
                "Segoe UI",
                8)).pack(
            anchor="e",
            pady=(
                4,
                0))

        body = tk.Frame(self, bg=P["BG"])
        body.pack(fill="both", expand=True, padx=18, pady=14)
        self.nb = ttk.Notebook(body)
        self.nb.pack(fill="both", expand=True)

        patch_tab = tk.Frame(self.nb, bg=P["BG"])
        self.nb.add(patch_tab, text="  Patch  ")
        self._build_patch_tab(patch_tab)
        unpatch_tab = tk.Frame(self.nb, bg=P["BG"])
        self.nb.add(unpatch_tab, text="  Unpatch  ")
        self._build_unpatch_tab(unpatch_tab)
        backups_tab = tk.Frame(self.nb, bg=P["BG"])
        self.nb.add(backups_tab, text="  Backups  ")
        self._build_backups_tab(backups_tab)
        about_tab = tk.Frame(self.nb, bg=P["BG"])
        self.nb.add(about_tab, text="  About  ")
        self._build_about_tab(about_tab)

        console_frame = tk.Frame(self, bg=P["BG"])
        console_frame.pack(fill="x", side="bottom", padx=18, pady=(0, 6))
        self._card(console_frame, "Console output")
        cw = tk.Frame(
            console_frame,
            bg=P["CONSOLE_BG"],
            highlightthickness=1,
            highlightbackground=P["BORDER"])
        cw.pack(fill="both", expand=True)
        toolbar = tk.Frame(cw, bg=P["CONSOLE_BG"])
        toolbar.pack(fill="x", padx=8, pady=(6, 2))
        ttk.Button(
            toolbar,
            text="Copy",
            style="Ghost.TButton",
            command=self._copy_log).pack(
            side="left")
        ttk.Button(
            toolbar,
            text="Clear",
            style="Ghost.TButton",
            command=self._clear_log).pack(
            side="left",
            padx=4)
        self.var_autoscroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            toolbar,
            text="Auto-scroll",
            variable=self.var_autoscroll,
            style="TCheckbutton").pack(
            side="left",
            padx=8)
        self.lbl_log_count = tk.Label(
            toolbar,
            text="",
            bg=P["CONSOLE_BG"],
            fg=P["CONSOLE_DIM"],
            font=(
                "Consolas",
                9))
        self.lbl_log_count.pack(side="right")
        self.log = scrolledtext.ScrolledText(
            cw,
            height=12,
            state="disabled",
            wrap="word",
            bg=P["CONSOLE_BG"],
            fg=P["CONSOLE_FG"],
            insertbackground=P["CONSOLE_FG"],
            font=(
                "Consolas",
                10),
            borderwidth=0,
            relief="flat",
            padx=12,
            pady=8)
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("cmd", foreground=P["CONSOLE_CMD"])
        self.log.tag_configure(
            "ok", foreground=P["CONSOLE_OK"], font=(
                "Consolas", 10, "bold"))
        self.log.tag_configure(
            "err", foreground=P["CONSOLE_ERR"], font=(
                "Consolas", 10, "bold"))
        self.log.tag_configure("dim", foreground=P["CONSOLE_DIM"])
        self.log.tag_configure(
            "warn", foreground=P["WARN"], font=(
                "Consolas", 10, "bold"))

        statusbar = tk.Frame(self, bg=P["CARD"], height=28)
        statusbar.pack(fill="x", side="bottom")
        statusbar.pack_propagate(False)
        self.lbl_status = tk.Label(
            statusbar,
            text="\u25CF Ready",
            bg=P["CARD"],
            fg=P["MUTED"],
            font=(
                "Segoe UI Semibold",
                9))
        self.lbl_status.pack(side="left", padx=14)
        self.progress = ttk.Progressbar(
            statusbar,
            mode="indeterminate",
            length=160,
            style="Horizontal.TProgressbar")
        self.progress.pack(side="right", padx=14, pady=6)
        self.progress.pack_forget()

        footer = tk.Frame(self, bg=P["BG"])
        footer.pack(fill="x", side="bottom", padx=18, pady=(0, 4))
        tk.Label(
            footer,
            text="Original files are never modified. In-place mode creates app.asar.bak.",  # noqa: E501
            bg=P["BG"],
            fg=P["MUTED"],
            font=(
                "Segoe UI",
                8)).pack(
            side="left")
        tk.Label(
            footer,
            text="Unbanded \u00A9",
            bg=P["BG"],
            fg=P["MUTED"],
            font=(
                "Segoe UI",
                8)).pack(
            side="right")

    def _build_patch_tab(self, parent):
        self._card(parent, "Inputs")
        inputs = tk.Frame(parent, bg=P["CARD"])
        inputs.pack(fill="x", pady=(0, 12))
        self._row(
            inputs,
            "Source directory (original app):",
            DEFAULT_SOURCE,
            "dir",
            tip="Folder containing the extracted/installed BAND app (must have resources/app.asar).")  # noqa: E501
        self.var_source = self._vars[0]
        self._row(
            inputs,
            "Userscript file:",
            DEFAULT_USERSCRIPT,
            "file",
            tip="Path to unbanded.user.js",
            filetypes=[
                ("JavaScript",
                 "*.js"),
                ("All",
                 "*.*")])
        self.var_script = self._vars[1]
        self._row(
            inputs,
            "Output directory (tree mode):",
            DEFAULT_OUTPUT,
            "dir",
            tip="Where the patched app tree will be written.")
        self.var_output = self._vars[2]
        self._row(
            inputs,
            "In-place target (optional):",
            "",
            "dir",
            tip="Installed app dir to patch in place (creates app.asar.bak).")
        self.var_inplace = self._vars[3]

        qa = tk.Frame(inputs, bg=P["CARD"])
        qa.pack(fill="x", padx=16, pady=(4, 10))
        ttk.Button(
            qa,
            text="\U0001F50D Auto-detect BAND app",
            style="Secondary.TButton",
            command=self._auto_detect).pack(
            side="left")
        ttk.Button(
            qa,
            text="\u2714 Verify output",
            style="Secondary.TButton",
            command=self._verify_output).pack(
            side="left",
            padx=8)
        ttk.Button(
            qa,
            text="\U0001F4C1 Open output",
            style="Secondary.TButton",
            command=self._open_output).pack(
            side="left")

        self._card(parent, "Options")
        opts_card = tk.Frame(parent, bg=P["CARD"])
        opts_card.pack(fill="x", pady=(0, 12))
        oi = tk.Frame(opts_card, bg=P["CARD"])
        oi.pack(fill="x", padx=16, pady=12)
        self.var_dry = tk.BooleanVar(value=self._cfg.get("dry", False))
        self.var_inplace_mode = tk.BooleanVar(
            value=self._cfg.get("inplace_mode", False))
        cb1 = ttk.Checkbutton(
            oi,
            text="Dry run (validate inputs only, write nothing)",
            variable=self.var_dry)
        cb1.pack(anchor="w", pady=2)
        cb2 = ttk.Checkbutton(
            oi,
            text="Use in-place mode (patch installed app; creates app.asar.bak)",  # noqa: E501
            variable=self.var_inplace_mode)
        cb2.pack(anchor="w", pady=2)
        Tooltip(
            cb1,
            "Runs all validations without writing any file. Good for a sanity check.")  # noqa: E501
        Tooltip(
            cb2,
            "Patches the installed app directly. A backup (app.asar.bak) is created first.")  # noqa: E501

        actions = tk.Frame(parent, bg=P["BG"])
        actions.pack(fill="x", pady=(0, 4))
        self.btn_patch = ttk.Button(
            actions,
            text="\u25B6  Patch",
            style="Primary.TButton",
            command=self._on_patch)
        self.btn_patch.pack(side="left")
        self.btn_cancel = ttk.Button(
            actions,
            text="Cancel",
            style="Secondary.TButton",
            command=self._on_cancel,
            state="disabled")
        self.btn_cancel.pack(side="left", padx=8)
        ttk.Button(
            actions,
            text="Clear log",
            style="Ghost.TButton",
            command=self._clear_log).pack(
            side="left")
        self.lbl_status2 = tk.Label(
            actions,
            text="",
            bg=P["BG"],
            fg=P["MUTED"],
            font=(
                "Segoe UI",
                9))
        self.lbl_status2.pack(side="right")

    def _build_unpatch_tab(self, parent):
        self._card(parent, "Unpatch (restore original app.asar)")
        info = tk.Label(
            parent,
            text="Restores the original, unpatched app.asar over the patched one.\n"  # noqa: E501
            "All Unbanded injections are removed. A backup of the current patched asar can be kept.",  # noqa: E501
            bg=P["BG"],
            fg=P["MUTED"],
            font=(
                "Segoe UI",
                9),
            justify="left")
        info.pack(anchor="w", pady=(0, 10))

        card = tk.Frame(parent, bg=P["CARD"])
        card.pack(fill="x", pady=(0, 12))

        # Target
        r = tk.Frame(card, bg=P["CARD"])
        r.pack(fill="x", padx=16, pady=6)
        tk.Label(
            r,
            text="Target app directory (patched):",
            bg=P["CARD"],
            fg=P["TEXT"],
            font=(
                "Segoe UI",
                10)).pack(
            side="left")
        self.var_unpatch_target = tk.StringVar(value="")
        e = ttk.Entry(r, textvariable=self.var_unpatch_target)
        e.pack(side="left", fill="x", expand=True, padx=10)
        ttk.Button(
            r,
            text="Browse",
            style="Browse.TButton",
            command=lambda: self._browse_dir(
                self.var_unpatch_target)).pack(
            side="right")
        Tooltip(e, "Installed/patched app dir containing resources/app.asar")

        # Source mode
        sm = tk.Frame(card, bg=P["CARD"])
        sm.pack(fill="x", padx=16, pady=6)
        tk.Label(
            sm,
            text="Restore from:",
            bg=P["CARD"],
            fg=P["TEXT"],
            font=(
                "Segoe UI",
                10)).pack(
            side="left")
        self.var_unpatch_source = tk.StringVar(value="backup")
        ttk.Radiobutton(
            sm,
            text="Backup (app.asar.bak)",
            variable=self.var_unpatch_source,
            value="backup").pack(
            side="left",
            padx=10)
        ttk.Radiobutton(
            sm,
            text="Original source dir",
            variable=self.var_unpatch_source,
            value="original").pack(
            side="left",
            padx=10)

        # Original source dir (used when mode=original)
        r2 = tk.Frame(card, bg=P["CARD"])
        r2.pack(fill="x", padx=16, pady=6)
        tk.Label(
            r2,
            text="Original source directory:",
            bg=P["CARD"],
            fg=P["TEXT"],
            font=(
                "Segoe UI",
                10)).pack(
            side="left")
        self.var_unpatch_original = tk.StringVar(value=DEFAULT_SOURCE)
        e2 = ttk.Entry(r2, textvariable=self.var_unpatch_original)
        e2.pack(side="left", fill="x", expand=True, padx=10)
        ttk.Button(
            r2,
            text="Browse",
            style="Browse.TButton",
            command=lambda: self._browse_dir(
                self.var_unpatch_original)).pack(
            side="right")
        Tooltip(e2, "Folder with the original (unpatched) app.asar")

        # Options
        oi = tk.Frame(card, bg=P["CARD"])
        oi.pack(fill="x", padx=16, pady=8)
        self.var_unpatch_keepbackup = tk.BooleanVar(value=True)
        cb = ttk.Checkbutton(
            oi,
            text="Keep a backup of the patched asar (app.asar.patched.bak) before unpatching",  # noqa: E501
            variable=self.var_unpatch_keepbackup)
        cb.pack(anchor="w", pady=2)
        Tooltip(
            cb,
            "Strongly recommended: keeps the patched asar so you can re-patch later.")  # noqa: E501

        # Status label
        self.lbl_unpatch_status = tk.Label(
            card,
            text="",
            bg=P["CARD"],
            fg=P["MUTED"],
            font=(
                "Segoe UI",
                9))
        self.lbl_unpatch_status.pack(anchor="w", padx=16, pady=(0, 6))

        # Auto-detect button
        qa = tk.Frame(card, bg=P["CARD"])
        qa.pack(fill="x", padx=16, pady=(0, 10))
        ttk.Button(
            qa,
            text="\U0001F50D Auto-detect",
            style="Secondary.TButton",
            command=self._unpatch_autodetect).pack(
            side="left")
        ttk.Button(qa, text="\u2714 Check", style="Secondary.TButton",
                   command=self._unpatch_check).pack(side="left", padx=8)

        # Action
        actions = tk.Frame(parent, bg=P["BG"])
        actions.pack(fill="x", pady=(0, 4))
        self.btn_unpatch = ttk.Button(
            actions,
            text="\u21A9  Unpatch",
            style="Primary.TButton",
            command=self._on_unpatch)
        self.btn_unpatch.pack(side="left")
        tk.Label(
            actions,
            text="This overwrites resources/app.asar in the target directory.",
            bg=P["BG"],
            fg=P["MUTED"],
            font=(
                "Segoe UI",
                9)).pack(
            side="left",
            padx=12)

    def _build_backups_tab(self, parent):
        self._card(parent, "Installed app backups (app.asar.bak)")
        top = tk.Frame(parent, bg=P["BG"])
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(
            top,
            text="\U0001F504 Refresh",
            style="Secondary.TButton",
            command=self._refresh_backups).pack(
            side="left")
        ttk.Button(
            top,
            text="\u21A9 Restore selected",
            style="Secondary.TButton",
            command=self._restore_backup).pack(
            side="left",
            padx=8)
        ttk.Button(
            top,
            text="\U0001F5D1 Delete selected",
            style="Secondary.TButton",
            command=self._delete_backup).pack(
            side="left")
        tk.Label(
            parent,
            text="Backups are created by in-place mode next to resources/app.asar.",  # noqa: E501
            bg=P["BG"],
            fg=P["MUTED"],
            font=(
                "Segoe UI",
                9)).pack(
            anchor="w",
            pady=(
                0,
                6))
        cols = ("path", "size", "modified")
        self.tree_backups = ttk.Treeview(
            parent, columns=cols, show="headings", height=16)
        self.tree_backups.heading("path", text="Backup file")
        self.tree_backups.heading("size", text="Size")
        self.tree_backups.heading("modified", text="Modified")
        self.tree_backups.column("path", width=520)
        self.tree_backups.column("size", width=90, anchor="e")
        self.tree_backups.column("modified", width=160)
        sb = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=self.tree_backups.yview)
        self.tree_backups.configure(yscrollcommand=sb.set)
        self.tree_backups.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.after(300, self._refresh_backups)

    def _build_about_tab(self, parent):
        self._card(parent, "About")
        box = tk.Frame(parent, bg=P["CARD"])
        box.pack(fill="both", expand=True, pady=(0, 8))
        lines = [
            ("Unbanded Patcher", "Segoe UI Semibold", 15, P["ACCENT"]),  # noqa: E501
            ("Version 1.0.0", "Segoe UI", 10, P["MUTED"]),  # noqa: E501
            ("", "Segoe UI", 6, P["MUTED"]),  # noqa: E501
            ("Injects the Unbanded userscript into the BAND desktop (Electron) client.", "Segoe UI", 10, P["TEXT"]),  # noqa: E501
            ("Forces BAND mode and adds a desktop header injection branch.", "Segoe UI", 10, P["TEXT"]),  # noqa: E501
            ("", "Segoe UI", 6, P["MUTED"]),
            ("Defaults:", "Segoe UI Semibold", 10, P["TEXT"]),  # noqa: E501
            ("  Source:        C:\\Program Files\\BAND", "Consolas", 9, P["MUTED"]),
            ("  Userscript:    unbanded.user.js (auto-downloaded next to main.py)", "Consolas", 9, P["MUTED"]),  # noqa: E501
            ("  Output:        %USERPROFILE%\\Downloads", "Consolas", 9, P["MUTED"]),
            ("  In-place:     optional (creates resources\\app.asar.bak)", "Consolas", 9, P["MUTED"]),  # noqa: E501
            ("", "Segoe UI", 6, P["MUTED"]),
            ("Safety:", "Segoe UI Semibold", 10, P["TEXT"]),
            ("  - Original files are only read, never modified.", "Segoe UI", 9, P["MUTED"]),
            ("  - In-place patching creates app.asar.bak before overwriting.", "Segoe UI", 9, P["MUTED"]),  # noqa: E501
            ("  - Re-running is idempotent.", "Segoe UI", 9, P["MUTED"]),
            ("", "Segoe UI", 6, P["MUTED"]),
            ("Keyboard shortcuts:", "Segoe UI Semibold", 10, P["TEXT"]),
            ("  Ctrl+Enter  ->  Run patch", "Consolas", 9, P["MUTED"]),
            ("  Esc         ->  Cancel running patch", "Consolas", 9, P["MUTED"]),  # noqa: E501
            ("  F5          ->  Refresh backups", "Consolas", 9, P["MUTED"]),
        ]
        if os.path.exists(LOGO_PATH):
            try:
                img = tk.PhotoImage(file=LOGO_PATH)
                self._about_logo = img.subsample(8, 8)
                tk.Label(box, image=self._about_logo, bg=P["CARD"]).pack(anchor="w", padx=16, pady=(8, 4))
            except Exception:
                self._about_logo = None
        for text, font, size, color in lines:
            tk.Label(
                box,
                text=text,
                bg=P["CARD"],
                fg=color,
                font=(
                    font,
                    size)).pack(
                anchor="w",
                padx=16,
                pady=1)

    def _card(self, parent, title):
        c = tk.Frame(parent, bg=P["BG"])
        c.pack(fill="x", pady=(0, 4))
        tk.Label(
            c,
            text=title.upper(),
            bg=P["BG"],
            fg=P["MUTED"],
            font=(
                "Segoe UI Semibold",
                9)).pack(
            anchor="w")

    def _make_entry_var(self, default):
        v = tk.StringVar(value=default)
        if not hasattr(self, "_vars"):
            self._vars = []
        self._vars.append(v)
        v.trace_add("write", lambda *_: self._validate_all())
        return v

    def _row(self, parent, label, default, kind, tip=None, filetypes=None):
        r = tk.Frame(parent, bg=P["CARD"])
        r.pack(fill="x", padx=16, pady=6)
        tk.Label(
            r,
            text=label,
            bg=P["CARD"],
            fg=P["TEXT"],
            font=(
                "Segoe UI",
                10)).pack(
            side="left")
        v = self._make_entry_var(default)
        e = ttk.Entry(r, textvariable=v)
        e.pack(side="left", fill="x", expand=True, padx=10)
        badge = tk.Label(
            r,
            text="",
            bg=P["CARD"],
            fg=P["MUTED"],
            font=(
                "Segoe UI",
                11),
            width=2)
        badge.pack(side="right")
        setattr(v, "_badge", badge)
        self._path_status[id(v)] = badge
        if kind == "dir":
            ttk.Button(
                r,
                text="Browse",
                style="Browse.TButton",
                command=lambda vv=v: self._browse_dir(vv)).pack(
                side="right",
                padx=(
                    6,
                    0))
        else:
            ttk.Button(
                r,
                text="Browse",
                style="Browse.TButton",
                command=lambda vv=v,
                ft=filetypes: self._browse_file(
                    vv,
                    ft)).pack(
                side="right",
                padx=(
                    6,
                    0))
        if tip:
            Tooltip(e, tip)

    def _validate_path(self, var):
        val = var.get().strip()
        badge = getattr(var, "_badge", None)
        if badge is None:
            badge = self._path_status.get(id(var))
        if badge is None:
            return
        if not val:
            badge.configure(text="", fg=P["MUTED"])
            return
        exists = os.path.exists(val)
        badge.configure(
            text="\u2714" if exists else "\u2716",
            fg=P["SUCCESS"] if exists else P["ERROR"])

    def _validate_all(self):
        for v in list(self._vars):
            self._validate_path(v)

    def _browse_dir(self, var):
        d = filedialog.askdirectory(initialdir=var.get() or ROOT)
        if d:
            var.set(d)

    def _browse_file(self, var, types):
        f = filedialog.askopenfilename(
            initialdir=os.path.dirname(
                var.get() or ROOT), filetypes=types)
        if f:
            var.set(f)

    def _auto_detect(self):
        self._log(
            "[auto-detect] searching for BAND desktop app.asar ...",
            "dim")
        found = self._find_band_asar()
        if found:
            src_dir = os.path.dirname(os.path.dirname(found))
            self.var_source.set(src_dir)
            self._log("Found: " + found, "ok")
            messagebox.showinfo(
                "Auto-detect",
                "Found BAND app at:\n" +
                src_dir)
        else:
            self._log("No BAND app.asar found in common locations.", "warn")
            messagebox.showwarning(
                "Auto-detect",
                "Could not find a BAND desktop installation.\nPlease browse manually.")  # noqa: E501

    def _find_band_asar(self):
        candidates_roots = []
        for r in (
            os.environ.get(
                "LOCALAPPDATA", ""), os.environ.get(
                "PROGRAMFILES", ""), os.environ.get(
                "PROGRAMFILES(X86)", ""), os.environ.get(
                    "APPDATA", "")):
            if r and os.path.isdir(r):
                candidates_roots.append(r)
        for r in (r"C:\Program Files", r"C:\Program Files (x86)"):
            if os.path.isdir(r) and r not in candidates_roots:
                candidates_roots.append(r)
        for root in candidates_roots:
            for dirpath, dirnames, filenames in os.walk(root):
                depth = dirpath.count(os.sep) - root.count(os.sep)
                if depth > 5:
                    del dirnames[:]
                    continue
                if "resources" in dirnames:
                    asar = os.path.join(dirpath, "resources", "app.asar")
                    if os.path.exists(asar) and "band" in dirpath.lower():
                        return asar
                for skip in ("node_modules", ".git", "Cache", "CachedData"):
                    if skip in dirnames:
                        dirnames.remove(skip)
        return None

    def _verify_output(self):
        out = self.var_output.get().strip()
        if not out or not os.path.isdir(out):
            messagebox.showwarning(
                "Verify", "Output directory does not exist.")
            return
        checks = []
        injected = os.path.join(out, "resources", "unbanded-injected.js")
        main_html = os.path.join(out, "main.html")
        asar = os.path.join(out, "resources", "app.asar")
        checks.append(("unbanded-injected.js", os.path.exists(injected)))
        checks.append(("main.html", os.path.exists(main_html)))
        checks.append(("app.asar", os.path.exists(asar)))
        tag_ok = False
        if os.path.exists(main_html):
            try:
                tag_ok = "unbanded-injected.js" in open(
                    main_html, encoding="utf-8").read()
            except Exception:
                tag_ok = False
        checks.append(("script tag in main.html", tag_ok))
        desktop_nav = isband = False
        if os.path.exists(injected):
            try:
                s = open(injected, encoding="utf-8").read()
                desktop_nav = "desktopNav" in s
                isband = "this.isBand = true" in s
            except Exception:
                pass
        checks.append(("desktopNav branch", desktop_nav))
        checks.append(("isBand forced", isband))
        msg = "\n".join(
            ("\u2714" if ok else "\u2716") +
            "  " +
            name for name,
            ok in checks)
        self._log("[verify] " + out, "dim")
        for name, ok in checks:
            self._log(
                ("  \u2714 " if ok else "  \u2716 ") + name,
                "ok" if ok else "err")
        all_ok = all(ok for _, ok in checks)
        messagebox.showinfo(
            "Verify", msg +
            ("\n\nAll checks passed."
             if all_ok else "\n\nSome checks failed."))

    def _open_output(self):
        out = self.var_output.get().strip()
        if not out or not os.path.isdir(out):
            messagebox.showwarning("Open", "Output directory does not exist.")
            return
        try:
            os.startfile(out)
        except Exception as e:
            messagebox.showerror("Open", str(e))

    def _refresh_backups(self):
        for item in self.tree_backups.get_children():
            self.tree_backups.delete(item)
        dirs_to_scan = set()
        for v in (self.var_source, self.var_inplace, self.var_output):
            val = v.get().strip()
            if val and os.path.isdir(val):
                dirs_to_scan.add(val)
                dirs_to_scan.add(os.path.join(val, "resources"))
        backups = []
        for d in dirs_to_scan:
            if not os.path.isdir(d):
                continue
            try:
                for name in os.listdir(d):
                    if name.endswith(".bak") or name.endswith(".asar.bak"):
                        full = os.path.join(d, name)
                        if os.path.isfile(full):
                            st = os.stat(full)
                            mtime = datetime.datetime.fromtimestamp(
                                st.st_mtime).strftime("%Y-%m-%d %H:%M")
                            backups.append(
                                (full, self._human_size(st.st_size), mtime))
            except Exception:
                pass
        for full, size, mtime in sorted(backups):
            self.tree_backups.insert("", "end", values=(full, size, mtime))

    def _human_size(self, n):
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.0f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    def _restore_backup(self):
        sel = self.tree_backups.selection()
        if not sel:
            messagebox.showwarning("Restore", "Select a backup first.")
            return
        vals = self.tree_backups.item(sel[0], "values")
        bak = vals[0]
        target = os.path.join(os.path.dirname(bak), "app.asar")
        if not messagebox.askyesno(
            "Restore",
                f"Restore backup over:\n{target}\n\nThis overwrites the current app.asar."):  # noqa: E501
            return
        try:
            shutil.copy2(bak, target)
            self._log("Restored " + bak + " -> " + target, "ok")
            messagebox.showinfo("Restore", "Restore completed.")
        except Exception as e:
            self._log("Restore failed: " + str(e), "err")
            messagebox.showerror("Restore", str(e))

    def _delete_backup(self):
        sel = self.tree_backups.selection()
        if not sel:
            messagebox.showwarning("Delete", "Select a backup first.")
            return
        vals = self.tree_backups.item(sel[0], "values")
        bak = vals[0]
        if not messagebox.askyesno("Delete",
                                   f"Delete backup permanently?\n{bak}"):
            return
        try:
            os.remove(bak)
            self._refresh_backups()
            self._log("Deleted " + bak, "ok")
        except Exception as e:
            messagebox.showerror("Delete", str(e))

    def _unpatch_autodetect(self):
        found = self._find_band_asar()
        if found:
            target = os.path.dirname(os.path.dirname(found))
            self.var_unpatch_target.set(target)
            self._log("[unpatch] detected: " + target, "ok")
        else:
            messagebox.showwarning("Auto-detect",
                                   "Could not find a BAND app installation.")

    def _unpatch_check(self):
        target = self.var_unpatch_target.get().strip()
        if not target:
            messagebox.showwarning("Check", "Target directory is required.")
            return
        asar = os.path.join(target, "resources", "app.asar")
        bak = os.path.join(target, "resources", "app.asar.bak")
        orig = os.path.join(
            self.var_unpatch_original.get().strip(),
            "resources",
            "app.asar")
        lines = []
        lines.append(("Target app.asar", os.path.exists(asar)))
        lines.append(("Backup app.asar.bak", os.path.exists(bak)))
        lines.append(("Original source app.asar", os.path.exists(orig)))
        # check if patched
        patched_marker = False
        if os.path.exists(asar):
            try:
                import tempfile
                import subprocess
                td = tempfile.mkdtemp()
                subprocess.run(
                    [shutil.which("npx") or "npx", "asar", "extract", asar,
                     td],
                    capture_output=True, text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                html_path = os.path.join(td, "main.html")
                if os.path.exists(html_path):
                    patched_marker = "unbanded-injected.js" in open(
                        html_path, encoding="utf-8").read()
                shutil.rmtree(td, ignore_errors=True)
            except Exception:
                patched_marker = False
        lines.append(("Currently patched", patched_marker))
        msg = "\n".join(
            ("✔" if ok else "✖") +
            "  " +
            name for name,
            ok in lines)
        self.lbl_unpatch_status.configure(
            text=" | ".join(
                f"{name}: {'✔' if ok else '✖'} "for name, ok in lines),
            fg=P["SUCCESS"] if all(ok for _, ok in lines[: 1]) else P
            ["MUTED"])
        self._log("[unpatch check] " + target, "dim")
        for name, ok in lines:
            self._log(
                ("  ✔ " if ok else "  ✖ ") + name,
                "ok" if ok else "warn")
        messagebox.showinfo("Check", msg)

    def _on_unpatch(self):
        target = self.var_unpatch_target.get().strip()
        if not target or not os.path.isdir(target):
            messagebox.showerror(
                "Missing target",
                "Target app directory does not exist.")
            return
        asar = os.path.join(target, "resources", "app.asar")
        if not os.path.exists(asar):
            messagebox.showerror(
                "Missing file",
                "app.asar not found in target.")
            return

        mode = self.var_unpatch_source.get()
        if mode == "backup":
            src_asar = os.path.join(target, "resources", "app.asar.bak")
            if not os.path.exists(src_asar):
                messagebox.showerror(
                    "Missing backup",
                    "app.asar.bak not found in target/resources.\n"
                    "Switch to 'Original source dir' mode.")
                return
        else:
            src_dir = self.var_unpatch_original.get().strip()
            if not src_dir or not os.path.isdir(src_dir):
                messagebox.showerror(
                    "Missing source",
                    "Original source directory does not exist.")
                return
            src_asar = os.path.join(src_dir, "resources", "app.asar")
            if not os.path.exists(src_asar):
                messagebox.showerror(
                    "Missing file",
                    "app.asar not found in original source.")
                return

        if not messagebox.askyesno("Confirm unpatch",
                                   f"Restore original app.asar over:\n{asar}\n\nFrom:\n{src_asar}\n\n"  # noqa: E501
                                   "This removes all Unbanded injections. Continue?"):  # noqa: E501
            return

        try:
            resources = os.path.join(target, "resources")
            # keep backup of patched asar
            if self.var_unpatch_keepbackup.get():
                patched_backup = os.path.join(
                    resources, "app.asar.patched.bak")
                if os.path.exists(asar):
                    shutil.copy2(asar, patched_backup)
                    self._log("Kept patched backup: " + patched_backup, "dim")
            # restore
            shutil.copy2(src_asar, asar)
            self._log("Unpatched: " + asar, "ok")
            self._set_status("Unpatched", P["SUCCESS"])
            messagebox.showinfo(
                "Unpatch",
                "Unpatch completed successfully.\nRestart the BAND app to apply.")  # noqa: E501
        except Exception as e:
            self._log("Unpatch failed: " + str(e), "err")
            self._set_status("Failed", P["ERROR"])
            messagebox.showerror("Unpatch", str(e))

    def _on_patch(self):
        if self._running:
            return
        source = self.var_source.get().strip()
        script = self.var_script.get().strip()
        output = self.var_output.get().strip()
        if not source or not script:
            messagebox.showerror(
                "Missing input",
                "Source and userscript are required.")
            return
        if not os.path.isdir(source):
            messagebox.showerror(
                "Missing input",
                "Source directory does not exist.")
            return
        if not os.path.isfile(script):
            messagebox.showerror(
                "Missing input",
                "Userscript file does not exist.")
            return
        if self.var_inplace_mode.get():
            if not self.var_inplace.get().strip():
                self.var_inplace.set(source)
            if not self.var_inplace.get().strip():
                messagebox.showerror(
                    "Missing target",
                    "In-place mode requires a target directory.")
                return
            if not os.path.isdir(self.var_inplace.get().strip()):
                messagebox.showerror(
                    "Missing target",
                    "In-place target directory does not exist.")
                return
        else:
            if not output:
                messagebox.showerror(
                    "Missing input", "Output directory is required.")
                return
        self._running = True
        self._cancel_requested = False
        self.btn_patch.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self._set_status("Running...", P["ACCENT"])
        self.progress.pack(side="right", padx=14, pady=6)
        self.progress.start(12)
        self._log("[patch] starting", "dim")
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            source = self.var_source.get().strip()
            script = self.var_script.get().strip()
            output = self.var_output.get().strip()
            in_place = self.var_inplace.get().strip() if (
                self.var_inplace_mode.get() and self.var_inplace.get().strip()) else None  # noqa: E501
            dry_run = self.var_dry.get()
            do_patch(
                source,
                script,
                output,
                in_place=in_place,
                dry_run=dry_run,
                log=self._log)
            if self._cancel_requested:
                self._log("Cancelled.", "warn")
                self._set_status("Cancelled", P["WARN"])
            else:
                self._log("")
                self._log("SUCCESS", "ok")
                self._set_status("Done", P["SUCCESS"])
                self._cfg["patched_version"] = _parse_userscript_version(script) or "unknown"  # noqa: E501
                self._save_history()
                messagebox.showinfo(
                    "Unbanded Patcher",
                    "Patcher compatible." if dry_run else "Patching completed successfully.")
        except Exception as e:
            self._log("ERROR: " + str(e), "err")
            self._set_status("Failed", P["ERROR"])
            messagebox.showerror("Unbanded Patcher", str(e))
        finally:
            self._running = False
            self._proc = None
            self.btn_patch.configure(state="normal")
            self.btn_cancel.configure(state="disabled")
            self.progress.stop()
            self.progress.pack_forget()

    def _on_cancel(self):
        self._cancel_requested = True
        for p in list(ACTIVE_PROCS):
            try:
                p.terminate()
            except Exception:
                pass
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._log("[cancelled]", "dim")

    def _toggle_theme(self):
        self._dark = not self._dark
        self._cfg["dark"] = self._dark
        save_config(self._cfg)
        for w in self.winfo_children():
            w.destroy()
        self._apply_palette()
        self.configure(bg=P["BG"])
        self._build_styles()
        self._build()
        self._load_history()
        self.after(200, self._validate_all)

    def _load_history(self):
        migrated = self._cfg.get("config_version") == CONFIG_VERSION
        src = self._cfg.get("source") if migrated else None
        script = self._cfg.get("script") if migrated else None
        out = self._cfg.get("output") if migrated else None
        inp = self._cfg.get("inplace") if migrated else None
        if src and os.path.isdir(src):
            self.var_source.set(src)
        if script and os.path.isfile(script):
            self.var_script.set(script)
        if out:
            self.var_output.set(out)
        if inp:
            self.var_inplace.set(inp)
        self.var_dry.set(self._cfg.get("dry", False))
        self.var_inplace_mode.set(self._cfg.get("inplace_mode", False))

    def _save_history(self):
        self._cfg["source"] = self.var_source.get().strip()
        self._cfg["script"] = self.var_script.get().strip()
        self._cfg["output"] = self.var_output.get().strip()
        self._cfg["inplace"] = self.var_inplace.get().strip()
        self._cfg["dry"] = self.var_dry.get()
        self._cfg["inplace_mode"] = self.var_inplace_mode.get()
        self._cfg["config_version"] = CONFIG_VERSION
        self._cfg["dark"] = self._dark
        save_config(self._cfg)

    def _bind_shortcuts(self):
        self.bind("<Control-Return>", lambda e: self._on_patch())
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.bind("<F5>", lambda e: self._refresh_backups())

    def _log(self, msg, tag=None):
        self._q.put((msg, tag))

    def _poll_log(self):
        try:
            while True:
                msg, tag = self._q.get_nowait()
                self.log.configure(state="normal")
                if tag:
                    self.log.insert("end", msg + "\n", tag)
                else:
                    low = msg.lower()
                    if msg.startswith("$"):
                        self.log.insert("end", msg + "\n", "cmd")
                    elif "success" in low or "done." in low:
                        self.log.insert("end", msg + "\n", "ok")
                    elif "error" in low or "failed" in low:
                        self.log.insert("end", msg + "\n", "err")
                    elif msg.startswith("["):
                        self.log.insert("end", msg + "\n", "dim")
                    else:
                        self.log.insert("end", msg + "\n")
                self.log.configure(state="disabled")
                if self.var_autoscroll.get():
                    self.log.see("end")
                try:
                    lines = int(self.log.index("end-1c").split(".")[0])
                    self.lbl_log_count.configure(text=f"{lines} lines")
                except Exception:
                    pass
        except queue.Empty:
            pass
        self.after(80, self._poll_log)

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _copy_log(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.log.get("1.0", "end"))
            self._set_status("Copied log to clipboard", P["SUCCESS"])
        except Exception as e:
            messagebox.showerror("Copy", str(e))

    def _set_status(self, msg, color=None):
        color = color or P["MUTED"]
        self.lbl_status.configure(text="\u25CF " + msg, fg=color)
        if hasattr(self, "lbl_status2"):
            self.lbl_status2.configure(text=msg, fg=color)

    def _start_userscript_update(self):
        def worker():
            try:
                tag, url = fetch_latest_release()
                local = _parse_userscript_version(DEFAULT_USERSCRIPT)
                if url and (local is None or local != tag):
                    import urllib.request
                    urllib.request.urlretrieve(url, DEFAULT_USERSCRIPT)
                    local = tag
                    self._q.put(
                        ("[update] Userscript updated to " + str(tag) + ".", "ok"))  # noqa: E501
                else:
                    self._q.put(
                        ("[update] Userscript up to date (" + str(local or tag) + ").",  # noqa: E501
                         "dim"))
                patched = self._cfg.get("patched_version")
                if patched and local and patched != local:
                    self._q.put(
                        ("[update] Installed app was patched with " + str(patched) +  # noqa: E501
                         " but userscript is now " + str(local) +
                         ". Re-patch to update.", "warn"))
            except Exception as e:
                self._q.put(
                    ("[update] Could not check for updates: " + str(e), "dim"))
        threading.Thread(target=worker, daemon=True).start()

    def _on_close(self):
        self._save_history()
        self.destroy()


def run_asar(args, log):
    import shutil as _sh
    npx = _sh.which("npx") or "npx"
    cmd = [npx, "asar"] + args
    log("$ " + " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    ACTIVE_PROCS.append(proc)
    try:
        for line in proc.stdout:
            if line.strip():
                log("  " + line.rstrip("\n"))
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError("asar failed (exit %d)" % proc.returncode)
    finally:
        try:
            ACTIVE_PROCS.remove(proc)
        except ValueError:
            pass
    return proc


def rmrf(p):
    if os.path.isdir(p) and not os.path.islink(p):
        shutil.rmtree(p)
    elif os.path.lexists(p):
        os.remove(p)


def mkdirp(p):
    os.makedirs(p, exist_ok=True)


def copy_dir(src, dst):
    if os.path.exists(dst):
        rmrf(dst)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def strip_userscript_header(code):
    return re.sub(
        r"^// ==UserScript==[\s\S]*?// ==/UserScript==\s*\n*",
        "",
        code,
        count=1,
        flags=re.M)


def userscript_version(code):
    m = re.search(r"@version\s+(\S+)", code)
    return m.group(1) if m else "unknown"


def build_payload(userscript_code):
    stripped = strip_userscript_header(userscript_code)
    ver = userscript_version(userscript_code)
    # Desktop client is the official BAND app: force BAND mode so the userscript  # noqa: E501
    # does not fall back to "demo mode" (which only shows the demo banner).
    stripped = re.sub(
        r"this\.isBand\s*=\s*this\.host\.includes\('band\.us'\)\s*\|\|\s*this\.host\.includes\('band\.site'\);",  # noqa: E501
        "this.isBand = true; // desktop client: forced BAND mode by unbanded patcher",  # noqa: E501
        stripped,)
    lines = [
        "// Unbanded injection payload - generated by unbanded patcher. Do not edit by hand.",  # noqa: E501
        "(function () {", '  "use strict";', "  try {",
        '    if (typeof window !== "undefined") {',
        "      window.unsafeWindow = window.unsafeWindow || window;",
        '      if (!window.GM_info) window.GM_info = { script: { name: "Unbanded", version: "' + ver + '" }, scriptHandler: "UnbandedPatcher" };',  # noqa: E501
        '      window.__UNBANDED_VERSION__ = "' + ver + '";',
        '      console.info("[Unbanded] injected userscript v' + ver + ' loaded.");',  # noqa: E501
        "    }",
        "    // --- begin unbanded userscript (stripped of Tampermonkey header) ---",  # noqa: E501
        stripped, "    // --- end unbanded userscript ---", "  } catch (e) {",
        '    console.error("[Unbanded] injection failed:", e);', "  }",
        "})();", "",]
    return "\n".join(lines)


def inject_into_html(html):
    tag = '<script src="unbanded-injected.js"></script>'
    if "unbanded-injected.js" in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", "  " + tag + "\n</body>", 1)
    return html + "\n" + tag + "\n"


def do_patch(
        source,
        userscript,
        output,
        in_place=None,
        dry_run=False,
        log=print):
    """Run the patch. `log` is a callable(str). Raises on error."""
    source_dir = os.path.abspath(source)
    userscript_path = os.path.abspath(userscript)
    output_dir = os.path.abspath(output)

    log("[Unbanded Patcher]")
    log("  source      : " + source_dir)
    log("  userscript  : " + userscript_path)
    log("  output      : " + (in_place or output_dir))
    log("  dry-run     : " + str(dry_run).lower())

    asar_path = os.path.join(source_dir, "resources", "app.asar")
    if not os.path.exists(asar_path):
        raise FileNotFoundError("app.asar not found at " + asar_path)
    if not os.path.exists(userscript_path):
        raise FileNotFoundError("userscript not found at " + userscript_path)
    if dry_run:
        log("Dry run: inputs valid. No files written.")
        return

    with open(userscript_path, "r", encoding="utf-8") as f:
        userscript_code = f.read()
    payload = build_payload(userscript_code)

    work_dir = tempfile.mkdtemp(prefix="unbanded-patch-")
    try:
        extract_dir = os.path.join(work_dir, "extracted")
        mkdirp(extract_dir)
        log("Extracting app.asar ...")
        run_asar(["extract", asar_path, extract_dir], log)

        with open(os.path.join(extract_dir, "unbanded-injected.js"), "w", encoding="utf-8") as f:  # noqa: E501
            f.write(payload)
        log("Wrote unbanded-injected.js (" + str(len(payload)) + " bytes)")

        main_html_path = os.path.join(extract_dir, "main.html")
        if os.path.exists(main_html_path):
            with open(main_html_path, "r", encoding="utf-8") as f:
                html = f.read()
            with open(main_html_path, "w", encoding="utf-8") as f:
                f.write(inject_into_html(html))
            log("Injected script tag into main.html")
        else:
            log("WARNING: main.html not found in asar; payload written but not auto-loaded.")  # noqa: E501

        if in_place:
            band_dir = os.path.abspath(in_place)
            target_asar = os.path.join(band_dir, "resources", "app.asar")
            if not os.path.exists(target_asar):
                raise FileNotFoundError(
                    "target app.asar not found at " + target_asar)
            backup = target_asar + ".bak"
            if not os.path.exists(backup):
                shutil.copy2(target_asar, backup)
                log("Backup created: " + backup)
            out_asar = os.path.join(work_dir, "app.asar")
            run_asar(["pack", extract_dir, out_asar], log)
            shutil.copy2(out_asar, target_asar)
            log("Patched in place: " + target_asar)
        else:
            mkdirp(output_dir)
            src_unpacked = os.path.join(
                source_dir, "resources", "app.asar.unpacked")
            dst_unpacked = os.path.join(
                output_dir, "resources", "app.asar.unpacked")
            if os.path.exists(src_unpacked):
                copy_dir(src_unpacked, dst_unpacked)
            # copy whole source tree (originals only read)
            copy_dir(source_dir, output_dir)
            run_asar(["pack", extract_dir, os.path.join(
                output_dir, "resources", "app.asar")], log)
            log("Patched app tree written: " + output_dir)
    finally:
        rmrf(work_dir)
    log("Done.")


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass
    PatcherGUI().mainloop()


if __name__ == "__main__":
    main()
