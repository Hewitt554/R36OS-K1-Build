import hashlib, importlib.util, io, pathlib, struct, sys, tarfile, tempfile, unittest, zlib
p=pathlib.Path(__file__).resolve().parents[1]/'k1'/'verify-k1-artifact.py'
spec=importlib.util.spec_from_file_location('cp13_verifier',p)
v=importlib.util.module_from_spec(spec);sys.modules[spec.name]=v;spec.loader.exec_module(v)
def fixture(changed=None):
    image=bytearray(96);image[0x38:0x3c]=b'ARM\x64'
    dtb=struct.pack('>II',0xd00dfeed,16)+bytes(8)
    body=b'synthetic initrd'
    header=bytearray(struct.pack('>7I4B32s',0x27051956,0,0,len(body),0,0,zlib.crc32(body)&0xffffffff,5,22,3,1,bytes(32)))
    header[4:8]=struct.pack('>I',zlib.crc32(header)&0xffffffff)
    conf='\n'.join(['hardware=R36XX-RK3326','panel=PANEL4_NV3051D_640X480','root_uuid='+v.EXPECTED_ROOT,
          'state_uuid='+v.EXPECTED_STATE,'boot_mode=R36OS_K1_BOOT_ONCE','modules_storage=R36STATE_BIND',
          'kernel_release=6.12.94-r36os-k1','candidate_id='+'a'*24])+'\n'
    data={'Image':bytes(image),'uInitrd':bytes(header)+body,'rk3326-r36s-k1.dtb':dtb,
          'modules.tar.xz':bytes.fromhex('fd377a585a00')+b'modules','K1.conf':conf.encode(),
          'BUILD_INFO.txt':b'synthetic source only\n'}
    manifest=b''.join((hashlib.sha256(d).hexdigest()+'  '+n+'\n').encode() for n,d in data.items())
    data['MANIFEST.sha256']=manifest
    if changed:changed(data)
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz') as t:
        for name,content in data.items():
            member=tarfile.TarInfo('root/K1/'+name);member.size=len(content)
            t.addfile(member,io.BytesIO(content))
    return output.getvalue()
class TestK1(unittest.TestCase):
    def check(self,blob,stage=False):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);archive=root/'result.tar.gz';archive.write_bytes(blob)
            out=root/'CP13_UNTESTED_K1_BOOT_FILES' if stage else None
            result=v.verify(archive,out)
            if out:self.assertEqual((out/'Image').read_bytes()[0x38:0x3c],b'ARM\x64')
            return result
    def test_valid(self):
        r=self.check(fixture());self.assertFalse(r['safe_to_flash']);self.assertEqual(r['checked_manifest_entries'],6)
    def test_stage(self):self.check(fixture(),stage=True)
    def test_hash_mismatch(self):
        def edit(data):data['Image']=b'corrupted'
        with self.assertRaisesRegex(v.Invalid,'hash mismatch'):self.check(fixture(edit))
    def test_missing_files(self):
        def edit(data):del data['modules.tar.xz']
        with self.assertRaisesRegex(v.Invalid,'complete K1 candidate'):self.check(fixture(edit))
    def test_bad_dtb(self):
        def edit(data):
            data['rk3326-r36s-k1.dtb']=bytes(16)
            data['MANIFEST.sha256']=b''.join((hashlib.sha256(d).hexdigest()+'  '+n+'\n').encode() for n,d in data.items() if n!='MANIFEST.sha256')
        with self.assertRaisesRegex(v.Invalid,'DTB FDT magic'):self.check(fixture(edit))
    def test_wrong_identity(self):
        def edit(data):data['K1.conf']=data['K1.conf'].replace(v.EXPECTED_ROOT.encode(),b'0'*36)
        with self.assertRaisesRegex(v.Invalid,'root_uuid'):self.check(fixture(edit))
    def test_header_crc(self):
        def edit(data):
            b=bytearray(data['uInitrd']);b[5]^=1;data['uInitrd']=bytes(b)
            data['MANIFEST.sha256']=b''.join((hashlib.sha256(d).hexdigest()+'  '+n+'\n').encode() for n,d in data.items() if n!='MANIFEST.sha256')
        with self.assertRaisesRegex(v.Invalid,'header CRC'):self.check(fixture(edit))
    def test_old_arm_ramdisk_header_recorded_as_gap(self):
        def edit(data):
            header=bytearray(data['uInitrd'])
            header[29]=2
            header[4:8]=bytes(4)
            header[4:8]=struct.pack('>I',zlib.crc32(header[:64])&0xffffffff)
            data['uInitrd']=bytes(header)
            data['MANIFEST.sha256']=b''.join((hashlib.sha256(d).hexdigest()+'  '+n+'\n').encode() for n,d in data.items() if n!='MANIFEST.sha256')
        result=self.check(fixture(edit))
        self.assertEqual(result['uboot_ramdisk_arch_id'],2)
        self.assertFalse(result['ready_for_alpha6_boot_integration'])
        self.assertTrue(any('IH_ARCH_ARM=2' in gap for gap in result['compatibility_gaps']))
    def test_missing_state_uuid_is_blocking_gap(self):
        def edit(data):
            lines=data['K1.conf'].decode().splitlines()
            data['K1.conf']=('\n'.join(x for x in lines if not x.startswith('state_uuid='))+'\n').encode()
            data['MANIFEST.sha256']=b''.join((hashlib.sha256(d).hexdigest()+'  '+n+'\n').encode() for n,d in data.items() if n!='MANIFEST.sha256')
        result=self.check(fixture(edit))
        self.assertFalse(result['ready_for_alpha6_boot_integration'])
        self.assertTrue(any('missing state_uuid' in gap for gap in result['compatibility_gaps']))
    def test_path_traversal(self):
        with self.assertRaisesRegex(v.Invalid,'unsafe'):v.norm_member('../boot.ini')
    def test_absolute_path(self):
        with self.assertRaisesRegex(v.Invalid,'unsafe'):v.norm_member('/boot.ini')
    def test_duplicate_checksums(self):
        line=b'a'*64+b'  Image\n'
        with self.assertRaisesRegex(v.Invalid,'duplicate'):v.parse_manifest(line+line)
    def test_existing_stage_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=pathlib.Path(tmp);archive=base/'data.tar.gz';archive.write_bytes(fixture())
            stage=base/'CP13_UNTESTED_K1_BOOT_FILES';stage.mkdir()
            with self.assertRaisesRegex(v.Invalid,'overwrite'):v.verify(archive,stage)
    def test_unexpected_output_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=pathlib.Path(tmp);archive=base/'data.tar.gz';archive.write_bytes(fixture())
            with self.assertRaisesRegex(v.Invalid,'unexpected output'):v.verify(archive,base/'boot.ini')
if __name__=='__main__':unittest.main()
