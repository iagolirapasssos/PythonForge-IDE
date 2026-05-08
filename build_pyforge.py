#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PythonForge IDE — Build Script
Generates executables for Linux, Windows and macOS.

Usage:
  python build_pyforge.py              # auto-detect current OS
  python build_pyforge.py --linux      # force Linux binary
  python build_pyforge.py --windows    # Windows .exe (needs Wine on Linux/macOS)
  python build_pyforge.py --mac        # macOS .app (only works on macOS)
  python build_pyforge.py --all        # all targets (limited by available tools)
  python build_pyforge.py --installer  # create NSIS installer (Windows, needs nsis)
"""

import sys
import os
import subprocess
import platform
import shutil
import argparse
from pathlib import Path

# ─────────────────────────────────────────────
SCRIPT      = "PythonForge_IDE.py"
APP_NAME    = "PythonForge IDE"
APP_ID      = "PythonForgeIDE"
VERSION     = "1.0.0"
ICON_ICO    = "icon.ico"    # optional — place beside this script
ICON_PNG    = "icon.png"    # optional
ICON_ICNS   = "icon.icns"   # optional (macOS)
DIST_DIR    = Path("dist")
BUILD_DIR   = Path("build")
# ─────────────────────────────────────────────

OS = platform.system()   # "Linux" | "Windows" | "Darwin"

def run(cmd, **kw):
    print(f"\n$ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kw)
    if result.returncode != 0:
        print(f"[ERRO] Saiu com código {result.returncode}")
        sys.exit(result.returncode)
    return result

def pip_install(pkg):
    run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", pkg])

def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa
        print("✓ PyInstaller já instalado")
    except ImportError:
        print("→ Instalando PyInstaller…")
        pip_install("pyinstaller")

def icon_flag(os_target):
    """Return --icon=... flag if a suitable icon file exists."""
    if os_target == "windows" and Path(ICON_ICO).exists():
        return [f"--icon={ICON_ICO}"]
    if os_target == "linux" and Path(ICON_PNG).exists():
        return [f"--icon={ICON_PNG}"]
    if os_target == "mac" and Path(ICON_ICNS).exists():
        return [f"--icon={ICON_ICNS}"]
    return []

def pyinstaller_base(os_target):
    """Common PyInstaller flags."""
    return [
        "pyinstaller",
        "--onefile",
        "--clean",
        f"--name={APP_ID}",
        f"--distpath=dist/{os_target}",
        f"--workpath=build/{os_target}",
        f"--specpath=build/{os_target}",
        *icon_flag(os_target),
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        "--hidden-import=tkinter.filedialog",
        "--hidden-import=tkinter.messagebox",
        "--hidden-import=tkinter.simpledialog",
        "--collect-all=tkinter",
    ]

# ─────────────────────────────────────────────
#  LINUX
# ─────────────────────────────────────────────

def build_linux():
    print("\n" + "═"*50)
    print("  BUILD: Linux (ELF binary)")
    print("═"*50)
    ensure_pyinstaller()

    cmd = [
        *pyinstaller_base("linux"),
        SCRIPT,
    ]
    run(cmd)

    out = Path(f"dist/linux/{APP_ID}")
    if out.exists():
        out.chmod(0o755)
        print(f"\n✓ Binário Linux: {out.resolve()}")
        _print_size(out)
    else:
        print("[ERRO] Arquivo não gerado.")

# ─────────────────────────────────────────────
#  WINDOWS  (nativo ou via Wine)
# ─────────────────────────────────────────────

def build_windows():
    print("\n" + "═"*50)
    print("  BUILD: Windows (.exe)")
    print("═"*50)

    if OS == "Windows":
        _build_windows_native()
    else:
        _build_windows_wine()

def _build_windows_native():
    ensure_pyinstaller()
    cmd = [
        *pyinstaller_base("windows"),
        "--noconsole",          # GUI app — no terminal window
        "--version-file=version_info.txt" if Path("version_info.txt").exists() else "",
        SCRIPT,
    ]
    cmd = [c for c in cmd if c]  # remove empty strings
    run(cmd)

    out = Path(f"dist/windows/{APP_ID}.exe")
    if out.exists():
        print(f"\n✓ Windows EXE: {out.resolve()}")
        _print_size(out)
    else:
        print("[ERRO] .exe não gerado.")

def _build_windows_wine():
    """
    Cross-compile Windows .exe from Linux/macOS using Wine + Python for Windows.
    Requires: wine, wine64, and Python Windows installer run under Wine.
    """
    wine = shutil.which("wine") or shutil.which("wine64")
    if not wine:
        print("""
[AVISO] Wine não encontrado. Para gerar .exe no Linux:

  Ubuntu/Debian:
    sudo dpkg --add-architecture i386
    sudo apt update
    sudo apt install wine wine64 winetricks

  Fedora:
    sudo dnf install wine

  Arch:
    sudo pacman -S wine

Após instalar Wine, configure um Python Windows:
  winetricks vcrun2019
  wine python-3.12.0-amd64.msi        ← baixe de python.org
  wine pip install pyinstaller

Depois execute:
  wine pyinstaller --onefile --noconsole --name PythonForgeIDE PythonForge_IDE.py
""")
        print("→ Tentando build com pyinstaller nativo (gerará binário Linux)…")
        build_linux()
        return

    # Check for Wine Python
    wine_python = Path(os.path.expanduser("~/.wine/drive_c/Python312/python.exe"))
    if not wine_python.exists():
        # Try common locations
        for p in Path(os.path.expanduser("~/.wine/drive_c")).glob("Python*/python.exe"):
            wine_python = p
            break

    if not wine_python.exists():
        print("""
[AVISO] Python para Windows não encontrado no Wine.

Instale com:
  wine python-3.12.0-amd64.msi
  wine pip install pyinstaller

Depois execute manualmente:
  wine ~/.wine/drive_c/Python312/Scripts/pyinstaller.exe \\
      --onefile --noconsole --name PythonForgeIDE PythonForge_IDE.py
""")
        return

    print(f"  Usando Wine Python: {wine_python}")

    # Install PyInstaller under Wine Python if needed
    wine_pi = wine_python.parent / "Scripts" / "pyinstaller.exe"
    if not wine_pi.exists():
        print("→ Instalando PyInstaller no Wine Python…")
        run([wine, str(wine_python), "-m", "pip", "install", "pyinstaller"])

    Path("dist/windows").mkdir(parents=True, exist_ok=True)

    cmd = [
        wine, str(wine_pi),
        "--onefile",
        "--noconsole",
        "--clean",
        f"--name={APP_ID}",
        "--distpath=dist/windows",
        f"--workpath=build/windows",
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        SCRIPT,
    ]
    if Path(ICON_ICO).exists():
        cmd += [f"--icon={ICON_ICO}"]
    run(cmd)

    out = Path(f"dist/windows/{APP_ID}.exe")
    if out.exists():
        print(f"\n✓ Windows EXE (via Wine): {out.resolve()}")
        _print_size(out)
    else:
        print("[ERRO] .exe não gerado via Wine.")

# ─────────────────────────────────────────────
#  MACOS
# ─────────────────────────────────────────────

def build_mac():
    print("\n" + "═"*50)
    print("  BUILD: macOS (.app bundle)")
    print("═"*50)

    if OS != "Darwin":
        print("""
[AVISO] Builds para macOS só podem ser feitos em um Mac.

Alternativas:
  • GitHub Actions com 'runs-on: macos-latest'
  • Serviço de build remoto (MacStadium, etc.)
  • VM macOS no Apple Silicon

Cole este script no Mac e execute:
  python build_pyforge.py --mac
""")
        return

    ensure_pyinstaller()

    cmd = [
        *pyinstaller_base("mac"),
        "--windowed",           # cria .app bundle (sem terminal)
        "--osx-bundle-identifier", f"com.pythonforge.{APP_ID.lower()}",
        SCRIPT,
    ]
    run(cmd)

    # PyInstaller creates APP_ID.app when --windowed is used on macOS
    app_bundle = Path(f"dist/mac/{APP_ID}.app")
    binary     = Path(f"dist/mac/{APP_ID}")

    if app_bundle.exists():
        print(f"\n✓ macOS App Bundle: {app_bundle.resolve()}")
        _pack_dmg(app_bundle)
    elif binary.exists():
        print(f"\n✓ macOS binary: {binary.resolve()}")
        _print_size(binary)
    else:
        print("[ERRO] .app não gerado.")

def _pack_dmg(app_bundle):
    """Create a .dmg disk image (requires hdiutil, macOS only)."""
    hdiutil = shutil.which("hdiutil")
    if not hdiutil:
        return
    dmg = Path(f"dist/{APP_ID}-{VERSION}.dmg")
    try:
        subprocess.run([
            hdiutil, "create",
            "-volname", APP_NAME,
            "-srcfolder", str(app_bundle),
            "-ov", "-format", "UDZO",
            str(dmg),
        ], check=True)
        print(f"✓ DMG criado: {dmg.resolve()}")
        _print_size(dmg)
    except Exception as e:
        print(f"[AVISO] DMG não gerado: {e}")

# ─────────────────────────────────────────────
#  WINDOWS NSIS INSTALLER  (opcional)
# ─────────────────────────────────────────────

def build_nsis_installer():
    """Generate a Windows NSIS installer (.exe setup) — requires nsis."""
    if OS != "Windows":
        print("[AVISO] NSIS installer só pode ser criado no Windows.")
        return

    makensis = shutil.which("makensis")
    if not makensis:
        print("""
[AVISO] NSIS não encontrado.
Instale em: https://nsis.sourceforge.io/Download
Ou via Chocolatey: choco install nsis
""")
        return

    exe_src = Path(f"dist/windows/{APP_ID}.exe")
    if not exe_src.exists():
        print("→ Gerando .exe primeiro…")
        build_windows()

    nsi = Path("installer.nsi")
    nsi.write_text(f"""
; NSIS Installer script para {APP_NAME}
!define APPNAME    "{APP_NAME}"
!define APPID      "{APP_ID}"
!define VERSION    "{VERSION}"
!define PUBLISHER  "PythonForge"

Name "${{APPNAME}} ${{VERSION}}"
OutFile "dist\\{APP_ID}-{VERSION}-setup.exe"
InstallDir "$PROGRAMFILES64\\${{APPNAME}}"
InstallDirRegKey HKCU "Software\\${{APPID}}" ""
RequestExecutionLevel admin

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
  SetOutPath $INSTDIR
  File "dist\\windows\\{APP_ID}.exe"
  WriteUninstaller "$INSTDIR\\uninstall.exe"
  CreateShortcut "$DESKTOP\\${{APPNAME}}.lnk" "$INSTDIR\\{APP_ID}.exe"
  CreateDirectory "$SMPROGRAMS\\${{APPNAME}}"
  CreateShortcut "$SMPROGRAMS\\${{APPNAME}}\\${{APPNAME}}.lnk" "$INSTDIR\\{APP_ID}.exe"
  CreateShortcut "$SMPROGRAMS\\${{APPNAME}}\\Uninstall.lnk"    "$INSTDIR\\uninstall.exe"
  WriteRegStr HKCU "Software\\${{APPID}}" "" $INSTDIR
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\\{APP_ID}.exe"
  Delete "$INSTDIR\\uninstall.exe"
  Delete "$DESKTOP\\${{APPNAME}}.lnk"
  RMDir  /r "$SMPROGRAMS\\${{APPNAME}}"
  RMDir  "$INSTDIR"
  DeleteRegKey HKCU "Software\\${{APPID}}"
SectionEnd
""", encoding="utf-8")

    run([makensis, str(nsi)])
    out = Path(f"dist/{APP_ID}-{VERSION}-setup.exe")
    if out.exists():
        print(f"\n✓ Installer NSIS: {out.resolve()}")
        _print_size(out)

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _print_size(path):
    size = path.stat().st_size
    if size > 1_000_000:
        print(f"   Tamanho: {size/1_048_576:.1f} MB")
    else:
        print(f"   Tamanho: {size/1024:.1f} KB")

def clean():
    for d in (BUILD_DIR, DIST_DIR):
        if d.exists():
            shutil.rmtree(d)
            print(f"✓ Removido: {d}")
    for f in Path(".").glob("*.spec"):
        f.unlink()
        print(f"✓ Removido: {f}")

def print_summary():
    print("\n" + "═"*50)
    print("  RESUMO DOS EXECUTÁVEIS GERADOS")
    print("═"*50)
    for p in sorted(Path("dist").rglob("*")):
        if p.is_file():
            size = p.stat().st_size / 1_048_576
            print(f"  {p}  ({size:.1f} MB)")
    print()

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Build PythonForge IDE executables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--linux",     action="store_true", help="Build Linux binary")
    parser.add_argument("--windows",   action="store_true", help="Build Windows .exe")
    parser.add_argument("--mac",       action="store_true", help="Build macOS .app")
    parser.add_argument("--all",       action="store_true", help="Build all targets")
    parser.add_argument("--installer", action="store_true", help="Build NSIS installer (Windows)")
    parser.add_argument("--clean",     action="store_true", help="Limpar artefatos de build")
    args = parser.parse_args()

    if not Path(SCRIPT).exists():
        print(f"[ERRO] '{SCRIPT}' não encontrado.")
        print("       Execute este script na mesma pasta que PythonForge_IDE.py")
        sys.exit(1)

    if args.clean:
        clean()
        return

    # Default: build for current OS
    if not any([args.linux, args.windows, args.mac, args.all, args.installer]):
        print(f"→ Nenhum alvo especificado. Construindo para {OS}…")
        if OS == "Linux":
            args.linux = True
        elif OS == "Windows":
            args.windows = True
        elif OS == "Darwin":
            args.mac = True

    if args.all:
        args.linux = args.windows = args.mac = True

    if args.linux:
        build_linux()
    if args.windows:
        build_windows()
    if args.mac:
        build_mac()
    if args.installer:
        build_nsis_installer()

    if DIST_DIR.exists():
        print_summary()

    print("""
┌─────────────────────────────────────────────────────┐
│          ✅  Build concluído!                        │
│                                                     │
│  Distribuição GitHub Actions (CI/CD multi-plat.):   │
│  → Veja README_BUILD.md para workflow completo      │
└─────────────────────────────────────────────────────┘
""")

if __name__ == "__main__":
    main()