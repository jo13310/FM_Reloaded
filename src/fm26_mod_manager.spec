# fm26_mod_manager.spec
import sys
from PyInstaller.utils.hooks import collect_all

# Collect tkinter and ttkbootstrap dependencies
datas, binaries, hiddenimports = collect_all('tkinter')

# Collect ttkbootstrap themes and assets
try:
    ttk_datas, ttk_binaries, ttk_hiddenimports = collect_all('ttkbootstrap')
    datas += ttk_datas
    binaries += ttk_binaries
    hiddenimports += ttk_hiddenimports
except Exception:
    pass  # ttkbootstrap not installed yet

app_name = "FM_Reloaded"
icon_path = "assets/icon.ico" if sys.platform.startswith("win") else "assets/icon.icns"

a = Analysis(
    ['fm26_mod_manager_gui.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas + [('assets', 'assets')],
    hiddenimports=hiddenimports + ['PIL._tkinter_finder'],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=icon_path,
)

# macOS app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name=f"{app_name}.app",
        icon=icon_path,
        bundle_identifier='com.fmreloaded.modmanager',
    )
