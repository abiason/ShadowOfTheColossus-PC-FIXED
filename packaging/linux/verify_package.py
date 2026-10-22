#!/usr/bin/env python3
"""Verify native archives, relocatable linkage and checksums without game data."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def verify(archive, require_public=True, check_linkage=True):
    with tempfile.TemporaryDirectory(prefix='sotc archive space ') as directory:
        dest=Path(directory)
        with tarfile.open(archive) as tar:
            members=tar.getmembers()
            roots=set()
            for member in members:
                p=PurePosixPath(member.name)
                if p.is_absolute() or '..' in p.parts or not p.parts or not (member.isfile() or member.isdir()):
                    raise ValueError('Unsafe archive member: '+member.name)
                roots.add(p.parts[0])
            if len(roots)!=1: raise ValueError('Archive must have one root directory')
            tar.extractall(dest, filter='data')
        root=dest/roots.pop()
        manifest=json.loads((root/'MANIFEST.json').read_text())
        if require_public:
            if manifest.get('private_preview_only'): raise ValueError('Private preview cannot be published')
            if not manifest.get('versioned_fsr_patch_state'): raise ValueError('Missing verified patch state')
            record=json.loads((root/'BUILD-PROVENANCE.json').read_text())
            if record.get('git',{}).get('head')!=manifest['git_head']: raise ValueError('Build/source commit mismatch')
        expected=set(manifest['sha256'])|{'MANIFEST.json'}
        actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
        if actual!=expected: raise ValueError('Unexpected or missing package files')
        for name,wanted in manifest['sha256'].items():
            p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts: raise ValueError('Invalid manifest path')
            if sha(root/name)!=wanted: raise ValueError('Hash mismatch: '+name)
        if any(p.suffix.lower() in ('.prx','.sprx') for p in root.rglob('*')): raise ValueError('Firmware in archive')
        if check_linkage:
            probe=root/'bin/bb-probe'
            rpath=subprocess.check_output(['patchelf','--print-rpath',str(probe)],text=True).strip()
            if rpath!='$ORIGIN/gpu': raise ValueError('Non-relocatable RUNPATH')
            for binary in (probe,root/'bin/gpu/libbbgpu.so',root/'bin/bb-gpu-capabilities'):
                output=subprocess.check_output(['ldd',str(binary)],text=True)
                if 'not found' in output: raise ValueError('Missing host library: '+str(binary))
                if binary==probe:
                    line=next((x for x in output.splitlines() if 'libbbgpu.so =>' in x),'')
                    if str(root/'bin/gpu/libbbgpu.so') not in line: raise ValueError('GPU library resolves outside package')
        return {'git_head':manifest['git_head'],'files_checked':len(expected)-1}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    archives=sorted(args.directory.glob('*.tar.gz'))
    if not archives: parser.error('No archives found')
    lines=[]
    for archive in archives:
        print(json.dumps({'archive':archive.name,**verify(archive)}))
        lines.append(sha(archive)+'  '+archive.name)
    (args.directory/'SHA256SUMS').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':main()
