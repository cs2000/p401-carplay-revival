# Build and native lab

The device C++ source and generated `brand_paths.h` are the exact source used for the tested UI1 library. Only build-path configuration and unused R-badge tracing metadata were adjusted for this repository. The prepared installer remains byte-for-byte identical to the last locally tested installer.

## Build inputs

Use Linux, Python 3, Clang/LLD, and these external inputs:

* Qt headers at tag `v4.7.4`, commit `092cd760d5fddf9640a310214fe01929f0fff3a8` from https://github.com/qt/qt. Set `P401_QT_HEADERS` to that checkout (including `src/corelib`, `src/gui`, `src/network`). The script generates forwarding headers; licenses are in `licenses/qt`.
* A metadata-preserving Linux extraction of the matching vendor rootfs. Set `P401_VENDOR_ROOT` to its root. The donor identity and extraction tool are documented in [building](../../docs/building.md) and [provenance](../../docs/provenance.md). Do not treat Windows text representations of symlinks as shared libraries.
* The ARM hard-float musl SDK **headers**, originally from the Alpine ARM sysroot, at `P401_ARM_HEADERS`. The original lab used Clang 20.1.8 and musl headers. Headers are not the target runtime: linking is explicitly against the vendor glibc/Qt libraries. Do not substitute time64 symbols, a host `struct stat`, double `qreal`, soft-float libraries, or modern Qt.

```sh
python experimental/ui1/src/build.py
```

Output goes to ignored `experimental/ui1/build`. The original tested library hash is `aac2e11c9255b82c6fc76e7e824585773019e762d2c9dfaef52cbd7299c3ac35`. A rebuild with a different compiler/path need not be byte-identical; it needs fresh native and delivery checks before packaging. Extract the exact existing binary from `packages/INSTALL.zip` for comparison.

## Current lab portability limit

`lab/reference` preserves the working native ARM simulator, framebuffer/pointer shim, original validators, package builder and CRC helper. It is a **reference implementation from the Windows + Alpine WSL lab**, not a claim that a Cloud GUI session has already been recreated. Its generic `/opt/p401-workspace` paths and Windows viewer launch commands still need wiring to the chosen Cloud environment. The device code and ready install/rollback packages do not depend on this workstation layout.

The original layout was `work/ui_customization`, `work/visual_emulator`, `work/qt4-headers`, a vendor root at `/opt/p401-build/candidate-r1/root`, and an ARM SDK at `/opt/p401-r4-arm`. The original WSL distribution was `Codex-P401-Build`. The package builder also referenced the installed W3 payload; only the exact rollback files and manifest are retained under `baseline` here, so do not run the reference builder blindly.

The lab runs the actual `MsnCoreApp` through QEMU in private mount/network/PID/IPC namespaces with a copied root, fake framebuffer and pointer injection. It does not emulate the MCU, Wi-Fi/Bluetooth radio, MFi device, an iPhone, media streaming or a physical reboot. Preserve isolation; do not start the vendor service stack directly on a host network. A Cloud environment may disallow the needed namespaces/mounts. If so, report that limitation rather than replacing native checks with a visual mock-up and calling it equivalent.

`validate_native.py` checks four naming cases, native Bluetooth desired-name generation, hostapd and advertised SSIDs, child preload removal, all eight application routes, and the hash of the actually loaded library. The Video route expects the vendor no-USB dialog in this hardware-free lab. `validate_delivery.py` runs ARM BusyBox/CRC checks and controlled healthy, disabled, incompatible, corrupt, crash and readiness-timeout cases. The 52 checks and their scope are recorded in `evidence`.

Portable artifact verification, which needs neither WSL nor hardware:

```sh
python tools/check_cloud_handover.py
```

To continue simulator work in Cloud, first recreate the pinned vendor/Qt/ARM inputs, port launch paths and static-QEMU handling, then rerun the actual native checks. Never label the old evidence as a fresh run. Private phone captures and raw field logs are deliberately not build inputs.
