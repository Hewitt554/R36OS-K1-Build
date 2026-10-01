# R60 CP02 — K1 Wi-Fi runtime bind

Purpose: fix the physical R59 result where USB 0bda:0179 enumerates under K1 but no wireless driver loads and NetworkManager reports WIFI-HW=missing.

This checkpoint does not rebuild the kernel. R59 already physically boots the Run-22 Image and its authenticated module tree contains rtl8xxxu, cfg80211, mac80211, modules.alias and modules.dep.

The helper:
- is a no-op outside 6.12.94-r36os-k1;
- requires exact USB 0bda:0179;
- verifies firmware and module metadata exist;
- loads cfg80211, mac80211 and rtl8xxxu;
- falls back to modprobe -d /usr for the R36STATE-backed /usr/lib/modules layout;
- gives normal USB driver registration time to bind;
- has an exact-interface bind fallback only for the matching Realtek interface;
- verifies a wireless netdev appears;
- writes privacy-safe status to /run and /r36state/logs;
- never logs SSID, MAC address, connection profile or password;
- does not restart R36OS or reboot the device.

This checkpoint must be independently statically validated and backed up before CP03 Graphics Lab work starts.
