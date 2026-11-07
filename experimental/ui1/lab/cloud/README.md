# Isolated Cloud native lab

This port runs the actual ARM `MsnCoreApp` and candidate UI library through static
QEMU. Docker supplies a private PID namespace, private IPC, `--network=none`, no
capabilities, and no real device mappings. A regular file replaces `/dev/fb0` and
Qt receives pointer events through the preserved lab shim. No privileged inner
mounts or host-network vendor services are needed. There is no interactive viewer.

The runtime does not emulate the MCU, physical radios, iPhone/MFi session, media
streaming or hardware reboot. A successful lab reboot-request test does not prove
the physical unit reboots. Native screenshots are 800×480 framebuffer captures;
English model substitutions used for visual checks are explicit test fixtures.

## Inputs and compiler

Read `../../BUILDING.md`. Use the pinned Qt v4.7.4 headers and matching
metadata-preserving vendor root. The Cloud continuation has these ignored inputs:

* `experimental/ui1/inputs/qt4-headers` — Qt commit
  `092cd760d5fddf9640a310214fe01929f0fff3a8`.
* `experimental/ui1/build/cloud/vendor-root` — matching vendor root extraction.
* `build/onboarding/release/rootfs_source_tree.tar` — preserved release root tree.

The current managed environment supplies `carplay-dev:local` with static
`/usr/bin/qemu-arm`. `Dockerfile.toolchain` extends it with Clang/LLD and ARM musl
headers; it links the UI against the existing vendor glibc and Qt libraries.
Do not substitute host Qt libraries or infer hardware compatibility from a build.

Use the managed Docker socket, preserving registry configuration and proxy defaults:

```sh
docker_local() {
  env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS \
      -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
      docker --host=unix:///var/run/docker.sock "$@"
}
docker_local build --secret "id=proxy_ca,src=$CODEX_PROXY_CERT" \
  -f experimental/ui1/lab/cloud/Dockerfile.toolchain \
  -t p401-ui-toolchain:local experimental/ui1/lab/cloud
```

The networked package-install step uses the managed CA secret with TLS verification
kept enabled. All subsequent builds and native GUI runs are offline.

```sh
docker_local run --rm --network=none \
  --mount "type=bind,src=$PWD,dst=/repo" \
  -e P401_QT_HEADERS=/repo/experimental/ui1/inputs/qt4-headers \
  -e P401_VENDOR_ROOT=/repo/experimental/ui1/build/cloud/vendor-root \
  -e P401_ARM_HEADERS=/usr/include/arm-linux-musleabihf \
  p401-ui-toolchain:local python /repo/experimental/ui1/src/build.py

python experimental/ui1/lab/cloud/native.py --prepare-image \
  build/onboarding/release/rootfs_source_tree.tar

docker_local run --rm --network=none \
  --mount "type=bind,src=$PWD,dst=/repo" \
  p401-ui-toolchain:local \
  python /repo/experimental/ui1/lab/cloud/native.py --build-probe
```

The separate test probe observes widgets and supplies controlled model fixtures.
Production-mode cases leave `P401_UI_LAB` unset, so native Bluetooth eligibility
and `/data` persistence are exercised. Synthetic request/control files must be
readable by the isolated container's mapped UID; `native.py` sets their modes.

## Evidence

Run the settings, menu and clock validators using their `--help` options for the case
selection supported by the current revision. Runtime files and new JSON reports
are under ignored `experimental/ui1/build/cloud`; old `evidence/*.json` files are
never overwritten. The clock report must cover a naturally advancing native
minute and hiding the clock overlay when the native Settings screen opens.

```sh
python experimental/ui1/lab/cloud/validate_settings.py
python experimental/ui1/lab/cloud/validate_menu.py
python experimental/ui1/lab/cloud/validate_clock.py
```

`validate.py` only aggregates already completed reports. It requires every report
to pass and name the exact hash of the library being packaged:

```sh
python experimental/ui1/lab/cloud/validate.py
```

This lab does not build or publish an install ZIP. Packaging and delivery checks
are separate, and the stable release and original install/rollback archives remain
preserved.

## RC2 feature checks

After building the RC2 production library, build its separate observer with
`native.py --build-rc2-probe` in the pinned ARM toolchain, then run
`python experimental/ui1/lab/cloud/validate_rc2.py --library PATH`.
The report is `build/cloud/rc2/RC2_FEATURE_CHECKS.json`; every expected case must
pass for `complete` and `passed` to be true. Native link-status events and
Bluetooth-ready tags are explicit synthetic input fixtures. They verify the
actual vendor event path and UI response, not a physical radio session.

The suite drives appearance Save/Cancel, reordered native app routing and
Factory → Advanced through actual Qt pointer events. It checks private persisted
preferences and unchanged synthetic factory profiles. Screenshots remain in
separate `runs/rc2-*` folders. English model replacements are labelled as visual
fixtures and restored before native route checks. No historical evidence is
overwritten, and physical installation/recovery remains outside this lab.

`validate_rc2_regressions.py` runs the original 13 naming, 11 menu/startup and
clock checks using a separate freshly compiled plain observer and isolated report
directory. The native CarPlay-name navigation row is located from its visible
model geometry. `test_preferences.py` records the 23 actual-ARM storage checks.
`aggregate_rc2.py` requires the complete matrices, exact binary/observer identities
and current production source snapshot before either RC2 packager may proceed.

## Standalone full-image integration

`validate_firmware.py --root-tar PATH --output REPORT` tests the separate stock-to-Jaguar candidate after its filesystem roundtrip. It executes the unchanged production runner and exact UI/CRC-helper ARM bytes. `firmware_dispatch.c` supplies test-only executable adapters because the Cloud host has no target binfmt registration; adapted verification paths refer to the original, independently verified ARM files. The runner, compatibility manifest and UI library are not patched or bypassed. Framebuffer and observation shims are lab-only.

Cases cover fresh userdata without field-W3 files, actual native Exit/Settings and pointer name save/restart request, saved-name endpoints after reload, disabled UI, corrupt manifest, crash and a real watchdog timeout, using the actual native interface for fallback. The separate image verifier checks the unadapted full filesystem before these lab copies are made. This does not execute the hardware-specific full `/etc/profile`, boot a kernel, emulate radios or prove physical recovery. See the [full-image build notes](../../../../docs/building.md).

For RC2 use `--variant rc2 --ui-evidence PATH --probe-library PATH`, supplying the
complete exact-UI aggregate and fresh plain regression observer. The extracted
image UI must match that hash. Existing-userdata reload also verifies retained
enabled state, appearance bytes and saved-name endpoints. Default RC1 checks keep
their historical pinned UI and navigation behavior.
