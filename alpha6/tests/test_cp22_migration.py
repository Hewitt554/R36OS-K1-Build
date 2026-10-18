"""CP22 no-install migration unit and actual-checkout safety tests."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

S=Path(__file__).resolve().parents[1]/'cp22'/'prepare-consumer-migration.py'
spec=importlib.util.spec_from_file_location('r36os_cp22',S)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

# Source-shape fixtures faithfully retain the K1 lines requiring migration.
BASE='''name: placeholder
on:
  workflow_dispatch:
jobs:
  ci:
    steps:
      - uses: actions/checkout@v4
      - name: {step}
        env:
          GH_TOKEN: ${{{{ github.token }}}}
        run: |
{body}      - name: Next legitimate workflow stage
        run: |
{after}      - uses: actions/upload-artifact@v4
'''
OLD='''          mkdir -p "$RUNNER_TEMP/cp14-k1"
          test "$(gh api repos/Hewitt554/R36OS-K1-Build/actions/artifacts/11124161537 --jq '.expired')" = false
          gh run download 36763257082 -R Hewitt554/R36OS-K1-Build \\
            -n R36OS-K1-CP04-CP05-result -D "$RUNNER_TEMP/cp14-k1"
'''


def source(name):
    assert name in m.NAMES
    body=OLD
    after='          echo verification\n'
    if name=='r36os-alpha6-cp13-k1-provenance.yml':
        after='''          mapfile -t ARCHIVES < <(find "$RUNNER_TEMP/cp13-k1" -type f -name 'R36OS_K1_CP04_CP05_RESULT_*.tar.gz' | sort)
          test "${#ARCHIVES[@]}" -eq 1 || { echo "Expected exactly one K1 result archive" >&2; exit 3; }
          python3 alpha6/k1/verify-k1-artifact.py "${ARCHIVES[0]}" \\
            alpha6/dist/cp13-k1-provenance.json
'''
    if name=='r36os-alpha6-cp16-k1-early-driver-audit.yml':
        after='''          archive="$(cat "$RUNNER_TEMP/cp16-inputs.txt")"
          python3 alpha6/k1/audit-k1-early-boot.py "$archive" foo.json
'''
    if name=='r36os-alpha6-cp18-first-boot-preflight.yml':
        body += '''          test "$(gh api repos/Hewitt554/R36OS-K1-Build/actions/artifacts/11924001285 --jq '.expired')" = false
          gh run download 38624606064 -R Hewitt554/R36OS-K1-Build -n r36os-alpha6-cp17-PANEL4-DIAGNOSTICS-UNTESTED -D "$RUNNER_TEMP/cp18-cp17-raw"
'''
    return BASE.format(step=m.NAMES[name],body=body,after=after)

class CP22Tests(unittest.TestCase):
    def test_six_exact_consumers(self):
        self.assertEqual(len(m.NAMES),6)
        self.assertEqual(len(set(m.NAMES)),6)
    def test_normalized_migration_for_every_consumer(self):
        for name in m.NAMES:
            with self.subTest(name=name):
                text=m.transform(name,source(name))
                self.assertNotIn(m.OLD_ART,text)
                self.assertNotIn(m.OLD_RUN,text)
                self.assertEqual(text.count(m.NEW_CALL),1)
                self.assertIn('GH_TOKEN: ${{ github.token }}',text)
                self.assertIn('echo "K1_ARCHIVE=$K1_ARCHIVE" >> "$GITHUB_ENV"',text)
    def test_cp13_consumes_exported_k1_path(self):
        t=m.transform('r36os-alpha6-cp13-k1-provenance.yml',source('r36os-alpha6-cp13-k1-provenance.yml'))
        self.assertIn('verify-k1-artifact.py "$K1_ARCHIVE"',t)
        self.assertNotIn('ARCHIVES[0]',t)
    def test_cp16_consumes_exported_k1_path(self):
        t=m.transform('r36os-alpha6-cp16-k1-early-driver-audit.yml',source('r36os-alpha6-cp16-k1-early-driver-audit.yml'))
        self.assertIn('archive="$K1_ARCHIVE"',t)
        self.assertNotIn('cp16-inputs.txt',t)
    def test_cp18_does_not_claim_cp17_repinned(self):
        t=m.transform('r36os-alpha6-cp18-first-boot-preflight.yml',source('r36os-alpha6-cp18-first-boot-preflight.yml'))
        self.assertIn('SEPARATE EXPIRY BLOCKER',t)
        self.assertEqual(t.count(str(m.OTHER_CP17_ARTIFACT)),1)
        self.assertEqual(t.count(m.LEGACY_CP17_RUN),1)
    def test_unknown_workflow_rejected(self):
        with self.assertRaises(m.Reject):m.transform('nonexistent.yml',source(next(iter(m.NAMES))))
    def test_missing_old_checksum_id_rejected(self):
        s=source(next(iter(m.NAMES))).replace(m.OLD_ART,'00000000000')
        with self.assertRaises(m.Reject):m.transform(next(iter(m.NAMES)),s)
    def test_wrong_old_run_rejected(self):
        s=source(next(iter(m.NAMES))).replace(m.OLD_RUN,'00000000000')
        with self.assertRaises(m.Reject):m.transform(next(iter(m.NAMES)),s)
    def test_multiple_old_run_ids_rejected(self):
        name='r36os-alpha6-cp14-k1-native-root.yml'
        s=source(name).replace('echo verification','echo '+m.OLD_RUN)
        with self.assertRaises(m.Reject):m.transform(name,s)
    def test_multiple_old_artifact_ids_rejected(self):
        name='r36os-alpha6-cp14-k1-native-root.yml'
        s=source(name).replace('echo verification','echo '+m.OLD_ART)
        with self.assertRaises(m.Reject):m.transform(name,s)
    def test_wrong_step_name_rejected(self):
        name=next(iter(m.NAMES))
        s=source(name).replace(m.NAMES[name],'Unexpected K1 step')
        with self.assertRaises(m.Reject):m.transform(name,s)
    def test_duplicate_step_name_rejected(self):
        name=next(iter(m.NAMES))
        s=source(name)+'      - name: '+m.NAMES[name]+'\n        run: echo duplicate\n'
        with self.assertRaises(m.Reject):m.transform(name,s)
    def test_no_double_transform(self):
        name='r36os-alpha6-cp14-k1-native-root.yml'
        out=m.transform(name,source(name))
        with self.assertRaises(m.Reject):m.transform(name,out)
    def test_forbid_apply_in_repo_folder(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp22-workflow-drafts-') as d:
            repo=Path(d)/'alpha6'
            repo.mkdir()
            with self.assertRaises(m.Reject):m.safe_out(repo)
    def test_require_empty_temp_workdir(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp22-workflow-drafts-') as d:
            p=Path(d)
            (p/'prior').touch()
            with self.assertRaises(m.Reject):m.safe_out(p)
    def test_require_marked_temp_workdir(self):
        with tempfile.TemporaryDirectory(prefix='unsafe-output-') as d:
            with self.assertRaises(m.Reject):m.safe_out(Path(d))
    def test_symlink_temp_rejected(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp22-workflow-drafts-') as d:
            alias=Path(d).with_name(Path(d).name+'-symlink')
            try:
                alias.symlink_to(Path(d),target_is_directory=True)
                with self.assertRaises(m.Reject):m.safe_out(alias)
            finally:
                alias.unlink(missing_ok=True)
    def test_staged_drafts_do_not_change_checkout(self):
        with tempfile.TemporaryDirectory(prefix='cp22-repo-fixture-') as r:
            root=Path(r)
            wd=root/'.github/workflows';wd.mkdir(parents=True)
            kp=root/'alpha6/k1';kp.mkdir(parents=True)
            (kp/'k1-candidate-pin.json').write_text('{"status":"PENDING_REBUILD"}')
            originals={}
            for name in m.NAMES:
                value=source(name)
                (wd/name).write_text(value)
                originals[name]=value
            with tempfile.TemporaryDirectory(prefix='r36os-cp22-workflow-drafts-') as td:
                data=m.generate(root,Path(td),{'status':'PENDING_REBUILD','run_id':None})
                self.assertFalse(data['ready_to_apply_to_development_branch'])
                self.assertFalse(data['source_files_edited'])
                self.assertFalse(data['safe_to_flash'])
                self.assertEqual(len(data['workflow_drafts']),6)
                self.assertTrue(data['old_cp17_artifact_may_expire'])
                for name in m.NAMES:
                    self.assertEqual((wd/name).read_text(),originals[name])
                    self.assertNotIn(m.OLD_ART,(Path(td)/name).read_text())
                self.assertEqual(json.loads((Path(td)/'CP22_REVIEW_ONLY.json').read_text())['format'],m.FORMAT)
    def test_real_checkouts_are_not_authorized_to_flash(self):
        # Source code itself has no write paths except designated draft files.
        code=S.read_text()
        self.assertNotIn('subprocess.run(',code)
        self.assertNotIn('os.system(',code)
        self.assertNotIn('mkfs.',code)
        self.assertNotIn('dd if=',code)
        self.assertNotIn("'ready_to_apply_to_development_branch':True",code)

if __name__=='__main__':unittest.main()