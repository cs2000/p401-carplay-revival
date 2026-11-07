"""Check standalone Jaguar startup with real ARM shell/verifier and process fixtures.

The GUI is a launch recorder, not the vendor application. No service, radio,
MCU, reboot, kernel boot or device flash is performed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
import zlib

REPO = Path(__file__).resolve().parents[1]
UI_PATH = "/usr/libexec/carplay-revival/ui"
HELPER_PATH = "/usr/libexec/carplay-revival/verify"
DATA_PATH = "/data/carplay-revival"


def crc(data):
    return f"{zlib.crc32(data):08x} {len(data)}"


def validate(root, output, real_timeout=False):
    root = root.resolve()
    checks = []
    passed = False
    timings = []
    real_timeout_exercised = False

    def check(label, ok):
        checks.append({"check": label, "passed": bool(ok)})
        print(("PASS " if ok else "FAIL ") + label, flush=True)
        if not ok:
            raise AssertionError(label)

    def run(argv, **kw):
        return subprocess.run(argv, capture_output=True, timeout=kw.pop("timeout", 20), **kw)

    def write(path, data, executable=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        path.chmod(0o755 if executable else 0o644)

    qemu = shutil.which("qemu-arm")
    if not qemu:
        raise RuntimeError("qemu-arm is required; run in the documented toolchain container")
    shell = [qemu, "-cpu", "cortex-a7", "-L", str(root), str(root / "bin/busybox"), "sh"]
    verifier = [qemu, "-cpu", "cortex-a7", str(root / HELPER_PATH.lstrip("/"))]
    ui = root / UI_PATH.lstrip("/")
    wrapper = (ui / "run-ui.sh").read_bytes()
    manifest = (ui / "compatibility.txt").read_bytes()
    outer_template = (REPO / "firmware/jaguar/launch-ui.sh.in").read_text()
    expected_outer = outer_template.replace("@RUNNER_CHECK@", crc(wrapper))
    profile = (root / "etc/profile").read_text()

    try:
        check("profile directly guards runner before background launch", expected_outer in profile)
        check("wrapper pins exact compatibility bytes", crc(manifest).encode() in wrapper)
        check("startup has no field W3 marker/helper dependency",
              all(token not in wrapper + expected_outer.encode() for token in
                  (b"/tmp/p401-w3-install-ok", b"/usr/lib/p401-r4", b"/data/p401-w3", b"p401-log")))
        check("rootfs runner syntax under native ARM shell",
              run(shell + ["-n", str(ui / "run-ui.sh")]).returncode == 0)
        check("profile syntax under native ARM shell",
              run(shell + ["-n", str(root / "etc/profile")]).returncode == 0)

        rows = []
        for line in manifest.decode().splitlines():
            checksum, size, absolute = line.split(" ", 2)
            path = root / absolute.lstrip("/")
            check("ARM verifier pins " + absolute,
                  run(verifier + ["verify", str(path), checksum, size]).returncode == 0)
            rows.append((checksum, size, absolute))

        with tempfile.TemporaryDirectory(prefix="jaguar-startup-") as temporary:
            fixture = Path(temporary)
            bindir = fixture / "bin"
            data = fixture / "data/carplay-revival"
            fixture_ui = fixture / "ui"
            tmp = fixture / "tmp"
            tmp.mkdir()
            for app in ("rm", "mkdir", "mv", "sync", "sleep"):
                command = [qemu, "-cpu", "cortex-a7", "-L", str(root), str(root / "bin/busybox"), app]
                write(bindir / app, "#!/bin/sh\nexec " + shlex.join(command) + ' "$@"\n', True)
            helper = fixture / "helper"
            helper_bytes = "#!/bin/sh\nexec " + shlex.join(verifier) + ' "$@"\n'
            write(helper, helper_bytes, True)
            recorder = """#!/bin/sh
if [ -n "$P401_TEST_PRELOAD" ]; then
    printf 'CUSTOM:%s:%s:%s:%s\\n' "$P401_UI_LAYOUT" "${P401_UI_NAMES-unset}" "${P401_UI_NAMES_REASON-unset}" "${P401_UI_LAB-unset}"
    case "$CASE" in
        crash|disable-write-fails|missing-data-crash) exit 139;;
        ready-then-crash) printf 'ready\\n' > "$FIXTURE/tmp/p401-ui-ready"; exit 139;;
        notready) exit 0;;
        timeout|real-timeout) exec "$FIXTURE/bin/sleep" 300;;
        ignore-term) trap '' TERM; exec "$FIXTURE/bin/sleep" 300;;
        healthy-long) printf 'ready\\n' > "$FIXTURE/tmp/p401-ui-ready"; "$FIXTURE/bin/sleep" 3; exit 0;;
        *) printf 'ready\\n' > "$FIXTURE/tmp/p401-ui-ready"; exit 0;;
    esac
else
    printf 'STOCK:%s:%s:%s:%s:%s\\n' "${LD_PRELOAD-unset}" "${P401_UI_LAYOUT-unset}" "${P401_UI_NAMES-unset}" "${P401_UI_NAMES_REASON-unset}" "${P401_UI_LAB-unset}"
fi
"""
            write(bindir / "MsnCoreApp", recorder, True)
            factory = fixture / "data/msncfg/FactoryConfig.ini"
            product = fixture / "data/msncfg/MsnProductInfo.ini"
            factory_bytes = b"[General]\nIphoneLinkType=1\nVolume=37\nDisableSetMCUType=0\n"
            product_bytes = b"[General]\nMcuType=6\nBlueToothType=3\nWlanType=1\nUnknownCalibration=keep\n"
            write(factory, factory_bytes)
            write(product, product_bytes)
            saved_name = b"JAGUAR PRIVATE\n"

            fixture_rows = []
            mapped_files = {}
            for checksum, size, absolute in rows:
                path = fixture / "payload" / absolute.lstrip("/")
                original = (root / absolute.lstrip("/")).read_bytes()
                write(path, original)
                mapped_files[absolute] = (path, original)
                fixture_rows.append(f"{checksum} {size} {path}\n")
            fixture_manifest = "".join(fixture_rows).encode()
            write(fixture_ui / "libp401-ui.so", (ui / "libp401-ui.so").read_bytes())
            script = wrapper.decode().replace(DATA_PATH, str(data)).replace(UI_PATH, str(fixture_ui)).replace(HELPER_PATH, str(helper))
            script = script.replace("/tmp/p401-", str(tmp / "p401-"))
            script = script.replace(crc(manifest), crc(fixture_manifest))
            # The recorder cannot load ARM Qt into the host process. All shell,
            # checksum and applet work still uses the actual ARM executables.
            script = script.replace("LD_PRELOAD=", "P401_TEST_PRELOAD=")
            short_script = script.replace('[ "$ticks" -lt 60 ]', '[ "$ticks" -lt 2 ]')
            fixture_runner = fixture_ui / "run-ui.sh"
            outer = expected_outer.replace(UI_PATH, str(fixture_ui)).replace(HELPER_PATH, str(helper))
            cases = ["absent-state", "enabled", "disabled", "malformed-state", "empty-state",
                     "enabled-no-newline", "enabled-extra-newline", "broken-state-link",
                     "corrupt-manifest", "corrupt-library", "incompatible-vendor", "helper-missing",
                     "crash", "notready", "ready-then-crash", "timeout", "ignore-term",
                     "disable-write-fails", "missing-data-crash", "healthy-long",
                     "outer-healthy", "outer-corrupt-runner", "outer-helper-missing"]
            if real_timeout:
                cases.append("real-timeout")
            for case in cases:
                for path in tmp.iterdir():
                    path.unlink()
                if data.exists():
                    shutil.rmtree(data)
                data.mkdir(parents=True)
                write(data / "network-name", saved_name)
                state = data / "state"
                if case != "absent-state":
                    write(state, b"enabled\n")
                state_values = {"disabled": b"disabled\n", "malformed-state": b"anything\n",
                                "empty-state": b"", "enabled-no-newline": b"enabled",
                                "enabled-extra-newline": b"enabled\n\n"}
                if case in state_values:
                    write(state, state_values[case])
                if case == "broken-state-link":
                    state.unlink()
                    state.symlink_to("missing-state-target")
                if case == "disable-write-fails":
                    (data / "state.new").mkdir()
                if case == "missing-data-crash":
                    shutil.rmtree(data)
                for path, original in mapped_files.values():
                    write(path, original)
                manifest_bytes = fixture_manifest
                case_script = script if case == "real-timeout" else short_script
                if case == "corrupt-library":
                    write(mapped_files[UI_PATH + "/libp401-ui.so"][0], b"corrupt")
                if case == "incompatible-vendor":
                    checksum, size, absolute = rows[1]
                    needle = f"{checksum} {size} {mapped_files[absolute][0]}\n"
                    manifest_bytes = fixture_manifest.replace(needle.encode(), f"00000000 1 {mapped_files[absolute][0]}\n".encode())
                    case_script = case_script.replace(crc(fixture_manifest), crc(manifest_bytes))
                write(fixture_ui / "compatibility.txt", b"bad\n" if case == "corrupt-manifest" else manifest_bytes)
                write(fixture_runner, case_script, True)
                write(helper, helper_bytes, True)
                launch = shell + [str(fixture_runner)]
                if case.startswith("outer-"):
                    case_outer = outer.replace(crc(wrapper), crc(case_script.encode()))
                    if case == "outer-corrupt-runner":
                        with fixture_runner.open("ab") as stream:
                            stream.write(b"\n# altered after pinning\n")
                    entry = fixture / "entry.sh"
                    write(entry, case_outer + "\nwait\n", True)
                    launch = shell + [str(entry)]
                if case in ("helper-missing", "outer-helper-missing"):
                    helper.unlink()
                env = dict(os.environ, PATH=str(bindir), CASE=case, FIXTURE=str(fixture),
                           P401_UI_NAMES="1", P401_UI_NAMES_REASON="obsolete", P401_UI_LAB="1")
                env.pop("LD_PRELOAD", None)
                began = time.monotonic()
                result = run(launch, env=env, timeout=150 if case == "real-timeout" else 15)
                elapsed = time.monotonic() - began
                timings.append({"case": case, "elapsed_seconds": round(elapsed, 3)})
                text = result.stdout.decode() + result.stderr.decode()
                custom = "CUSTOM:xfr:unset:unset:unset" in text
                stock = "STOCK:unset:unset:unset:unset:unset" in text
                failures = {"crash", "notready", "ready-then-crash", "timeout", "ignore-term",
                            "disable-write-fails", "missing-data-crash", "real-timeout"}
                healthy = {"absent-state", "enabled", "healthy-long", "outer-healthy"}
                if case in healthy:
                    ok = custom and not stock
                    if case == "absent-state":
                        ok = ok and not state.exists()
                    else:
                        ok = ok and state.read_bytes() == b"enabled\n"
                elif case in failures:
                    ok = custom and stock
                    if case == "disable-write-fails":
                        ok = ok and state.read_bytes() == b"enabled\n"
                    else:
                        ok = ok and state.read_bytes() == b"disabled\n"
                    if case == "real-timeout":
                        ok = ok and elapsed >= 59 and elapsed < 140 and (tmp / "p401-ui-timeout").is_file()
                        real_timeout_exercised = ok
                else:
                    ok = stock and not custom
                if not ok or result.returncode:
                    print(text)
                check(case + " launch/fallback", result.returncode == 0 and ok)
                check(case + " preserves factory and MCU bytes",
                      factory.read_bytes() == factory_bytes and product.read_bytes() == product_bytes)
                if case != "missing-data-crash":
                    check(case + " preserves custom name", (data / "network-name").read_bytes() == saved_name)
                if case in failures and case != "disable-write-fails":
                    check(case + " disable state permissions private", state.stat().st_mode & 0o777 == 0o600)
        passed = True
    finally:
        report = {"passed": passed and bool(checks) and all(row["passed"] for row in checks),
                  "count": len(checks), "checks": checks,
                  "runner_sha256": hashlib.sha256(wrapper).hexdigest(),
                  "helper_sha256": hashlib.sha256((root / HELPER_PATH.lstrip("/")).read_bytes()).hexdigest(),
                  "real_60_second_watchdog_exercised": real_timeout_exercised,
                  "process_fixture_timings": timings,
                  "scope": "Fresh actual ARM BusyBox shell/applets and standalone ARM CRC verifier, redirected GUI process fixtures. No vendor GUI execution, MCU, radio, physical reboot, kernel boot or flash test."}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--real-timeout", action="store_true")
    args = parser.parse_args()
    report = validate(args.root, args.output, args.real_timeout)
    print(json.dumps({"passed": report["passed"], "checks": report["count"]}))
