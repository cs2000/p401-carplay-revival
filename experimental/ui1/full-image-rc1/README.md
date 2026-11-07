# Jaguar RC1 technical archive

For installation, use the [public firmware download](../../../releases/2026.11-jaguar-xfr-rc1/README.md). This directory stores build inputs, source, inventory, manifests and test evidence; it is not the normal USB download page.

- [Validation summary](VALIDATION.json), [manifest](MANIFEST.json) and [source archive](SOURCE.zip).
- [Image checks](IMAGE_CHECKS.json), [startup checks](STARTUP_CHECKS.json), [runner checks](WRAPPER_CHECKS.json) and [native UI checks](NATIVE_CHECKS.json).
- [Verifier build](VERIFIER_BUILD.json) and [legacy-syscall checks](VERIFIER_LINUX34.json).
- [Inventory](INVENTORY.json), [changes](CHANGES.json) and [original release notes](ORIGINAL_RELEASE_NOTES.txt).
- [UI recovery downloads](../../../recovery/2026.11-jaguar-xfr-rc1/README.md) are separate from the firmware USB.

All firmware and historical evidence bytes are retained. The complete image remains offline/native tested with no vehicle installation test or full-flash recovery proof. The source archive captures the original assembly; current build tools use the equivalent preserved UI installer under experimental/ui1/candidates. The firmware ZIP is an exact archive duplicate of the public download.
