# R60 CP03 — K1 Graphics Lab external-session checkpoint

Physical R59 evidence:
- Panfrost probes Mali-G31 successfully.
- /dev/dri/card0, card1 and renderD128 exist.
- Graphics Lab stops before Weston with input_supervisor_pid=<pid> ready=no.

Exact runtime provenance:
- Base r36os-graphics-test-session SHA-256:
  764fe5cb26da8ba66701c1154fbef8e3f944f9fe2330180cd97829c20aa88393
- Exact r36os-input-supervisor SHA-256:
  7a3e941160d8bc4efbac1b607dab47f17ebd21239a482a7683fe28702923ab45
- Exact input-supervisor C source SHA-256:
  818053663591492801c9c47bdf6c262053f28318188c7a9326a68b1d77f16da6
- Exact r36os-win-common SHA-256:
  081f2f0a9a48b5858c24491bf63221ca5ff2a53abc738814cac61d25aa9e09d0

The byte-exact originals were recovered from the preserved Alpha 5R36 / Alpha 5R37 recovery artifacts and matched against the current R58/R59 core-manifest hashes.

Root cause:
- r36_external_begin() starts the legacy input supervisor and waits for its ready marker.
- The supervisor expects the old single named gamepad topology.
- K1 exposes controls as split gpio-keys + adc-joystick.
- The supervisor additionally requires uinput to create its virtual devices.
- K1 currently has no /dev/uinput.
- The supervisor therefore exits before writing its ready marker, so Weston never starts.

CP03 scope:
- Do NOT modify r36os-input-supervisor.
- Do NOT modify game sessions.
- Do NOT alter legacy 4.4 Graphics Lab behavior.
- Only Graphics Lab on exact K1 uses a no-input external-session path.
- The graphics workloads are autonomous and remain protected by the existing 42-second timeout, kernel-Oops checks and D-state checks.
- Legacy/non-K1 Graphics Lab continues to call the original r36_external_begin() path.

Patched payload:
- Reconstruct by concatenating payload/r36os-graphics-test-session.b64.part00..03 and base64-decoding.
- Expected decoded SHA-256:
  9830642ae3b67397d74358718cae260fc228f497b9ae9aacec0ec452ac695291

This is an isolated checkpoint. It must pass its own static gate before any R60 updater is built.
