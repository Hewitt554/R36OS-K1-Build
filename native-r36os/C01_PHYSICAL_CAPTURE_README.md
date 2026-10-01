# Native R36OS C01 read-only physical dependency capture

The existing Alpha 5R60 diagnostics do not contain enough information to close
Chapter 1.  This collector fills only the missing inventory.

It writes evidence under:

/r36state/logs/native-audit/

It does NOT install/remove packages, alter services, load/unload modules,
change networking, scan Wi-Fi, change boot files or write configuration.

Privacy exclusions are deliberate: no saved network profiles, SSID scans,
IP/MAC inventories, tokens, SSH keys, shell histories or environment dumps.

Expected result:
- R36OS-native-c01-audit-<timestamp>.tar.gz
- matching .sha256

The resulting archive is reviewed before Chapter 1 can be marked complete.
