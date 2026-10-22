#!/usr/bin/env python3
"""Pads the ROM, writes the ROM end address and checksum into the header."""
import struct
import sys

path = sys.argv[1]
data = bytearray(open(path, "rb").read())
size = 0x20000
while size < len(data):
    size *= 2
data += b"\xff" * (size - len(data))
struct.pack_into(">I", data, 0x1A4, size - 1)
csum = 0
for i in range(0x200, size, 2):
    csum = (csum + (data[i] << 8 | data[i + 1])) & 0xFFFF
struct.pack_into(">H", data, 0x18E, csum)
open(path, "wb").write(data)
print(f"{path}: {size // 1024} KB, checksum {csum:04X}")
