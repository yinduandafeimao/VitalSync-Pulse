# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
    ['fluent_ui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\Cython', 'Cython'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\paddleocr\\tools', 'paddleocr/tools'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\paddleocr\\ppocr', 'paddleocr/ppocr'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\paddleocr\\ppstructure', 'paddleocr/ppstructure'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\shapely', 'shapely'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\pyclipper', 'pyclipper'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\skimage', 'skimage'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\lmdb', 'lmdb'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\albumentations', 'albumentations'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\docx', 'docx'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\paddle', 'paddle'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\scipy', 'scipy'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\yaml', 'yaml'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\lxml', 'lxml'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\fontTools', 'fontTools'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\certifi', 'certifi'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\pyautogui', 'pyautogui'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\pygame', 'pygame'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\edge_tts', 'edge_tts'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\keyboard', 'keyboard'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\qtawesome', 'qtawesome'),
        ("team_members(choice box).py", "."),
        ("Zhu Xian World Health Bar Test(choice box).py", "."),
        ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\prettytable', 'prettytable')
    ],
    hiddenimports=[
        'ppocr', 'ppstructure', 'requests', 'shapely', 'pyclipper', 
        'skimage', 'lmdb', 'albumentations', 'docx', 'paddle', 'PIL', 
        'scipy', 'yaml', 'lxml', 'fontTools', 'certifi', 'pyautogui', 
        'pygame', 'edge_tts', 'keyboard', 'qtawesome', 'prettytable'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='fluent_ui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico'
)
