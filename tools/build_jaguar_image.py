#!/usr/bin/env python3
"""Assemble the Jaguar full image from pinned public RC1 and owner-tested UI1.

Run as root in a disposable Linux build environment. Creates only NEW local
outputs; never opens a flash device. It does not rebuild or re-patch W3/UI1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import struct
import subprocess
import tarfile
import zipfile
import zlib

from build_image import inventory

REPO = Path(__file__).resolve().parents[1]
RELEASE = "2026.11-jaguar-xfr-rc1"
ARCHIVE_NAME = "P401_2026.11_JAGUAR_XFR_RC1.zip"
SOURCE_TAR_SHA = "be982d06fdefbc91229cd9d72081ac47f08ac3dc9733fcfa8aac02af10ee1b56"
BASE_ZIP_SHA = "826592230326d57be22895fc89a1228504a16d45015c5996e5d6cca4c1e02278"
UI_INSTALL_SHA = "3fffedb75dd811ea6a41f0c81f756ced773b41a472420e6ff7f2c038dfead383"
UI_LIBRARY_SHA = "c62c2d49d3ce423d9cf11d96325e7ee5e50d7967ce0a865b2cf6f3a6f6593639"
BASE_FILES = {
    "update": (20, "fd4c7328b55789ea720829f7983ba47ca6342096da4bf9ce2f06136ad667679e"),
    "zImage": (3255848, "04dc369f6fa30443a5c4353467cb5f8994af3a95798824e3f2815d360a46f9fc"),
    "rootfs.img": (99614720, "f0a56487359a94c556fc4bd38026b648b98d6ee55a94ccef8d3512a299537e4d"),
}
UI_ROOT = "usr/libexec/carplay-revival/ui"
HELPER = "usr/libexec/carplay-revival/verify"
LIBRARY = UI_ROOT + "/libp401-ui.so"
MANIFEST = UI_ROOT + "/compatibility.txt"
RUNNER = UI_ROOT + "/run-ui.sh"
W3_PINS = {
    "usr/lib/libAirPlay.so": "551112f2b5e525a0ff4994357ee1563c5d1e1dad56f59df6724962a0be8e34db",
    "usr/libexec/carplay-revival/udhcpd": "bddafb863e3f37da68fc680db389f0c1b4c5fd0468953580f0f4422726c382d7",
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return digest(path.read_bytes())


def description(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": digest(data)}


def crc_length(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xffffffff:08x} {len(data)}"


def manifest_row(path: str, data: bytes) -> bytes:
    return f"{crc_length(data)} /{path}\n".encode("ascii")


def check_elf(data: bytes, *, static: bool) -> None:
    require(len(data) >= 52 and data[:7] == b"\x7fELF\x01\x01\x01", "Expected little-endian ELF32")
    elf_type, machine = struct.unpack_from("<HH", data, 16)
    require(machine == 40 and elf_type in (2, 3), "Expected ARM executable/shared object")
    require(struct.unpack_from("<I", data, 36)[0] & 0x400 != 0, "Expected ARM hard-float ABI")
    if static:
        phoff = struct.unpack_from("<I", data, 28)[0]
        phentsize, phnum = struct.unpack_from("<HH", data, 42)
        require(phentsize >= 32 and phoff + phnum * phentsize <= len(data), "Invalid ELF program headers")
        types = [struct.unpack_from("<I", data, phoff + n * phentsize)[0] for n in range(phnum)]
        require(2 not in types and 3 not in types, "Verifier must be static (no PT_DYNAMIC/PT_INTERP)")


def read_base_zip(path: Path) -> dict[str, bytes]:
    require(sha(path) == BASE_ZIP_SHA, "Base ZIP is not exact public W3 RC1")
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, "Base ZIP CRC failure")
        require(len(archive.namelist()) == 3 and set(archive.namelist()) == set(BASE_FILES), "Unexpected base ZIP contents")
        files = {name: archive.read(name) for name in BASE_FILES}
    for name, data in files.items():
        require((len(data), digest(data)) == BASE_FILES[name], "Base payload pin failed: " + name)
    return files


def read_ui_zip(path: Path) -> tuple[bytes, bytes]:
    require(sha(path) == UI_INSTALL_SHA, "UI installer is not exact owner-tested artifact")
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, "UI ZIP CRC failure")
        library = archive.read("msn_autocopy/data/carplay-revival/lib/libp401-ui.so")
        compatibility = archive.read("msn_autocopy/data/carplay-revival/compatibility.txt")
    require(digest(library) == UI_LIBRARY_SHA, "Owner-tested UI library pin failed")
    check_elf(library, static=False)
    require(len(compatibility.splitlines()) == 10, "Expected library and nine vendor ABI pins")
    require(compatibility.splitlines()[0] == manifest_row("data/carplay-revival/lib/libp401-ui.so", library).strip(), "Unexpected original UI library pin")
    return library, compatibility


def validate_tar(path: Path) -> None:
    require(sha(path) == SOURCE_TAR_SHA, "Use exact metadata-preserving public RC1 extraction")
    with tarfile.open(path) as archive:
        for item in archive:
            rel = PurePosixPath(item.name)
            require(not rel.is_absolute() and ".." not in rel.parts, "Unsafe source tar path")
            require(item.isfile() or item.isdir() or item.issym() or item.islnk(), "Unexpected special source entry")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-tar", type=Path, required=True)
    ap.add_argument("--base-zip", type=Path, default=REPO / "releases/2026.11-w3-rc1/P401_2026.11_W3_RC1.zip")
    ap.add_argument("--ui-install", type=Path, default=REPO / "experimental/ui1/candidates/glass-clock-2026-11-06/INSTALL.zip")
    ap.add_argument("--verifier", type=Path, required=True)
    ap.add_argument("--verifier-evidence", type=Path)
    ap.add_argument("--build-dir", type=Path, required=True)
    args = ap.parse_args()
    require(os.geteuid() == 0, "Linux root is required to preserve vendor ownership and modes")
    source = args.source_tar.resolve()
    base_files = read_base_zip(args.base_zip)
    library, old_compatibility = read_ui_zip(args.ui_install)
    validate_tar(source)
    verifier = args.verifier.read_bytes()
    check_elf(verifier, static=True)
    evidence = None
    if args.verifier_evidence:
        evidence = json.loads(args.verifier_evidence.read_text())
        require(evidence.get("binary_sha256") == digest(verifier) and evidence.get("binary_bytes") == len(verifier),
                "Verifier evidence does not match supplied binary")
        cases = evidence.get("arm_qemu_tests")
        require(isinstance(cases, list) and bool(cases) and all(case.get("passed") is True for case in cases),
                "Verifier ARM QEMU evidence has not passed")
        require(evidence.get("repeated_build_identical") is True, "Verifier repeated build did not match")
        require(evidence.get("source") == "firmware/jaguar/verify.c" and
                evidence.get("source_sha256") == sha(REPO / "firmware/jaguar/verify.c"),
                "Verifier evidence does not match current helper source")
    build = args.build_dir.absolute()
    require(not build.exists() and not build.is_symlink(), "Build directory must be new")
    require(not build.resolve().is_relative_to((REPO / "releases").resolve()), "Use an ignored build directory, not releases")
    templates = {name: (REPO / "firmware/jaguar" / name).read_bytes() for name in ("run-ui.sh.in", "launch-ui.sh.in")}
    require(templates["run-ui.sh.in"].count(b"@MANIFEST_CHECK@") == 1, "Expected one runner manifest placeholder")
    require(templates["launch-ui.sh.in"].count(b"@RUNNER_CHECK@") == 1, "Expected one outer runner placeholder")
    build.mkdir(parents=True)
    root = build / "root"
    root.mkdir()
    commands = []

    def run(argv: list) -> str:
        argv = [str(x) for x in argv]
        result = subprocess.run(argv, capture_output=True, text=True)
        commands.append({"argv": argv, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        (build / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        require(result.returncode == 0, "Command failed: " + " ".join(argv) + "\n" + result.stdout + result.stderr)
        return result.stdout

    run(["tar", "--numeric-owner", "--same-owner", "-xpf", source, "-C", root])
    before = inventory(root)
    for path, expected in W3_PINS.items():
        require(sha(root / path) == expected, "Base W3 content mismatch: " + path)
    for line in old_compatibility.splitlines()[1:]:
        crc, size, path = line.decode("ascii").split()
        data = (root / path.lstrip("/")).read_bytes()
        require(crc_length(data) == crc + " " + size, "Public RC1 differs from tested UI vendor ABI: " + path)

    def install(path: str, data: bytes, mode: int) -> None:
        dest = root / path
        require(not dest.is_symlink(), "Refusing symlink output: " + path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        dest.chmod(mode)
        os.chown(dest, 0, 0)

    install(LIBRARY, library, 0o644)
    install(HELPER, verifier, 0o755)
    compatibility = manifest_row(LIBRARY, library) + b"".join(line + b"\n" for line in old_compatibility.splitlines()[1:]) + manifest_row(HELPER, verifier)
    install(MANIFEST, compatibility, 0o644)
    runner = templates["run-ui.sh.in"].replace(b"@MANIFEST_CHECK@", crc_length(compatibility).encode("ascii"))
    install(RUNNER, runner, 0o755)
    launch = templates["launch-ui.sh.in"].replace(b"@RUNNER_CHECK@", crc_length(runner).encode("ascii"))
    profile_path = root / "etc/profile"
    profile_stat = profile_path.stat()
    profile_before = profile_path.read_bytes()
    marker = b"MsnCoreApp -qws&"
    require(profile_before.count(marker) == 1, "Expected exact public RC1 GUI launch point")
    profile = profile_before.replace(marker, launch.rstrip())
    install("etc/profile", profile, stat.S_IMODE(profile_stat.st_mode))
    os.chown(profile_path, profile_stat.st_uid, profile_stat.st_gid)
    for rel in ("etc/profile", RUNNER):
        run(["/bin/sh", "-n", root / rel])
    for path, expected in W3_PINS.items():
        require(sha(root / path) == expected, "Assembly changed W3: " + path)
    after = inventory(root)
    changes = [{"path": path, "before": before.get(path), "after": after.get(path)}
               for path in sorted(before.keys() | after.keys()) if before.get(path) != after.get(path)]
    allowed = {"etc/profile", HELPER, UI_ROOT, LIBRARY, MANIFEST, RUNNER}
    require(all(row["path"] in allowed for row in changes), "Assembly changed an unexpected rootfs path")
    require(not any(path.startswith("data/") for path in after.keys() - before.keys()), "Do not populate persistent userdata")
    (build / "inventory.json").write_text(json.dumps(after, indent=2) + "\n")
    (build / "changes.json").write_text(json.dumps(changes, indent=2) + "\n")
    image = build / "rootfs.ubifs"
    run(["mkfs.ubifs", "-r", root, "-m", "2048", "-e", "126976", "-c", "848", "-j", "8388608", "-x", "lzo", "-f", "8", "-F", "-k", "r5", "-p", "1", "-l", "5", "-o", image, "-v"])
    size = image.stat().st_size
    require(size % 126976 == 0 and size // 126976 <= 840, "Rootfs exceeds conservative original flash budget")
    config = build / "ubinize.ini"
    config.write_text("[rootfs]\nmode=ubi\nimage=" + str(image) + "\nvol_type=dynamic\nvol_flags=autoresize\nvol_id=0\nvol_name=rootfs\nvol_alignment=1\nvol_size=" + str(size) + "\n")
    run(["ubinize", "-o", build / "rootfs.img", "-p", "131072", "-m", "2048", "-s", "2048", "-O", "2048", "-x", "1", "-Q", "24958429", config])
    require((build / "rootfs.img").stat().st_size < 106 * 1024 * 1024, "Rootfs image exceeds conservative partition budget")
    usb = build / "usb"
    usb.mkdir()
    for name in ("update", "zImage"):
        (usb / name).write_bytes(base_files[name])
    shutil.copyfile(build / "rootfs.img", usb / "rootfs.img")
    archive_path = build / ARCHIVE_NAME
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(BASE_FILES):
            info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (usb / name).read_bytes(), compresslevel=9)
    with zipfile.ZipFile(archive_path) as archive:
        require(archive.testzip() is None and len(archive.namelist()) == 3 and set(archive.namelist()) == set(BASE_FILES), "Output ZIP verification failed")
        require(all(archive.read(name) == (usb / name).read_bytes() for name in BASE_FILES), "Output ZIP payload differs")
    source_paths = [Path(__file__), REPO / "tools/build_jaguar_verifier.py",
                    *(REPO / "firmware/jaguar").rglob("*")]
    source_snapshot = {p.relative_to(REPO).as_posix(): description(p.read_bytes()) for p in sorted(source_paths) if p.is_file() and "__pycache__" not in p.parts}
    summary = {
        "release": RELEASE,
        "status": "New full-image candidate; exact W3 and UI components retained; requires independent image validation",
        "base_zip_sha256": BASE_ZIP_SHA, "source_tar_sha256": SOURCE_TAR_SHA,
        "ui_installer_sha256": UI_INSTALL_SHA, "library_sha256": UI_LIBRARY_SHA,
        "verifier": description(verifier), "verifier_build_evidence": evidence,
        "source_snapshot": source_snapshot,
        "rootfs_sha256": sha(build / "rootfs.img"), "rootfs_bytes": (build / "rootfs.img").stat().st_size,
        "ubifs_lebs": size // 126976,
        "usb_files": [{"name": name, **description((usb / name).read_bytes())} for name in sorted(BASE_FILES)],
        "download": {"name": archive_path.name, **description(archive_path.read_bytes())},
        "changed_paths": [row["path"] for row in changes],
        "kernel_and_update_unchanged": True, "w3_components_unchanged": True,
        "owner_tested_ui_binary_unchanged": True, "requires_field_w3_layout": False,
        "settings_migration": False, "mcu_type_forced": False, "device_writes": False,
        "complete_image_vehicle_tested": False, "full_flash_recovery_proven": False,
        "reproducibility": "Repeatable content/metadata assembly; UBIFS timestamps/UUID can change whole-image hashes",
        "versions": {name: run([name, "--version"]).splitlines()[0] for name in ("mkfs.ubifs", "ubinize", "tar")},
    }
    (build / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({key: summary[key] for key in ("release", "rootfs_sha256", "rootfs_bytes", "ubifs_lebs", "changed_paths", "download")}, indent=2))


if __name__ == "__main__":
    main()
