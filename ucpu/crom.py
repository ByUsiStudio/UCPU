"""CROM 内存镜像 (v3: zlib 压缩 + CRC32 校验) 与 CPUSA 二进制程序格式。

优先调用 Go 原生库 (ucpu.native) 进行压缩/解压, 无原生库时回退到 zlib。
"""

import os
import struct
import zlib
from typing import TYPE_CHECKING, Optional

from .errors import CPUSimulatorError
from .isa import Constants

if TYPE_CHECKING:
    from .cpu import CPU
    from .logger import Logger
    from .memory import FastMemory

CROM_HEADER_SIZE = 16


def save_crom(memory: 'FastMemory', path: str, compress: bool = True,
              logger: Optional['Logger'] = None) -> None:
    mem_data = bytes(memory.get_snapshot())

    packed = None
    try:
        from . import native
        engine = native.get_engine(logger)
        if engine is not None:
            packed = engine.crom_pack(mem_data, compress)
    except Exception:
        packed = None

    if packed is None:
        flags = 0x01 if compress else 0x00
        payload = zlib.compress(mem_data, level=6) if compress else mem_data
        checksum = zlib.crc32(payload) & 0xFFFFFFFF
        header = (Constants.CROM_MAGIC
                  + struct.pack('<B', Constants.CROM_VERSION)
                  + struct.pack('<I', len(mem_data))
                  + struct.pack('<B', flags)
                  + struct.pack('<I', checksum)
                  + b'\x00\x00')
        packed = header + payload

    with open(path, 'wb') as f:
        f.write(packed)
    if logger:
        logger.info(f".crom saved to {path} ({len(packed)} bytes, "
                    f"compressed={compress})")


def load_crom(memory: 'FastMemory', path: str, logger: Optional['Logger'] = None) -> None:
    with open(path, 'rb') as f:
        data = f.read()

    if len(data) < 8:
        raise CPUSimulatorError(f".crom file too short: {len(data)} bytes")

    if data[:4] != Constants.CROM_MAGIC:
        # 旧版裸格式: 前 4 字节为 mem_size
        mem_size = struct.unpack('<I', data[:4])[0]
        memory.load_bytes(0, data[4:4 + mem_size])
        if logger:
            logger.info(f"Loaded legacy .crom: {min(mem_size, len(data) - 4)} bytes")
        return

    version = data[4]
    if version != Constants.CROM_VERSION:
        raise CPUSimulatorError(f"Unsupported .crom version: {version}")
    if len(data) < CROM_HEADER_SIZE:
        raise CPUSimulatorError(".crom header incomplete")

    mem_size = struct.unpack('<I', data[5:9])[0]
    flags = data[9]
    compressed = bool(flags & 0x01)
    checksum = struct.unpack('<I', data[10:14])[0]
    payload = data[CROM_HEADER_SIZE:]

    if zlib.crc32(payload) & 0xFFFFFFFF != checksum:
        raise CPUSimulatorError(".crom checksum mismatch (file corrupted?)")

    if compressed:
        try:
            raw = zlib.decompress(payload)
        except zlib.error as e:
            raise CPUSimulatorError(f"Failed to decompress .crom: {e}")
    else:
        raw = payload

    memory.load_bytes(0, raw[:min(mem_size, len(raw))])
    if logger:
        logger.info(f"Loaded .crom v3: {min(mem_size, len(raw))} bytes, "
                    f"compressed={compressed}")


# ==================== CPUSA 二进制程序 ====================

def save_bin(cpu: 'CPU', path: str, logger: Optional['Logger'] = None) -> None:
    from .native import encode_program
    all_labels = dict(cpu.labels)
    all_labels.update(cpu.data_labels)
    bytecode = encode_program(cpu.instructions, cpu.entry_pc, all_labels)
    mem_image = bytes(cpu.memory.get_snapshot())

    with open(path, 'wb') as f:
        f.write(Constants.MAGIC_NUMBER)                       # 5B
        f.write(struct.pack('<B', Constants.BIN_VERSION))     # 1B
        f.write(struct.pack('<I', len(mem_image)))            # 4B
        f.write(struct.pack('<I', cpu.entry_pc))              # 4B
        f.write(struct.pack('<Q', cpu.sp))                    # 8B
        f.write(struct.pack('<I', len(bytecode)))             # 4B
        f.write(b'\x00' * 8)                                  # 保留
        f.write(mem_image)
        f.write(bytecode)
    if logger:
        logger.info(f"Binary saved to {path} ({len(bytecode)} bytecode bytes)")


def load_bin(cpu: 'CPU', path: str) -> None:
    from .native import decode_program
    with open(path, 'rb') as f:
        magic = f.read(5)
        if magic != Constants.MAGIC_NUMBER:
            raise CPUSimulatorError("Invalid binary file (bad magic)")
        version = struct.unpack('<B', f.read(1))[0]
        if version != Constants.BIN_VERSION:
            raise CPUSimulatorError(f"Unsupported binary version: {version}")
        mem_size = struct.unpack('<I', f.read(4))[0]
        entry = struct.unpack('<I', f.read(4))[0]
        sp = struct.unpack('<Q', f.read(8))[0]
        bc_len = struct.unpack('<I', f.read(4))[0]
        f.read(8)
        mem_image = f.read(mem_size)
        bytecode = f.read(bc_len)

    if len(mem_image) > len(cpu.memory):
        cpu.memory.resize(len(mem_image))
        cpu.config.mem_size = len(mem_image)
    cpu.memory.load_bytes(0, mem_image)
    cpu.instructions, cpu.entry_pc = decode_program(bytecode)
    cpu.pc = entry
    cpu.sp = sp
