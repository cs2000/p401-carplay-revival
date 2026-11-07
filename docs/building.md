# Building and verification

The repository can be checked out on a Linux machine or a cloud build runner. Build locally in a disposable filesystem/container as root to preserve vendor Unix ownership and modes. No physical device is needed to build or validate the image; none of these tools flashes hardware.

## Inputs

1. Obtain the exact `AA-NEW=P306.zip` reference listed in [provenance](provenance.md), and verify its SHA256. This is a build input, **not a USB update package to use unchanged**.
2. Extract its `rootfs.img` and `zImage` to an ignored `inputs/` directory. Verify the hashes in provenance.
3. Install Python dependencies with `python -m pip install -r requirements.txt`. Linux also needs GNU tar and mtd-utils (`mkfs.ubifs`, `ubinize`) with LZO support. The release used mtd-utils 2.2.1.

```sh
python tools/archive_ubi_tree.py inputs/rootfs.img build/donor
sudo python tools/build_image.py \
  --source-tar build/donor/rootfs_source_tree.tar \
  --build-dir /opt/carplay-revival-new-build
```

The builder requires a new output directory and checks the known tar hash. It preserves vendor ownership, modes and links, applies the small reviewed overlay, patches only the hash-identified library, installs the pinned DHCP binary and emits a UBI image. It does not copy private phone data into the filesystem.

Generated UBIFS UUIDs and modification timestamps can change the whole-image hash between builds. This is a repeatable build procedure with full content/metadata verification, not a claim of byte-for-byte reproducible UBI output.

## Verify a rebuilt image

Use `archive_ubi_tree.py` on the resulting rootfs and compare its complete inventory to the build's `inventory.json`. `tools/image_checks.py` exposes `medium(Path)` for UBI/UBIFS CRC and geometry checks and `dependencies(Path_to_roundtrip_tar)` for ARM ELF dependency closure. The published report records the release image checks and explicit limitations.

`python tools/test_startup.py --root /opt/carplay-revival-new-build/root --output build/startup-tests.json` runs the settings preflight under the actual ARM BusyBox through QEMU, using filesystem fixtures. Install `qemu-arm` (QEMU user emulation) for this check. It exercises different MCU selections, USB-only settings, missing/empty files and the recorded volatile-data state after mount failure; input files must remain unchanged. It also resolves the native applications through the vendor ARM loader without starting hardware services.

## DHCP source

The repository includes the exact BusyBox 1.38.0 source archive, `.config` and binary provenance under `third_party/busybox`. `tools/build_dhcp.sh` uses an ARM hard-float cross compiler supplied through `CROSS_COMPILE`. For example, use an ARM musl toolchain that emits ARMv7-A/VFPv3-D16 code and supports Linux 3.4. The original build used Alpine clang 20.1.8 with an ARM musl sysroot and produced the hash listed in provenance; another toolchain need not reproduce identical bytes.

The release builder intentionally accepts only the exact field-tested DHCP binary. A new binary requires its own validation and an explicit hash update; do not relabel it as field-tested automatically.

## Jaguar stock-to-UI full image

`tools/build_jaguar_image.py` builds the separate `2026.11-jaguar-xfr-rc1` candidate from the exact public W3 RC1 ZIP and its metadata-preserving rootfs extraction. It retains the kernel, update selector, W3 binaries and exact owner-tested UI1 library. It adds a standalone rootfs launcher instead of importing the field-W3 runner or manifests. Existing userdata settings and any saved UI name remain outside the image.

Inputs are pinned in the builder: public RC1 ZIP SHA256 `826592230326d57be22895fc89a1228504a16d45015c5996e5d6cca4c1e02278`, extracted RC1 tar SHA256 `be982d06fdefbc91229cd9d72081ac47f08ac3dc9733fcfa8aac02af10ee1b56`, and the tested UI overlay/library. Run `archive_ubi_tree.py` on the public RC1 rootfs to obtain that tar. Use the offline Docker runtimes described in the [Cloud lab](../experimental/ui1/lab/cloud/README.md).

```sh
python tools/build_jaguar_verifier.py
# In the disposable Linux build container as root, with the repo at /repo:
python tools/build_jaguar_image.py \
  --source-tar build/onboarding/release/rootfs_source_tree.tar \
  --verifier build/jaguar/verifier/verify \
  --verifier-evidence build/jaguar/verifier/BUILD.json \
  --build-dir build/jaguar/full-image
```

Use a new build directory. The helper has a reproducible static ARM build, 36 native-QEMU checks, and a separate `tools/test_jaguar_verifier_linux34.py` test forcing missing `statx` and observing the legacy `fstat64` fallback. The latter proves syscall fallback, not a complete old-kernel boot.

Validation uses `tools/test_startup.py --variant jaguar`, `tools/test_jaguar_ui_startup.py --real-timeout`, a complete `archive_ubi_tree.py` roundtrip followed by `tools/verify_jaguar_image.py`, and `experimental/ui1/lab/cloud/validate_firmware.py --root-tar ...`. The native test executes the unchanged integrated runner, ARM CRC helper and UI with documented private execution adapters/fake framebuffer; it does not execute the hardware-specific full profile or boot a kernel. Default `test_startup.py` still tests the unchanged clean RC1 variant.

The [new release](../releases/2026.11-jaguar-xfr-rc1/README.md) includes exact inputs, image/USB hashes, source, inventory and separate validation reports. UI disable/re-enable bundles are generated by `tools/package_jaguar_ui_controls.py`; they only write UI state and are not firmware recovery. Any new combined image needs its own vehicle installation test even when its components were already field-tested.

## Download / USB verification

```text
python tools/verify_usb.py PATH_TO_EXTRACTED_ZIP
```

This verifies the release's three file sizes/hashes and selector and rejects conflicting updater/autocopy/configuration payloads. It performs no writes. Read the release warning before putting the files in a vehicle.

## Cloud handoff

All public source, settings-preservation policy, release hashes and redacted findings live here. Private captures and local Windows/WSL paths are not required for documentation work or release verification. Protocol replay with the vendor libraries needs its own isolated network namespaces and synthetic fixtures; the private phone captures are not repository inputs. Do not treat a cloud runner's green result as vehicle validation.
