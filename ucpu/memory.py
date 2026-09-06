import struct
from typing import Dict, Optional

from .console import Console, Table
from .errors import MemoryAccessError


class FastMemory:
    def __init__(self, size: int = 64 * 1024):
        self._size = size
        self._memory = bytearray(size)
        self._view = memoryview(self._memory)
        self._protection: Dict[int, str] = {}
        # 调试日志钩子 (DEBUG 级别记录每次读写)
        self._log = None

    def attach_logger(self, logger) -> None:
        """挂接日志器, DEBUG 级别下记录所有内存读写。"""
        self._log = logger

    @property
    def _mem_trace(self) -> bool:
        return self._log is not None and self._log.is_debug

    def _trace_mem(self, op: str, addr: int, value, width: int) -> None:
        vs = f"0x{value:x}" if isinstance(value, int) else repr(value)
        self._log.trace(f"  MEM {op:<5} @0x{addr:04x} w={width} value={vs}")

    def __len__(self) -> int:
        return self._size

    @property
    def size(self) -> int:
        return self._size

    def reset(self, size: Optional[int] = None) -> None:
        if size is not None:
            self._size = size
        self._memory = bytearray(self._size)
        self._view = memoryview(self._memory)
        self._protection.clear()

    def resize(self, new_size: int) -> None:
        if new_size <= self._size:
            return
        new_mem = bytearray(new_size)
        new_mem[:self._size] = self._memory
        self._memory = new_mem
        self._view = memoryview(self._memory)
        self._size = new_size

    def set_protection(self, addr: int, perms: str, size: int = 1) -> None:
        for i in range(size):
            self._protection[addr + i] = perms

    def check_access(self, addr: int, access: str) -> bool:
        perm = self._protection.get(addr, 'rwx')
        return access in perm

    def _check_bounds(self, addr: int, size: int = 1) -> None:
        if not 0 <= addr <= self._size - size:
            raise MemoryAccessError(
                f"Address 0x{addr:x} out of bounds (memory size 0x{self._size:x}, "
                f"access width {size})")

    def _check_protection(self, addr: int, access: str) -> None:
        if not self.check_access(addr, access):
            raise MemoryAccessError(
                f"Memory protection violation at 0x{addr:x} for '{access}'")

    def _check_protection_range(self, addr: int, size: int, access: str) -> None:
        """对 [addr, addr+size) 内每个被保护字节做访问检查 (块读写统一入口)。"""
        if not self._protection:
            return
        end = addr + size
        for paddr, perms in self._protection.items():
            if addr <= paddr < end and access not in perms:
                raise MemoryAccessError(
                    f"Memory protection violation at 0x{paddr:x} "
                    f"for '{access}' (range 0x{addr:x}+{size})")

    def read_byte(self, addr: int) -> int:
        self._check_bounds(addr)
        self._check_protection(addr, 'r')
        v = self._view[addr]
        if self._mem_trace:
            self._trace_mem('RD', addr, v, 1)
        return v

    def write_byte(self, addr: int, value: int) -> None:
        self._check_bounds(addr)
        self._check_protection(addr, 'w')
        self._view[addr] = value & 0xFF
        if self._mem_trace:
            self._trace_mem('WR', addr, value & 0xFF, 1)

    def read_word(self, addr: int) -> int:
        self._check_bounds(addr, 2)
        v = struct.unpack_from('<H', self._view, addr)[0]
        if self._mem_trace:
            self._trace_mem('RD', addr, v, 2)
        return v

    def write_word(self, addr: int, value: int) -> None:
        self._check_bounds(addr, 2)
        struct.pack_into('<H', self._view, addr, value & 0xFFFF)
        if self._mem_trace:
            self._trace_mem('WR', addr, value & 0xFFFF, 2)

    def read_dword(self, addr: int) -> int:
        self._check_bounds(addr, 4)
        v = struct.unpack_from('<I', self._view, addr)[0]
        if self._mem_trace:
            self._trace_mem('RD', addr, v, 4)
        return v

    def write_dword(self, addr: int, value: int) -> None:
        self._check_bounds(addr, 4)
        struct.pack_into('<I', self._view, addr, value & 0xFFFFFFFF)
        if self._mem_trace:
            self._trace_mem('WR', addr, value & 0xFFFFFFFF, 4)

    def read_qword(self, addr: int) -> int:
        self._check_bounds(addr, 8)
        v = struct.unpack_from('<Q', self._view, addr)[0]
        if self._mem_trace:
            self._trace_mem('RD', addr, v, 8)
        return v

    def write_qword(self, addr: int, value: int) -> None:
        self._check_bounds(addr, 8)
        struct.pack_into('<Q', self._view, addr, value & 0xFFFFFFFFFFFFFFFF)
        if self._mem_trace:
            self._trace_mem('WR', addr, value & 0xFFFFFFFFFFFFFFFF, 8)

    def read_float(self, addr: int) -> float:
        self._check_bounds(addr, 4)
        self._check_protection(addr, 'r')
        return struct.unpack_from('<f', self._view, addr)[0]

    def write_float(self, addr: int, value: float) -> None:
        self._check_bounds(addr, 4)
        self._check_protection(addr, 'w')
        struct.pack_into('<f', self._view, addr, value)

    def read_double(self, addr: int) -> float:
        self._check_bounds(addr, 8)
        self._check_protection(addr, 'r')
        return struct.unpack_from('<d', self._view, addr)[0]

    def write_double(self, addr: int, value: float) -> None:
        self._check_bounds(addr, 8)
        self._check_protection(addr, 'w')
        struct.pack_into('<d', self._view, addr, value)

    def read_block(self, addr: int, size: int) -> bytes:
        self._check_bounds(addr, size)
        self._check_protection_range(addr, size, 'r')
        return bytes(self._view[addr:addr + size])

    def write_block(self, addr: int, data) -> None:
        size = len(data)
        self._check_bounds(addr, size)
        self._check_protection_range(addr, size, 'w')
        self._view[addr:addr + size] = data

    def read_string(self, addr: int, max_len: int = 4096) -> str:
        chars = []
        for _ in range(max_len):
            b = self.read_byte(addr)
            if b == 0:
                break
            chars.append(b)
            addr += 1
        return bytes(chars).decode('utf-8', errors='replace')

    def write_string(self, addr: int, text: str) -> int:
        data = text.encode('utf-8') + b'\x00'
        self.write_block(addr, data)
        return len(data)

    def load_bytes(self, addr: int, data) -> None:
        self.write_block(addr, bytes(data))

    def get_snapshot(self, start: int = 0, count: int = -1) -> bytes:
        if count < 0:
            count = self._size - start
        return bytes(self._view[start:start + count])

    def display_memory(self, title: str = "Memory Dump", start: int = 0,
                       count: int = 32, console: Optional[Console] = None) -> None:
        if console is None:
            return
        table = Table(title=title)
        table.add_column("Address")
        table.add_column("Hex")
        table.add_column("ASCII")
        table.add_column("Prot")
        end = min(start + count, self._size)
        for i in range(start, end, 16):
            chunk = self._view[i:min(i + 16, end)]
            hex_str = ' '.join(f'{b:02X}' for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            perm = self._protection.get(i, 'rwx')
            table.add_row(f"{i:04X}", hex_str, ascii_str, perm)
        console.print(str(table))
