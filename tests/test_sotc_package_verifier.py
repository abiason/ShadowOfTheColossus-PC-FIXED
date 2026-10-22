"""Archive verifier checks without executing native code."""
import hashlib,io,json,sys,tarfile,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packaging/linux'))
from verify_package import verify

class VerifierTests(unittest.TestCase):
    def archive(self, root, corrupt=False):
        record=json.dumps({'git':{'head':'abc'}}).encode()
        files={'BUILD-PROVENANCE.json':record,'SotC.sh':b'wrapper'}
        manifest={'git_head':'abc','private_preview_only':False,
                  'versioned_fsr_patch_state':{'diff_sha256':'known'},
                  'sha256':{n:hashlib.sha256(v).hexdigest() for n,v in files.items()}}
        if corrupt: files['SotC.sh']=b'corrupted'
        files['MANIFEST.json']=json.dumps(manifest).encode()
        path=root/'package.tar.gz'
        with tarfile.open(path,'w:gz') as tar:
            for name,data in files.items():
                item=tarfile.TarInfo('package/'+name);item.size=len(data)
                tar.addfile(item,io.BytesIO(data))
        return path

    def test_hashes_and_source_record(self):
        with tempfile.TemporaryDirectory() as folder:
            result=verify(self.archive(Path(folder)),check_linkage=False)
            self.assertEqual(result['git_head'],'abc')
            self.assertEqual(result['files_checked'],2)
            with self.assertRaisesRegex(ValueError,'Hash mismatch'):
                verify(self.archive(Path(folder),True),check_linkage=False)

    def test_path_traversal_and_links_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            for name,kind in [('../escape',tarfile.REGTYPE),('package/link',tarfile.SYMTYPE)]:
                path=Path(folder)/'bad.tar.gz'
                with tarfile.open(path,'w:gz') as tar:
                    item=tarfile.TarInfo(name);item.type=kind;item.linkname='/tmp/escape'
                    tar.addfile(item)
                with self.assertRaisesRegex(ValueError,'Unsafe archive'):
                    verify(path,check_linkage=False)

if __name__=='__main__': unittest.main()
