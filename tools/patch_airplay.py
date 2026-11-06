"""Apply the two-byte W3 fix only to the exact, identified vendor library."""
from pathlib import Path
import argparse
import hashlib

ORIGINAL = 'f86ec8573bf9a1dbd1526b8e99a5e6ff503a4191fd5f9d0024518f7fc4110716'
PATCHED = '551112f2b5e525a0ff4994357ee1563c5d1e1dad56f59df6724962a0be8e34db'
OFFSET = 0x244b4

def patch(data):
    if hashlib.sha256(data).hexdigest() != ORIGINAL:
        raise ValueError('Unsupported library: original SHA256 does not match')
    if data[OFFSET:OFFSET+4] != bytes.fromhex('411fa013'):
        raise ValueError('Unexpected ARM instruction')
    result = data[:OFFSET] + bytes.fromhex('0410a013') + data[OFFSET+4:]
    assert hashlib.sha256(result).hexdigest() == PATCHED
    assert sum(a != b for a, b in zip(data, result)) == 2
    return result

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    result = patch(args.input.read_bytes())
    with args.output.open('xb') as f:
        f.write(result)
    print(PATCHED)
