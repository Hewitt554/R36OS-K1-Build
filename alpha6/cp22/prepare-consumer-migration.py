#!/usr/bin/env python3
"""CP22: stage REVIEW-ONLY workflow patches for CP21 K1 pins.

This tool never touches the working repository, SD media, or real boot files.
Only emits .yml drafts and JSON evidence under a NEW marked /tmp folder.
Pending pins MUST NOT become active merely because drafts are generated.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile

FORMAT = 'R36OS_CP22_K1_WORKFLOW_MIGRATION_DRAFT_ONLY_V1'
OLD_RUN = '36763257082'
OLD_ART = '11124161537'
NEW_CALL = 'bash alpha6/k1/cp21-download-pinned-k1.sh "$K1_ARCHIVE"'
NAMES = {
 'r36os-alpha6-cp13-k1-provenance.yml': 'Download pinned 2026-09-30 K1 development artifact',
 'r36os-alpha6-cp14-k1-native-root.yml': 'Retrieve pinned successful K1 kernel artifact (READ ONLY)',
 'r36os-alpha6-cp15-native-initrd.yml': 'Download checksum-pinned historical K1 kernel candidate',
 'r36os-alpha6-cp16-k1-early-driver-audit.yml': 'Retrieve historical K1 release artifact (read only)',
 'r36os-alpha6-cp17-panel4-diagnostics.yml': 'Retrieve pinned K1 artifact containing Panel 4 device tree (read only)',
 'r36os-alpha6-cp18-first-boot-preflight.yml': 'Download pinned historical K1 and passing CP17 diagnostic artifacts',
}
OTHER_CP17_ARTIFACT = '11924001285'
LEGACY_CP17_RUN = '38624606064'

class Reject(ValueError):pass


def load_pin(path: Path)->dict:
    source=Path(__file__).resolve().parents[1]/'k1'/'cp21_pinned_artifact.py'
    if not source.is_file():
        # In local tests and standalone source ZIP, a checked-in pin copy must
        # still come from CP21, never a user-defined lookalike implementation.
        raise Reject('CP21 validator must exist at alpha6/k1/cp21_pinned_artifact.py')
    spec=importlib.util.spec_from_file_location('cp21_for_cp22',source)
    module=importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module.valid_pin(module.read_json(path))


def pinned_download_step(indent: str='      ')->str:
    return (
        indent+'- name: Fetch explicitly pinned CP21 K1 archive (READ ONLY)\n'
        +indent+'  env:\n'
        +indent+'    GH_TOKEN: ${{ github.token }}\n'
        +indent+'  run: |\n'
        +indent+'    set -euo pipefail\n'
        +indent+'    K1_ARCHIVE="$RUNNER_TEMP/cp22-verified-k1.tar.gz"\n'
        +indent+'    '+NEW_CALL+'\n'
        +indent+'    echo "K1_ARCHIVE=$K1_ARCHIVE" >> "$GITHUB_ENV"\n'
    )

STEP_RX = re.compile(r'(?ms)^      - name: (?P<name>[^\n]+)\n(?P<body>.*?)(?=^      - (?:name:|uses:)|\Z)')


def replace_step(text:str, expected:str)->str:
    matches=[m for m in STEP_RX.finditer(text) if m.group('name')==expected]
    if len(matches)!=1:raise Reject('expected one historical K1 step: '+expected)
    old=matches[0]
    if OLD_RUN not in old.group() or OLD_ART not in old.group():
        raise Reject('historical K1 provenance reference absent from expected step')
    # Keep original CP17 download in the CP18 workflow: K1 re-pinning does not
    # automatically authorize the old CP17 artifact, which may also expire.
    if expected==NAMES['r36os-alpha6-cp18-first-boot-preflight.yml']:
        cp17=(
            '      - name: Fetch old CP17 diagnostic artifact (SEPARATE EXPIRY BLOCKER)\n'
            '        env:\n'
            '          GH_TOKEN: ${{ github.token }}\n'
            '        run: |\n'
            '          set -euo pipefail\n'
            '          mkdir -p "$RUNNER_TEMP/cp18-cp17-raw" "$RUNNER_TEMP/cp18-cp17-files"\n'
            f'          test "$(gh api repos/Hewitt554/R36OS-K1-Build/actions/artifacts/{OTHER_CP17_ARTIFACT} --jq .expired)" = false\n'
            f'          gh run download {LEGACY_CP17_RUN} -R Hewitt554/R36OS-K1-Build \\\n'
            '            -n r36os-alpha6-cp17-PANEL4-DIAGNOSTICS-UNTESTED -D "$RUNNER_TEMP/cp18-cp17-raw"\n'
            '          for file in \\\n'
            '            CP17-ARCH2-DIAGNOSTIC-UNTESTED.uInitrd \\\n'
            '            CP17-ARCH22-DIAGNOSTIC-UNTESTED.uInitrd \\\n'
            '            cp17-diagnostic-report.json cp17-k1-panel4-dtb-report.json DO_NOT_FLASH.txt; do\n'
            '            mapfile -t FOUND < <(find "$RUNNER_TEMP/cp18-cp17-raw" -type f -name "$file" | sort)\n'
            '            test "${#FOUND[@]}" -eq 1\n'
            '            cp -- "${FOUND[0]}" "$RUNNER_TEMP/cp18-cp17-files/$file"\n'
            '          done\n'
        )
        new=pinned_download_step()+cp17
    else: new=pinned_download_step()
    return text[:old.start()]+new+text[old.end():]


def transform(name:str,text:str)->str:
    if name not in NAMES:raise Reject('unexpected workflow name')
    if text.count(OLD_RUN)!=1 or text.count(OLD_ART)!=1:
        raise Reject('expected exactly one historical K1 reference each')
    if NEW_CALL in text:raise Reject('workflow already migrated; refusing double edit')
    updated=replace_step(text,NAMES[name])
    if name=='r36os-alpha6-cp13-k1-provenance.yml':
        old='''          mapfile -t ARCHIVES < <(find "$RUNNER_TEMP/cp13-k1" -type f -name 'R36OS_K1_CP04_CP05_RESULT_*.tar.gz' | sort)
          test "${#ARCHIVES[@]}" -eq 1 || { echo "Expected exactly one K1 result archive" >&2; exit 3; }'''
        new='''          test -f "$K1_ARCHIVE"'''
        updated=once(updated,old,new)
        updated=once(updated,'"${ARCHIVES[0]}" \\\n', '"$K1_ARCHIVE" \\\n')
    elif name=='r36os-alpha6-cp16-k1-early-driver-audit.yml':
        updated=once(updated,'archive="$(cat "$RUNNER_TEMP/cp16-inputs.txt")"','archive="$K1_ARCHIVE"')
    elif name=='r36os-alpha6-cp18-first-boot-preflight.yml':
        # CP18 previously exported the archive path in the combined old step.
        # New downloader step does so before the unchanged report stage.
        if 'K1_ARCHIVE' not in updated:raise Reject('no archive path exported')
    if OLD_RUN in updated or OLD_ART in updated:raise Reject('expired K1 ID survived migration')
    if updated.count(NEW_CALL)!=1:raise Reject('must call exactly one pinned download')
    if 'GH_TOKEN: ${{ github.token }}' not in updated:raise Reject('read-only API credentials missing')
    if 'boot.ini' in updated and name!='r36os-alpha6-cp15-native-initrd.yml' and name!='r36os-alpha6-cp17-panel4-diagnostics.yml' and name!='r36os-alpha6-cp18-first-boot-preflight.yml':
        raise Reject('unexpected boot.ini reference in migration')
    if name=='r36os-alpha6-cp18-first-boot-preflight.yml':
        if updated.count(str(OTHER_CP17_ARTIFACT))!=1 or updated.count(LEGACY_CP17_RUN)!=1:
            raise Reject('CP18 old CP17 dependency must remain explicit')
    return updated


def once(data:str, old:str, new:str)->str:
    if data.count(old)!=1:raise Reject('expected unique workflow contract, got '+str(data.count(old)))
    return data.replace(old,new,1)


def safe_out(out:Path)->Path:
    root=out.resolve(strict=True)
    temp=Path(tempfile.gettempdir()).resolve(strict=True)
    if (out.is_symlink() or not out.is_dir() or temp not in root.parents or
        not root.name.startswith('r36os-cp22-workflow-drafts-') or any(root.iterdir())):
        raise Reject('output must be NEW EMPTY marked temporary directory')
    return root


def generate(repo:Path,out:Path,pin:dict):
    root=repo.resolve(strict=True)
    if not (root/'alpha6/k1/k1-candidate-pin.json').is_file():raise Reject('not a source checkout')
    target=safe_out(out)
    manifest=[]
    for filename in NAMES:
        source=root/'.github/workflows'/filename
        if not source.is_file() or source.is_symlink():raise Reject('missing workflow: '+filename)
        before=source.read_text(encoding='utf8')
        after=transform(filename,before)
        # Never write generated candidates into .github/workflows! Only /tmp.
        p=target/filename
        p.write_text(after,encoding='utf8')
        manifest.append({'workflow':filename,'historical_k1_reference_removed':True,
                         'new_cp21_pin_required':True,'generated_candidate':str(p.name),
                         'cp17_dependency_unresolved':filename.startswith('r36os-alpha6-cp18-')})
    data={'format':FORMAT,'pin_status':pin['status'],'pin_run_id':pin['run_id'],
          'ready_to_apply_to_development_branch':False,
          'all_generated_workflows_are_review_only':True,
          'safe_to_flash':False,'hardware_boot_tested':False,
          'old_cp17_artifact_may_expire':True,
          'source_files_edited':False,
          'workflow_drafts':manifest,
          'next_gate':'Require CP20 full archive CP13 verification + complete run SHA256 before reviewing individual workflow changes'}
    (target/'CP22_REVIEW_ONLY.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
    return data


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv)
    try:
        root=a.repo_root.resolve(strict=True)
        pin=load_pin(root/'alpha6/k1/k1-candidate-pin.json')
        r=generate(root,a.out,pin)
        print('CP22 migration drafts PASS:',len(r['workflow_drafts']),'workflows; not applied, status',r['pin_status'])
    except (OSError,Reject) as e:p.error(str(e))

if __name__=='__main__':main()