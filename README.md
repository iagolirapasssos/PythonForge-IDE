# PythonForge IDE — Guia de Build

## Estrutura de arquivos

```
PythonForge_IDE.py     ← Código-fonte da IDE
build_pyforge.py       ← Script de build local
build.yml              ← GitHub Actions (CI/CD)
icon.ico               ← Ícone Windows   (opcional)
icon.png               ← Ícone Linux     (opcional)
icon.icns              ← Ícone macOS     (opcional)
```

---

## Build local (na sua máquina)

### Pré-requisito único: PyInstaller
```bash
pip install pyinstaller
```

### Linux → binário ELF
```bash
python build_pyforge.py --linux
# Saída: dist/linux/PythonForgeIDE
```

### Windows → .exe (no próprio Windows)
```bash
python build_pyforge.py --windows
# Saída: dist/windows/PythonForgeIDE.exe
```

### Windows .exe via Wine (no Linux)
```bash
# 1. Instale o Wine
sudo apt install wine wine64 winetricks      # Ubuntu/Debian
sudo dnf install wine                        # Fedora
sudo pacman -S wine                          # Arch

# 2. Configure o Wine e instale Python para Windows
winetricks vcrun2019
wget https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.msi
wine python-3.12.0-amd64.msi

# 3. Instale PyInstaller no Wine Python
wine ~/.wine/drive_c/Python312/python.exe -m pip install pyinstaller

# 4. Execute o build
python build_pyforge.py --windows
# Saída: dist/windows/PythonForgeIDE.exe
```

### macOS → .app bundle (só no Mac)
```bash
python build_pyforge.py --mac
# Saída: dist/mac/PythonForgeIDE.app
#        dist/PythonForgeIDE-1.0.0.dmg  (se hdiutil disponível)
```

### Todos os alvos de uma vez
```bash
python build_pyforge.py --all
```

### Limpar artefatos de build
```bash
python build_pyforge.py --clean
```

---

## Build automático via GitHub Actions (recomendado)

O arquivo `build.yml` configura builds automáticos para **todas as plataformas em paralelo** usando os runners do GitHub.

### Setup
```bash
# 1. Crie um repositório no GitHub
git init
git add PythonForge_IDE.py build_pyforge.py

# 2. Coloque o workflow no lugar certo
mkdir -p .github/workflows
cp build.yml .github/workflows/

git add .github/
git commit -m "Initial commit"
git remote add origin https://github.com/SEU_USER/PythonForge.git
git push -u origin main
```

### Gerar uma release
```bash
git tag v1.0.0
git push --tags
# → GitHub Actions gera automaticamente Linux + Windows + macOS
# → Cria Release com os 3 binários disponíveis para download
```

### Resultado
- `PythonForgeIDE`           → Linux (ELF, ~12 MB)
- `PythonForgeIDE.exe`       → Windows (PE32+, ~15 MB)
- `PythonForgeIDE-mac.zip`   → macOS (.app bundle, ~18 MB)

---

## Installer Windows (NSIS)

Para um instalador profissional com atalho no Desktop e Painel de Controle:

```bash
# 1. Instale NSIS: https://nsis.sourceforge.io/Download
#    ou: choco install nsis

# 2. Gere o .exe primeiro
python build_pyforge.py --windows

# 3. Gere o installer
python build_pyforge.py --installer
# Saída: dist/PythonForgeIDE-1.0.0-setup.exe
```

---

## Tamanhos esperados dos executáveis

| Plataforma | Formato | Tamanho aprox. |
|------------|---------|---------------|
| Linux      | ELF binary | 10–15 MB |
| Windows    | .exe       | 12–18 MB |
| macOS      | .app.zip   | 15–20 MB |

> Os executáveis incluem o interpretador Python — não é necessário instalar nada na máquina do usuário final.

---

## Notas de compatibilidade

| OS | Versão mínima |
|----|--------------|
| Linux   | Ubuntu 20.04+ / qualquer distro com glibc 2.31+ |
| Windows | Windows 10 / 11 (64-bit) |
| macOS   | macOS 11 Big Sur+ |

Para suporte a versões mais antigas de Linux, use `--target-arch x86_64` e compile em uma máquina com glibc mais antigo (ex: Ubuntu 18.04 via Docker).