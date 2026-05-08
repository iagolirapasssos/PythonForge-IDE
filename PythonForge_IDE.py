#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PythonForge IDE - Cross-Platform Python IDE
Dark Theme (Monokai/Sublime Text Style)
Compatible with Linux, Windows and macOS
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import subprocess
import sys
import os
import re
import ast
import threading
import json
import venv
import shutil
import platform
import tempfile
import queue
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────
#  COLOUR PALETTE  (Monokai / Sublime-like)
# ─────────────────────────────────────────────
C = {
    "bg":          "#1E1E1E",   # editor background
    "bg2":         "#252526",   # sidebar / panels
    "bg3":         "#2D2D2D",   # tab bar
    "bg4":         "#333333",   # active tab
    "fg":          "#D4D4D4",   # default text
    "fg2":         "#9D9D9D",   # dimmed text / line numbers
    "accent":      "#FF6B35",   # orange accent (PythonForge brand)
    "accent2":     "#0078D4",   # blue accent
    "border":      "#3E3E3E",
    "selection":   "#264F78",
    "cursor":      "#AEAFAD",
    "lineno_bg":   "#252526",
    # Syntax tokens
    "kw":    "#569CD6",   # keywords  (blue)
    "str":   "#CE9178",   # strings   (orange-brown)
    "num":   "#B5CEA8",   # numbers   (green)
    "cmt":   "#6A9955",   # comments  (green)
    "func":  "#DCDCAA",   # functions (yellow)
    "cls":   "#4EC9B0",   # classes   (teal)
    "dec":   "#C586C0",   # decorators(purple)
    "bltin": "#4FC1FF",   # builtins  (light blue)
    "self":  "#9CDCFE",   # self/cls  (sky)
    "op":    "#D4D4D4",   # operators
    "error": "#F44747",   # errors
    "warn":  "#FFCC02",   # warnings
    "ok":    "#89D185",   # success
}

PYTHON_KEYWORDS = {
    "False","None","True","and","as","assert","async","await",
    "break","class","continue","def","del","elif","else","except",
    "finally","for","from","global","if","import","in","is","lambda",
    "nonlocal","not","or","pass","raise","return","try","while",
    "with","yield",
}

PYTHON_BUILTINS = {
    "abs","all","any","ascii","bin","bool","breakpoint","bytearray",
    "bytes","callable","chr","classmethod","compile","complex","copyright",
    "delattr","dict","dir","divmod","enumerate","eval","exec","filter",
    "float","format","frozenset","getattr","globals","hasattr","hash",
    "help","hex","id","input","int","isinstance","issubclass","iter",
    "len","list","locals","map","max","memoryview","min","next","object",
    "oct","open","ord","pow","print","property","range","repr","reversed",
    "round","set","setattr","slice","sorted","staticmethod","str","sum",
    "super","tuple","type","vars","zip","__import__","__name__","__file__",
}

# ─────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────

def get_python_exe(venv_path=None):
    """Return python executable path (venv-aware, cross-platform)."""
    if venv_path:
        if platform.system() == "Windows":
            exe = Path(venv_path) / "Scripts" / "python.exe"
        else:
            exe = Path(venv_path) / "bin" / "python"
        if exe.exists():
            return str(exe)
    return sys.executable

def get_pip_exe(venv_path=None):
    """Return pip executable path."""
    if venv_path:
        if platform.system() == "Windows":
            exe = Path(venv_path) / "Scripts" / "pip.exe"
        else:
            exe = Path(venv_path) / "bin" / "pip"
        if exe.exists():
            return str(exe)
    return None

def extract_imports(code):
    """Parse code and return a set of top-level module names being imported."""
    modules = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
    except SyntaxError:
        # Fallback: regex scan
        for m in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", code, re.M):
            modules.add(m.group(1))
    return modules

def is_stdlib(name):
    """Check if a module name is part of the standard library."""
    stdlib = sys.stdlib_module_names if hasattr(sys, "stdlib_module_names") else set()
    if not stdlib:
        # Fallback list for Python < 3.10
        import importlib.util
        try:
            spec = importlib.util.find_spec(name)
            if spec and spec.origin and "site-packages" not in (spec.origin or ""):
                return True
        except (ModuleNotFoundError, ValueError):
            pass
        return False
    return name in stdlib

# Pip package name aliases (import name → pip name)
PIP_ALIASES = {
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
    "wx": "wxPython",
    "gi": "PyGObject",
    "usb": "pyusb",
    "serial": "pyserial",
    "Crypto": "pycryptodome",
    "jwt": "PyJWT",
    "magic": "python-magic",
    "dateutil": "python-dateutil",
    "attr": "attrs",
    "MySQLdb": "mysqlclient",
    "psutil": "psutil",
}

def pip_name(import_name):
    return PIP_ALIASES.get(import_name, import_name)


# ─────────────────────────────────────────────
#  SYNTAX HIGHLIGHTER
# ─────────────────────────────────────────────

class SyntaxHighlighter:
    PATTERNS = [
        ("comment",   r"#[^\n]*"),
        ("string3dq", r'"""[\s\S]*?"""'),
        ("string3sq", r"'''[\s\S]*?'''"),
        ("stringdq",  r'"(?:\\.|[^"\\])*"'),
        ("stringsq",  r"'(?:\\.|[^'\\])*'"),
        ("decorator", r"@[A-Za-z_][A-Za-z0-9_.]*"),
        ("classdef",  r"\bclass\s+([A-Za-z_]\w*)"),
        ("funcdef",   r"\bdef\s+([A-Za-z_]\w*)"),
        ("number",    r"\b(?:0x[0-9A-Fa-f]+|0b[01]+|0o[0-7]+|\d+\.?\d*(?:[eE][+-]?\d+)?[jJ]?)\b"),
        ("keyword",   r"\b(?:" + "|".join(sorted(PYTHON_KEYWORDS, key=len, reverse=True)) + r")\b"),
        ("builtin",   r"\b(?:" + "|".join(sorted(PYTHON_BUILTINS, key=len, reverse=True)) + r")\b"),
        ("self_cls",  r"\b(?:self|cls)\b"),
        ("funcall",   r"\b([A-Za-z_]\w*)\s*(?=\()"),
    ]
    COMPILED = [(name, re.compile(pat)) for name, pat in PATTERNS]

    TAG_MAP = {
        "comment":   C["cmt"],
        "string3dq": C["str"],
        "string3sq": C["str"],
        "stringdq":  C["str"],
        "stringsq":  C["str"],
        "decorator": C["dec"],
        "classdef":  C["cls"],
        "funcdef":   C["func"],
        "number":    C["num"],
        "keyword":   C["kw"],
        "builtin":   C["bltin"],
        "self_cls":  C["self"],
        "funcall":   C["func"],
    }

    def __init__(self, text_widget):
        self.widget = text_widget
        for tag, color in self.TAG_MAP.items():
            text_widget.tag_configure(tag, foreground=color)
        text_widget.tag_configure("sel", background=C["selection"])

    def highlight(self, event=None):
        """Re-highlight the visible portion and schedule full highlight."""
        self.widget.after_idle(self._do_highlight)

    def _do_highlight(self):
        w = self.widget
        content = w.get("1.0", "end-1c")
        # Remove all syntax tags
        for tag in self.TAG_MAP:
            w.tag_remove(tag, "1.0", "end")
        for name, pattern in self.COMPILED:
            for m in pattern.finditer(content):
                start_idx = m.start()
                end_idx = m.end()
                # For classdef / funcdef, highlight only the name part (group 1)
                if name in ("classdef", "funcdef") and m.lastindex:
                    # First highlight keyword
                    kw_end = content.index(m.group(1), start_idx)
                    w.tag_add("keyword", f"1.0+{start_idx}c", f"1.0+{kw_end}c")
                    # Then name with class/func color
                    name_tag = "classdef" if name == "classdef" else "funcdef"
                    w.tag_add(name_tag, f"1.0+{kw_end}c", f"1.0+{end_idx}c")
                else:
                    w.tag_add(name, f"1.0+{start_idx}c", f"1.0+{end_idx}c")


# ─────────────────────────────────────────────
#  CUSTOM TEXT — proxy that fires <<Change>>
# ─────────────────────────────────────────────

class CustomText(tk.Text):
    """tk.Text subclass that generates <<Change>> on every content/scroll change."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rename the internal Tcl command and insert our proxy
        self._orig = self._w + "_orig"
        self.tk.call("rename", self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy)

    def _proxy(self, command, *args):
        try:
            result = self.tk.call(self._orig, command, *args)
        except tk.TclError:
            return ""

        # Fire <<Change>> for anything that can alter visible content or scroll pos
        if (command in ("insert", "replace", "delete")
                or (command == "mark"  and args[:1] == ("set",) and args[1:2] == ("insert",))
                or (command in ("yview", "xview"))):
            self.event_generate("<<Change>>", when="tail")

        return result


# ─────────────────────────────────────────────
#  LINE-NUMBER WIDGET
# ─────────────────────────────────────────────

class LineNumbers(tk.Canvas):
    """Canvas that draws line numbers beside a CustomText widget."""

    def __init__(self, parent, text_widget, **kw):
        super().__init__(parent, width=52, bg=C["lineno_bg"],
                         highlightthickness=0, **kw)
        self.text = text_widget
        # <<Change>> is fired by CustomText proxy on every edit/scroll
        self.text.bind("<<Change>>",   lambda e: self.after_idle(self.redraw))
        self.text.bind("<Configure>",  lambda e: self.after_idle(self.redraw))
        self.font = ("Consolas", 10)

    def redraw(self):
        self.delete("all")

        # Count total lines to decide canvas width
        total = int(self.text.index("end-1c").split(".")[0])
        needed_w = max(52, len(str(total)) * 9 + 16)
        if self.winfo_width() != needed_w:
            self.configure(width=needed_w)

        # Walk every visible display line
        i = self.text.index("@0,0")
        last_drawn = None

        while True:
            dline = self.text.dlineinfo(i)
            if dline is None:
                break

            y    = dline[1]          # pixel y of this line top
            line = i.split(".")[0]   # integer line number as string

            # Draw the number only for the first display-line of each logical line
            if line != last_drawn:
                self.create_text(
                    needed_w - 6, y,
                    anchor="ne",
                    text=line,
                    fill=C["fg2"],
                    font=self.font,
                )
                last_drawn = line

            # Advance to next display line (handles wrapped lines too)
            next_i = self.text.index(f"{i}+1display line")
            if next_i == i:   # no advance → end of file
                break
            i = next_i


# ─────────────────────────────────────────────
#  AUTO-COMPLETE (simple keyword popup)
# ─────────────────────────────────────────────

COMPLETIONS = sorted(PYTHON_KEYWORDS | PYTHON_BUILTINS)

class AutoComplete:
    def __init__(self, text_widget):
        self.w = text_widget
        self.popup = None
        self.listbox = None
        text_widget.bind("<KeyRelease>", self._on_key)
        text_widget.bind("<Escape>", self._hide)

    def _on_key(self, event):
        if event.keysym in ("Return","Tab","Escape","Up","Down","Left","Right"):
            return
        self._show()

    def _get_word(self):
        idx = self.w.index("insert")
        line_start = f"{idx.split('.')[0]}.0"
        text = self.w.get(line_start, idx)
        m = re.search(r"[A-Za-z_]\w*$", text)
        return m.group(0) if m else ""

    def _show(self):
        word = self._get_word()
        if len(word) < 2:
            self._hide()
            return
        matches = [c for c in COMPLETIONS if c.startswith(word) and c != word]
        if not matches:
            self._hide()
            return
        if self.popup is None:
            self.popup = tk.Toplevel(self.w)
            self.popup.wm_overrideredirect(True)
            self.popup.config(bg=C["border"])
            self.listbox = tk.Listbox(self.popup, bg=C["bg3"], fg=C["fg"],
                                      selectbackground=C["accent2"],
                                      font=("Consolas", 10), relief="flat",
                                      bd=0, height=6)
            self.listbox.pack(fill="both", expand=True, padx=1, pady=1)
            self.listbox.bind("<Double-Button-1>", self._complete)
            self.listbox.bind("<Return>", self._complete)
        self.listbox.delete(0, "end")
        for m in matches[:10]:
            self.listbox.insert("end", m)
        self.listbox.select_set(0)
        # Position popup below cursor
        bbox = self.w.bbox("insert")
        if bbox:
            x = self.w.winfo_rootx() + bbox[0]
            y = self.w.winfo_rooty() + bbox[1] + bbox[3] + 2
            self.popup.geometry(f"160x120+{x}+{y}")
            self.popup.deiconify()

    def _complete(self, event=None):
        if self.popup and self.listbox.curselection():
            chosen = self.listbox.get(self.listbox.curselection()[0])
            word = self._get_word()
            idx = self.w.index("insert")
            start = f"{idx.split('.')[0]}.{int(idx.split('.')[1]) - len(word)}"
            self.w.delete(start, "insert")
            self.w.insert("insert", chosen)
        self._hide()

    def _hide(self, event=None):
        if self.popup:
            self.popup.destroy()
            self.popup = None
            self.listbox = None


# ─────────────────────────────────────────────
#  EDITOR TAB
# ─────────────────────────────────────────────

class EditorTab:
    def __init__(self, notebook, filepath=None):
        self.notebook = notebook
        self.filepath = filepath
        self.modified = False
        self.frame = ttk.Frame(notebook)

        # Line numbers + editor side by side
        self.line_frame = tk.Frame(self.frame, bg=C["lineno_bg"])
        self.line_frame.pack(side="left", fill="y")

        self.editor = CustomText(
            self.frame,
            bg=C["bg"], fg=C["fg"],
            insertbackground=C["cursor"],
            selectbackground=C["selection"],
            font=("Consolas", 12),
            undo=True, wrap="none",
            relief="flat", bd=0,
            padx=8, pady=4,
            tabs=("1c",),
        )
        self.scrolly = ttk.Scrollbar(self.frame, orient="vertical",
                                     command=self.editor.yview)
        self.scrollx = ttk.Scrollbar(self.frame, orient="horizontal",
                                     command=self.editor.xview)

        def _yscroll(first, last):
            self.scrolly.set(first, last)
            if hasattr(self, "linenums"):
                self.linenums.after_idle(self.linenums.redraw)

        self.editor.configure(yscrollcommand=_yscroll,
                               xscrollcommand=self.scrollx.set)

        self.scrollx.pack(side="bottom", fill="x")
        self.scrolly.pack(side="right", fill="y")
        self.editor.pack(side="left", fill="both", expand=True)

        self.linenums = LineNumbers(self.line_frame, self.editor)
        self.linenums.pack(fill="y", expand=True)

        self.highlighter = SyntaxHighlighter(self.editor)
        self.autocomplete = AutoComplete(self.editor)

        self.editor.bind("<<Modified>>", self._on_modified)
        self.editor.bind("<KeyRelease>", self._on_keyrelease)
        self.editor.bind("<Tab>", self._on_tab)
        self.editor.bind("<Return>", self._on_return)
        self.editor.bind("<Control-z>", lambda e: self.editor.edit_undo())
        self.editor.bind("<Control-y>", lambda e: self.editor.edit_redo())

        if filepath and Path(filepath).exists():
            self.load_file()

    # ── Tab → 4 spaces
    def _on_tab(self, event):
        self.editor.insert("insert", "    ")
        return "break"

    # ── Auto-indent
    def _on_return(self, event):
        idx = self.editor.index("insert")
        line = idx.split(".")[0]
        text = self.editor.get(f"{line}.0", f"{line}.end")
        indent = len(text) - len(text.lstrip())
        extra = 4 if text.rstrip().endswith(":") else 0
        self.editor.insert("insert", "\n" + " " * (indent + extra))
        return "break"

    def _on_modified(self, event=None):
        if self.editor.edit_modified():
            self.modified = True
            self.editor.edit_modified(False)
            self._update_tab_title()

    def _on_keyrelease(self, event=None):
        self.highlighter.highlight()
        # linenums redraw is driven automatically by <<Change>> from CustomText

    def _update_tab_title(self):
        title = self.get_title()
        idx = self.notebook.index(self.frame)
        self.notebook.tab(idx, text=("● " if self.modified else "") + title)

    def get_title(self):
        if self.filepath:
            return Path(self.filepath).name
        return "Untitled"

    def get_content(self):
        return self.editor.get("1.0", "end-1c")

    def set_content(self, text):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)
        self.editor.edit_modified(False)
        self.modified = False
        self.highlighter.highlight()
        self.linenums.redraw()

    def load_file(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.set_content(f.read())
            self.modified = False
            self._update_tab_title()
        except Exception as e:
            messagebox.showerror("Erro ao abrir", str(e))

    def save(self):
        if not self.filepath:
            return self.save_as()
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write(self.get_content())
            self.modified = False
            self._update_tab_title()
            return True
        except Exception as e:
            messagebox.showerror("Erro ao salvar", str(e))
            return False

    def save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        if path:
            self.filepath = path
            return self.save()
        return False


# ─────────────────────────────────────────────
#  TERMINAL / OUTPUT PANEL
# ─────────────────────────────────────────────

class Terminal(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["bg2"], **kw)
        self.proc = None
        self.q = queue.Queue()

        toolbar = tk.Frame(self, bg=C["bg3"], height=28)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        tk.Label(toolbar, text=" ⬛ TERMINAL", bg=C["bg3"], fg=C["fg2"],
                 font=("Consolas", 9, "bold")).pack(side="left", padx=6)

        btn_style = dict(bg=C["bg4"], fg=C["fg"], relief="flat", bd=0,
                         font=("Consolas", 9), padx=6, pady=2, cursor="hand2")
        tk.Button(toolbar, text="⬜ Limpar", command=self.clear, **btn_style).pack(side="right", padx=4)
        tk.Button(toolbar, text="⏹ Parar", command=self.stop, **btn_style).pack(side="right", padx=4)

        self.out = tk.Text(self, bg="#0D0D0D", fg=C["fg"], font=("Consolas", 11),
                           state="disabled", relief="flat", bd=0, padx=8, pady=4,
                           wrap="word", insertbackground=C["cursor"])
        sc = ttk.Scrollbar(self, command=self.out.yview)
        self.out.configure(yscrollcommand=sc.set)
        sc.pack(side="right", fill="y")
        self.out.pack(fill="both", expand=True)

        # Color tags
        self.out.tag_configure("error",   foreground=C["error"])
        self.out.tag_configure("warn",    foreground=C["warn"])
        self.out.tag_configure("ok",      foreground=C["ok"])
        self.out.tag_configure("info",    foreground=C["accent2"])
        self.out.tag_configure("accent",  foreground=C["accent"])
        self.out.tag_configure("dim",     foreground=C["fg2"])

        # Input bar
        inp_frame = tk.Frame(self, bg=C["bg3"])
        inp_frame.pack(fill="x")
        tk.Label(inp_frame, text="›", bg=C["bg3"], fg=C["accent"],
                 font=("Consolas", 14)).pack(side="left", padx=4)
        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(inp_frame, textvariable=self.input_var,
                                    bg=C["bg3"], fg=C["fg"],
                                    insertbackground=C["fg"],
                                    relief="flat", font=("Consolas", 11))
        self.input_entry.pack(side="left", fill="x", expand=True, pady=4)
        self.input_entry.bind("<Return>", self._send_input)

        self._poll()

    def _poll(self):
        try:
            while True:
                tag, text = self.q.get_nowait()
                self._append(text, tag)
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def _append(self, text, tag=None):
        self.out.configure(state="normal")
        if tag:
            self.out.insert("end", text, tag)
        else:
            self.out.insert("end", text)
        self.out.see("end")
        self.out.configure(state="disabled")

    def write(self, text, tag=None):
        self.q.put((tag, text))

    def clear(self):
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        self.out.configure(state="disabled")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.write("\n[Processo interrompido]\n", "warn")

    def _send_input(self, event=None):
        text = self.input_var.get()
        if self.proc and self.proc.stdin:
            try:
                self.proc.stdin.write(text + "\n")
                self.proc.stdin.flush()
                self.write(f"› {text}\n", "dim")
            except Exception:
                pass
        self.input_var.set("")

    def run_code(self, code, python_exe, extra_env=None):
        self.stop()
        self.clear()
        self.write("─" * 60 + "\n", "dim")
        self.write(f"  Python: {python_exe}\n", "info")
        self.write(f"  {datetime.now().strftime('%H:%M:%S')}\n", "dim")
        self.write("─" * 60 + "\n", "dim")

        # Write to temp file
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                          delete=False, encoding="utf-8")
        tmp.write(code)
        tmp.close()

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        try:
            self.proc = subprocess.Popen(
                [python_exe, tmp.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                env=env,
                bufsize=1,
            )
        except Exception as e:
            self.write(f"Erro ao iniciar: {e}\n", "error")
            return

        def read_stream(stream, tag):
            for line in iter(stream.readline, ""):
                self.write(line, tag)
            stream.close()

        threading.Thread(target=read_stream,
                         args=(self.proc.stdout, None), daemon=True).start()
        threading.Thread(target=read_stream,
                         args=(self.proc.stderr, "error"), daemon=True).start()

        def wait_proc():
            code = self.proc.wait()
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
            if code == 0:
                self.write(f"\n✓ Concluído (código {code})\n", "ok")
            else:
                self.write(f"\n✗ Encerrado com código {code}\n", "error")

        threading.Thread(target=wait_proc, daemon=True).start()

    def run_command(self, cmd, cwd=None, on_done=None):
        """Run a shell command and stream output."""
        self.write(f"\n$ {' '.join(cmd)}\n", "info")
        env = os.environ.copy()

        def _run():
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, env=env, cwd=cwd,
                )
                for line in iter(proc.stdout.readline, ""):
                    self.write(line)
                proc.wait()
                if on_done:
                    self.after(0, on_done, proc.returncode)
            except Exception as e:
                self.write(f"Erro: {e}\n", "error")
                if on_done:
                    self.after(0, on_done, -1)

        threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────
#  PACKAGE MANAGER DIALOG
# ─────────────────────────────────────────────

class PackageManager(tk.Toplevel):
    def __init__(self, parent, terminal, python_exe_fn):
        super().__init__(parent)
        self.title("Gerenciador de Pacotes")
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self.geometry("640x480")
        self.python_exe_fn = python_exe_fn
        self.terminal = terminal

        # Search bar
        top = tk.Frame(self, bg=C["bg2"], pady=6)
        top.pack(fill="x")
        tk.Label(top, text="Pacote:", bg=C["bg2"], fg=C["fg"],
                 font=("Consolas", 11)).pack(side="left", padx=8)
        self.pkg_var = tk.StringVar()
        entry = tk.Entry(top, textvariable=self.pkg_var, bg=C["bg4"],
                         fg=C["fg"], insertbackground=C["fg"],
                         relief="flat", font=("Consolas", 11), width=28)
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda e: self.install())

        btn_kw = dict(bg=C["accent"], fg="white", relief="flat",
                      font=("Consolas", 10, "bold"), padx=10, pady=4,
                      cursor="hand2", bd=0)
        tk.Button(top, text="⬇ Instalar", command=self.install, **btn_kw).pack(side="left", padx=4)
        btn_kw2 = dict(bg=C["bg4"], fg=C["fg"], relief="flat",
                       font=("Consolas", 10), padx=10, pady=4, cursor="hand2", bd=0)
        tk.Button(top, text="🗑 Desinstalar", command=self.uninstall, **btn_kw2).pack(side="left", padx=4)
        tk.Button(top, text="↻ Atualizar lista", command=self.refresh, **btn_kw2).pack(side="right", padx=8)

        # Installed packages list
        mid = tk.Frame(self, bg=C["bg"])
        mid.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(mid, text="Pacotes instalados:", bg=C["bg"], fg=C["fg2"],
                 font=("Consolas", 9)).pack(anchor="w")
        lst_frame = tk.Frame(mid, bg=C["bg3"])
        lst_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(lst_frame, bg=C["bg3"], fg=C["fg"],
                                  selectbackground=C["accent2"],
                                  font=("Consolas", 10), relief="flat", bd=0)
        sc = ttk.Scrollbar(lst_frame, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sc.set)
        sc.pack(side="right", fill="y")
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        self.status = tk.Label(self, text="", bg=C["bg"], fg=C["fg2"],
                               font=("Consolas", 9))
        self.status.pack(anchor="w", padx=8, pady=2)

        self.refresh()

    def _on_select(self, event=None):
        sel = self.listbox.curselection()
        if sel:
            pkg = self.listbox.get(sel[0]).split(" ")[0]
            self.pkg_var.set(pkg)

    def refresh(self):
        self.status.config(text="Carregando lista…", fg=C["fg2"])
        py = self.python_exe_fn()
        def _do():
            try:
                result = subprocess.run(
                    [py, "-m", "pip", "list", "--format=columns"],
                    capture_output=True, text=True
                )
                lines = result.stdout.strip().split("\n")[2:]  # skip header
                self.after(0, self._populate, lines)
            except Exception as e:
                self.after(0, lambda: self.status.config(
                    text=f"Erro: {e}", fg=C["error"]))
        threading.Thread(target=_do, daemon=True).start()

    def _populate(self, lines):
        self.listbox.delete(0, "end")
        for line in lines:
            if line.strip():
                self.listbox.insert("end", line.strip())
        self.status.config(text=f"{len(lines)} pacotes instalados", fg=C["ok"])

    def install(self):
        pkg = self.pkg_var.get().strip()
        if not pkg:
            return
        py = self.python_exe_fn()
        cmd = [py, "-m", "pip", "install", pkg]
        self.terminal.run_command(cmd, on_done=lambda rc: self.refresh())
        self.status.config(text=f"Instalando {pkg}…", fg=C["warn"])

    def uninstall(self):
        pkg = self.pkg_var.get().strip()
        if not pkg:
            return
        if not messagebox.askyesno("Confirmar", f"Desinstalar '{pkg}'?"):
            return
        py = self.python_exe_fn()
        cmd = [py, "-m", "pip", "uninstall", "-y", pkg]
        self.terminal.run_command(cmd, on_done=lambda rc: self.refresh())


# ─────────────────────────────────────────────
#  VIRTUAL ENVIRONMENT DIALOG
# ─────────────────────────────────────────────

class VenvManager(tk.Toplevel):
    def __init__(self, parent, terminal, on_venv_change):
        super().__init__(parent)
        self.title("Ambientes Virtuais")
        self.configure(bg=C["bg"])
        self.geometry("560x420")
        self.terminal = terminal
        self.on_venv_change = on_venv_change

        tk.Label(self, text="🐍  Ambientes Virtuais (venv)",
                 bg=C["bg"], fg=C["fg"], font=("Consolas", 12, "bold")).pack(pady=12)

        # Current venv info
        self.info_var = tk.StringVar(value="Nenhum ambiente ativo")
        tk.Label(self, textvariable=self.info_var, bg=C["bg"],
                 fg=C["accent"], font=("Consolas", 10)).pack()

        # Buttons
        btn_frame = tk.Frame(self, bg=C["bg"])
        btn_frame.pack(pady=10)
        btn_kw = dict(relief="flat", bd=0, font=("Consolas", 10),
                      padx=12, pady=6, cursor="hand2")
        tk.Button(btn_frame, text="➕ Criar Novo", bg=C["accent"], fg="white",
                  command=self.create_venv, **btn_kw).grid(row=0, column=0, padx=4)
        tk.Button(btn_frame, text="📂 Usar Existente", bg=C["bg4"], fg=C["fg"],
                  command=self.load_venv, **btn_kw).grid(row=0, column=1, padx=4)
        tk.Button(btn_frame, text="❌ Desativar", bg=C["bg4"], fg=C["fg"],
                  command=self.deactivate, **btn_kw).grid(row=0, column=2, padx=4)

        # List of detected envs
        tk.Label(self, text="Ambientes detectados na pasta atual:",
                 bg=C["bg"], fg=C["fg2"], font=("Consolas", 9)).pack(anchor="w", padx=16)

        lst_frame = tk.Frame(self, bg=C["bg3"])
        lst_frame.pack(fill="both", expand=True, padx=16, pady=8)
        self.listbox = tk.Listbox(lst_frame, bg=C["bg3"], fg=C["fg"],
                                  selectbackground=C["accent2"],
                                  font=("Consolas", 10), relief="flat", bd=0)
        sc = ttk.Scrollbar(lst_frame, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sc.set)
        sc.pack(side="right", fill="y")
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<Double-Button-1>", self._activate_selected)

        tk.Button(self, text="✓ Ativar selecionado", bg=C["accent2"], fg="white",
                  command=self._activate_selected, relief="flat", bd=0,
                  font=("Consolas", 10), padx=12, pady=6, cursor="hand2").pack(pady=4)

        self._scan_envs()

    def _scan_envs(self):
        self.listbox.delete(0, "end")
        cwd = Path.cwd()
        for d in cwd.iterdir():
            if d.is_dir():
                # Check if it looks like a venv
                if (d / "pyvenv.cfg").exists():
                    self.listbox.insert("end", str(d))

    def create_venv(self):
        name = simpledialog.askstring("Nome", "Nome do ambiente virtual:",
                                      initialvalue="venv", parent=self)
        if not name:
            return
        path = Path.cwd() / name
        if path.exists():
            messagebox.showerror("Erro", f"'{name}' já existe.", parent=self)
            return

        def _create():
            try:
                self.terminal.write(f"\nCriando venv '{name}'…\n", "info")
                venv.create(str(path), with_pip=True)
                self.terminal.write(f"✓ Ambiente '{name}' criado!\n", "ok")
                self.after(0, lambda: self.on_venv_change(str(path)))
                self.after(0, self._scan_envs)
                self.after(0, lambda: self.info_var.set(f"Ativo: {path}"))
            except Exception as e:
                self.terminal.write(f"Erro: {e}\n", "error")

        threading.Thread(target=_create, daemon=True).start()

    def load_venv(self):
        path = filedialog.askdirectory(title="Selecionar pasta do venv", parent=self)
        if path and (Path(path) / "pyvenv.cfg").exists():
            self.on_venv_change(path)
            self.info_var.set(f"Ativo: {path}")
            self.terminal.write(f"\n✓ Usando venv: {path}\n", "ok")
        elif path:
            messagebox.showerror("Erro", "Pasta não parece ser um ambiente virtual.", parent=self)

    def deactivate(self):
        self.on_venv_change(None)
        self.info_var.set("Nenhum ambiente ativo")
        self.terminal.write("\nVenv desativado. Usando Python do sistema.\n", "warn")

    def _activate_selected(self, event=None):
        sel = self.listbox.curselection()
        if sel:
            path = self.listbox.get(sel[0])
            self.on_venv_change(path)
            self.info_var.set(f"Ativo: {path}")
            self.terminal.write(f"\n✓ Ativado: {path}\n", "ok")


# ─────────────────────────────────────────────
#  FIND / REPLACE BAR
# ─────────────────────────────────────────────

class FindBar(tk.Frame):
    def __init__(self, parent, get_editor):
        super().__init__(parent, bg=C["bg3"])
        self.get_editor = get_editor
        self.visible = False

        kw = dict(bg=C["bg3"], fg=C["fg2"], font=("Consolas", 10))
        tk.Label(self, text="Buscar:", **kw).pack(side="left", padx=4)
        self.find_var = tk.StringVar()
        tk.Entry(self, textvariable=self.find_var, bg=C["bg4"], fg=C["fg"],
                 insertbackground=C["fg"], relief="flat",
                 font=("Consolas", 11), width=24).pack(side="left", padx=2)

        tk.Label(self, text="Substituir:", **kw).pack(side="left", padx=4)
        self.replace_var = tk.StringVar()
        tk.Entry(self, textvariable=self.replace_var, bg=C["bg4"], fg=C["fg"],
                 insertbackground=C["fg"], relief="flat",
                 font=("Consolas", 11), width=20).pack(side="left", padx=2)

        btn_kw = dict(bg=C["bg4"], fg=C["fg"], relief="flat", bd=0,
                      font=("Consolas", 9), padx=8, pady=2, cursor="hand2")
        tk.Button(self, text="⬆", command=self.find_prev, **btn_kw).pack(side="left", padx=2)
        tk.Button(self, text="⬇", command=self.find_next, **btn_kw).pack(side="left", padx=2)
        tk.Button(self, text="Substituir", command=self.replace_one, **btn_kw).pack(side="left", padx=2)
        tk.Button(self, text="Todos", command=self.replace_all, **btn_kw).pack(side="left", padx=2)
        tk.Button(self, text="✕", command=self.hide, bg=C["bg3"], fg=C["fg2"],
                  relief="flat", bd=0, font=("Consolas", 10), cursor="hand2").pack(side="right", padx=4)

        self.count_label = tk.Label(self, text="", **kw)
        self.count_label.pack(side="left", padx=8)

    def show(self):
        self.pack(fill="x")
        self.visible = True

    def hide(self):
        self.pack_forget()
        self.visible = False

    def _editor(self):
        return self.get_editor()

    def find_next(self, from_pos="insert+1c"):
        ed = self._editor()
        if not ed:
            return
        term = self.find_var.get()
        if not term:
            return
        ed.tag_remove("found", "1.0", "end")
        start = ed.search(term, from_pos, stopindex="end", nocase=True)
        if start:
            end = f"{start}+{len(term)}c"
            ed.tag_add("found", start, end)
            ed.tag_configure("found", background=C["warn"], foreground="#000")
            ed.see(start)
            ed.mark_set("insert", start)
        else:
            # Wrap
            self.find_next("1.0")

    def find_prev(self):
        ed = self._editor()
        if not ed:
            return
        term = self.find_var.get()
        if not term:
            return
        ed.tag_remove("found", "1.0", "end")
        start = ed.search(term, "insert-1c", stopindex="1.0",
                          backwards=True, nocase=True)
        if start:
            end = f"{start}+{len(term)}c"
            ed.tag_add("found", start, end)
            ed.tag_configure("found", background=C["warn"], foreground="#000")
            ed.see(start)

    def replace_one(self):
        ed = self._editor()
        if not ed:
            return
        term = self.find_var.get()
        repl = self.replace_var.get()
        try:
            start = ed.index("found.first")
            end = ed.index("found.last")
            ed.delete(start, end)
            ed.insert(start, repl)
        except tk.TclError:
            self.find_next()

    def replace_all(self):
        ed = self._editor()
        if not ed:
            return
        term = self.find_var.get()
        repl = self.replace_var.get()
        if not term:
            return
        content = ed.get("1.0", "end-1c")
        new_content, n = re.subn(re.escape(term), repl, content, flags=re.IGNORECASE)
        if n:
            ed.delete("1.0", "end")
            ed.insert("1.0", new_content)
            self.count_label.config(text=f"{n} substituição(ões)", fg=C["ok"])
        else:
            self.count_label.config(text="Não encontrado", fg=C["error"])


# ─────────────────────────────────────────────
#  MAIN IDE WINDOW
# ─────────────────────────────────────────────

class PythonForgeIDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PythonForge IDE")
        self.geometry("1280x800")
        self.configure(bg=C["bg"])
        self.minsize(900, 600)

        self.venv_path = None   # currently active venv
        self.tabs: list[EditorTab] = []
        self.recent_files = []

        self._setup_styles()
        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()

        # Open a blank tab on start
        self.new_file()

        # Detect missing imports every time file is saved
        self._auto_detect_enabled = True

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Styles ────────────────────────────────

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=C["bg3"], borderwidth=0,
                        tabmargins=[0, 0, 0, 0])
        style.configure("TNotebook.Tab", background=C["bg3"], foreground=C["fg2"],
                        padding=[12, 6], font=("Consolas", 10), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", C["bg4"]), ("active", C["bg4"])],
                  foreground=[("selected", C["fg"]), ("active", C["fg"])])
        style.configure("Vertical.TScrollbar", background=C["bg3"],
                        troughcolor=C["bg2"], borderwidth=0, arrowsize=12)
        style.configure("Horizontal.TScrollbar", background=C["bg3"],
                        troughcolor=C["bg2"], borderwidth=0, arrowsize=12)
        style.configure("TPanedwindow", background=C["bg"])
        style.configure("TSeparator", background=C["border"])

    # ── Menu ──────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self, bg=C["bg2"], fg=C["fg"],
                          activebackground=C["accent2"], activeforeground="white",
                          relief="flat", bd=0)
        self.configure(menu=menubar)

        def menu(label):
            m = tk.Menu(menubar, tearoff=0, bg=C["bg2"], fg=C["fg"],
                        activebackground=C["accent2"], activeforeground="white",
                        relief="flat", bd=0)
            menubar.add_cascade(label=label, menu=m)
            return m

        # File
        f = menu("Arquivo")
        f.add_command(label="Novo               Ctrl+N", command=self.new_file)
        f.add_command(label="Abrir…             Ctrl+O", command=self.open_file)
        f.add_command(label="Salvar             Ctrl+S", command=self.save_file)
        f.add_command(label="Salvar como…  Ctrl+Shift+S", command=self.save_as)
        f.add_separator()
        f.add_command(label="Fechar aba    Ctrl+W", command=self.close_tab)
        f.add_separator()
        f.add_command(label="Sair", command=self._on_close)

        # Edit
        e = menu("Editar")
        e.add_command(label="Desfazer   Ctrl+Z", command=lambda: self._current_editor() and self._current_editor().edit_undo())
        e.add_command(label="Refazer    Ctrl+Y", command=lambda: self._current_editor() and self._current_editor().edit_redo())
        e.add_separator()
        e.add_command(label="Buscar/Substituir  Ctrl+H", command=self.toggle_find)
        e.add_command(label="Comentar linha     Ctrl+/", command=self.toggle_comment)
        e.add_separator()
        e.add_command(label="Selecionar tudo    Ctrl+A", command=lambda: self._current_editor() and self._current_editor().tag_add("sel", "1.0", "end"))
        e.add_command(label="Ir para linha…     Ctrl+G", command=self.goto_line)

        # Run
        r = menu("Executar")
        r.add_command(label="▶  Executar código  F5",    command=self.run_code)
        r.add_command(label="⏹  Parar execução   F6",    command=lambda: self.terminal.stop())
        r.add_separator()
        r.add_command(label="🔍 Detectar imports ausentes", command=self.detect_missing_imports)

        # Packages
        p = menu("Pacotes")
        p.add_command(label="📦 Gerenciador de Pacotes  Ctrl+P", command=self.open_package_manager)
        p.add_separator()
        p.add_command(label="🐍 Ambientes Virtuais       Ctrl+E", command=self.open_venv_manager)

        # View
        v = menu("Exibir")
        v.add_command(label="Aumentar fonte  Ctrl++", command=lambda: self._change_font(1))
        v.add_command(label="Diminuir fonte  Ctrl+-", command=lambda: self._change_font(-1))
        v.add_separator()
        v.add_command(label="Limpar terminal", command=self.terminal.clear if hasattr(self, 'terminal') else lambda: None)

    # ── UI Layout ─────────────────────────────

    def _build_ui(self):
        # Top toolbar
        self._build_toolbar()

        # Main paned window (editor top, terminal bottom)
        self.main_pane = ttk.PanedWindow(self, orient="vertical")
        self.main_pane.pack(fill="both", expand=True)

        # Editor notebook
        editor_container = tk.Frame(self.main_pane, bg=C["bg"])
        self.main_pane.add(editor_container, weight=3)

        # Find bar (hidden by default)
        self.find_bar = FindBar(editor_container, self._current_editor)

        self.notebook = ttk.Notebook(editor_container)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

        # Terminal
        terminal_container = tk.Frame(self.main_pane, bg=C["bg2"])
        self.main_pane.add(terminal_container, weight=1)
        self.terminal = Terminal(terminal_container)
        self.terminal.pack(fill="both", expand=True)

        # Status bar
        self._build_statusbar()

        # Show welcome message
        self._welcome()

    def _build_toolbar(self):
        tb = tk.Frame(self, bg=C["bg3"], height=40)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        # Logo
        tk.Label(tb, text=" 🐍 PythonForge IDE",
                 bg=C["bg3"], fg=C["accent"],
                 font=("Consolas", 12, "bold")).pack(side="left", padx=8)

        sep = tk.Frame(tb, bg=C["border"], width=1)
        sep.pack(side="left", fill="y", padx=4)

        btn_kw = dict(bg=C["bg4"], fg=C["fg"], relief="flat", bd=0,
                      font=("Consolas", 10), padx=10, pady=6,
                      cursor="hand2", activebackground=C["bg3"],
                      activeforeground=C["fg"])

        tk.Button(tb, text="📄 Novo",      command=self.new_file,  **btn_kw).pack(side="left", padx=2)
        tk.Button(tb, text="📂 Abrir",     command=self.open_file, **btn_kw).pack(side="left", padx=2)
        tk.Button(tb, text="💾 Salvar",    command=self.save_file, **btn_kw).pack(side="left", padx=2)

        sep2 = tk.Frame(tb, bg=C["border"], width=1)
        sep2.pack(side="left", fill="y", padx=6)

        run_btn = tk.Button(tb, text="▶  Executar (F5)",
                            command=self.run_code,
                            bg=C["ok"], fg="#0D1117",
                            font=("Consolas", 10, "bold"),
                            relief="flat", bd=0, padx=14, pady=6,
                            cursor="hand2")
        run_btn.pack(side="left", padx=2)

        tk.Button(tb, text="⏹ Parar", command=lambda: self.terminal.stop(),
                  bg=C["error"], fg="white",
                  font=("Consolas", 10), relief="flat", bd=0,
                  padx=10, pady=6, cursor="hand2").pack(side="left", padx=2)

        sep3 = tk.Frame(tb, bg=C["border"], width=1)
        sep3.pack(side="left", fill="y", padx=6)

        tk.Button(tb, text="📦 Pacotes", command=self.open_package_manager, **btn_kw).pack(side="left", padx=2)
        tk.Button(tb, text="🐍 venv",    command=self.open_venv_manager,    **btn_kw).pack(side="left", padx=2)
        tk.Button(tb, text="🔍 Imports", command=self.detect_missing_imports, **btn_kw).pack(side="left", padx=2)

        # Venv indicator (right side)
        self.venv_label = tk.Label(tb, text="⚙ Sistema Python",
                                   bg=C["bg3"], fg=C["fg2"],
                                   font=("Consolas", 9))
        self.venv_label.pack(side="right", padx=12)

    def _build_statusbar(self):
        sb = tk.Frame(self, bg=C["bg2"], height=22)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)

        self.status_left = tk.Label(sb, text="Pronto", bg=C["bg2"], fg=C["fg2"],
                                    font=("Consolas", 9))
        self.status_left.pack(side="left", padx=8)

        self.status_pos = tk.Label(sb, text="Ln 1, Col 1", bg=C["bg2"], fg=C["fg2"],
                                   font=("Consolas", 9))
        self.status_pos.pack(side="right", padx=8)

        self.status_enc = tk.Label(sb, text="UTF-8  |  Python",
                                   bg=C["bg2"], fg=C["fg2"], font=("Consolas", 9))
        self.status_enc.pack(side="right", padx=8)

        self.after(200, self._update_status)

    def _update_status(self):
        ed = self._current_editor()
        if ed:
            idx = ed.index("insert")
            ln, col = idx.split(".")
            self.status_pos.config(text=f"Ln {ln}, Col {int(col)+1}")
        self.after(300, self._update_status)

    # ── Helpers ───────────────────────────────

    def _current_tab(self) -> EditorTab | None:
        if not self.tabs:
            return None
        try:
            current = self.notebook.select()
            for tab in self.tabs:
                if str(tab.frame) == current:
                    return tab
        except Exception:
            pass
        return self.tabs[-1] if self.tabs else None

    def _current_editor(self):
        tab = self._current_tab()
        return tab.editor if tab else None

    def _python_exe(self):
        return get_python_exe(self.venv_path)

    def _welcome(self):
        self.terminal.write("┌─────────────────────────────────────┐\n", "accent")
        self.terminal.write("│      🐍  PythonForge IDE  v1.0       │\n", "accent")
        self.terminal.write("│  Dark Theme · venv · Auto-Install    │\n", "accent")
        self.terminal.write("└─────────────────────────────────────┘\n", "accent")
        self.terminal.write(f"\n  Python: {sys.executable}\n", "info")
        self.terminal.write(f"  Versão: {sys.version.split()[0]}\n", "info")
        self.terminal.write(f"  SO: {platform.system()} {platform.release()}\n", "info")
        self.terminal.write("\n  F5  →  Executar código\n", "dim")
        self.terminal.write("  Ctrl+P  →  Gerenciador de pacotes\n", "dim")
        self.terminal.write("  Ctrl+E  →  Ambientes virtuais\n\n", "dim")

    # ── File operations ───────────────────────

    def new_file(self):
        tab = EditorTab(self.notebook)
        self.tabs.append(tab)
        self.notebook.add(tab.frame, text="Untitled")
        self.notebook.select(tab.frame)
        tab.editor.focus_set()

    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        if not path:
            return
        # Check if already open
        for tab in self.tabs:
            if tab.filepath == path:
                self.notebook.select(tab.frame)
                return
        tab = EditorTab(self.notebook, filepath=path)
        self.tabs.append(tab)
        self.notebook.add(tab.frame, text=Path(path).name)
        self.notebook.select(tab.frame)
        tab.editor.focus_set()

    def save_file(self):
        tab = self._current_tab()
        if tab:
            if tab.save():
                self.status_left.config(text=f"Salvo: {tab.get_title()}", fg=C["ok"])
                if self._auto_detect_enabled:
                    self.detect_missing_imports(silent=True)

    def save_as(self):
        tab = self._current_tab()
        if tab:
            tab.save_as()

    def close_tab(self):
        tab = self._current_tab()
        if not tab:
            return
        if tab.modified:
            ans = messagebox.askyesnocancel(
                "Salvar?", f"'{tab.get_title()}' tem alterações não salvas. Salvar?")
            if ans is None:
                return
            if ans:
                if not tab.save():
                    return
        self.notebook.forget(tab.frame)
        self.tabs.remove(tab)
        if not self.tabs:
            self.new_file()

    # ── Execution ─────────────────────────────

    def run_code(self):
        tab = self._current_tab()
        if not tab:
            return
        if tab.modified and tab.filepath:
            tab.save()
        code = tab.get_content()
        py = self._python_exe()
        self.terminal.run_code(code, py)
        self.status_left.config(text="Executando…", fg=C["warn"])

    # ── Import detection & auto-install ───────

    def detect_missing_imports(self, silent=False):
        tab = self._current_tab()
        if not tab:
            return
        code = tab.get_content()
        imports = extract_imports(code)
        py = self._python_exe()
        missing = []

        for mod in imports:
            if is_stdlib(mod):
                continue
            try:
                result = subprocess.run(
                    [py, "-c", f"import {mod}"],
                    capture_output=True, timeout=5
                )
                if result.returncode != 0:
                    missing.append(mod)
            except Exception:
                missing.append(mod)

        if not missing:
            if not silent:
                self.terminal.write("\n✓ Todos os imports estão disponíveis.\n", "ok")
            return

        pkg_names = [pip_name(m) for m in missing]
        self.terminal.write(f"\n⚠ Imports ausentes: {', '.join(missing)}\n", "warn")

        if silent:
            ans = messagebox.askyesno(
                "Imports ausentes",
                f"Módulos não instalados:\n  {', '.join(pkg_names)}\n\nInstalar automaticamente?"
            )
        else:
            ans = messagebox.askyesno(
                "Instalar pacotes ausentes",
                f"Os seguintes pacotes não foram encontrados:\n\n  {chr(10).join(pkg_names)}\n\n"
                "Deseja instalar automaticamente?"
            )
        if ans:
            cmd = [py, "-m", "pip", "install"] + pkg_names
            self.terminal.run_command(cmd, on_done=lambda rc:
                self.terminal.write("✓ Pacotes instalados!\n", "ok") if rc == 0
                else self.terminal.write("✗ Falha na instalação.\n", "error")
            )

    # ── Find/Replace ──────────────────────────

    def toggle_find(self):
        if self.find_bar.visible:
            self.find_bar.hide()
        else:
            self.find_bar.show()

    def toggle_comment(self):
        ed = self._current_editor()
        if not ed:
            return
        try:
            start = ed.index("sel.first linestart")
            end = ed.index("sel.last lineend")
        except tk.TclError:
            start = ed.index("insert linestart")
            end = ed.index("insert lineend")
        lines = ed.get(start, end).split("\n")
        all_commented = all(l.lstrip().startswith("#") or l.strip() == "" for l in lines)
        new_lines = []
        for line in lines:
            if all_commented:
                new_lines.append(re.sub(r"^(\s*)# ?", r"\1", line, count=1))
            else:
                stripped = line.lstrip()
                indent = line[:len(line) - len(stripped)]
                new_lines.append(f"{indent}# {stripped}" if stripped else line)
        ed.delete(start, end)
        ed.insert(start, "\n".join(new_lines))

    def goto_line(self):
        ed = self._current_editor()
        if not ed:
            return
        line = simpledialog.askinteger("Ir para linha", "Número da linha:", parent=self)
        if line:
            ed.see(f"{line}.0")
            ed.mark_set("insert", f"{line}.0")
            ed.focus_set()

    # ── Package manager ───────────────────────

    def open_package_manager(self):
        PackageManager(self, self.terminal, self._python_exe)

    # ── Venv manager ──────────────────────────

    def open_venv_manager(self):
        VenvManager(self, self.terminal, self._set_venv)

    def _set_venv(self, path):
        self.venv_path = path
        if path:
            py = get_python_exe(path)
            self.venv_label.config(text=f"🐍 venv: {Path(path).name}", fg=C["ok"])
            self.status_enc.config(text=f"UTF-8  |  venv:{Path(path).name}")
        else:
            self.venv_label.config(text="⚙ Sistema Python", fg=C["fg2"])
            self.status_enc.config(text="UTF-8  |  Python")

    # ── Font size ─────────────────────────────

    def _change_font(self, delta):
        for tab in self.tabs:
            current = tab.editor.cget("font")
            try:
                parts = list(self.tk.splitlist(current))
                size = int(parts[1]) + delta
                size = max(8, min(32, size))
                parts[1] = str(size)
                tab.editor.configure(font=tuple(parts))
            except Exception:
                pass

    # ── Tab events ────────────────────────────

    def _on_tab_change(self, event=None):
        tab = self._current_tab()
        if tab:
            tab.editor.focus_set()
            tab.highlighter.highlight()

    # ── Shortcuts ─────────────────────────────

    def _bind_shortcuts(self):
        self.bind("<F5>",              lambda e: self.run_code())
        self.bind("<F6>",              lambda e: self.terminal.stop())
        self.bind("<Control-n>",       lambda e: self.new_file())
        self.bind("<Control-o>",       lambda e: self.open_file())
        self.bind("<Control-s>",       lambda e: self.save_file())
        self.bind("<Control-S>",       lambda e: self.save_as())
        self.bind("<Control-w>",       lambda e: self.close_tab())
        self.bind("<Control-p>",       lambda e: self.open_package_manager())
        self.bind("<Control-e>",       lambda e: self.open_venv_manager())
        self.bind("<Control-h>",       lambda e: self.toggle_find())
        self.bind("<Control-slash>",   lambda e: self.toggle_comment())
        self.bind("<Control-g>",       lambda e: self.goto_line())
        self.bind("<Control-equal>",   lambda e: self._change_font(1))
        self.bind("<Control-minus>",   lambda e: self._change_font(-1))

    # ── Close ─────────────────────────────────

    def _on_close(self):
        modified = [t for t in self.tabs if t.modified]
        if modified:
            names = ", ".join(t.get_title() for t in modified)
            ans = messagebox.askyesnocancel(
                "Sair", f"Arquivo(s) com alterações não salvas:\n{names}\n\nSalvar antes de sair?")
            if ans is None:
                return
            if ans:
                for t in modified:
                    t.save()
        self.destroy()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # On macOS, allow high-DPI rendering
    if platform.system() == "Darwin":
        from subprocess import call
        call(["defaults", "write", "NSGlobalDomain", "AppleFontSmoothing", "-int", "0"],
             stderr=subprocess.DEVNULL)

    # On Windows, enable DPI awareness
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    app = PythonForgeIDE()
    app.mainloop()