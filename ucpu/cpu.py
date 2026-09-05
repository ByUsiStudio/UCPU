import math
import os
import random
import struct
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from .assembler import Assembler
from .cache import Cache
from .config import Config
from .console import Colors, Console, Panel
from .errors import CPUSimulatorError, ExecutionError
from .isa import Constants, Opcode, Syscall
from .logger import Logger
from .memory import FastMemory
from .registers import RegisterFile, VectorRegisterFile
from .stats import Statistics

Operand = Tuple[Any, ...]
Instruction = Tuple[str, List[Operand]]

MASK64 = 0xFFFFFFFFFFFFFFFF
MASK32 = 0xFFFFFFFF


def _f_to_bits(f: float) -> int:
    return struct.unpack('<Q', struct.pack('<d', f))[0]


def _bits_to_f(b: int) -> float:
    return struct.unpack('<d', struct.pack('<Q', b & MASK64))[0]


def _format_float(v: float) -> str:
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "+Inf" if v > 0 else "-Inf"
    s = repr(v)
    if 'e' not in s and 'E' not in s and '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s or "0"


class CPU:
    def __init__(self, config: Config, filename: Optional[str] = None,
                 crom_file: Optional[str] = None,
                 from_bin: bool = False,
                 console: Optional[Console] = None):

        self.console = console or Console()
        self.config = config
        self.filename = filename

        # debug 模式强制 DEBUG 级别 (超详细日志)
        if config.debug_mode and config.log_level.upper() != 'DEBUG':
            config.log_level = 'DEBUG'
        self.logger = Logger(self.console, config.log_level)
        if config.log_file:
            self.logger.set_log_file(config.log_file)
        # 逐指令超详细追踪开关 (DEBUG 级别启用)
        self._trace = self.logger.is_debug

        self.memory = FastMemory(config.mem_size)
        self.cache = Cache(config.cache_size, config.cache_assoc)
        # 内存访问日志 (DEBUG 级别生效)
        self.memory.attach_logger(self.logger)

        self.regs = RegisterFile(self.console)
        self.vec_regs = VectorRegisterFile()

        self.pstate: Dict[str, bool] = {'N': False, 'Z': False, 'C': False, 'V': False}
        self.pc = 0
        self.sp = (config.mem_size - Constants.STACK_SLOT) & ~0x7
        self.heap_ptr = config.mem_size // 2

        self.logger.dump("CPU 初始化", {
            'memory': f"0x{config.mem_size:x} bytes",
            'cache': f"{config.cache_size} lines x {config.cache_assoc}-way",
            'sp_init': f"0x{self.sp:x}",
            'heap_base': f"0x{self.heap_ptr:x}",
            'native': config.use_native,
            'jit': config.enable_jit,
            'log_level': config.log_level,
        })

        self.instructions: List[Instruction] = []
        self.labels: Dict[str, int] = {}
        self.data_labels: Dict[str, int] = {}
        self.entry_pc = 0

        self.stats = Statistics()
        self.jit = None
        if config.enable_jit and not config.debug_mode and not config.step_mode:
            try:
                from .jit import JITCompiler
                self.jit = JITCompiler(logger=self.logger)
                self.logger.info("JIT compiler enabled")
            except Exception as e:
                self.logger.warning(f"JIT unavailable: {e}")
        self.running = False
        self.is_debugging = False
        self.breakpoints: set = set()
        self.debug_server = None

        self.input_buffer: str = ""
        self._input_pos = 0
        self.output_buffer: List[str] = []
        self._capture_output = False
        self.native_engine = None
        self.native_used = False

        self._sys_buffers = [bytearray(64) for _ in range(8)]
        self._sys_buf_idx = 0
        self._rand = random.Random()

        self._init_dispatch()

        if filename:
            self.load_program(filename, crom_file=crom_file, from_bin=from_bin)

    def load_program(self, filename: str, crom_file: Optional[str] = None,
                     from_bin: bool = False) -> None:
        if not os.path.exists(filename):
            raise CPUSimulatorError(f"File '{filename}' not found")

        ext = os.path.splitext(filename)[1].lower()

        if ext == '.cin':
            from .cin import CINCompiler
            compiler = CINCompiler(self.console, logger=self.logger)
            result = compiler.compile(filename)
            self.instructions = result.instructions
            self.labels = result.labels
            self.data_labels = result.data_labels
            for addr, data in result.data_writes:
                self.memory.write_block(addr, data)
            # pc 0 为 bootstrap (CALL main; HALT), main 标签为函数体入口
            self.entry_pc = 0
            self.pc = 0
            self.logger.info(f"CIN compiled: {len(self.instructions)} instructions")
            return

        if from_bin or ext == '.bin':
            from .native import decode_program
            from . import crom as crom_mod
            crom_mod.load_bin(self, filename)
            self.logger.info(f"Binary loaded: {len(self.instructions)} instructions")
            return

        # .pl / .asm
        if crom_file is None:
            base = os.path.splitext(filename)[0]
            candidate = base + '.crom'
            if os.path.exists(candidate):
                crom_file = candidate
        if crom_file and os.path.exists(crom_file):
            from . import crom as crom_mod
            crom_mod.load_crom(self.memory, crom_file, self.logger)

        asm = Assembler(self.memory, self.console, strict=self.config.strict_mode,
                        logger=self.logger)
        self.instructions, self.labels, self.data_labels = asm.assemble_file(filename)
        self.entry_pc = self.labels.get('main', 0)
        self.pc = self.entry_pc
        self.cache.warmup(self.instructions)
        self.logger.info(f"Assembly successful: {len(self.instructions)} instructions")
        if self.logger.is_debug:
            self.logger.dump("汇编标签表", {name: f"0x{pc:x}"
                                        for name, pc in
                                        sorted(self.labels.items())})
    def _init_dispatch(self) -> None:
        t: Dict[str, Any] = {}
        t['MOV'] = self._op_mov
        t['LOAD'] = self._op_load
        t['STORE'] = self._op_store
        t['ADD'] = self._op_add
        t['SUB'] = self._op_sub
        t['MUL'] = self._op_mul
        t['DIV'] = self._op_div
        t['AND'] = self._op_and
        t['OR'] = self._op_or
        t['XOR'] = self._op_xor
        t['SHL'] = self._op_shl
        t['SHR'] = self._op_shr
        t['INC'] = self._op_inc
        t['DEC'] = self._op_dec
        t['CMP'] = self._op_cmp
        t['JMP'] = self._op_jmp
        t['JZ'] = self._op_jz
        t['JNZ'] = self._op_jnz
        t['JE'] = self._op_je
        t['JL'] = self._op_jl
        t['JG'] = self._op_jg
        t['PUSH'] = self._op_push
        t['POP'] = self._op_pop
        t['CALL'] = self._op_call
        t['RET'] = self._op_ret
        t['IN'] = self._op_in
        t['OUT'] = self._op_out
        t['HALT'] = self._op_halt
        t['ADDS'] = self._op_adds
        t['SUBS'] = self._op_subs
        t['ADDC'] = self._op_addc
        t['SUBC'] = self._op_subc
        t['LSL'] = self._op_lsl
        t['LSR'] = self._op_lsr
        t['ASR'] = self._op_asr
        t['ROR'] = self._op_ror
        t['MVN'] = self._op_mvn
        t['EOR'] = self._op_eor
        t['BIC'] = self._op_bic
        t['ORN'] = self._op_orn
        t['LDR'] = self._op_ldr
        t['STR'] = self._op_str
        t['LDP'] = self._op_ldp
        t['STP'] = self._op_stp
        t['CBZ'] = self._op_cbz
        t['CBNZ'] = self._op_cbnz
        t['TBZ'] = self._op_tbz
        t['TBNZ'] = self._op_tbnz
        t['B'] = self._op_b
        t['BL'] = self._op_bl
        t['BR'] = self._op_br
        t['NOP'] = self._op_nop
        t['WFE'] = self._op_nop
        t['WFI'] = self._op_nop
        t['SEV'] = self._op_nop
        t['CSEL'] = self._op_csel
        t['CSINC'] = self._op_csinc
        t['CSINV'] = self._op_csinv
        t['CSNEG'] = self._op_csneg
        t['SXTB'] = self._op_sxtb
        t['SXTH'] = self._op_sxth
        t['SXTW'] = self._op_sxtw
        t['UXTB'] = self._op_uxtb
        t['UXTH'] = self._op_uxth
        t['CLZ'] = self._op_clz
        t['CLS'] = self._op_cls
        t['RBIT'] = self._op_rbit
        t['REV'] = self._op_rev
        t['FADD'] = self._op_fadd
        t['FSUB'] = self._op_fsub
        t['FMUL'] = self._op_fmul
        t['FDIV'] = self._op_fdiv
        t['FCMP'] = self._op_fcmp
        t['FCVT'] = self._op_fcvt
        t['FABS'] = self._op_fabs
        t['FNEG'] = self._op_fneg
        t['LDRS'] = self._op_ldrs
        t['STRS'] = self._op_strs
        t['VADD'] = self._op_vadd
        t['VSUB'] = self._op_vsub
        t['VMUL'] = self._op_vmul
        t['VDIV'] = self._op_vdiv
        t['VLD1'] = self._op_vld1
        t['VST1'] = self._op_vst1
        t['LB'] = self._op_lb
        t['LH'] = self._op_lh
        t['LW'] = self._op_lw
        t['LD'] = self._op_ld
        t['SB'] = self._op_sb
        t['SH'] = self._op_sh
        t['SW'] = self._op_sw
        t['SD'] = self._op_sd
        t['ADDI'] = self._op_addi
        t['SLTI'] = self._op_slti
        t['SLTIU'] = self._op_sltiu
        t['XORI'] = self._op_xori
        t['ORI'] = self._op_ori
        t['ANDI'] = self._op_andi
        t['SLLI'] = self._op_slli
        t['SRLI'] = self._op_srli
        t['SRAI'] = self._op_srai
        t['BEQ'] = self._op_beq
        t['BNE'] = self._op_bne
        t['BLT'] = self._op_blt
        t['BGE'] = self._op_bge
        t['BLTU'] = self._op_bltu
        t['BGEU'] = self._op_bgeu
        t['JALR'] = self._op_jalr
        t['JAL'] = self._op_jal
        t['LUI'] = self._op_lui
        t['AUIPC'] = self._op_auipc
        t['SYS'] = self._op_sys
        self._dispatch = t

    # ==================== 操作数辅助 ====================

    def _reg(self, n: int) -> int:
        if n == Constants.SP_REG:
            return self.sp & MASK64
        return self.regs.read(n)

    def _set_reg(self, n: int, v: int) -> None:
        v &= MASK64
        if self._trace:
            old = self._reg(n)
            if old != v:
                sv = v if v < (1 << 63) else v - (1 << 64)
                self.logger.trace(f"  R[{n}] {self._fmt_reg(n, old)} -> "
                                  f"0x{v:016x} ({sv})")
        if n == Constants.SP_REG:
            self.sp = v
        else:
            self.regs.write(n, v)

    @staticmethod
    def _fmt_reg(n: int, v: int) -> str:
        return f"0x{v:016x}"

    def _fmt_op_trace(self, op: Operand) -> str:
        """格式化操作数并附带当前值 (超详细追踪)。"""
        kind = op[0]
        try:
            if kind == 'reg':
                n = op[1]
                v = self._reg(n)
                return f"X{n}=0x{v:x}({v if v < (1 << 63) else v - (1 << 64)})"
            if kind == 'imm':
                return f"#{op[1]}"
            if kind == 'mem':
                addr = self._mem_addr(op)
                return (f"[{op[1] if op[1] >= 0 else 'abs'}"
                        f"{op[2]:+d}]@0x{addr:x}"
                        f"=0x{self.memory.read_qword(addr):x}")
            if kind == 'cond':
                return (f"{op[1]}="
                        f"{int(self._condition(op[1]))}"
                        f"{{N={int(self.pstate['N'])} Z={int(self.pstate['Z'])} "
                        f"C={int(self.pstate['C'])} V={int(self.pstate['V'])}}}")
            if kind == 'label':
                return f"{op[1]}->0x{self.labels.get(op[1], -1):x}"
            if kind == 'str':
                return f'"@{op[1]}"'
            if kind == 'float':
                return f"#{op[1]}f"
        except Exception:
            pass
        return self._fmt_operand(op)

    def _trace_flags(self) -> str:
        p = self.pstate
        return (f"N={int(p['N'])} Z={int(p['Z'])} "
                f"C={int(p['C'])} V={int(p['V'])}")

    def _trace_cache(self, addr: int, hit: bool, kind: str) -> None:
        cs = self.cache.get_stats()
        self.logger.trace(
            f"  CACHE {'HIT ' if hit else 'MISS'} {kind} @0x{addr:x} "
            f"(hit_rate={cs['hit_rate'] * 100:.1f}%)")

    def _val(self, op: Operand) -> Union[int, float]:
        kind = op[0]
        if kind == 'reg':
            return self._reg(op[1])
        if kind == 'imm':
            return op[1] & MASK64
        if kind == 'vec':
            return int(self.vec_regs.read_scalar(op[1]))
        if kind == 'veclane':
            return int(self.vec_regs.read_scalar(op[1], op[2]))
        if kind == 'float':
            return op[1]
        if kind == 'mem':
            addr = self._mem_addr(op)
            return self.memory.read_qword(addr)
        if kind == 'cond':
            return 1 if self._condition(op[1]) else 0
        if kind == 'str':
            return op[1]
        if kind == 'label':
            target = self.labels.get(op[1])
            if target is None:
                raise ExecutionError(f"Undefined label: {op[1]}")
            return target
        raise ExecutionError(f"Unsupported operand kind: {kind}")

    def _mem_addr(self, op: Operand) -> int:
        # ('mem', base, off): base == -1 表示绝对地址
        base = op[1] if len(op) > 1 else -1
        off = op[2] if len(op) > 2 else 0
        if isinstance(off, tuple):
            off = self._val(off)
        if base >= 0:
            return (self._reg(base) + off) & MASK64
        return off & MASK64

    def _condition(self, cond: str) -> bool:
        n, z, c, v = (self.pstate['N'], self.pstate['Z'],
                      self.pstate['C'], self.pstate['V'])
        table = {
            'EQ': z, 'NE': not z,
            'CS': c, 'CC': not c,
            'MI': n, 'PL': not n,
            'VS': v, 'VC': not v,
            'HI': c and not z, 'LS': not c or z,
            'GE': n == v, 'LT': n != v,
            'GT': not z and (n == v), 'LE': z or (n != v),
            'AL': True, 'NV': False,
        }
        return table.get(cond.upper(), False)

    def _set_flags_sub(self, a: int, b: int, result: int) -> None:
        a &= MASK64
        b &= MASK64
        result &= MASK64
        sa = a if a < (1 << 63) else a - (1 << 64)
        sb = b if b < (1 << 63) else b - (1 << 64)
        sr = sa - sb
        old = dict(self.pstate)
        self.pstate['Z'] = (result == 0)
        self.pstate['N'] = bool(result & (1 << 63))
        self.pstate['C'] = a >= b            # 无借位
        self.pstate['V'] = (sr > (1 << 63) - 1) or (sr < -(1 << 63))
        if self._trace and old != self.pstate:
            self.logger.trace(f"  FLAGS <- {self._trace_flags()} "
                              f"(a=0x{a:x} b=0x{b:x})")

    def _set_flags_add(self, a: int, b: int, result: int) -> None:
        a &= MASK64
        b &= MASK64
        result &= MASK64
        sa = a if a < (1 << 63) else a - (1 << 64)
        sb = b if b < (1 << 63) else b - (1 << 64)
        ss = sa + sb
        old = dict(self.pstate)
        self.pstate['Z'] = (result == 0)
        self.pstate['N'] = bool(result & (1 << 63))
        self.pstate['C'] = (a + b) > MASK64
        self.pstate['V'] = (ss > (1 << 63) - 1) or (ss < -(1 << 63))
        if self._trace and old != self.pstate:
            self.logger.trace(f"  FLAGS <- {self._trace_flags()} "
                              f"(a=0x{a:x} b=0x{b:x})")

    # ==================== 栈 ====================

    def _push(self, value: int) -> None:
        self.sp = (self.sp - Constants.STACK_SLOT) & MASK64
        if self.sp < self.heap_ptr + 4096:
            raise ExecutionError("Stack overflow (collides with heap)")
        self.memory.write_qword(self.sp, value & MASK64)
        if self._trace:
            self.logger.trace(f"  PUSH @0x{self.sp:x} <- "
                              f"0x{value & MASK64:016x}")

    def _pop(self) -> int:
        if self.sp >= len(self.memory) - Constants.STACK_SLOT:
            raise ExecutionError("Stack underflow")
        value = self.memory.read_qword(self.sp)
        self.sp = (self.sp + Constants.STACK_SLOT) & MASK64
        if self._trace:
            self.logger.trace(f"  POP  @0x{self.sp - 8:x} -> "
                              f"0x{value:016x}")
        return value

    def _check_stack(self) -> None:
        if self.sp < self.heap_ptr + 4096:
            raise ExecutionError("Stack overflow (collides with heap)")

    # ==================== I/O ====================

    def _emit_text(self, text: str) -> None:
        if self._capture_output:
            self.output_buffer.append(text)
        else:
            sys.stdout.write(text)
            sys.stdout.flush()

    def _read_input_int(self) -> int:
        if self._input_pos < len(self.input_buffer):
            end = self.input_buffer.find('\n', self._input_pos)
            if end < 0:
                end = len(self.input_buffer)
            line = self.input_buffer[self._input_pos:end].strip()
            self._input_pos = end + 1
            try:
                return int(line)
            except ValueError:
                return 0
        try:
            return int(input())
        except (ValueError, EOFError):
            return 0

    # ==================== 基础指令 ====================

    def _op_mov(self, args):
        self._set_reg(args[0][1], self._val(args[1]))
        return True

    def _op_load(self, args):
        rd = args[0][1]
        addr = self._mem_addr(args[1]) if args[1][0] == 'mem' else self._val(args[1])
        self.stats.record_memory_read()
        hit = self.cache.read(addr)
        self.stats.record_cache(hit)
        if self._trace:
            self._trace_cache(addr, hit, 'R')
        self._set_reg(rd, self.memory.read_dword(addr))
        return True

    def _op_store(self, args):
        rs = args[0][1]
        addr = self._mem_addr(args[1]) if args[1][0] == 'mem' else self._val(args[1])
        self.stats.record_memory_write()
        hit = self.cache.write(addr)
        self.stats.record_cache(hit)
        if self._trace:
            self._trace_cache(addr, hit, 'W')
        self.memory.write_dword(addr, self._reg(rs))
        return True

    def _op_add(self, args):
        rd = args[0][1]
        self._set_reg(rd, self._reg(rd) + self._val(args[1]))
        return True

    def _op_sub(self, args):
        rd = args[0][1]
        self._set_reg(rd, self._reg(rd) - self._val(args[1]))
        return True

    def _op_mul(self, args):
        rd = args[0][1]
        self._set_reg(rd, self._reg(rd) * self._val(args[1]))
        return True

    def _op_div(self, args):
        rd = args[0][1]
        d = self._val(args[1])
        if d == 0:
            raise ExecutionError("Division by zero")
        a = self._reg(rd)
        self._set_reg(rd, self._sdiv(a, d))
        return True

    @staticmethod
    def _sdiv(a: int, b: int) -> int:
        """有符号 64 位除法。"""
        sa = a if a < (1 << 63) else a - (1 << 64)
        sb = b if b < (1 << 63) else b - (1 << 64)
        q = abs(sa) // abs(sb)
        if (sa < 0) != (sb < 0):
            q = -q
        return q & MASK64

    def _op_and(self, args):
        rd = args[0][1]
        self._set_reg(rd, self._reg(rd) & self._val(args[1]))
        return True

    def _op_or(self, args):
        rd = args[0][1]
        self._set_reg(rd, self._reg(rd) | self._val(args[1]))
        return True

    def _op_xor(self, args):
        rd = args[0][1]
        self._set_reg(rd, self._reg(rd) ^ self._val(args[1]))
        return True

    def _op_shl(self, args):
        rd = args[0][1]
        self._set_reg(rd, self._reg(rd) << (self._val(args[1]) & 63))
        return True

    def _op_shr(self, args):
        rd = args[0][1]
        self._set_reg(rd, (self._reg(rd) & MASK64) >> (self._val(args[1]) & 63))
        return True

    def _op_inc(self, args):
        rd = args[0][1]
        self._set_reg(rd, self._reg(rd) + 1)
        return True

    def _op_dec(self, args):
        rd = args[0][1]
        self._set_reg(rd, self._reg(rd) - 1)
        return True

    def _op_cmp(self, args):
        a = self._val(args[0])
        b = self._val(args[1])
        self._set_flags_sub(a, b, (a - b) & MASK64)
        return True

    def _op_jmp(self, args):
        self.pc = self._val(args[0])
        return True

    def _op_jz(self, args):
        if self.pstate['Z']:
            self.pc = self._val(args[0])
        return True

    def _op_jnz(self, args):
        if not self.pstate['Z']:
            self.pc = self._val(args[0])
        return True

    def _op_je(self, args):
        if self.pstate['Z']:
            self.pc = self._val(args[0])
        return True

    def _op_jl(self, args):
        if self.pstate['N'] != self.pstate['V']:
            self.pc = self._val(args[0])
        return True

    def _op_jg(self, args):
        if not self.pstate['Z'] and self.pstate['N'] == self.pstate['V']:
            self.pc = self._val(args[0])
        return True

    def _op_push(self, args):
        self._check_stack()
        self._push(self._val(args[0]))
        return True

    def _op_pop(self, args):
        self._set_reg(args[0][1], self._pop())
        return True

    def _op_call(self, args):
        self._check_stack()
        self._push(self.pc)
        self.pc = self._val(args[0])
        return True

    def _op_ret(self, args):
        self.pc = self._pop()
        return True

    def _op_in(self, args):
        if self.config.allow_io:
            self._set_reg(args[0][1], self._read_input_int())
        return True

    def _op_out(self, args):
        if not self.config.allow_io:
            return True
        op = args[0]
        if op[0] == 'str':
            text = self.memory.read_string(op[1])
        else:
            val = self._val(op)
            if op[0] == 'float' or (op[0] == 'vec') or (op[0] == 'veclane'):
                text = _format_float(float(val))
            else:
                iv = int(val)
                text = '\n' if iv == 10 else str(iv)
        if self._trace:
            shown = text.replace('\n', '\\n')
            self.logger.trace(f"  OUT -> {shown!r}")
        self._emit_text(text)
        return True

    def _op_halt(self, args):
        return False

    # ==================== ARM64 扩展 ====================

    def _op_adds(self, args):
        rd, rn = args[0][1], args[1][1]
        a, b = self._reg(rn), self._val(args[2])
        r = (a + b) & MASK64
        self._set_flags_add(a, b, r)
        self._set_reg(rd, r)
        return True

    def _op_subs(self, args):
        rd, rn = args[0][1], args[1][1]
        a, b = self._reg(rn), self._val(args[2])
        r = (a - b) & MASK64
        self._set_flags_sub(a, b, r)
        self._set_reg(rd, r)
        return True

    def _op_addc(self, args):
        rd, rn = args[0][1], args[1][1]
        a, b = self._reg(rn), self._val(args[2])
        r = (a + b + (1 if self.pstate['C'] else 0)) & MASK64
        self._set_flags_add(a, b, r)
        self._set_reg(rd, r)
        return True

    def _op_subc(self, args):
        rd, rn = args[0][1], args[1][1]
        a, b = self._reg(rn), self._val(args[2])
        r = (a - b - (0 if self.pstate['C'] else 1)) & MASK64
        self._set_flags_sub(a, b, r)
        self._set_reg(rd, r)
        return True

    def _op_lsl(self, args):
        rd, rn = args[0][1], args[1][1]
        self._set_reg(rd, (self._reg(rn) << (self._val(args[2]) & 63)) & MASK64)
        return True

    def _op_lsr(self, args):
        rd, rn = args[0][1], args[1][1]
        self._set_reg(rd, (self._reg(rn) & MASK64) >> (self._val(args[2]) & 63))
        return True

    def _op_asr(self, args):
        rd, rn = args[0][1], args[1][1]
        v = self._reg(rn)
        sv = v if v < (1 << 63) else v - (1 << 64)
        r = sv >> (self._val(args[2]) & 63)
        self._set_reg(rd, r & MASK64)
        return True

    def _op_ror(self, args):
        rd, rn = args[0][1], args[1][1]
        v = self._reg(rn) & MASK64
        amt = self._val(args[2]) & 63
        r = ((v >> amt) | (v << (64 - amt))) & MASK64 if amt else v
        self._set_reg(rd, r)
        return True

    def _op_mvn(self, args):
        self._set_reg(args[0][1], (~self._val(args[1])) & MASK64)
        return True

    def _op_eor(self, args):
        rd, rn = args[0][1], args[1][1]
        self._set_reg(rd, self._reg(rn) ^ self._val(args[2]))
        return True

    def _op_bic(self, args):
        rd, rn = args[0][1], args[1][1]
        self._set_reg(rd, self._reg(rn) & (~self._val(args[2]) & MASK64))
        return True

    def _op_orn(self, args):
        rd, rn = args[0][1], args[1][1]
        self._set_reg(rd, self._reg(rn) | (~self._val(args[2]) & MASK64))
        return True

    def _op_ldr(self, args):
        rd = args[0][1]
        addr = self._mem_addr(args[1]) if args[1][0] == 'mem' else self._val(args[1])
        self.stats.record_memory_read()
        hit = self.cache.read(addr)
        self.stats.record_cache(hit)
        if self._trace:
            self._trace_cache(addr, hit, 'R')
        self._set_reg(rd, self.memory.read_dword(addr))
        return True

    def _op_str(self, args):
        rs = args[0][1]
        addr = self._mem_addr(args[1]) if args[1][0] == 'mem' else self._val(args[1])
        self.stats.record_memory_write()
        hit = self.cache.write(addr)
        self.stats.record_cache(hit)
        if self._trace:
            self._trace_cache(addr, hit, 'W')
        self.memory.write_dword(addr, self._reg(rs))
        return True

    def _op_ldp(self, args):
        rt, rt2 = args[0][1], args[1][1]
        addr = self._mem_addr(args[2]) if args[2][0] == 'mem' else self._val(args[2])
        self.stats.record_memory_read()
        self._set_reg(rt, self.memory.read_qword(addr))
        self._set_reg(rt2, self.memory.read_qword(addr + 8))
        return True

    def _op_stp(self, args):
        rt, rt2 = args[0][1], args[1][1]
        addr = self._mem_addr(args[2]) if args[2][0] == 'mem' else self._val(args[2])
        self.stats.record_memory_write()
        self.memory.write_qword(addr, self._reg(rt))
        self.memory.write_qword(addr + 8, self._reg(rt2))
        return True

    def _op_cbz(self, args):
        if self._reg(args[0][1]) == 0:
            self.pc = self._val(args[1])
        return True

    def _op_cbnz(self, args):
        if self._reg(args[0][1]) != 0:
            self.pc = self._val(args[1])
        return True

    def _op_tbz(self, args):
        rn, bit = self._reg(args[0][1]), self._val(args[1]) & 63
        if not (rn & (1 << bit)):
            self.pc = self._val(args[2])
        return True

    def _op_tbnz(self, args):
        rn, bit = self._reg(args[0][1]), self._val(args[1]) & 63
        if rn & (1 << bit):
            self.pc = self._val(args[2])
        return True

    def _op_b(self, args):
        # 可选条件操作数 ('cond', 'EQ'); 条件不满足则不跳转
        cond_op = next((a for a in args if a[0] == 'cond'), None)
        if cond_op is not None and not self._condition(cond_op[1]):
            return True
        for op in args:
            if op[0] != 'cond':
                self.pc = self._val(op)
        return True

    def _op_bl(self, args):
        self._check_stack()
        self._push(self.pc)
        self.pc = self._val(args[0])
        return True

    def _op_br(self, args):
        self.pc = self._reg(args[0][1])
        return True

    def _op_nop(self, args):
        return True

    def _op_csel(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2]
        cond = args[3][1] if args[3][0] == 'cond' else 'AL'
        self._set_reg(rd, self._reg(rn) if self._condition(cond) else self._val(rm))
        return True

    def _op_csinc(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2]
        cond = args[3][1] if args[3][0] == 'cond' else 'AL'
        if self._condition(cond):
            self._set_reg(rd, self._reg(rn))
        else:
            self._set_reg(rd, self._val(rm) + 1)
        return True

    def _op_csinv(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2]
        cond = args[3][1] if args[3][0] == 'cond' else 'AL'
        if self._condition(cond):
            self._set_reg(rd, self._reg(rn))
        else:
            self._set_reg(rd, (~self._val(rm)) & MASK64)
        return True

    def _op_csneg(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2]
        cond = args[3][1] if args[3][0] == 'cond' else 'AL'
        if self._condition(cond):
            self._set_reg(rd, self._reg(rn))
        else:
            self._set_reg(rd, (-self._val(rm)) & MASK64)
        return True

    @staticmethod
    def _sign_extend(v: int, bits: int) -> int:
        sign = 1 << (bits - 1)
        v &= (1 << bits) - 1
        return (v ^ sign) - sign

    def _op_sxtb(self, args):
        self._set_reg(args[0][1], self._sign_extend(self._val(args[1]), 8) & MASK64)
        return True

    def _op_sxth(self, args):
        self._set_reg(args[0][1], self._sign_extend(self._val(args[1]), 16) & MASK64)
        return True

    def _op_sxtw(self, args):
        self._set_reg(args[0][1], self._sign_extend(self._val(args[1]), 32) & MASK64)
        return True

    def _op_uxtb(self, args):
        self._set_reg(args[0][1], self._val(args[1]) & 0xFF)
        return True

    def _op_uxth(self, args):
        self._set_reg(args[0][1], self._val(args[1]) & 0xFFFF)
        return True

    def _op_clz(self, args):
        v = self._val(args[1]) & MASK64
        self._set_reg(args[0][1], 64 - v.bit_length() if v else 64)
        return True

    def _op_cls(self, args):
        v = self._val(args[1]) & MASK64
        sv = v if v < (1 << 63) else v - (1 << 64)
        if sv >= 0:
            self._set_reg(args[0][1], 63 - sv.bit_length() if sv else 63)
        else:
            self._set_reg(args[0][1], 63 - (~sv & MASK64).bit_length() + 1)
        return True

    def _op_rbit(self, args):
        v = self._val(args[1]) & MASK64
        r = int(f'{v:064b}'[::-1], 2)
        self._set_reg(args[0][1], r)
        return True

    def _op_rev(self, args):
        v = self._val(args[1]) & MASK64
        b = v.to_bytes(8, 'little')
        self._set_reg(args[0][1], int.from_bytes(b[::-1], 'little'))
        return True

    # ==================== 浮点 / 向量 ====================

    def _op_fadd(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        self.vec_regs.write_scalar(rd, self.vec_regs.read_scalar(rn) + self.vec_regs.read_scalar(rm))
        return True

    def _op_fsub(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        self.vec_regs.write_scalar(rd, self.vec_regs.read_scalar(rn) - self.vec_regs.read_scalar(rm))
        return True

    def _op_fmul(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        self.vec_regs.write_scalar(rd, self.vec_regs.read_scalar(rn) * self.vec_regs.read_scalar(rm))
        return True

    def _op_fdiv(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        b = self.vec_regs.read_scalar(rm)
        if b == 0:
            raise ExecutionError("Float division by zero")
        self.vec_regs.write_scalar(rd, self.vec_regs.read_scalar(rn) / b)
        return True

    def _op_fcmp(self, args):
        rn, rm = args[0][1], args[1][1]
        a, b = self.vec_regs.read_scalar(rn), self.vec_regs.read_scalar(rm)
        self.pstate['Z'] = (a == b)
        self.pstate['N'] = (a < b)
        self.pstate['C'] = (a >= b)
        self.pstate['V'] = False
        return True

    def _op_fcvt(self, args):
        rd, rs = args[0][1], args[1][1]
        if args[1][0] in ('vec', 'veclane'):
            # float -> int
            self._set_reg(rd, int(self.vec_regs.read_scalar(rs)))
        else:
            # int -> float
            self.vec_regs.write_scalar(rd, float(self._reg(rs)))
        return True

    def _op_fabs(self, args):
        self.vec_regs.write_scalar(args[0][1], abs(self.vec_regs.read_scalar(args[1][1])))
        return True

    def _op_fneg(self, args):
        self.vec_regs.write_scalar(args[0][1], -self.vec_regs.read_scalar(args[1][1]))
        return True

    def _op_ldrs(self, args):
        rd = args[0][1]
        addr = self._mem_addr(args[1]) if args[1][0] == 'mem' else self._val(args[1])
        self.stats.record_memory_read()
        self.vec_regs.write_scalar(rd, self.memory.read_float(addr))
        return True

    def _op_strs(self, args):
        rs = args[0][1]
        addr = self._mem_addr(args[1]) if args[1][0] == 'mem' else self._val(args[1])
        self.stats.record_memory_write()
        self.memory.write_float(addr, self.vec_regs.read_scalar(rs))
        return True

    def _vec_bin(self, args, fn):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        v1 = self.vec_regs.read_vector(rn)
        v2 = self.vec_regs.read_vector(rm)
        self.vec_regs.write_vector(rd, [fn(v1[i], v2[i]) for i in range(Constants.VECTOR_LANES)])
        return True

    def _op_vadd(self, args):
        return self._vec_bin(args, lambda a, b: a + b)

    def _op_vsub(self, args):
        return self._vec_bin(args, lambda a, b: a - b)

    def _op_vmul(self, args):
        return self._vec_bin(args, lambda a, b: a * b)

    def _op_vdiv(self, args):
        def f(a, b):
            if b == 0:
                raise ExecutionError("Vector division by zero")
            return a / b
        return self._vec_bin(args, f)

    def _op_vld1(self, args):
        rd = args[0][1]
        addr = self._mem_addr(args[1]) if args[1][0] == 'mem' else self._val(args[1])
        self.stats.record_memory_read()
        data = self.memory.read_block(addr, 16)
        self.vec_regs.write_vector(rd, [float(x) for x in struct.unpack('<4f', data)])
        return True

    def _op_vst1(self, args):
        rs = args[0][1]
        addr = self._mem_addr(args[1]) if args[1][0] == 'mem' else self._val(args[1])
        self.stats.record_memory_write()
        vec = self.vec_regs.read_vector(rs)
        self.memory.write_block(addr, struct.pack('<4f', *[float(x) for x in vec]))
        return True

    # ==================== RISC-V 扩展 ====================

    def _load_width(self, args, bits: int, signed: bool):
        rd = args[0][1]
        addr = self._mem_addr(args[1]) if args[1][0] == 'mem' else self._val(args[1])
        self.stats.record_memory_read()
        hit = self.cache.read(addr)
        self.stats.record_cache(hit)
        if self._trace:
            self._trace_cache(addr, hit, 'R')
        if bits == 8:
            v = self.memory.read_byte(addr)
            if signed:
                v = self._sign_extend(v, 8)
        elif bits == 16:
            v = self.memory.read_word(addr)
            if signed:
                v = self._sign_extend(v, 16)
        elif bits == 32:
            v = self.memory.read_dword(addr)
            if signed:
                v = self._sign_extend(v, 32)
        else:
            v = self.memory.read_qword(addr)
        self._set_reg(rd, v & MASK64)
        return True

    def _store_width(self, args, bits: int):
        rs = args[0][1]
        addr = self._mem_addr(args[1]) if args[1][0] == 'mem' else self._val(args[1])
        self.stats.record_memory_write()
        hit = self.cache.write(addr)
        self.stats.record_cache(hit)
        if self._trace:
            self._trace_cache(addr, hit, 'W')
        v = self._reg(rs)
        if bits == 8:
            self.memory.write_byte(addr, v & 0xFF)
        elif bits == 16:
            self.memory.write_word(addr, v & 0xFFFF)
        elif bits == 32:
            self.memory.write_dword(addr, v & MASK32)
        else:
            self.memory.write_qword(addr, v & MASK64)
        return True

    def _op_lb(self, args):
        return self._load_width(args, 8, True)

    def _op_lh(self, args):
        return self._load_width(args, 16, True)

    def _op_lw(self, args):
        return self._load_width(args, 32, True)

    def _op_ld(self, args):
        return self._load_width(args, 64, False)

    def _op_sb(self, args):
        return self._store_width(args, 8)

    def _op_sh(self, args):
        return self._store_width(args, 16)

    def _op_sw(self, args):
        return self._store_width(args, 32)

    def _op_sd(self, args):
        return self._store_width(args, 64)

    def _op_addi(self, args):
        rd, rs1 = args[0][1], args[1][1]
        self._set_reg(rd, self._reg(rs1) + self._val(args[2]))
        return True

    def _op_slti(self, args):
        rd, rs1 = args[0][1], args[1][1]
        a = self._reg(rs1)
        b = self._val(args[2])
        sa = a if a < (1 << 63) else a - (1 << 64)
        sb = b if b < (1 << 63) else b - (1 << 64)
        self._set_reg(rd, 1 if sa < sb else 0)
        return True

    def _op_sltiu(self, args):
        rd, rs1 = args[0][1], args[1][1]
        self._set_reg(rd, 1 if (self._reg(rs1) & MASK64) < (self._val(args[2]) & MASK64) else 0)
        return True

    def _op_xori(self, args):
        rd, rs1 = args[0][1], args[1][1]
        self._set_reg(rd, self._reg(rs1) ^ self._val(args[2]))
        return True

    def _op_ori(self, args):
        rd, rs1 = args[0][1], args[1][1]
        self._set_reg(rd, self._reg(rs1) | self._val(args[2]))
        return True

    def _op_andi(self, args):
        rd, rs1 = args[0][1], args[1][1]
        self._set_reg(rd, self._reg(rs1) & self._val(args[2]))
        return True

    def _op_slli(self, args):
        rd, rs1 = args[0][1], args[1][1]
        self._set_reg(rd, (self._reg(rs1) << (self._val(args[2]) & 63)) & MASK64)
        return True

    def _op_srli(self, args):
        rd, rs1 = args[0][1], args[1][1]
        self._set_reg(rd, (self._reg(rs1) & MASK64) >> (self._val(args[2]) & 63))
        return True

    def _op_srai(self, args):
        rd, rs1 = args[0][1], args[1][1]
        v = self._reg(rs1)
        sv = v if v < (1 << 63) else v - (1 << 64)
        self._set_reg(rd, (sv >> (self._val(args[2]) & 63)) & MASK64)
        return True

    def _branch_rs(self, args, pred_taken: bool, predicted: bool):
        self.stats.record_branch(self.pc, pred_taken, predicted)
        if pred_taken:
            self.pc = self._val(args[2])

    def _op_beq(self, args):
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        taken = self._reg(args[0][1]) == self._reg(args[1][1])
        self._branch_rs(args, taken, predicted)
        return True

    def _op_bne(self, args):
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        taken = self._reg(args[0][1]) != self._reg(args[1][1])
        self._branch_rs(args, taken, predicted)
        return True

    def _op_blt(self, args):
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        a, b = self._reg(args[0][1]), self._reg(args[1][1])
        sa = a if a < (1 << 63) else a - (1 << 64)
        sb = b if b < (1 << 63) else b - (1 << 64)
        self._branch_rs(args, sa < sb, predicted)
        return True

    def _op_bge(self, args):
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        a, b = self._reg(args[0][1]), self._reg(args[1][1])
        sa = a if a < (1 << 63) else a - (1 << 64)
        sb = b if b < (1 << 63) else b - (1 << 64)
        self._branch_rs(args, sa >= sb, predicted)
        return True

    def _op_bltu(self, args):
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        taken = (self._reg(args[0][1]) & MASK64) < (self._reg(args[1][1]) & MASK64)
        self._branch_rs(args, taken, predicted)
        return True

    def _op_bgeu(self, args):
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        taken = (self._reg(args[0][1]) & MASK64) >= (self._reg(args[1][1]) & MASK64)
        self._branch_rs(args, taken, predicted)
        return True

    def _op_jalr(self, args):
        # JALR rd, rs1, imm  /  jalr rs1  (单寄存器形式视为 ret, rd 丢弃)
        regs = [a[1] for a in args if a[0] == 'reg']
        imm = 0
        for a in args:
            if a[0] == 'imm':
                imm = a[1]
            elif a[0] == 'mem':
                imm = a[2]
                if a[1] >= 0 and len(regs) < 2:
                    regs.append(a[1])
        if len(regs) >= 2:
            rd, rs1 = regs[0], regs[1]
        elif len(regs) == 1:
            rd, rs1 = 31, regs[0]
        else:
            rd, rs1 = 31, 31
        if rd != 31:
            self._set_reg(rd, self.pc)
        self.pc = (self._reg(rs1) + imm) & MASK64
        return True

    def _op_jal(self, args):
        rd = args[0][1] if args[0][0] == 'reg' else 31
        if rd != 31:
            self._set_reg(rd, self.pc)
        target = args[1] if args[0][0] == 'reg' else args[0]
        self.pc = self._val(target)
        return True

    def _op_lui(self, args):
        rd = args[0][1]
        imm = self._val(args[1]) if args[1][0] != 'imm' else args[1][1]
        self._set_reg(rd, (imm & 0xFFFFF) << 12)
        return True

    def _op_auipc(self, args):
        rd = args[0][1]
        imm = self._val(args[1]) if args[1][0] != 'imm' else args[1][1]
        self._set_reg(rd, self.pc + ((imm & 0xFFFFF) << 12))
        return True

    # ==================== SYS 宿主调用 ====================

    def _sys_buffer(self) -> int:
        idx = self._sys_buf_idx % len(self._sys_buffers)
        self._sys_buf_idx += 1
        # 缓冲放在内存高地址区下方 (heap 之后)
        addr = self.heap_ptr + 2048 + idx * 64
        return addr

    def _op_sys(self, args):
        if not args or args[0][0] != 'imm':
            raise ExecutionError("SYS requires an immediate call id")
        call_id = args[0][1]
        x0 = self._reg(0)
        x1 = self._reg(1)
        x2 = self._reg(2)
        if self._trace:
            name = Syscall(call_id).name if call_id in Syscall._value2member_map_ \
                else f'UNKNOWN({call_id})'
            self.logger.trace(f"  SYS #{call_id} ({name}) "
                              f"x0=0x{x0:x} x1=0x{x1:x} x2=0x{x2:x}")

        if call_id == Syscall.ABS:
            self._set_reg(0, abs(x0 if x0 < (1 << 63) else x0 - (1 << 64)))
        elif call_id in (Syscall.SQRT,):
            self._set_reg(0, _f_to_bits(math.sqrt(_bits_to_f(x0))))
        elif call_id == Syscall.POW:
            self._set_reg(0, _f_to_bits(math.pow(_bits_to_f(x0), _bits_to_f(x1))))
        elif call_id == Syscall.SIN:
            self._set_reg(0, _f_to_bits(math.sin(_bits_to_f(x0))))
        elif call_id == Syscall.COS:
            self._set_reg(0, _f_to_bits(math.cos(_bits_to_f(x0))))
        elif call_id == Syscall.TAN:
            self._set_reg(0, _f_to_bits(math.tan(_bits_to_f(x0))))
        elif call_id == Syscall.FADD:
            self._set_reg(0, _f_to_bits(_bits_to_f(x0) + _bits_to_f(x1)))
        elif call_id == Syscall.FSUB:
            self._set_reg(0, _f_to_bits(_bits_to_f(x0) - _bits_to_f(x1)))
        elif call_id == Syscall.FMUL:
            self._set_reg(0, _f_to_bits(_bits_to_f(x0) * _bits_to_f(x1)))
        elif call_id == Syscall.FDIV:
            b = _bits_to_f(x1)
            if b == 0:
                raise ExecutionError("Float division by zero (SYS)")
            self._set_reg(0, _f_to_bits(_bits_to_f(x0) / b))
        elif call_id == Syscall.FCMP:
            a, b = _bits_to_f(x0), _bits_to_f(x1)
            self._set_reg(0, -1 if a < b else (1 if a > b else 0))
        elif call_id == Syscall.FTOI:
            self._set_reg(0, int(_bits_to_f(x0)))
        elif call_id == Syscall.ITOF:
            self._set_reg(0, _f_to_bits(float(x0 if x0 < (1 << 63) else x0 - (1 << 64))))
        elif call_id == Syscall.RAND:
            self._set_reg(0, self._rand.randrange(1 << 31))
        elif call_id == Syscall.SRAND:
            self._rand.seed(x0)
        elif call_id == Syscall.TIME:
            self._set_reg(0, int(time.time()))
        elif call_id == Syscall.STRLEN:
            n = 0
            while self.memory.read_byte(x0 + n) != 0:
                n += 1
            self._set_reg(0, n)
        elif call_id == Syscall.STRCMP:
            i = 0
            while True:
                ca = self.memory.read_byte(x0 + i)
                cb = self.memory.read_byte(x1 + i)
                if ca != cb or ca == 0:
                    self._set_reg(0, ca - cb)
                    break
                i += 1
        elif call_id in (Syscall.STRCPY, Syscall.STRCAT):
            dst = x0
            if call_id == Syscall.STRCAT:
                while self.memory.read_byte(dst) != 0:
                    dst += 1
            src = x1
            i = 0
            while True:
                ch = self.memory.read_byte(src + i)
                self.memory.write_byte(dst + i, ch)
                i += 1
                if ch == 0:
                    break
            self._set_reg(0, x0)
        elif call_id == Syscall.MALLOC:
            size = (x0 + 15) & ~0xF
            ptr = self.heap_ptr
            self.heap_ptr += size
            if self.heap_ptr > self.sp:
                raise ExecutionError("Heap exhausted")
            self._set_reg(0, ptr)
        elif call_id == Syscall.PRINT_FLOAT:
            self._emit_text(_format_float(_bits_to_f(x0)))
        elif call_id == Syscall.ITOA:
            addr = self._sys_buffer()
            signed = x0 if x0 < (1 << 63) else x0 - (1 << 64)
            self.memory.write_string(addr, str(signed))
            self._set_reg(0, addr)
        elif call_id == Syscall.FTOA:
            addr = self._sys_buffer()
            self.memory.write_string(addr, _format_float(_bits_to_f(x0)))
            self._set_reg(0, addr)
        elif call_id == Syscall.PRINT_STR:
            self._emit_text(self.memory.read_string(x0))
        elif call_id == Syscall.STR_CONCAT:
            sa = self.memory.read_string(x0)
            sb = self.memory.read_string(x1)
            data = (sa + sb).encode('utf-8') + b'\x00'
            size = (len(data) + 15) & ~0xF
            ptr = self.heap_ptr
            self.heap_ptr += size
            if self.heap_ptr > self.sp:
                raise ExecutionError("Heap exhausted (string concat)")
            self.memory.write_block(ptr, data)
            self._set_reg(0, ptr)
        elif call_id == Syscall.BOOL_STR:
            addr = self._sys_buffer()
            self.memory.write_string(addr, "true" if x0 != 0 else "false")
            self._set_reg(0, addr)
        else:
            raise ExecutionError(f"Unknown SYS call id: {call_id}")
        return True

    # ==================== 执行引擎 ====================

    def execute(self, opcode: str, args: List[Operand]) -> bool:
        if self._trace:
            ops = ' '.join(self._fmt_op_trace(a) for a in args)
            self.logger.trace(
                f"PC=0x{self.pc:04x} #{self.stats.instruction_count:08d} "
                f"{opcode} {ops}  SP=0x{self.sp:x}")
        self.pc += 1
        handler = self._dispatch.get(opcode)
        if handler is None:
            raise ExecutionError(f"Unimplemented instruction: {opcode}")
        result = handler(args)
        self.stats.record_instruction(opcode)
        if self._trace:
            self.logger.trace(
                f"  => pc=0x{self.pc:04x} {self._trace_flags()}")
        return result

    def step(self) -> bool:
        if self.pc < 0 or self.pc >= len(self.instructions):
            return False
        opcode, args = self.instructions[self.pc]
        return self.execute(opcode, args)

    def _try_native_run(self) -> Optional[bool]:
        """尝试使用 Go 原生库执行整个程序; 不可用/不支持时返回 None。"""
        if not self.config.use_native or self.config.debug_mode or self.config.step_mode:
            return None
        if self.config.enable_jit:
            return None
        try:
            from . import native
        except Exception:
            return None
        engine = native.get_engine(self.logger)
        if engine is None:
            return None

        from .native import encode_program
        all_labels = dict(self.labels)
        all_labels.update(self.data_labels)
        bytecode = encode_program(self.instructions, self.entry_pc, all_labels)
        mem_image = self.memory.get_snapshot()
        self.logger.debug(
            f"Native run: bytecode={len(bytecode)}B mem={len(mem_image)}B "
            f"entry={self.entry_pc} sp=0x{self.sp:x} "
            f"heap=0x{self.heap_ptr:x} max_steps={self.config.max_instructions}")
        import time as _time
        t0 = _time.perf_counter()
        result = engine.run(
            bytecode=bytecode,
            mem=mem_image,
            entry=self.entry_pc,
            sp=self.sp,
            heap_base=self.heap_ptr,
            input_data=self.input_buffer.encode('utf-8'),
            max_steps=self.config.max_instructions,
        )
        elapsed = _time.perf_counter() - t0
        if result is None:
            self.logger.debug("Native run failed (result None)")
            return None

        self.logger.debug(
            f"Native result: status={result.get('status')} "
            f"halted={result.get('halted')} steps={result.get('steps')} "
            f"pc={result.get('pc')} elapsed={elapsed * 1000:.2f}ms "
            f"error={result.get('error')}")

        if result.get('error') == 'unsupported':
            # 原生库遇到不支持的指令: 同步状态后回退解释执行
            self._apply_native_state(result)
            self.logger.debug(
                f"Native engine hit unsupported opcode, falling back to "
                f"interpreter at PC=0x{result.get('pc', 0):x}")
            return None

        # 应用原生执行结果
        self._apply_native_state(result)
        self.native_used = True
        if result.get('output'):
            self._emit_text(result['output'])
        return not result.get('halted', False) or result.get('error') is None

    def _apply_native_state(self, result: dict) -> None:
        if 'regs' in result:
            self.regs.set_all(list(result['regs'])[:32])
        if 'sp' in result:
            self.sp = result['sp'] & MASK64
        if 'pc' in result:
            self.pc = result['pc']
        if 'vec_regs' in result:
            self.vec_regs.set_all(result['vec_regs'])
        if 'mem' in result:
            mem = result['mem']
            self.memory.write_block(0, bytes(mem[:len(self.memory)]))
        if 'steps' in result:
            for _ in range(min(result['steps'], self.config.max_instructions)):
                self.stats.record_instruction('?')
            self.stats.instruction_count = result['steps']
            self.stats.opcode_count.clear()
        if 'heap_ptr' in result:
            self.heap_ptr = result['heap_ptr']

    def run(self) -> None:
        self.running = True
        self.stats.start()
        self.logger.info("Starting program execution")

        native_outcome = None
        if self.config.use_native and not self.config.debug_mode and not self.config.step_mode:
            native_outcome = self._try_native_run()

        try:
            if native_outcome is not None:
                # 原生执行完成
                if not native_outcome:
                    self.logger.info("HALT (native)")
            else:
                self._run_interpreted()
        except KeyboardInterrupt:
            self.logger.info("User interrupt")
            self.console.print(f"\n{Colors.colorize('User interrupt', Colors.YELLOW)}")
        except Exception as e:
            if self.config.debug_mode:
                # 超详细: rich 彩色完整堆栈
                self.logger.exception(f"Execution error: {e}")
            else:
                self.logger.error(f"Execution error: {e}")
                self.console.print(Panel(
                    f"{e}", title="Execution Error", border_style='red'))
        finally:
            self.running = False
            self.stats.stop()
            self.cache.flush()
            self.logger.info("Program execution finished")

            if self.config.profile or self.config.debug_mode:
                self.display_state("Execution Complete")
                cache_stats = self.cache.get_stats()
                self.stats.display_summary(self.console, cache_stats,
                                           native_used=self.native_used)

            if self.config.auto_save_crom:
                from . import crom as crom_mod
                crom_file = os.path.splitext(self.filename)[0] + '.crom' if self.filename else 'program.crom'
                crom_mod.save_crom(self.memory, crom_file,
                                   compress=self.config.compress_crom,
                                   logger=self.logger)

    def _run_interpreted(self) -> None:
        while self.running:
            if self.pc < 0 or self.pc >= len(self.instructions):
                self.logger.info("Program ended normally")
                break

            if self.stats.instruction_count >= self.config.max_instructions:
                self.logger.warning(f"Max instruction limit reached: "
                                    f"{self.config.max_instructions}")
                break

            if self.debug_server and self.debug_server.check_conditional_breakpoints():
                self.is_debugging = True
                self.debug_command_loop()
                continue

            if self.pc in self.breakpoints:
                self.console.print(
                    f"{Colors.colorize(f'Breakpoint hit at PC={self.pc:#x}', Colors.YELLOW)}")
                self.is_debugging = True
                self.debug_command_loop()
                continue

            if self.jit is not None:
                jit_result = self.jit.try_step(self)
                if jit_result is True:
                    continue
                if jit_result is False:
                    self.logger.info("Program ended (JIT)")
                    break
                # None: 该指令不适合 JIT, 回退解释执行

            opcode, args = self.instructions[self.pc]
            continue_exec = self.execute(opcode, args)

            if not continue_exec:
                self.logger.info("HALT instruction executed")
                break

            if self.config.step_mode and self.config.interactive_mode:
                self.display_state("Step Execution", opcode, args)
                if input(f"{Colors.colorize('Continue? (y/n)', Colors.YELLOW)} "
                         ).lower() != 'y':
                    break

            if self.config.execution_interval > 0:
                time.sleep(self.config.execution_interval)

    # ==================== 状态显示 / 调试 ====================

    def display_state(self, title: str = "CPU State", opcode: Optional[str] = None,
                      args: Optional[List[Operand]] = None) -> None:
        self.console.clear()
        self.console.rule(f"{Colors.colorize(title, Colors.MAGENTA, True)}")

        if opcode:
            instr_text = f"{opcode} " + ", ".join(self._fmt_operand(a) for a in (args or []))
            self.console.print(str(Panel(instr_text.strip(), title="Current Instruction")))

        reg_info = {
            'PSTATE': ' '.join(f"{k}={int(v)}" for k, v in self.pstate.items()),
            'SP': self.sp,
            'PC': self.pc,
        }
        if self.breakpoints:
            reg_info['BREAKPOINTS'] = ', '.join(f"{b:#x}" for b in self.breakpoints)
        self.regs.display_registers("General Registers (X0-X31)", reg_info, self.console)

        if self.config.show_vector_regs:
            self.vec_regs.display_vector_registers("Vector Registers (V0-V31)", self.console)

        self.memory.display_memory("Memory (first 64 bytes)", 0, 64, self.console)

        cache_stats = self.cache.get_stats()
        self.console.print(
            f"Cache: {cache_stats['hits']} hits, {cache_stats['misses']} misses "
            f"({cache_stats['hit_rate'] * 100:.1f}% hit rate)")
        self.console.rule()

    @staticmethod
    def _fmt_operand(op: Operand) -> str:
        kind = op[0]
        if kind == 'reg':
            return f"X{op[1]}"
        if kind == 'vec':
            return f"V{op[1]}"
        if kind == 'veclane':
            return f"V{op[1]}.{op[2]}"
        if kind == 'imm':
            return f"#{op[1]}"
        if kind == 'mem':
            base, off = op[1], op[2]
            if base >= 0:
                return f"[X{base}, #{off}]" if off else f"[X{base}]"
            return f"[#{off}]"
        if kind == 'cond':
            return op[1]
        if kind == 'str':
            return f"\"@{op[1]}\""
        return str(op)

    def add_breakpoint(self, addr: int) -> None:
        self.breakpoints.add(addr)
        self.logger.info(f"Breakpoint set at PC={addr:#x}")

    def remove_breakpoint(self, addr: int) -> None:
        self.breakpoints.discard(addr)
        self.logger.info(f"Breakpoint removed at PC={addr:#x}")

    def debug_command_loop(self) -> None:
        from .debugger import DebugServer
        if self.debug_server is None:
            self.debug_server = DebugServer(self)

        self.is_debugging = True
        self.console.print(
            f"{Colors.colorize('Debug mode (type help for commands)', Colors.BLUE, True)}")

        while self.is_debugging:
            try:
                cmd = input(f"{Colors.colorize('dbg>', Colors.YELLOW)} ").strip()
            except EOFError:
                break
            if not cmd:
                continue
            parts = cmd.split()
            command = parts[0].lower()

            if command == 'help':
                self._debug_help()
            elif command in ('continue', 'c'):
                self.is_debugging = False
                return
            elif command in ('step', 's'):
                self.debug_server.record_state()
                if not self.step():
                    self.is_debugging = False
                    return
                self.display_state("Step Execution")
            elif command == 'reverse':
                if self.debug_server.reverse_step():
                    self.console.print(f"{Colors.colorize('Reversed one step', Colors.GREEN)}")
                    self.display_state("Reverse Step")
                else:
                    self.console.print(f"{Colors.colorize('No history available', Colors.RED)}")
            elif command == 'forward':
                if self.debug_server.forward_step():
                    self.console.print(f"{Colors.colorize('Forward one step', Colors.GREEN)}")
                    self.display_state("Forward Step")
                else:
                    self.console.print(f"{Colors.colorize('No forward history', Colors.RED)}")
            elif command in ('print', 'p'):
                self._debug_print(parts)
            elif command == 'break':
                self._debug_break(parts)
            elif command == 'delete':
                if len(parts) > 1:
                    try:
                        self.remove_breakpoint(int(parts[1]))
                    except ValueError:
                        self.console.print(f"{Colors.colorize('Invalid address', Colors.RED)}")
            elif command == 'watch':
                if len(parts) > 1:
                    try:
                        addr = int(parts[1], 0)
                        access = parts[2] if len(parts) > 2 else 'rw'
                        self.memory.set_protection(addr, access)
                        self.console.print(
                            f"{Colors.colorize(f'Watchpoint set at {addr:#x} for {access}', Colors.GREEN)}")
                    except ValueError:
                        self.console.print(f"{Colors.colorize('Invalid address', Colors.RED)}")
            elif command in ('list', 'info'):
                self.console.print(f"{Colors.colorize('Breakpoints:', Colors.BOLD)}")
                for addr in sorted(self.breakpoints):
                    self.console.print(f"  {addr:#x}")
                for bp in self.debug_server.conditional_breakpoints:
                    self.console.print(f"  {bp.address:#x} (cond: {bp.condition}, "
                                       f"hits: {bp.hit_count})")
            elif command in ('quit', 'q'):
                sys.exit(0)
            else:
                self.console.print(f"{Colors.colorize('Unknown command', Colors.RED)}")

    def _debug_print(self, parts):
        if len(parts) < 2:
            self.console.print(f"{Colors.colorize('Missing argument', Colors.RED)}")
            return
        target = parts[1]
        if target.lower().startswith('x') and target[1:].isdigit():
            idx = int(target[1:])
            self.console.print(f"{target.upper()} = {self._reg(idx)} (0x{self._reg(idx):x})")
        elif target == 'regs':
            self.regs.display_registers(console=self.console)
        elif target == 'mem':
            if len(parts) > 2:
                try:
                    addr = int(parts[2], 0)
                    value = self.memory.read_qword(addr)
                    self.console.print(f"mem[{addr:#x}] = {value} (0x{value:x})")
                except ValueError:
                    self.console.print(f"{Colors.colorize('Invalid address', Colors.RED)}")
            else:
                self.memory.display_memory(console=self.console)
        elif target == 'cache':
            self.console.print(f"Cache stats: {self.cache.get_stats()}")
        elif target == 'pc':
            self.console.print(f"PC: {self.pc:#x}")
        else:
            self.console.print(f"{Colors.colorize('Unknown target', Colors.RED)}")

    def _debug_break(self, parts):
        if len(parts) < 2:
            self.console.print(f"{Colors.colorize('Missing address', Colors.RED)}")
            return
        try:
            addr = int(parts[1], 0)
        except ValueError:
            self.console.print(f"{Colors.colorize('Invalid address', Colors.RED)}")
            return
        if len(parts) > 2:
            condition = ' '.join(parts[2:])
            self.debug_server.add_conditional_breakpoint(addr, condition)
            self.console.print(
                f"{Colors.colorize(f'Conditional breakpoint set at {addr:#x}: {condition}', Colors.GREEN)}")
        else:
            self.add_breakpoint(addr)
            self.console.print(f"{Colors.colorize(f'Breakpoint set at {addr:#x}', Colors.GREEN)}")

    def _debug_help(self) -> None:
        help_text = f"""
{Colors.colorize('Debug Commands:', Colors.CYAN, True)}
  {Colors.colorize('continue / c', Colors.GREEN)}  - Continue execution
  {Colors.colorize('step / s', Colors.GREEN)}      - Single step
  {Colors.colorize('reverse', Colors.GREEN)}       - Reverse one step
  {Colors.colorize('forward', Colors.GREEN)}       - Forward one step
  {Colors.colorize('break <addr> [cond]', Colors.GREEN)} - Set breakpoint
  {Colors.colorize('delete <addr>', Colors.GREEN)} - Remove breakpoint
  {Colors.colorize('watch <addr> [r|w|rw]', Colors.GREEN)} - Set watchpoint
  {Colors.colorize('list / info', Colors.GREEN)}   - List breakpoints
  {Colors.colorize('print / p <target>', Colors.GREEN)} - X0-X31, regs, mem [addr], cache, pc
  {Colors.colorize('quit / q', Colors.GREEN)}      - Exit simulator
  {Colors.colorize('help', Colors.GREEN)}          - Show this help
        """
        self.console.print(help_text)
