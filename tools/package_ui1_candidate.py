#!/usr/bin/env python3
"""Package a locally validated UI1 candidate without changing archived releases.

Requires fresh native evidence for the supplied ARM library. This creates only
an autocopy overlay for the development R1 + field-W3 startup layout; it neither
builds a firmware image nor supplies full-flash recovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import struct
import subprocess
import tempfile
import zipfile
import zlib

REPO = Path(__file__).resolve().parents[1]
UI = REPO / "experimental/ui1"
BASELINE_COMMIT = "84e454fa06b633cf732b988ee58379e18fe0d06f"
ARCHIVED_INSTALL_SHA256 = "2d43baa7ce7f244e48fcb14cde7d9a853be6e599f3b3fa47d8ab83391b06c53f"
ARCHIVED_ROLLBACK_SHA256 = "6e1572046f5cc2d8d386509a19a60a67de9154bdc89ce23057b5426fcf966a03"
PREFIX = "msn_autocopy/"
LIBRARY = "data/carplay-revival/lib/libp401-ui.so"
COMPATIBILITY = "data/carplay-revival/compatibility.txt"
WRAPPER = "data/carplay-revival/run-ui.sh"
STATE = "data/carplay-revival/state"
RUNNER = "usr/bin/p401-recovery-run-core.sh"
W3_MANIFEST = "data/p401-w3/install-checks.txt"
INSTALL_PATHS = {LIBRARY, COMPATIBILITY, WRAPPER, STATE, RUNNER, W3_MANIFEST}
OUTPUT_MARKER = ".p401-ui1-candidate"
OUTPUT_FILES = {"INSTALL.zip", "ROLLBACK.zip", "MANIFEST.json", "NATIVE_EVIDENCE.json", OUTPUT_MARKER}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def description(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": sha256(data)}


def crc_length(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xffffffff:08x} {len(data)}"


def row(data: bytes, path: str) -> bytes:
    return f"{crc_length(data)} /{path}".encode("ascii")


def read_zip(data: bytes) -> dict[str, bytes]:
    from io import BytesIO

    with zipfile.ZipFile(BytesIO(data)) as archive:
        require(archive.testzip() is None, "Archive CRC verification failed")
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        require(len(names) == len(set(names)), "Duplicate archive entry")
        for name in names:
            path = PurePosixPath(name)
            require(name.startswith(PREFIX) and ".." not in path.parts and not path.is_absolute(),
                    f"Unsafe archive entry: {name}")
        return {name: archive.read(name) for name in names}


def archived_packages() -> tuple[dict[str, bytes], dict[str, bytes], bytes]:
    """Verify every archive and payload against the preserved handover manifest."""
    manifest = json.loads((UI / "packages/MANIFEST.json").read_text())
    pins = {"INSTALL.zip": ARCHIVED_INSTALL_SHA256, "ROLLBACK.zip": ARCHIVED_ROLLBACK_SHA256}
    require({package["file"] for package in manifest["packages"]} == set(pins),
            "Unexpected archived package list")
    payloads = {}
    archive_bytes = {}
    for package in manifest["packages"]:
        name = package["file"]
        data = (UI / "packages" / name).read_bytes()
        require(package["sha256"] == pins[name] and sha256(data) == pins[name],
                f"Archived package hash changed: {name}")
        require(len(data) == package["bytes"], f"Archived package size changed: {name}")
        files = read_zip(data)
        require(set(files) == set(package["files"]), f"Archived payload list changed: {name}")
        for path, content in files.items():
            require(description(content) == package["files"][path], f"Archived payload changed: {path}")
        payloads[name] = files
        archive_bytes[name] = data
    install, rollback = payloads["INSTALL.zip"], payloads["ROLLBACK.zip"]
    require(set(install) == {PREFIX + p for p in INSTALL_PATHS}, "Archived installer is not the six-file overlay")
    require(set(rollback) == {PREFIX + p for p in (RUNNER, W3_MANIFEST, STATE)}, "Unexpected rollback payload")
    require(sha256(install[PREFIX + LIBRARY]) == manifest["library_sha256"], "Archived library pin changed")
    for path, content in rollback.items():
        require(content == (UI / "baseline" / path[len(PREFIX):]).read_bytes(),
                f"Rollback differs from exact baseline: {path}")
    require(rollback[PREFIX + STATE] == b"disabled\n", "Rollback must disable UI1")
    return install, rollback, archive_bytes["ROLLBACK.zip"]


def source_snapshot() -> dict:
    files = {}
    suffixes = {".cpp", ".h", ".in", ".py", ".png", ".svg", ".json"}
    for path in sorted((UI / "src").rglob("*")):
        if "__pycache__" in path.parts or path.suffix not in suffixes:
            continue
        require(not path.is_symlink(), f"Source snapshot may not follow a symlink: {path}")
        if path.is_file():
            files[path.relative_to(REPO).as_posix()] = description(path.read_bytes())
    require(bool(files), "No source files captured")
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": sha256(encoded), "encoding": "SHA256 of canonical JSON files map (sorted keys, compact separators)",
            "files": files, "note": "Source snapshot at packaging; not a claim of byte-for-byte reproducibility."}


def replace_manifest_row(manifest: bytes, before: bytes, after: bytes, what: str) -> bytes:
    rows = manifest.splitlines(keepends=True)
    matches = [index for index, line in enumerate(rows) if line.rstrip(b"\r\n") == before]
    require(len(matches) == 1, f"Expected one {what} manifest row")
    index = matches[0]
    old = rows[index]
    ending = old[len(old.rstrip(b"\r\n")):]
    rows[index] = after + ending
    return b"".join(rows)


def package_metadata(name: str, data: bytes) -> dict:
    return {"file": name, **description(data),
            "files": {path: description(content) for path, content in sorted(read_zip(data).items())}}


def zip_install(files: dict[str, bytes]) -> bytes:
    from io import BytesIO

    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(files.items()):
            # Fixed metadata makes repeated packaging of identical inputs stable.
            item = zipfile.ZipInfo(name, (2026, 11, 6, 0, 0, 0))
            item.create_system = 3
            item.external_attr = (0o100644 << 16)
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, content, compresslevel=9)
    data = out.getvalue()
    require(read_zip(data) == files, "Generated installer failed roundtrip verification")
    return data


def output_is_safe(output: Path, replace: bool) -> None:
    require(not output.is_symlink(), "Candidate destination may not be a symlink")
    destination = output.resolve()
    require(not destination.is_relative_to((UI / "packages").resolve()), "Do not overwrite the archived packages directory")
    require(not destination.is_relative_to((REPO / "releases").resolve()), "Do not write a public release")
    if not output.exists():
        return
    require(replace, f"Destination already exists: {output}; use a new path or --replace for this tool's output")
    require(output.is_dir(), "Candidate destination is not a directory")
    require((output / OUTPUT_MARKER).is_file() and (output / OUTPUT_MARKER).read_bytes() == b"p401-ui1-candidate-v1\n",
            "Refusing to replace a directory not created by this tool")
    require({path.name for path in output.iterdir()} == OUTPUT_FILES,
            "Candidate directory contains files not generated by this tool")
    require(all(path.is_file() and not path.is_symlink() for path in output.iterdir()),
            "Candidate output contains a non-regular file")


def build_candidate(binary_path: Path, evidence_path: Path, output: Path, replace: bool) -> dict:
    install, rollback, rollback_archive = archived_packages()
    binary = binary_path.read_bytes()
    require(len(binary) >= 52 and binary[:6] == b"\x7fELF\x01\x01", "Candidate must be a little-endian ELF32 library")
    require(struct.unpack_from("<HH", binary, 16) == (3, 40), "Candidate must be an ARM shared object")
    require(struct.unpack_from("<I", binary, 36)[0] & 0x400 != 0, "Candidate must use ARM hard-float ABI")
    binary_sha256 = sha256(binary)
    evidence_bytes = evidence_path.read_bytes()
    evidence = json.loads(evidence_bytes)
    require(evidence.get("passed") is True, "Native evidence has not passed")
    require(evidence.get("library_sha256") == binary_sha256, "Native evidence does not match the supplied library")
    require(binary_sha256 != sha256(install[PREFIX + LIBRARY]), "Candidate library is still the archived UI1 artifact")
    output_is_safe(output, replace)

    old_compatibility = install[PREFIX + COMPATIBILITY]
    compatibility_rows = old_compatibility.splitlines()
    require(compatibility_rows and compatibility_rows[0] == row(install[PREFIX + LIBRARY], LIBRARY),
            "Archived compatibility first row does not pin its UI library")
    require(len(compatibility_rows) == 10, "Unexpected vendor compatibility pin count")
    compatibility = replace_manifest_row(old_compatibility, compatibility_rows[0], row(binary, LIBRARY), "UI library")
    require(compatibility.splitlines()[1:] == compatibility_rows[1:], "Vendor compatibility pins changed")

    template = (UI / "src/run-ui.sh.in").read_bytes()
    require(template.count(b"@MANIFEST_CHECK@") == 1, "Expected one compatibility placeholder in the UI wrapper")
    wrapper = template.replace(b"@MANIFEST_CHECK@", crc_length(compatibility).encode("ascii"))
    old_runner = rollback[PREFIX + RUNNER]
    stock_launch = b"MsnCoreApp -qws 2>&1 | /bin/sh /usr/bin/p401-log-stream.sh core"
    require(old_runner.count(stock_launch) == 1, "Exact baseline launch command is missing or ambiguous")
    replacement = (b'if "$helper" verify /data/carplay-revival/run-ui.sh ' + crc_length(wrapper).encode() + b'; then\n'
                   b'    /bin/sh /data/carplay-revival/run-ui.sh 2>&1 | /bin/sh /usr/bin/p401-log-stream.sh core\n'
                   b'else\n    ' + stock_launch + b'\nfi')
    runner = old_runner.replace(stock_launch, replacement)
    old_manifest = rollback[PREFIX + W3_MANIFEST]
    manifest = replace_manifest_row(old_manifest, row(old_runner, RUNNER), row(runner, RUNNER), "W3 runner")
    require([(a, b) for a, b in zip(old_manifest.splitlines(), manifest.splitlines()) if a != b]
            == [(row(old_runner, RUNNER), row(runner, RUNNER))], "Only the GUI runner row may change in the W3 manifest")
    files = {PREFIX + LIBRARY: binary, PREFIX + COMPATIBILITY: compatibility, PREFIX + WRAPPER: wrapper,
             PREFIX + STATE: b"enabled\n", PREFIX + RUNNER: runner, PREFIX + W3_MANIFEST: manifest}
    require(set(files) == {PREFIX + path for path in INSTALL_PATHS}, "Candidate must contain exactly six files")
    installer = zip_install(files)
    snapshot = source_snapshot()
    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    report = {
        "revision": "ui1-cloud-candidate",
        "status": "Experimental native PC-validated candidate; physical radio naming and reboot untested",
        "baseline": "Development R1 + field W3 startup layout; not standalone public RC1",
        "baseline_commit": BASELINE_COMMIT,
        "checkout_head": current_head,
        "library_sha256": binary_sha256,
        "published": False,
        "packager": {"file": Path(__file__).relative_to(REPO).as_posix(), **description(Path(__file__).read_bytes())},
        "native_evidence": {"file": "NATIVE_EVIDENCE.json", **description(evidence_bytes)},
        "source_snapshot": snapshot,
        "packages": [package_metadata("INSTALL.zip", installer), package_metadata("ROLLBACK.zip", rollback_archive)],
        "rollback_note": "Exact archived rollback ZIP copied unchanged, restoring the prior W3 GUI runner and manifest.",
        "hardware_radio_tested": False,
        "physical_reboot_tested": False,
        "flash_backup": False,
        "full_flash_restore_available": False,
        "warning": "Does not back up firmware. Rollback requires a booting box accepting autocopy; no bricked-unit recovery is offered.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ui1-candidate-", dir=output.parent) as temporary:
        stage = Path(temporary)
        contents = {"INSTALL.zip": installer, "ROLLBACK.zip": rollback_archive,
                    "NATIVE_EVIDENCE.json": evidence_bytes,
                    "MANIFEST.json": (json.dumps(report, indent=2) + "\n").encode(),
                    OUTPUT_MARKER: b"p401-ui1-candidate-v1\n"}
        for name, data in contents.items():
            (stage / name).write_bytes(data)
        output.mkdir(exist_ok=replace)
        for name in sorted(contents):
            os.replace(stage / name, output / name)
    return {"output": str(output), "library_sha256": binary_sha256,
            "source_tree_sha256": snapshot["sha256"], "packages": report["packages"],
            "native_evidence_sha256": sha256(evidence_bytes), "hardware_radio_tested": False,
            "physical_reboot_tested": False, "published": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=UI / "build/libp401-ui.so")
    parser.add_argument("--evidence", type=Path, required=True, help="Fresh native JSON report for this exact ARM library")
    parser.add_argument("--output", type=Path, default=UI / "build/cloud/candidate")
    parser.add_argument("--replace", action="store_true", help="Replace only a directory previously generated by this tool")
    args = parser.parse_args()
    try:
        report = build_candidate(args.binary.resolve(), args.evidence.resolve(), args.output.absolute(), args.replace)
    except (ValueError, OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Candidate packaging refused: {error}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
