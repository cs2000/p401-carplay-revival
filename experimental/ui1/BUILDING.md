# Build and native lab

## RC2 continuation

The current RC2 library is `dbc68cef18e146e8f67700698445b17af29793e6ec702f9317db69d7a4d26eb1`. It adds native session observation, appearance preferences/editor and scoped Settings styling to the existing four source units. Earlier c62 owner success remains separate from this new build's evidence.

Run `lab/cloud/validate_rc2.py`, `lab/cloud/validate_rc2_regressions.py` and the preferences storage checks, then `lab/cloud/aggregate_rc2.py`. The aggregate binds the exact library, separate observers and current production source/assets. Package the current development car with `tools/package_ui1_rc2_upgrade.py` and validate it with `tools/test_ui1_rc2_upgrade.py`. Its exact previous-UI restore is the unchanged owner-tested installer; the separate UI-off archive is also unchanged.

The standalone full-image builder uses `--variant rc2 --ui-library PATH --ui-evidence PATH`. It retains the pinned W3 base and kernel, adds the exact `libLinkLibs.so` compatibility pin required by session observation, and needs its own image roundtrip/startup/native integration checks. The full-image and field-overlay launchers and recovery payloads are distinct. See [full RC2 technical records](full-image-rc2/README.md) and [assembly commands](../../docs/building.md).

## Previous Glass + Clock build

The original installer and historical evidence refer to UI1 source at commit `84e454fa06b633cf732b988ee58379e18fe0d06f` and remain unchanged. Glass + Clock added the approved photographic theme, clock replacing Main, native name eligibility, Exit classification and early startup cover. Its packaged library is `c62c2d49d3ce423d9cf11d96325e7ee5e50d7967ce0a865b2cf6f3a6f6593639`. Native evidence and source hashes remain with the [packaging snapshot](candidates/glass-clock-2026-11-06/MANIFEST.json); the [owner's later successful report](../../docs/evidence/ui1-owner-report-2026-11-07.json) is separate. The obsolete public overlay folder was removed. Full-flash recovery remains unproven.

## Build inputs

Use Linux, Python 3, Clang/LLD, and these external inputs:

* Qt headers at tag `v4.7.4`, commit `092cd760d5fddf9640a310214fe01929f0fff3a8` from https://github.com/qt/qt. Set `P401_QT_HEADERS` to that checkout (including `src/corelib`, `src/gui`, `src/network`). The script generates forwarding headers; licenses are in `licenses/qt`.
* A metadata-preserving Linux extraction of the matching vendor rootfs. Set `P401_VENDOR_ROOT` to its root. The donor identity and extraction tool are documented in [building](../../docs/building.md) and [provenance](../../docs/provenance.md). Do not treat Windows text representations of symlinks as shared libraries.
* The ARM hard-float musl SDK **headers**, originally from the Alpine ARM sysroot, at `P401_ARM_HEADERS`. The original lab used Clang 20.1.8 and musl headers. Headers are not the target runtime: linking is explicitly against the vendor glibc/Qt libraries. Do not substitute time64 symbols, a host `struct stat`, double `qreal`, soft-float libraries, or modern Qt.

```sh
python experimental/ui1/src/build.py
```

Output goes to ignored `experimental/ui1/build`. The original tested library hash is `aac2e11c9255b82c6fc76e7e824585773019e762d2c9dfaef52cbd7299c3ac35`. A rebuild with a different compiler/path need not be byte-identical; it needs fresh native and delivery checks before packaging. Extract the exact existing binary from `packages/INSTALL.zip` for comparison.

## Cloud and reference labs

The [stock-to-Jaguar full image](../../releases/2026.11-jaguar-xfr-rc1/README.md) reuses this exact UI library, with separate `firmware/jaguar` launcher/verifier and `tools/build_jaguar_image.py`. It requires no field-W3 startup tree. See [full-image build notes](../../docs/building.md) for its independent validation and state-only UI rollback; the exact combined image remains untested in a vehicle.

[lab/cloud](lab/cloud/README.md) now runs the actual ARM GUI in an isolated Docker filesystem, private network/PID/IPC namespaces and a fake framebuffer. The candidate passed 13 production-mode naming cases, 11 menu/startup cases, and the live-clock/header checks. Test-only observers do not enable the laboratory naming bypass. There is no interactive Cloud viewer.

`lab/reference` preserves the original native ARM simulator, framebuffer/pointer shim, validators, package builder and CRC helper from the Windows + Alpine WSL lab. Those reference launcher paths and Windows viewer commands remain historical; use the separate Cloud harness rather than running them blindly. The device code and ready install/rollback packages do not depend on the workstation layout.

The original layout was `work/ui_customization`, `work/visual_emulator`, `work/qt4-headers`, a vendor root at `/opt/p401-build/candidate-r1/root`, and an ARM SDK at `/opt/p401-r4-arm`. The original WSL distribution was `Codex-P401-Build`. The package builder also referenced the installed W3 payload; only the exact rollback files and manifest are retained under `baseline` here, so do not run the reference builder blindly.

The lab runs the actual `MsnCoreApp` through QEMU in private mount/network/PID/IPC namespaces with a copied root, fake framebuffer and pointer injection. It does not emulate the MCU, Wi-Fi/Bluetooth radio, MFi device, an iPhone, media streaming or a physical reboot. Preserve isolation; do not start the vendor service stack directly on a host network. A Cloud environment may disallow the needed namespaces/mounts. If so, report that limitation rather than replacing native checks with a visual mock-up and calling it equivalent.

`validate_native.py` checks four naming cases, native Bluetooth desired-name generation, hostapd and advertised SSIDs, child preload removal, all eight application routes, and the hash of the actually loaded library. The Video route expects the vendor no-USB dialog in this hardware-free lab. `validate_delivery.py` runs ARM BusyBox/CRC checks and controlled healthy, disabled, incompatible, corrupt, crash and readiness-timeout cases. The 52 checks and their scope are recorded in `evidence`.

Portable artifact verification, which needs neither WSL nor hardware:

```sh
python tools/check_cloud_handover.py
```

Follow the Cloud harness README to recreate the pinned vendor/Qt/ARM inputs and run fresh native checks. `tools/package_ui1_candidate.py` requires passed evidence for the exact supplied ARM hash; `lab/cloud/delivery.py` independently checks the generated archive and its startup/failure fixtures. Never label historical evidence as a fresh run. Private phone captures and raw field logs are deliberately not build inputs.
