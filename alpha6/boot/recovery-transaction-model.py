#!/usr/bin/env python3
"""Offline CP08 transactional recovery state model, NOT an actual updater."""
from dataclasses import dataclass, replace
STEPS = {
    "stable": {"stage": "staged"},
    "staged": {"snapshot_verified": "backup_ok", "cancel": "stable"},
    "backup_ok": {"arm_rescue": "rescue_armed", "cancel": "stable"},
    "rescue_armed": {"offline_apply": "applying", "cancel": "stable"},
    "applying": {"apply_ok": "trial", "apply_failed": "need_restore"},
    "trial": {"healthy": "committed", "unhealthy": "need_restore", "interrupted": "need_restore"},
    "need_restore": {"restore_begin": "restoring"},
    "restoring": {"restore_verified": "restored", "restore_failed": "restore_incomplete"},
    "restore_incomplete": {"retry": "restoring"},
    "restored": {"clear_recovery": "stable"},
    "committed": {"cleanup": "stable"},
}
@dataclass(frozen=True)
class Transaction:
    state: str = "stable"
    snapshot: bool = False
    armed: bool = False
    def step(self, event):
        next_state = STEPS.get(self.state, {}).get(event)
        if next_state is None:
            raise ValueError("unsafe transition: " + self.state + " -> " + event)
        if event == "offline_apply" and not (self.snapshot and self.armed):
            raise ValueError("no verified backup or rescue request")
        return replace(self, state=next_state,
                       snapshot=(self.snapshot or event == "snapshot_verified") and next_state != "stable",
                       armed=(self.armed or event == "arm_rescue") and next_state != "stable")
    def may_write(self):
        return self.state in ("applying", "restoring") and self.snapshot and self.armed
    def may_boot_normal(self):
        return self.state in ("stable", "restored", "committed") or (
            self.state == "trial" and self.armed and self.snapshot)
