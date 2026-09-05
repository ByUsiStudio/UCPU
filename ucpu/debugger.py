"""调试器: 条件断点、执行历史(前进/后退)、TCP 远程调试服务。"""

import socket
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

from .console import Colors

if TYPE_CHECKING:
    from .cpu import CPU


@dataclass
class ConditionalBreakpoint:
    address: int
    condition: str
    count: int = 0
    hit_count: int = 0
    enabled: bool = True


class DebugServer:
    def __init__(self, cpu: 'CPU', port: int = 1234):
        self.cpu = cpu
        self.port = port
        self.socket = None
        self.connected = False
        self.running = False
        self.execution_history: List[Dict] = []
        self.history_limit = 1000
        self.history_index = 0
        self.conditional_breakpoints: List[ConditionalBreakpoint] = []

    # ---------------- 历史记录 ----------------

    def record_state(self) -> None:
        snapshot = {
            'pc': self.cpu.pc,
            'regs': self.cpu.regs.get_all(),
            'sp': self.cpu.sp,
            'pstate': self.cpu.pstate.copy(),
            'timestamp': time.time(),
        }
        self.execution_history.append(snapshot)
        if len(self.execution_history) > self.history_limit:
            self.execution_history.pop(0)
        self.history_index = len(self.execution_history) - 1

    def _restore(self, snapshot: Dict) -> None:
        self.cpu.pc = snapshot['pc']
        self.cpu.regs.set_all(snapshot['regs'])
        self.cpu.sp = snapshot['sp']
        self.cpu.pstate = snapshot['pstate'].copy()

    def reverse_step(self) -> bool:
        if self.history_index > 0:
            self.history_index -= 1
            self._restore(self.execution_history[self.history_index])
            return True
        return False

    def forward_step(self) -> bool:
        if self.history_index < len(self.execution_history) - 1:
            self.history_index += 1
            self._restore(self.execution_history[self.history_index])
            return True
        return False

    # ---------------- 条件断点 ----------------

    def add_conditional_breakpoint(self, address: int, condition: str) -> None:
        bp = ConditionalBreakpoint(address=address, condition=condition)
        self.conditional_breakpoints.append(bp)
        self.cpu.breakpoints.add(address)
        self.cpu.logger.info(f"Conditional breakpoint set at PC={address:#x}: {condition}")

    def check_conditional_breakpoints(self) -> bool:
        for bp in self.conditional_breakpoints:
            if bp.address == self.cpu.pc and bp.enabled:
                try:
                    namespace = {
                        'regs': self.cpu.regs.get_all(),
                        'pc': self.cpu.pc,
                        'sp': self.cpu.sp,
                        'pstate': self.cpu.pstate.copy(),
                    }
                    if eval(bp.condition, {"__builtins__": {}}, namespace):
                        bp.hit_count += 1
                        self.cpu.console.print(
                            f"{Colors.colorize('Conditional breakpoint hit', Colors.YELLOW)} "
                            f"at PC={self.cpu.pc:#x}: {bp.condition}")
                        return True
                except Exception as e:
                    self.cpu.logger.warning(f"Condition evaluation failed: {e}")
        return False

    # ---------------- TCP 服务 ----------------

    def start(self) -> None:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('localhost', self.port))
            self.socket.listen(1)
            self.cpu.logger.info(f"Debug server listening on port {self.port}")
            self.running = True
            while self.running:
                conn, addr = self.socket.accept()
                self.connected = True
                self.cpu.logger.info(f"Debug client connected from {addr}")
                self._handle_connection(conn)
        except Exception as e:
            self.cpu.logger.error(f"Debug server error: {e}")

    def _handle_connection(self, conn) -> None:
        try:
            while self.running:
                data = conn.recv(1024)
                if not data:
                    break
                response = self._process_command(data)
                if response:
                    conn.send(response.encode())
        except Exception as e:
            self.cpu.logger.debug(f"Debug connection error: {e}")
        finally:
            conn.close()
            self.connected = False

    def _process_command(self, data: bytes) -> str:
        cmd = data.decode().strip()
        parts = cmd.split()
        if not parts:
            return "ERROR: Empty command"
        command = parts[0].lower()

        if command == 'step':
            self.record_state()
            self.cpu.step()
            return "OK: Stepped"
        elif command == 'continue':
            self.cpu.running = True
            return "OK: Continuing"
        elif command == 'reverse':
            return "OK: Reversed" if self.reverse_step() else "ERROR: No history"
        elif command == 'forward':
            return "OK: Forwarded" if self.forward_step() else "ERROR: No history"
        elif command == 'break':
            if len(parts) > 1:
                try:
                    addr = int(parts[1], 0)
                    if len(parts) > 2:
                        cond = ' '.join(parts[2:])
                        self.add_conditional_breakpoint(addr, cond)
                        return f"OK: Conditional breakpoint at {addr:#x}: {cond}"
                    self.cpu.add_breakpoint(addr)
                    return f"OK: Breakpoint at {addr:#x}"
                except ValueError:
                    return "ERROR: Invalid address"
            return "ERROR: Missing address"
        elif command == 'delete':
            if len(parts) > 1:
                try:
                    addr = int(parts[1], 0)
                    self.cpu.remove_breakpoint(addr)
                    self.conditional_breakpoints = [
                        bp for bp in self.conditional_breakpoints if bp.address != addr]
                    return f"OK: Removed breakpoint at {addr:#x}"
                except ValueError:
                    return "ERROR: Invalid address"
            return "ERROR: Missing address"
        elif command == 'watch':
            if len(parts) > 1:
                try:
                    addr = int(parts[1], 0)
                    access = parts[2] if len(parts) > 2 else 'rw'
                    self.cpu.memory.set_protection(addr, access)
                    return f"OK: Watchpoint at {addr:#x} for {access}"
                except ValueError:
                    return "ERROR: Invalid address"
            return "ERROR: Missing address"
        elif command == 'regs':
            return str(self.cpu.regs.get_all())
        elif command == 'pc':
            return f"PC: {self.cpu.pc:#x}"
        elif command == 'mem':
            if len(parts) > 1:
                try:
                    addr = int(parts[1], 0)
                    if len(parts) > 2:
                        value = int(parts[2], 0)
                        self.cpu.memory.write_byte(addr, value)
                        return f"OK: mem[{addr:#x}] = {value:#x}"
                    value = self.cpu.memory.read_byte(addr)
                    return f"mem[{addr:#x}] = {value:#x}"
                except ValueError:
                    return "ERROR: Invalid address or value"
            return "ERROR: Missing address"
        elif command == 'history':
            if len(parts) > 1 and parts[1] == 'clear':
                self.execution_history.clear()
                self.history_index = 0
                return "OK: History cleared"
            return f"OK: History size: {len(self.execution_history)}, index: {self.history_index}"
        elif command == 'info':
            if len(parts) > 1:
                if parts[1] == 'break':
                    lines = ["Breakpoints:"]
                    for bp in self.cpu.breakpoints:
                        lines.append(f"  {bp:#x}")
                    for bp in self.conditional_breakpoints:
                        lines.append(f"  {bp.address:#x} (cond: {bp.condition})")
                    return "\n".join(lines)
                elif parts[1] == 'regs':
                    return str(self.cpu.regs.get_all())
                elif parts[1] == 'pc':
                    return f"PC: {self.cpu.pc:#x}"
            return "ERROR: Missing info target"
        elif command == 'quit':
            self.running = False
            return "OK: Quitting"
        return f"ERROR: Unknown command: {command}"
