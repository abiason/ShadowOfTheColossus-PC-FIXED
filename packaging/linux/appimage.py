#!/usr/bin/env python3
"""Build a CachyOS AppImage from a verified native distribution archive."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_dependencies import atomic_write, download, reject_symlinks
from verify_package import verify, sha

ROOT = Path(__file__).resolve().parents[2]
# These belong to the running host: libc and the graphics/driver stack.
HOST_LIBRARIES = re.compile(
    r'^(?:ld-linux|lib(?:c|m|mvec|pthread|rt|dl|resolv|util|anl)\.so|'
    r'libnss_|libvulkan|libGL|libEGL|libGLES|libOpenGL|libGLX|libglapi|'
    r'libdrm|libgbm|libgallium|libamdvlk|amdvlk|.*_dri\.so|'
    r'libnvidia|libcuda|libnvcuvid|libOpenCL|libva[.-]|libvdpau)')
APPRUN = '''#!/bin/sh
set -eu
APPDIR=${APPDIR:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}
export APPDIR
if [ "${SOTC_APPIMAGE:-}" != 1 ]; then
    SOTC_APPIMAGE_ORIGINAL_LD_LIBRARY_PATH=${LD_LIBRARY_PATH-}
    export SOTC_APPIMAGE_ORIGINAL_LD_LIBRARY_PATH
fi
SOTC_APPIMAGE=1
PYTHONHOME="$APPDIR/usr"
PYTHONNOUSERSITE=1
PYTHONDONTWRITEBYTECODE=1
unset PYTHONPATH
LD_LIBRARY_PATH="$APPDIR/usr/lib"
TCL_LIBRARY="$APPDIR/usr/lib/@TCL@"
TK_LIBRARY="$APPDIR/usr/lib/@TK@"
SOTC_DATA_DIR=${SOTC_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/sotc-pc}
export SOTC_APPIMAGE PYTHONHOME PYTHONNOUSERSITE PYTHONDONTWRITEBYTECODE
export LD_LIBRARY_PATH TCL_LIBRARY TK_LIBRARY SOTC_DATA_DIR
if [ "${1:-}" = --sotc-appimage-check ]; then
    shift
    exec "$APPDIR/usr/bin/python3" "$APPDIR/appimage_check.py" "$@"
fi
exec "$APPDIR/usr/bin/python3" "$APPDIR/usr/share/sotc/launcher/sotc_launcher.py" "$@"
'''
CHECK = '''import json,os,sys,tkinter,hashlib,ssl,ctypes,struct,subprocess
from pathlib import Path
from PIL import Image,ImageTk
root=Path(os.environ['APPDIR']).resolve()
manifest=json.loads((root/'APPIMAGE-MANIFEST.json').read_text())
actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
assert actual==set(manifest)|{'APPIMAGE-MANIFEST.json'}
for name,wanted in manifest.items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==wanted,name
assert Path(sys.executable).resolve().is_relative_to(root)
assert Path(tkinter.__file__).resolve().is_relative_to(root)
assert Path(Image.__file__).resolve().is_relative_to(root)
tcl=tkinter.Tcl()
assert Path(tcl.eval('info library')).resolve().is_relative_to(root)
if '--gui' in sys.argv:
    ui=tkinter.Tk();ui.withdraw()
    im=ImageTk.PhotoImage(Image.new('RGB',(2,2)),master=ui)
    ui.update();ui.destroy()
sys.path.insert(0,str(root/'usr/share/sotc/launcher'))
import sotc_launcher_win as app
assert not app.data_dir().is_relative_to(root)
if '--gui' in sys.argv:
    from tkinter import ttk,filedialog,messagebox
    from unittest import mock
    ui=tkinter.Tk();ui.withdraw()
    with mock.patch.object(app.Launcher,'show_setup'),mock.patch.object(app.Launcher,'detect_gpu'),mock.patch.object(app.Launcher,'refresh_library'):
        launcher=app.Launcher(ui,tkinter,ttk,filedialog,messagebox)
        for page in launcher.pages:launcher.show(page);ui.update()
        launcher.collect()
    ui.destroy()
    assert app.CONFIG_FILE.is_file()
print(json.dumps({'python':sys.version.split()[0],'bundled_python':True,'bundled_tk':True,'bundled_pillow':True,'gui_checked':'--gui' in sys.argv,'game_started':False,'data':str(app.data_dir())}))
'''


def run(*args, **kwargs):
    return subprocess.check_output(list(map(str, args)), text=True, **kwargs).strip()


def elf(path):
    if not path.is_file():
        return False
    with path.open('rb') as f:
        return f.read(4) == b'\x7fELF'


def dependencies(binary):
    result = subprocess.run(['ldd', str(binary)], capture_output=True, text=True)
    if result.returncode or 'not found' in result.stdout:
        raise ValueError(f'Unresolved dependencies for {binary}: {result.stdout} {result.stderr}')
    found = []
    for line in result.stdout.splitlines():
        match = re.match(r'\s*(\S+) => (/.*?) \(', line)
        if match:
            # ldd can print an absolute loader name before '=>'. Never let it
            # turn a destination under usr/lib into an absolute host path.
            found.append((Path(match[1]).name, Path(match[2])))
    return found


def copy_tree(source, target):
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(
        '__pycache__', '*.pyc', 'site-packages', 'test', 'tests', 'idlelib', 'ensurepip', 'config-*'))


def bundle_libraries(appdir):
    pending = [p for p in appdir.rglob('*') if elf(p)]
    seen, copied, excluded, owners = set(), {}, set(), set()
    while pending:
        binary = pending.pop()
        resolved = binary.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        for soname, source in dependencies(binary):
            if HOST_LIBRARIES.match(soname):
                excluded.add(soname)
                continue
            if source.resolve().is_relative_to(appdir.resolve()):
                continue
            if not source.resolve().is_relative_to(Path('/usr/lib')):
                raise ValueError(f'Unexpected library source: {source}')
            dest = appdir / 'usr/lib' / soname
            digest = sha(source)
            if soname in copied:
                if copied[soname]['sha256'] != digest:
                    raise ValueError('Conflicting library: ' + soname)
                continue
            shutil.copy2(source, dest)
            dest.chmod(0o755)
            package = run('pacman', '-Qqo', source.resolve())
            if not package or '\n' in package:
                raise ValueError('Ambiguous package owner: ' + str(source))
            owners.add(package)
            copied[soname] = {'source': str(source), 'sha256': digest, 'package': package}
            pending.append(dest)
    return copied, sorted(excluded), owners


def collect_licenses(appdir, packages):
    target = appdir / 'usr/share/licenses/bundled'
    target.mkdir(parents=True)
    records = {}
    for package in sorted(packages | {'python', 'python-pillow', 'tcl', 'tk'}):
        details = run('pacman', '-Qi', package, env={**os.environ, 'LC_ALL': 'C'})
        records[package] = details
        files = run('pacman', '-Qlq', package).splitlines()
        for filename in files:
            source = Path(filename)
            if source.is_file() and (filename.startswith('/usr/share/licenses/') or
                                     filename.endswith('/LICENSE.txt') or '/licenses/' in filename):
                dest = target / package / source.relative_to('/')
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
    # Arch packages using SPDX identifiers refer to these standard license texts.
    spdx = Path('/usr/share/licenses/spdx')
    if not spdx.is_dir():
        raise ValueError('Install the licenses package before bundling')
    shutil.copytree(spdx, target / 'SPDX')
    (target / 'PACKAGES.json').write_text(json.dumps(records, indent=2) + '\n')


def tools(root=ROOT):
    pins = json.loads((root / 'packaging/linux/appimage-tools.json').read_text())
    dest = root / 'out/dependencies/appimage'
    reject_symlinks(dest)
    dest.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in ('appimagetool', 'runtime', 'runtime-LICENSE.txt'):
        entry = pins[name]
        path = dest / name
        reject_symlinks(path)
        if not path.is_file() or sha(path) != entry['sha256']:
            content = download(entry['url'])
            if hashlib.sha256(content).hexdigest() != entry['sha256']:
                raise ValueError('Tool checksum mismatch: ' + name)
            atomic_write(path, content)
        path.chmod(0o644 if name.endswith('.txt') else 0o755)
        paths[name] = path
    return paths, pins


def stage(archive, appdir):
    report = verify(archive)
    if appdir.exists():
        raise ValueError('AppDir must not exist: ' + str(appdir))
    appdir.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='sotc appimage native ') as temp:
        with tarfile.open(archive) as tar:
            tar.extractall(temp, filter='data')
        package = next(Path(temp).iterdir())
        shutil.copytree(package, appdir / 'usr/share/sotc')
    bindir = appdir / 'usr/bin'
    bindir.mkdir(parents=True)
    shutil.copy2(Path(sys.executable).resolve(), bindir / 'python3')
    stdlib = Path(sysconfig.get_path('stdlib'))
    copy_tree(stdlib, appdir / 'usr/lib' / stdlib.name)
    import PIL
    copy_tree(Path(PIL.__file__).parent, appdir / 'usr/lib' / stdlib.name / 'site-packages/PIL')
    import tkinter
    tcl = Path(tkinter.Tcl().eval('info library'))
    tk = tcl.parent / ('tk' + str(tkinter.TkVersion))
    if not (tk / 'tk.tcl').is_file():
        raise ValueError('Tk scripts missing')
    copy_tree(tcl, appdir / 'usr/lib' / tcl.name)
    copy_tree(tk, appdir / 'usr/lib' / tk.name)
    libraries, excluded, owners = bundle_libraries(appdir)
    collect_licenses(appdir, owners)
    icon = appdir / 'usr/share/sotc/launcher/sotc.png'
    shutil.copy2(icon, appdir / 'sotc.png')
    shutil.copy2(icon, appdir / '.DirIcon')
    (appdir / 'sotc.desktop').write_text(
        '[Desktop Entry]\nType=Application\nName=Shadow of the Colossus\n'
        'Exec=AppRun\nIcon=sotc\nTerminal=false\nCategories=Game;\n')
    (appdir / 'AppRun').write_text(APPRUN.replace('@TCL@', tcl.name).replace('@TK@', tk.name))
    (appdir / 'AppRun').chmod(0o755)
    (appdir / 'appimage_check.py').write_text(CHECK)
    record = {'native_archive': archive.name, 'native_archive_sha256': sha(archive),
              'git_head': report['git_head'], 'bundled_libraries': libraries,
              'host_libraries': excluded, 'python_version': sys.version,
              'target': 'CachyOS Linux x86_64; compatible host glibc and Vulkan driver required'}
    (appdir / 'APPIMAGE-BUNDLE.json').write_text(json.dumps(record, indent=2) + '\n')
    run('desktop-file-validate', appdir / 'sotc.desktop')
    return record


def build(archive, output, work, root=ROOT):
    reject_symlinks(output.absolute())
    reject_symlinks(work.absolute())
    archive, output, work = archive.resolve(), output.resolve(), work.resolve()
    if os.uname().machine != 'x86_64':
        raise ValueError('Only native x86_64 builds supported')
    if (output / 'APPIMAGE-BUNDLE.json').exists():
        raise ValueError('Bundle report already exists in output directory')
    reject_symlinks(work)
    work.mkdir(parents=True, exist_ok=True)
    appdir = work / 'SotC.AppDir'
    record = stage(archive, appdir)
    paths, pins = tools(root)
    shutil.copy2(paths['runtime-LICENSE.txt'], appdir / 'usr/share/licenses/bundled/AppImage-runtime.txt')
    record['tools'] = pins
    (appdir / 'APPIMAGE-BUNDLE.json').write_text(json.dumps(record, indent=2) + '\n')
    files = [p for p in appdir.rglob('*') if p.is_file()]
    if any(p.suffix.lower() in ('.sprx', '.prx') for p in files):
        raise ValueError('Firmware must not enter an AppImage')
    (appdir / 'APPIMAGE-MANIFEST.json').write_text(json.dumps(
        {str(p.relative_to(appdir)): sha(p) for p in sorted(files)}, indent=2) + '\n')
    # Extract appimagetool without FUSE; never execute unchecked downloads.
    subprocess.run([str(paths['appimagetool']), '--appimage-extract'], cwd=work,
                   check=True, stdout=subprocess.DEVNULL)
    output.mkdir(parents=True, exist_ok=True)
    result = output / ('SotC-PC-' + record['git_head'][:12] + '-x86_64.AppImage')
    if result.exists():
        raise ValueError('Output already exists: ' + str(result))
    subprocess.run([str(work / 'squashfs-root/AppRun'), '--runtime-file', str(paths['runtime']),
                    str(appdir), str(result)], check=True,
                   env={**os.environ, 'ARCH': 'x86_64', 'SOURCE_DATE_EPOCH': '0'})
    result.chmod(0o755)
    record.update(tools=pins, appimage=result.name, appimage_sha256=sha(result))
    (output / 'APPIMAGE-BUNDLE.json').write_text(json.dumps(record, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, default=Path('dist'))
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.archive, args.output, args.work))


if __name__ == '__main__':
    main()
