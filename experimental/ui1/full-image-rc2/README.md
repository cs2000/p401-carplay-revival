# Jaguar RC2 source and validation archive

For installation, use the [full firmware download](../../../releases/2026.11-jaguar-xfr-rc2/README.md). This directory holds technical records, not a second firmware download. The owner's small development-car update is retained locally and is not a public download.

RC2 uses the approved graphite/glass theme, session indication, accent/picture/order preferences and matching native Settings. Advanced access bypasses only its PIN navigation, preserving the existing native controls and MCU-version display. Factory/MCU configuration and the W3 repair remain unchanged.

The exact new ARM binary has its own fresh evidence. The owner's earlier successful Glass/Clock result applies only to the preserved previous package. No RC2 vehicle installation, physical radio session, hardware reboot or full-flash recovery is established here.

Full-image disable/re-enable files are [separate state-only controls](../../../recovery/2026.11-jaguar-xfr-rc2/README.md). The current-car update has its own exact previous-UI restore and historical UI-off rollback; those field runner/manifest files must not be applied to the standalone image.

- [Manifest](MANIFEST.json), [validation summary](VALIDATION.json) and [source archive](SOURCE.zip).
- [Exact UI aggregate](UI_NATIVE_EVIDENCE.json), [RC2 features](RC2_FEATURE_CHECKS.json), [naming](SETTINGS_CLOUD_CHECKS.json), [menu/startup](MENU_CLOUD_CHECKS.json), [clock](CLOCK_CLOUD_CHECKS.json) and [storage](PREFERENCES_CHECKS.json).
- [Full image/inventory checks](IMAGE_CHECKS.json), [settings/startup checks](STARTUP_CHECKS.json), [standalone runner checks](WRAPPER_CHECKS.json) and [native full-image integration](NATIVE_CHECKS.json).
- [Current-car upgrade manifest](UPGRADE_MANIFEST.json) and [delivery checks](UPGRADE_DELIVERY_CHECKS.json).
- [Build summary](BUILD_SUMMARY.json), [inventory](INVENTORY.json), [changes](CHANGES.json) and [build commands](BUILD_COMMANDS.json).
- [Final English native previews](PREVIEWS/PROVENANCE.json) distinguish original native-model Home from the explicit six-app visual fixture.

The exact unchanged verifier's [earlier build evidence](VERIFIER_BUILD.json) and [legacy syscall evidence](VERIFIER_LINUX34.json) are retained with their original scope; they are not presented as a new RC2 helper build or old-kernel boot. [Checksums](SHA256SUMS.txt) cover this technical archive. The firmware ZIP is only in the public release folder.
