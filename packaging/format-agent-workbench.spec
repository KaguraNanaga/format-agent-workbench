from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


project_root = Path.cwd().resolve()
datas = collect_data_files("streamlit") + copy_metadata("streamlit") + [
    (str(project_root / "app.py"), "."),
    (str(project_root / "assets"), "assets"),
    (str(project_root / ".streamlit"), ".streamlit"),
    (str(project_root / "docs" / "images" / "workbench-home.png"), "docs/images"),
]

hiddenimports = collect_submodules("core") + [
    "app",
    "fitz",
    "pymupdf",
    "pythoncom",
    "pywintypes",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "win32com",
    "win32com.client",
]

a = Analysis(
    [str(project_root / "launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "scipy",
        "matplotlib",
        "openpyxl",
        "sqlalchemy",
        "tensorflow",
        "torch",
        "keras",
        "sklearn",
        "pypdfium2",
        "pypdfium2_raw",
        "plotly",
        "bokeh",
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Format Agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Format Agent Workbench",
)
