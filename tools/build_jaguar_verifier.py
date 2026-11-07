#!/usr/bin/env python3
"""Build/test the read-only ARM verifier in the offline local musl toolchain.

From the repository root: python tools/build_jaguar_verifier.py
Output: ignored build/jaguar/verifier/verify and BUILD.json. No UI is rebuilt.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zlib


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, **kwargs):
    return subprocess.run([str(part) for part in argv], check=True,
                          capture_output=True, text=True, **kwargs).stdout.strip()


def test(binary, output):
    """Run actual ARM machine code; all fixtures are isolated regular files."""
    results = []
    with tempfile.TemporaryDirectory(prefix="test-", dir=output) as temporary:
        fixtures = Path(temporary)
        empty = fixtures / "empty"
        vector = fixtures / "vector"
        large = fixtures / "large"
        corrupt = fixtures / "corrupt"
        truncated = fixtures / "truncated"
        empty.write_bytes(b"")
        vector.write_bytes(b"123456789")
        payload = bytes(range(256)) * 4096 + b"tail\x00\xff"
        large.write_bytes(payload)
        corrupt.write_bytes(payload[:517] + bytes([payload[517] ^ 1]) + payload[518:])
        truncated.write_bytes(payload[:-1])
        alias = fixtures / "alias"
        alias.symlink_to(vector.name)
        dangling = fixtures / "dangling"
        dangling.symlink_to("missing")
        fifo = fixtures / "fifo"
        os.mkfifo(fifo)
        expected_crc = f"{zlib.crc32(payload):08x}"
        before = {p.name: sha(p) for p in (empty, vector, large, corrupt, truncated)}

        def case(name, args, expected):
            process = subprocess.run(["qemu-arm", str(binary), *map(str, args)],
                                     capture_output=True, timeout=10)
            if process.returncode != expected or process.stdout or process.stderr:
                raise AssertionError(f"{name}: exit={process.returncode}, expected={expected}, "
                                     f"stdout={process.stdout!r}, stderr={process.stderr!r}")
            results.append({"case": name, "passed": True, "exit_code": process.returncode})

        case("empty IEEE vector", ["verify", empty, "00000000", "0"], 0)
        case("123456789 IEEE vector", ["verify", vector, "cbf43926", "9"], 0)
        case("uppercase CRC", ["verify", vector, "CBF43926", "9"], 0)
        case("large binary and partial read block", ["verify", large, expected_crc, len(payload)], 0)
        case("relative symlink followed", ["verify", alias, "cbf43926", "9"], 0)
        case("one-byte corruption", ["verify", corrupt, expected_crc, len(payload)], 1)
        case("truncation", ["verify", truncated, expected_crc, len(payload)], 1)
        case("wrong CRC", ["verify", vector, "cbf43927", "9"], 1)
        case("short expected length", ["verify", vector, "cbf43926", "8"], 1)
        case("long expected length", ["verify", vector, "cbf43926", "10"], 1)
        case("missing file", ["verify", fixtures / "absent", "00000000", "0"], 1)
        case("dangling symlink", ["verify", dangling, "00000000", "0"], 1)
        case("directory rejected", ["verify", fixtures, "00000000", "0"], 1)
        case("FIFO rejected without blocking", ["verify", fifo, "00000000", "0"], 1)
        case("maximum uint64 parsed safely", ["verify", vector, "cbf43926", "18446744073709551615"], 1)
        for value in ("", "cbf4392", "cbf439266", "0xcbf43926", "cbf4392g", " cbf43926", "cbf43926 "):
            case("malformed CRC " + repr(value), ["verify", vector, value, "9"], 2)
        for value in ("", "-1", "+9", " 9", "9 ", "9x", "0x9", "18446744073709551616"):
            case("malformed length " + repr(value), ["verify", vector, "cbf43926", value], 2)
        for args in ([], ["verify"], ["verify", vector, "cbf43926"],
                     ["same", vector, "cbf43926", "9"],
                     ["verify", vector, "cbf43926", "9", "extra"]):
            case("bad arguments " + repr(list(map(str, args))), args, 2)
        after = {p.name: sha(p) for p in (empty, vector, large, corrupt, truncated)}
        if before != after:
            raise AssertionError("verifier changed a fixture")
        results.append({"case": "input contents unchanged", "passed": True})
    return results


def build(output):
    repo = Path(__file__).resolve().parents[1]
    source = repo / "firmware/jaguar/verify.c"
    output.mkdir(parents=True, exist_ok=True)
    musl = Path("/usr/lib/arm-linux-musleabihf")
    command = ["clang-19", "--target=armv7a-linux-musleabihf", "-march=armv7-a",
               "-marm", "-mfpu=vfpv3-d16", "-mfloat-abi=hard", "-Os", "-std=c99",
               "-Wall", "-Wextra", "-Werror", "-Wconversion", "-Wshadow",
               "-fno-ident", "-fno-stack-protector", "-ffunction-sections", "-fdata-sections",
               "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-nostdinc",
               "-isystem", "/usr/include/arm-linux-musleabihf", "-D_GNU_SOURCE",
               "-nostdlib", "-static", "-fuse-ld=lld", "-Wl,--build-id=none",
               "-Wl,--gc-sections", "-Wl,-z,noexecstack", "-Wl,-s",
               str(musl / "crt1.o"), str(musl / "crti.o"), str(source),
               "-L" + str(musl), "-lc", str(musl / "crtn.o")]
    binary = output / "verify"
    run([*command, "-o", binary])
    binary.chmod(0o755)
    # Compile twice independently to verify byte reproducibility here.
    with tempfile.TemporaryDirectory(prefix="repeat-", dir=output) as temporary:
        repeated = Path(temporary) / "verify"
        run([*command, "-o", repeated])
        if binary.read_bytes() != repeated.read_bytes():
            raise AssertionError("repeated verifier build is not byte-identical")
    header = run(["readelf", "-h", binary])
    program = run(["readelf", "-l", binary])
    dynamic = run(["readelf", "-d", binary])
    if "ARM" not in header or "hard-float ABI" not in header or "INTERP" in program or "NEEDED" in dynamic:
        raise AssertionError("verifier must be a static ARM hard-float ELF with no interpreter")
    tests = test(binary, output)
    summary = {
        "source": "firmware/jaguar/verify.c", "source_sha256": sha(source),
        "binary": "verify", "binary_sha256": sha(binary), "binary_bytes": binary.stat().st_size,
        "compiler": run(["clang-19", "--version"]).splitlines()[0],
        "qemu": run(["qemu-arm", "--version"]).splitlines()[0],
        "compile_command": [*command, "-o", str(binary)],
        "readelf_header": header, "readelf_program_headers": program,
        "readelf_dynamic": dynamic, "repeated_build_identical": True,
        "arm_qemu_tests": tests, "vehicle_tested": False,
        "interface": "verify verify FILE CRCHEX LENGTH",
        "purpose": "Read-only CRC32 and length guard; no authentication or device services."
    }
    (output / "BUILD.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({key: summary[key] for key in ("binary_sha256", "binary_bytes", "source_sha256")}))
    print(f"Passed {len(tests)} ARM QEMU checks; repeated build is byte-identical.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="p401-ui-toolchain:local")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--in-container", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    output = (args.output or repo / "build/jaguar/verifier").absolute()
    if args.in_container:
        build(output)
        return
    output.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        environment.pop(key, None)
    docker = [shutil.which("docker") or "docker", "--host=unix:///var/run/docker.sock"]
    image_id = run([*docker, "image", "inspect", "--format={{.Id}}", args.image], env=environment)
    process = subprocess.run([*docker, "run", "--rm", "--network=none", "--cap-drop=ALL",
                              "--security-opt=no-new-privileges", "--user", f"{os.getuid()}:{os.getgid()}",
                              "--mount", f"type=bind,src={repo},dst=/repo,readonly",
                              "--mount", f"type=bind,src={output},dst=/output",
                              args.image, "python3", "/repo/tools/build_jaguar_verifier.py",
                              "--in-container", "--output", "/output"], env=environment)
    if process.returncode:
        raise SystemExit(process.returncode)
    summary_path = output / "BUILD.json"
    summary = json.loads(summary_path.read_text())
    summary.update(toolchain_image=args.image, toolchain_image_id=image_id,
                   reproduce="python tools/build_jaguar_verifier.py")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
