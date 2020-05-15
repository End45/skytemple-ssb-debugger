# -*- mode: python ; coding: utf-8 -*-
import os
import sys

pkg_path = os.path.abspath(os.path.join('..', 'skytemple_ssb_debugger'))
site_packages = next(p for p in sys.path if 'site-packages' in p)

additional_files = []
additional_datas = [
    (os.path.join(pkg_path, 'data'), 'data'),
    (os.path.join(pkg_path, '*.glade'), '.'),
    (os.path.join(pkg_path, '*.lang'), 'skytemple_ssb_debugger'),
    #(os.path.join(pkg_path, '*.css'), '.'),
    (os.path.join(pkg_path, 'controller', '*.glade'), 'skytemple_ssb_debugger/controller'),
    (os.path.join(site_packages, 'skytemple_files', '_resources'), 'skytemple_files/_resources'),
]
additional_binaries = [
    (os.path.join(site_packages, "desmume", "libdesmume.dll"), "."),
    (os.path.join(site_packages, "desmume", "SDL.dll"), "."),
]

block_cipher = None


a = Analysis(['../skytemple_ssb_debugger/main.py'],
             pathex=[os.path.abspath(os.path.join('..', 'ssb_debugger'))],
             binaries=additional_binaries,
             datas=additional_datas,
             hiddenimports=['pkg_resources.py2_warn', 'packaging.version', 'packaging.specifiers',
                            'packaging.requirements', 'packaging.markers'],
             #hookspath=[os.path.abspath(os.path.join('.', 'hooks'))],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='skytemple-ssb-debugger',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,  # TODO: Disable at some point.
          icon=os.path.abspath(os.path.join('.', 'skytemple-ssb-debugger.ico')))

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               additional_files,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='skytemple-ssb-debugger')
