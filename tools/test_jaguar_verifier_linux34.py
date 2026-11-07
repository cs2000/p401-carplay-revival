#!/usr/bin/env python3
"""Prove the unchanged verifier's statx ENOSYS -> fstat64 fallback in ARM QEMU.

Run: python tools/test_jaguar_verifier_linux34.py
Uses the offline local toolchain and private container networking. It changes
only QEMU guest registers and writes an ignored JSON report; no image is rebuilt.
This checks one old-kernel fallback, not an entire Linux 3.4 kernel/device boot.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import struct
import subprocess
import sys
import time
import zlib


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Gdb:
    def __init__(self, channel):
        self.channel = channel
        channel.settimeout(20)

    def receive(self, size):
        result = bytearray()
        while len(result) < size:
            chunk = self.channel.recv(size - len(result))
            if not chunk:
                raise RuntimeError("GDB connection closed before reply")
            result.extend(chunk)
        return bytes(result)

    def command(self, text):
        payload = text.encode()
        self.channel.sendall(b"$" + payload + b"#" + f"{sum(payload) & 255:02x}".encode())
        while self.receive(1) != b"$":
            pass
        reply = bytearray()
        while True:
            char = self.receive(1)
            if char == b"#":
                break
            reply.extend(char)
        assert int(self.receive(2), 16) == sum(reply) & 255
        self.channel.sendall(b"+")
        return reply.decode()


def thumb_syscalls(binary):
    image = binary.read_bytes()
    assert image[:6] == b"\x7fELF\x01\x01", "Expected little-endian ELF32"
    assert struct.unpack_from("<H", image, 18)[0] == 40, "Expected ARM"
    phoff = struct.unpack_from("<I", image, 28)[0]
    phsize, phcount = struct.unpack_from("<HH", image, 42)
    points = []
    for index in range(phcount):
        kind, offset, address, _, size, _, flags, _ = struct.unpack_from("<8I", image, phoff + index * phsize)
        if kind == 1 and flags & 1:
            for step in range(0, size - 1, 2):
                if image[offset + step:offset + step + 2] == b"\x00\xdf":
                    points.append(address + step)
    assert points, "No executable Thumb SVC instructions found"
    return points


def check(binary, path):
    assert path.is_symlink(), "Use the actual vendor SONAME aliases"
    contents = path.read_bytes()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    command = ["qemu-arm", "-g", str(port), "-strace", str(binary), "verify", str(path),
               f"{zlib.crc32(contents):08x}", str(len(contents))]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                channel = socket.create_connection(("127.0.0.1", port), timeout=1)
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise
                time.sleep(0.05)
        with channel:
            gdb = Gdb(channel)
            assert "QCatchSyscalls+" in gdb.command("qSupported")
            points = thumb_syscalls(binary)
            for point in points:
                assert gdb.command(f"Z0,{point:x},2") == "OK"
            injected = []
            syscalls = []
            finished = gdb.command("c")
            while not finished.startswith("W"):
                assert len(syscalls) < 128, "Too many stops before statx"
                assert finished.startswith("T05"), finished
                pc = int.from_bytes(bytes.fromhex(gdb.command("pf")), "little")
                number = int.from_bytes(bytes.fromhex(gdb.command("p7")), "little")
                assert pc in points, (pc, finished)
                syscalls.append(number)
                if number == 397:  # ARM statx; absent on Linux 3.4.
                    assert gdb.command(f"m{pc:x},2") == "00df"
                    assert gdb.command("P0=daffffff") == "OK"  # r0 = -ENOSYS (-38).
                    assert gdb.command("Pf=" + (pc + 2).to_bytes(4, "little").hex()) == "OK"
                    injected.append({"instruction_address": hex(pc), "syscall": number,
                                     "result_r0": gdb.command("p0"), "next_pc": gdb.command("pf")})
                    assert injected[-1]["result_r0"] == "daffffff"
                    for point in points:
                        assert gdb.command(f"z0,{point:x},2") == "OK"
                    assert gdb.command("QCatchSyscalls:1;c5") == "OK"
                    fallback_entry = gdb.command("c")
                    assert "syscall_entry:c5" in fallback_entry, fallback_entry
                    syscalls.append(197)  # ARM legacy fstat64.
                    fallback_return = gdb.command("c")
                    assert "syscall_return:c5" in fallback_return, fallback_return
                    injected[-1].update(fallback_entry=fallback_entry, fallback_return=fallback_return)
                    assert gdb.command("QCatchSyscalls:0") == "OK"
                    finished = gdb.command("c")
                else:
                    assert gdb.command(f"z0,{pc:x},2") == "OK"
                    finished = gdb.command("s")
                    if not finished.startswith("W"):
                        assert gdb.command(f"Z0,{pc:x},2") == "OK"
                        finished = gdb.command("c")
            assert finished.startswith("W00"), finished
        stdout, stderr = process.communicate(timeout=10)
        trace = stderr.decode()
        assert process.returncode == 0, trace
        assert not stdout
        assert injected and 197 in syscalls, (injected, syscalls)
        assert any("fstat64(" in row and row.endswith(" = 0") for row in trace.splitlines()), trace
        assert " statx(" not in trace, "Target statx must be skipped, not executed"
        assert " write(" not in trace and " socket(" not in trace
        return {"path": path.name, "bytes": len(contents), "crc32": f"{zlib.crc32(contents):08x}",
                "symlink": str(path.readlink()), "injected_syscalls": injected,
                "observed_syscall_numbers": sorted(set(syscalls)),
                "syscall_trace_without_reads": [row for row in trace.splitlines() if " read(" not in row],
                "exit_code": process.returncode, "passed": True}
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=repo / "build/jaguar/verifier/verify")
    parser.add_argument("--vendor-root", type=Path, default=repo / "experimental/ui1/build/cloud/vendor-root")
    parser.add_argument("--output", type=Path, default=repo / "build/jaguar/verifier/LINUX34.json")
    parser.add_argument("--image", default="p401-ui-toolchain:local")
    parser.add_argument("--in-container", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.in_container:
        results = [check(args.binary, args.vendor_root / rel)
                   for rel in ("lib/libc.so.6", "lib/libstdc++.so.6")]
        summary = {
            "binary_sha256": sha(args.binary), "source_sha256": sha(repo / "firmware/jaguar/verify.c"),
            "test_script": "tools/test_jaguar_verifier_linux34.py", "test_script_sha256": sha(Path(__file__)),
            "method": "Private offline QEMU GDB breakpoints stop immediately before Thumb SVC. For target ARM statx (397), skip the SVC and set r0 to -ENOSYS (-38). The unchanged musl wrapper then executes legacy fstat64 (197) successfully. No host or container-wide syscall policy change.",
            "checks": results, "all_passed": True, "vehicle_tested": False,
            "qemu": subprocess.check_output(["qemu-arm", "--version"], text=True).splitlines()[0],
            "limitation": "Proves the statx ENOSYS fallback; does not emulate the complete Linux 3.4 kernel or a physical device boot."
        }
        args.output.write_text(json.dumps(summary, indent=2) + "\n")
        print("Passed both vendor ABI symlink checks with statx ENOSYS and actual fstat64 fallback.")
        return
    binary, vendor, output = args.binary.resolve(), args.vendor_root.resolve(), args.output.absolute()
    assert binary.is_file() and vendor.is_dir()
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        environment.pop(key, None)
    docker = [shutil.which("docker") or "docker", "--host=unix:///var/run/docker.sock"]
    image_id = subprocess.check_output([*docker, "image", "inspect", "--format={{.Id}}", args.image],
                                       env=environment, text=True).strip()
    subprocess.run([*docker, "run", "--rm", "--network=none", "--cap-drop=ALL",
                    "--security-opt=no-new-privileges", "--user", f"{os.getuid()}:{os.getgid()}",
                    "--mount", f"type=bind,src={repo},dst=/repo,readonly",
                    "--mount", f"type=bind,src={binary},dst=/verifier/verify,readonly",
                    "--mount", f"type=bind,src={vendor},dst=/vendor-root,readonly",
                    "--mount", f"type=bind,src={output.parent},dst=/results",
                    args.image, "python3", "/repo/tools/test_jaguar_verifier_linux34.py",
                    "--in-container", "--binary", "/verifier/verify", "--vendor-root", "/vendor-root",
                    "--output", "/results/" + output.name], env=environment, check=True)
    summary = json.loads(output.read_text())
    summary.update(toolchain_image=args.image, toolchain_image_id=image_id,
                   reproduce=shlex.join(["python", "tools/test_jaguar_verifier_linux34.py", *sys.argv[1:]]))
    output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({key: summary[key] for key in ("binary_sha256", "test_script_sha256", "all_passed")}))


if __name__ == "__main__":
    main()
