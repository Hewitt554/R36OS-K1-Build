from pathlib import Path
base = Path(__file__).resolve().parents[1]
script = (base / "ci/build-native-rootfs.sh").read_text()
manifest = (base / "manifest/core-arm64-packages.txt").read_text()
workflow = (base.parent / ".github/workflows/r36os-alpha6-native-root.yml").read_text()
assert "debootstrap --arch=arm64" in script
assert "update_apply_enabled=false" in script
assert "flash_image_ready=false" in script
assert "NOT FLASHABLE" in script
assert "runs-on: ubuntu-24.04-arm" in workflow
assert "pull_request:" in workflow
assert "systemd-sysv" in manifest
assert "emulationstation-go2" not in manifest
for bad in ("dd of=/dev/", "mkfs.ext4 /dev/", "wipefs /dev/", "sfdisk /dev/"):
    assert bad not in script
print("CP06 static recipe checks passed")
