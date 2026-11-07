#!/usr/bin/env python3
"""Check the field-layout RC2 autocopy upgrade and exact previous-UI restore.

Run in the prepared isolated toolchain container with QEMU and the vendor root.
No vendor service is started and no flash/MCU/radio operation is performed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

from package_ui1_candidate import (
    COMPATIBILITY, INSTALL_PATHS, LIBRARY, PREFIX, RUNNER, STATE, UI,
    W3_MANIFEST, WRAPPER, crc_length, read_zip, row, sha256,
)
from package_ui1_rc2_upgrade import (
    LINK_ROW, PREVIOUS_INSTALL_SHA256, PREVIOUS_LIBRARY_SHA256, previous_package,
)


def validate(candidate: Path, vendor: Path, output: Path) -> dict:
    checks = []

    def check(label: str, ok: bool) -> None:
        checks.append({"check": label, "passed": bool(ok)})
        print(("PASS " if ok else "FAIL ") + label, flush=True)
        if not ok:
            raise AssertionError(label)

    report = {"passed": False, "complete": False, "checks": checks,
              "scope": "Fresh archive, actual ARM BusyBox/CRC and redirected process fixtures; synthetic userdata apply/restore. The redirected wrapper watchdog is shortened from 60 seconds to two seconds only in its process fixture. Unchanged W3 rows are preserved, not a fresh test of unavailable field logging payloads. No physical radio, MCU, reboot, autocopy, flash or unbootable-unit recovery proof."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    previous, previous_zip, disable_zip = previous_package()
    install_zip = (candidate / "INSTALL.zip").read_bytes()
    restore_zip = (candidate / "RESTORE_PREVIOUS_UI.zip").read_bytes()
    install = read_zip(install_zip)
    restore = read_zip(restore_zip)
    disable = (candidate / "DISABLE_UI.zip").read_bytes()
    check("RC2 exact six UI-only paths", set(install) == {PREFIX + path for path in INSTALL_PATHS})
    check("restore exact six prior UI-only paths", set(restore) == set(install))
    check("restore archive byte-for-byte owner-tested previous installer",
          restore_zip == previous_zip and sha256(restore_zip) == PREVIOUS_INSTALL_SHA256)
    check("restore payload byte-for-byte previous working files", restore == previous)
    check("restore exact previous c62 library", sha256(restore[PREFIX + LIBRARY]) == PREVIOUS_LIBRARY_SHA256)
    check("historical disable archive unchanged", disable == disable_zip)
    check("new binary differs from previous owner-tested binary", install[PREFIX + LIBRARY] != restore[PREFIX + LIBRARY])
    check("both versions enable their respective Jaguar UI", install[PREFIX + STATE] == restore[PREFIX + STATE] == b"enabled\n")
    compatibility = install[PREFIX + COMPATIBILITY].splitlines()
    prior_compatibility = restore[PREFIX + COMPATIBILITY].splitlines()
    check("RC2 compatibility has UI plus ten vendor rows", len(compatibility) == 11)
    check("RC2 retains previous nine vendor ABI rows", compatibility[1:10] == prior_compatibility[1:])
    check("RC2 adds exact native connection ABI pin", compatibility[10] == LINK_ROW)
    shell = ["qemu-arm", "-L", str(vendor), str(vendor / "bin/busybox"), "sh"]
    verifier = ["qemu-arm", str(UI / "lab/reference/p401-diag")]

    # Reuse the existing ARM wrapper fixture checks with the untouched historical
    # UI-disable package; this also verifies the new extra native ABI row.
    spec = importlib.util.spec_from_file_location("ui1_delivery", UI / "lab/cloud/delivery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="rc2-upgrade-check-", dir=UI / "build/cloud") as temporary:
        temporary = Path(temporary)
        alias = temporary / "base-delivery"
        alias.mkdir()
        (alias / "INSTALL.zip").write_bytes(install_zip)
        (alias / "ROLLBACK.zip").write_bytes(disable)
        base_report = module.validate(alias, vendor, temporary / "BASE_DELIVERY_CHECKS.json")
        check("RC2 ARM shell, all compatibility rows and startup/fallback fixtures pass", base_report.get("passed") is True)
        checks.extend(base_report["checks"])

        for label, payload in (("RC2", install), ("previous", restore)):
            root = temporary / label
            for name, data in payload.items():
                dest = root / name.removeprefix(PREFIX)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            for rel in (RUNNER, WRAPPER):
                result = subprocess.run(shell + ["-n", str(root / rel)], capture_output=True)
                check(label + " ARM shell syntax " + rel, result.returncode == 0)
            manifest_rows = payload[PREFIX + W3_MANIFEST].splitlines()
            check(label + " W3 manifest pins its exact runner", row(payload[PREFIX + RUNNER], RUNNER) in manifest_rows)
            check(label + " runner pins its exact UI wrapper", crc_length(payload[PREFIX + WRAPPER]).encode() in payload[PREFIX + RUNNER])
            check(label + " wrapper pins its exact compatibility manifest", crc_length(payload[PREFIX + COMPATIBILITY]).encode() in payload[PREFIX + WRAPPER])
            for line in payload[PREFIX + COMPATIBILITY].decode().splitlines():
                checksum, size, absolute = line.split(" ", 2)
                path = root / LIBRARY if absolute.endswith("/libp401-ui.so") else vendor / absolute.lstrip("/")
                result = subprocess.run(verifier + ["verify", str(path), checksum, size], capture_output=True)
                check(label + " actual ARM CRC " + absolute, path.is_file() and result.returncode == 0)

        old_rows = restore[PREFIX + W3_MANIFEST].splitlines()
        new_rows = install[PREFIX + W3_MANIFEST].splitlines()
        check("upgrade W3 manifest changes only the GUI runner pin",
              len(old_rows) == len(new_rows) and [(a, b) for a, b in zip(old_rows, new_rows) if a != b]
              == [(row(restore[PREFIX + RUNNER], RUNNER), row(install[PREFIX + RUNNER], RUNNER))])
        filesystem = temporary / "synthetic-car"
        sentinels = {
            "data/msncfg/MsnProductInfo.ini": b"[General]\nMcuType=7\nBlueToothType=3\nWlanType=1\n",
            "data/msncfg/FactoryConfig.ini": b"[General]\nSyntheticFixture=retain-exactly\n",
            "data/carplay-revival/network-name": b"Synthetic Jaguar\n",
            "data/carplay-revival/appearance": b"synthetic-private-existing-appearance\n",
            "data/p401-w3/payload/usr/lib/libAirPlay.so": b"synthetic-working-W3-file-unchanged",
            "data/p401-w3/payload/usr/bin/udhcpd": b"synthetic-working-DHCP-file-unchanged",
            "etc/profile": b"synthetic-installed-field-profile-unchanged\n",
            "boot/zImage": b"synthetic-existing-kernel-unchanged",
        }

        def apply(files: dict[str, bytes]) -> None:
            for name, data in files.items():
                dest = filesystem / name.removeprefix(PREFIX)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)

        for name, data in sentinels.items():
            dest = filesystem / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        apply(previous)
        apply(install)
        check("synthetic upgrade installs all exact RC2 payload bytes", all((filesystem / name.removeprefix(PREFIX)).read_bytes() == data for name, data in install.items()))
        check("synthetic upgrade preserves name, appearance, factory, W3, startup and kernel sentinels", all((filesystem / name).read_bytes() == data for name, data in sentinels.items()))
        apply(restore)
        check("synthetic restore returns all six exact previous working files", all((filesystem / name.removeprefix(PREFIX)).read_bytes() == data for name, data in previous.items()))
        check("synthetic restore preserves name, appearance, factory, W3, startup and kernel sentinels", all((filesystem / name).read_bytes() == data for name, data in sentinels.items()))

    report.update(passed=True, complete=True, library_sha256=sha256(install[PREFIX + LIBRARY]),
                  installer_sha256=sha256(install_zip), restore_sha256=sha256(restore_zip),
                  disable_sha256=sha256(disable), checks=checks, check_count=len(checks))
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--vendor-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate(args.candidate.resolve(), args.vendor_root.resolve(), args.output.resolve())
