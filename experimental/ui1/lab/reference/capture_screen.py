"""Encode actual emulated framebuffer bytes as PNG; no drawing or mock screen."""
from pathlib import Path
import struct, zlib

def png_from_bgra(data, width=800, height=480):
    assert len(data) == width * height * 4
    rgb = bytearray(width * height * 3)
    rgb[0::3] = data[2::4]
    rgb[1::3] = data[1::4]
    rgb[2::3] = data[0::4]
    scan = b''.join(b'\x00' + rgb[y * width * 3:(y+1) * width * 3] for y in range(height))
    def chunk(kind, payload):
        return struct.pack('!I', len(payload)) + kind + payload + struct.pack('!I', zlib.crc32(kind + payload))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(scan, 3)) + chunk(b'IEND', b'')

if __name__ == '__main__':
    work = Path(__file__).resolve().parent
    data = (work / 'framebuffer.bgra').read_bytes()
    (work / 'screen.png').write_bytes(png_from_bgra(data))
    print('Framebuffer bytes:', len(data), 'nonzero bytes:', sum(v != 0 for v in data))
