#!/usr/bin/env python3
# cpu.py - Complete CPU Simulator with CIN/PL/ASM Support
# Version: 4.3 - Fixed recursion issues

import sys
import re
import time
import os
import struct
import json
import zlib
import traceback
from typing import List, Tuple, Optional, Dict, Set, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict
from pathlib import Path
import math
import socket

# ==================== ANSI Colors ====================

class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'
    
    @staticmethod
    def colorize(text: str, color: str, bold: bool = False) -> str:
        return f"{Colors.BOLD if bold else ''}{color}{text}{Colors.RESET}"

# ==================== Console ====================

class Console:
    def __init__(self):
        self.width = 80
        self._color_support = sys.stdout.isatty()
    
    def print(self, *args, **kwargs):
        text = ' '.join(str(arg) for arg in args)
        if self._color_support:
            print(text)
        else:
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            print(ansi_escape.sub('', text))
    
    def clear(self):
        if sys.platform == 'win32':
            os.system('cls')
        else:
            os.system('clear')
    
    def rule(self, title: str = ""):
        if title:
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_title = ansi_escape.sub('', title)
            padding = max(0, (50 - len(clean_title) - 2) // 2)
            line = '=' * padding + ' ' + title + ' ' + '=' * padding
            if len(line) < 50:
                line = line + '=' * (50 - len(line))
            print(line)
        else:
            print('=' * 50)
    
    def clear_line(self):
        print('\r' + ' ' * 80 + '\r', end='')

class Panel:
    def __init__(self, content, title="", border_style="", box=None):
        self.content = content
        self.title = title
    
    def __str__(self):
        if self.title:
            return f"┌─ {self.title} ───────────────────────┐\n{self.content}\n└────────────────────────────────────┘"
        return f"┌────────────────────────────┐\n{self.content}\n└────────────────────────────┘"

class Table:
    def __init__(self, title="", box=None, border_style=""):
        self.title = title
        self.headers = []
        self.rows = []
        self.col_widths = []
    
    def add_column(self, name, style="", width=0):
        self.headers.append(name)
        self.col_widths.append(width if width > 0 else len(name) + 2)
    
    def add_row(self, *args):
        self.rows.append(args)
        for i, val in enumerate(args):
            if i < len(self.col_widths):
                self.col_widths[i] = max(self.col_widths[i], len(str(val)) + 2)
    
    def __str__(self):
        if not self.headers:
            return ""
        
        lines = []
        if self.title:
            lines.append(f"  {Colors.colorize(self.title, Colors.CYAN, True)}")
        
        header_parts = []
        for i, h in enumerate(self.headers):
            header_parts.append(f"{Colors.colorize(h, Colors.BOLD)}".ljust(self.col_widths[i]))
        lines.append("  " + " │ ".join(header_parts))
        lines.append("  " + "─┼─".join("─" * w for w in self.col_widths))
        
        for row in self.rows:
            row_parts = []
            for i, val in enumerate(row):
                if i < len(self.col_widths):
                    row_parts.append(str(val).ljust(self.col_widths[i]))
            lines.append("  " + " │ ".join(row_parts))
        
        return "\n".join(lines)

# ==================== Opcode ====================

class Opcode(Enum):
    MOV = 0
    LOAD = 1
    STORE = 2
    ADD = 3
    SUB = 4
    MUL = 5
    DIV = 6
    AND = 7
    OR = 8
    XOR = 9
    SHL = 10
    SHR = 11
    INC = 12
    DEC = 13
    CMP = 14
    JMP = 15
    JZ = 16
    JNZ = 17
    JE = 18
    JL = 19
    JG = 20
    PUSH = 21
    POP = 22
    CALL = 23
    RET = 24
    IN = 25
    OUT = 26
    HALT = 27
    ADDS = 28
    SUBS = 29
    ADDC = 30
    SUBC = 31
    LSL = 32
    LSR = 33
    ASR = 34
    ROR = 35
    MVN = 36
    EOR = 37
    BIC = 38
    ORN = 39
    LDR = 40
    STR = 41
    LDP = 42
    STP = 43
    CBZ = 44
    CBNZ = 45
    TBZ = 46
    TBNZ = 47
    B = 48
    BL = 49
    BR = 50
    NOP = 51
    WFE = 52
    WFI = 53
    SEV = 54
    CSEL = 55
    CSINC = 56
    CSINV = 57
    CSNEG = 58
    SXTB = 59
    SXTH = 60
    SXTW = 61
    UXTB = 62
    UXTH = 63
    CLZ = 64
    CLS = 65
    RBIT = 66
    REV = 67
    FADD = 68
    FSUB = 69
    FMUL = 70
    FDIV = 71
    FCMP = 72
    FCVT = 73
    FABS = 74
    FNEG = 75
    LDRS = 76
    STRS = 77
    VADD = 78
    VSUB = 79
    VMUL = 80
    VDIV = 81
    VLD1 = 82
    VST1 = 83
    LB = 84
    LH = 85
    LW = 86
    LD = 87
    SB = 88
    SH = 89
    SW = 90
    SD = 91
    ADDI = 92
    SLTI = 93
    SLTIU = 94
    XORI = 95
    ORI = 96
    ANDI = 97
    SLLI = 98
    SRLI = 99
    SRAI = 100
    BEQ = 101
    BNE = 102
    BLT = 103
    BGE = 104
    BLTU = 105
    BGEU = 106
    JALR = 107
    JAL = 108
    LUI = 109
    AUIPC = 110

# ==================== Constants ====================

class Constants:
    NUM_REGISTERS: int = 32
    NUM_VECTOR_REGISTERS: int = 32
    INSTR_SIZE: int = 16
    DEFAULT_MEM_SIZE: int = 1024
    MAGIC_NUMBER: bytes = b'CPUSA'
    CROM_MAGIC: bytes = b'CROM'
    CROM_VERSION: int = 3
    VERSION: int = 2
    MAX_INSTRUCTIONS: int = 100000
    STACK_RESERVED: int = 128
    
    OPCODE_NAMES: Dict[Opcode, str] = {
        Opcode.MOV: 'MOV', Opcode.LOAD: 'LOAD', Opcode.STORE: 'STORE',
        Opcode.ADD: 'ADD', Opcode.SUB: 'SUB', Opcode.MUL: 'MUL',
        Opcode.DIV: 'DIV', Opcode.AND: 'AND', Opcode.OR: 'OR',
        Opcode.XOR: 'XOR', Opcode.SHL: 'SHL', Opcode.SHR: 'SHR',
        Opcode.INC: 'INC', Opcode.DEC: 'DEC', Opcode.CMP: 'CMP',
        Opcode.JMP: 'JMP', Opcode.JZ: 'JZ', Opcode.JNZ: 'JNZ',
        Opcode.JE: 'JE', Opcode.JL: 'JL', Opcode.JG: 'JG',
        Opcode.PUSH: 'PUSH', Opcode.POP: 'POP', Opcode.CALL: 'CALL',
        Opcode.RET: 'RET', Opcode.IN: 'IN', Opcode.OUT: 'OUT',
        Opcode.HALT: 'HALT',
        Opcode.ADDS: 'ADDS', Opcode.SUBS: 'SUBS',
        Opcode.ADDC: 'ADDC', Opcode.SUBC: 'SUBC',
        Opcode.LSL: 'LSL', Opcode.LSR: 'LSR',
        Opcode.ASR: 'ASR', Opcode.ROR: 'ROR',
        Opcode.MVN: 'MVN', Opcode.EOR: 'EOR',
        Opcode.BIC: 'BIC', Opcode.ORN: 'ORN',
        Opcode.LDR: 'LDR', Opcode.STR: 'STR',
        Opcode.LDP: 'LDP', Opcode.STP: 'STP',
        Opcode.CBZ: 'CBZ', Opcode.CBNZ: 'CBNZ',
        Opcode.TBZ: 'TBZ', Opcode.TBNZ: 'TBNZ',
        Opcode.B: 'B', Opcode.BL: 'BL', Opcode.BR: 'BR',
        Opcode.NOP: 'NOP', Opcode.WFE: 'WFE',
        Opcode.WFI: 'WFI', Opcode.SEV: 'SEV',
        Opcode.CSEL: 'CSEL', Opcode.CSINC: 'CSINC',
        Opcode.CSINV: 'CSINV', Opcode.CSNEG: 'CSNEG',
        Opcode.SXTB: 'SXTB', Opcode.SXTH: 'SXTH',
        Opcode.SXTW: 'SXTW', Opcode.UXTB: 'UXTB',
        Opcode.UXTH: 'UXTH',
        Opcode.CLZ: 'CLZ', Opcode.CLS: 'CLS',
        Opcode.RBIT: 'RBIT', Opcode.REV: 'REV',
        Opcode.FADD: 'FADD', Opcode.FSUB: 'FSUB',
        Opcode.FMUL: 'FMUL', Opcode.FDIV: 'FDIV',
        Opcode.FCMP: 'FCMP', Opcode.FCVT: 'FCVT',
        Opcode.FABS: 'FABS', Opcode.FNEG: 'FNEG',
        Opcode.LDRS: 'LDRS', Opcode.STRS: 'STRS',
        Opcode.VADD: 'VADD', Opcode.VSUB: 'VSUB',
        Opcode.VMUL: 'VMUL', Opcode.VDIV: 'VDIV',
        Opcode.VLD1: 'VLD1', Opcode.VST1: 'VST1',
        Opcode.LB: 'LB', Opcode.LH: 'LH', Opcode.LW: 'LW',
        Opcode.LD: 'LD', Opcode.SB: 'SB', Opcode.SH: 'SH',
        Opcode.SW: 'SW', Opcode.SD: 'SD',
        Opcode.ADDI: 'ADDI', Opcode.SLTI: 'SLTI',
        Opcode.SLTIU: 'SLTIU', Opcode.XORI: 'XORI',
        Opcode.ORI: 'ORI', Opcode.ANDI: 'ANDI',
        Opcode.SLLI: 'SLLI', Opcode.SRLI: 'SRLI',
        Opcode.SRAI: 'SRAI',
        Opcode.BEQ: 'BEQ', Opcode.BNE: 'BNE',
        Opcode.BLT: 'BLT', Opcode.BGE: 'BGE',
        Opcode.BLTU: 'BLTU', Opcode.BGEU: 'BGEU',
        Opcode.JALR: 'JALR', Opcode.JAL: 'JAL',
        Opcode.LUI: 'LUI', Opcode.AUIPC: 'AUIPC'
    }
    
    OPCODE_NAME_TO_ENUM: Dict[str, Opcode] = {v: k for k, v in OPCODE_NAMES.items()}
    
    ARG_COUNTS: Dict[Opcode, int] = {
        Opcode.MOV: 2, Opcode.LOAD: 2, Opcode.STORE: 2,
        Opcode.ADD: 2, Opcode.SUB: 2, Opcode.MUL: 2,
        Opcode.DIV: 2, Opcode.AND: 2, Opcode.OR: 2,
        Opcode.XOR: 2, Opcode.SHL: 2, Opcode.SHR: 2,
        Opcode.INC: 1, Opcode.DEC: 1, Opcode.CMP: 2,
        Opcode.JMP: 1, Opcode.JZ: 1, Opcode.JNZ: 1,
        Opcode.JE: 1, Opcode.JL: 1, Opcode.JG: 1,
        Opcode.PUSH: 1, Opcode.POP: 1, Opcode.CALL: 1,
        Opcode.RET: 0, Opcode.IN: 1, Opcode.OUT: 1,
        Opcode.HALT: 0,
        Opcode.ADDS: 3, Opcode.SUBS: 3,
        Opcode.ADDC: 3, Opcode.SUBC: 3,
        Opcode.LSL: 3, Opcode.LSR: 3,
        Opcode.ASR: 3, Opcode.ROR: 3,
        Opcode.MVN: 2, Opcode.EOR: 3,
        Opcode.BIC: 3, Opcode.ORN: 3,
        Opcode.LDR: 2, Opcode.STR: 2,
        Opcode.LDP: 3, Opcode.STP: 3,
        Opcode.CBZ: 2, Opcode.CBNZ: 2,
        Opcode.TBZ: 3, Opcode.TBNZ: 3,
        Opcode.B: 1, Opcode.BL: 1, Opcode.BR: 1,
        Opcode.NOP: 0, Opcode.WFE: 0,
        Opcode.WFI: 0, Opcode.SEV: 0,
        Opcode.CSEL: 4, Opcode.CSINC: 4,
        Opcode.CSINV: 4, Opcode.CSNEG: 4,
        Opcode.SXTB: 2, Opcode.SXTH: 2,
        Opcode.SXTW: 2,
        Opcode.UXTB: 2, Opcode.UXTH: 2,
        Opcode.CLZ: 2, Opcode.CLS: 2,
        Opcode.RBIT: 2, Opcode.REV: 2,
        Opcode.FADD: 3, Opcode.FSUB: 3,
        Opcode.FMUL: 3, Opcode.FDIV: 3,
        Opcode.FCMP: 2, Opcode.FCVT: 2,
        Opcode.FABS: 2, Opcode.FNEG: 2,
        Opcode.LDRS: 2, Opcode.STRS: 2,
        Opcode.VADD: 3, Opcode.VSUB: 3,
        Opcode.VMUL: 3, Opcode.VDIV: 3,
        Opcode.VLD1: 2, Opcode.VST1: 2,
        Opcode.LB: 2, Opcode.LH: 2, Opcode.LW: 2,
        Opcode.LD: 2, Opcode.SB: 2, Opcode.SH: 2,
        Opcode.SW: 2, Opcode.SD: 2,
        Opcode.ADDI: 3, Opcode.SLTI: 3,
        Opcode.SLTIU: 3, Opcode.XORI: 3,
        Opcode.ORI: 3, Opcode.ANDI: 3,
        Opcode.SLLI: 3, Opcode.SRLI: 3,
        Opcode.SRAI: 3,
        Opcode.BEQ: 3, Opcode.BNE: 3,
        Opcode.BLT: 3, Opcode.BGE: 3,
        Opcode.BLTU: 3, Opcode.BGEU: 3,
        Opcode.JALR: 2, Opcode.JAL: 2,
        Opcode.LUI: 2, Opcode.AUIPC: 2
    }
    
    CONDITIONS: Set[str] = {
        'EQ', 'NE', 'CS', 'CC', 'MI', 'PL', 'VS', 'VC',
        'HI', 'LS', 'GE', 'LT', 'GT', 'LE', 'AL', 'NV'
    }
    
    DATA_DIRECTIVES: Set[str] = {'DB', 'DW', 'DD', 'DQ'}
    
    PL_KEYWORDS: Dict[str, str] = {
        'set': 'MOV', 'load': 'LOAD', 'store': 'STORE',
        'add': 'ADD', 'subtract': 'SUB', 'multiply': 'MUL', 'divide': 'DIV',
        'and': 'AND', 'or': 'OR', 'xor': 'XOR',
        'shift_left': 'SHL', 'shift_right': 'SHR',
        'increment': 'INC', 'decrement': 'DEC',
        'compare': 'CMP', 'jump': 'JMP', 'jump_zero': 'JZ',
        'jump_not_zero': 'JNZ', 'jump_equal': 'JE',
        'jump_less': 'JL', 'jump_greater': 'JG',
        'push': 'PUSH', 'pop': 'POP', 'call': 'CALL',
        'return': 'RET', 'input': 'IN', 'output': 'OUT', 'stop': 'HALT',
        'add_set': 'ADDS', 'subtract_set': 'SUBS',
        'add_carry': 'ADDC', 'subtract_carry': 'SUBC',
        'logical_shift_left': 'LSL', 'logical_shift_right': 'LSR',
        'arithmetic_shift_right': 'ASR', 'rotate_right': 'ROR',
        'move_not': 'MVN', 'exclusive_or': 'EOR',
        'bit_clear': 'BIC', 'or_not': 'ORN',
        'load_register': 'LDR', 'store_register': 'STR',
        'load_pair': 'LDP', 'store_pair': 'STP',
        'compare_branch_zero': 'CBZ', 'compare_branch_not_zero': 'CBNZ',
        'test_branch_zero': 'TBZ', 'test_branch_not_zero': 'TBNZ',
        'branch': 'B', 'branch_link': 'BL', 'branch_register': 'BR',
        'nop': 'NOP', 'wait_event': 'WFE', 'wait_interrupt': 'WFI', 'send_event': 'SEV',
        'select': 'CSEL', 'select_increment': 'CSINC',
        'select_invert': 'CSINV', 'select_negate': 'CSNEG',
        'sign_extend_byte': 'SXTB', 'sign_extend_half': 'SXTH',
        'sign_extend_word': 'SXTW', 'zero_extend_byte': 'UXTB',
        'zero_extend_half': 'UXTH', 'count_leading_zeros': 'CLZ',
        'count_leading_sign': 'CLS', 'reverse_bits': 'RBIT',
        'reverse_bytes': 'REV',
        'float_add': 'FADD', 'float_subtract': 'FSUB',
        'float_multiply': 'FMUL', 'float_divide': 'FDIV',
        'float_compare': 'FCMP', 'float_convert': 'FCVT',
        'float_abs': 'FABS', 'float_negate': 'FNEG',
        'load_float': 'LDRS', 'store_float': 'STRS',
        'vec_add': 'VADD', 'vec_subtract': 'VSUB',
        'vec_multiply': 'VMUL', 'vec_divide': 'VDIV',
        'vec_load': 'VLD1', 'vec_store': 'VST1',
        'load_byte': 'LB', 'load_half': 'LH', 'load_word': 'LW', 'load_double': 'LD',
        'store_byte': 'SB', 'store_half': 'SH', 'store_word': 'SW', 'store_double': 'SD',
        'add_imm': 'ADDI', 'set_less_than_imm': 'SLTI',
        'set_less_than_imm_unsigned': 'SLTIU',
        'xor_imm': 'XORI', 'or_imm': 'ORI', 'and_imm': 'ANDI',
        'shift_left_logical_imm': 'SLLI',
        'shift_right_logical_imm': 'SRLI',
        'shift_right_arithmetic_imm': 'SRAI',
        'branch_equal': 'BEQ', 'branch_not_equal': 'BNE',
        'branch_less_than': 'BLT', 'branch_greater_equal': 'BGE',
        'branch_less_than_unsigned': 'BLTU',
        'branch_greater_equal_unsigned': 'BGEU',
        'jump_and_link_register': 'JALR',
        'jump_and_link': 'JAL',
        'load_upper_imm': 'LUI', 'add_upper_imm_pc': 'AUIPC'
    }

# ==================== Exceptions ====================

class CPUSimulatorError(Exception):
    def __init__(self, message: str, detail: Optional[Any] = None):
        self.message = message
        self.detail = detail
        super().__init__(message)

class AssemblerError(CPUSimulatorError):
    def __init__(self, line: str, detail: str, line_num: Optional[int] = None, filename: Optional[str] = None):
        self.line = line
        self.line_num = line_num
        self.filename = filename
        location = f"{filename}:{line_num}" if filename and line_num else f"Line {line_num}" if line_num else ""
        prefix = f"{location}: " if location else ""
        super().__init__(f"{prefix}Assembler error: {line} - {detail}")

class ExecutionError(CPUSimulatorError):
    pass

class MemoryError(CPUSimulatorError):
    pass

# ==================== Logger ====================

class Logger:
    def __init__(self, console: Optional[Console] = None, level: str = 'INFO'):
        self.console = console or Console()
        self.level = self._parse_level(level)
        self.log_file = None
        self._color_support = sys.stdout.isatty()
    
    def _parse_level(self, level: str) -> int:
        levels = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}
        return levels.get(level.upper(), 1)
    
    def set_log_file(self, filename: str) -> None:
        self.log_file = open(filename, 'w', encoding='utf-8')
    
    def _colorize(self, text: str, color: str) -> str:
        if self._color_support:
            return f"{color}{text}{Colors.RESET}"
        return text
    
    def _log(self, message: str, level: str, color: str) -> None:
        if self._parse_level(level) >= self.level:
            timestamp = time.strftime("%H:%M:%S")
            color_map = {
                'DEBUG': Colors.BLUE,
                'INFO': Colors.GREEN,
                'WARNING': Colors.YELLOW,
                'ERROR': Colors.RED,
                'CRITICAL': f"{Colors.RED}{Colors.BOLD}"
            }
            colored_level = self._colorize(f"[{level}]", color_map.get(level, Colors.WHITE))
            formatted = f"[{timestamp}] {colored_level} {message}"
            if self.log_file:
                self.log_file.write(f"[{timestamp}] [{level}] {message}\n")
                self.log_file.flush()
            if self.console:
                self.console.print(formatted)
    
    def debug(self, msg: str) -> None:
        self._log(msg, 'DEBUG', 'blue')
    def info(self, msg: str) -> None:
        self._log(msg, 'INFO', 'green')
    def warning(self, msg: str) -> None:
        self._log(msg, 'WARNING', 'yellow')
    def error(self, msg: str) -> None:
        self._log(msg, 'ERROR', 'red')
    def critical(self, msg: str) -> None:
        self._log(msg, 'CRITICAL', 'bold red')
    
    def close(self) -> None:
        if self.log_file:
            self.log_file.close()

# ==================== Config ====================

@dataclass
class Config:
    mem_size: int = Constants.DEFAULT_MEM_SIZE
    stack_size: int = 128
    step_mode: bool = False
    debug_mode: bool = False
    auto_save_crom: bool = False
    execution_interval: float = 0.1
    max_execution_time: float = 60.0
    interactive_mode: bool = True
    sandbox_mode: bool = False
    max_instructions: int = 100000
    allow_io: bool = True
    log_level: str = 'INFO'
    log_file: Optional[str] = None
    show_memory_bytes: int = 32
    show_vector_regs: bool = True
    show_timings: bool = True
    strict_mode: bool = False
    output_file: Optional[str] = None
    optimize: int = 0
    enable_jit: bool = False
    cache_size: int = 64
    cache_assoc: int = 4
    profile: bool = False
    compress_crom: bool = True
    compile_to_bin: bool = False
    
    @classmethod
    def from_args(cls, args: List[str]) -> 'Config':
        config = cls()
        i = 1
        while i < len(args):
            arg = args[i]
            if arg == '--step':
                config.step_mode = True
                config.interactive_mode = True
            elif arg == '--debug':
                config.debug_mode = True
                config.interactive_mode = True
            elif arg == '--save':
                config.auto_save_crom = True
            elif arg == '--sandbox':
                config.sandbox_mode = True
            elif arg == '--jit':
                config.enable_jit = True
            elif arg == '--profile':
                config.profile = True
            elif arg == '--no-compress':
                config.compress_crom = False
            elif arg == '--compile':
                config.compile_to_bin = True
            elif arg == '--output' and i + 1 < len(args):
                config.output_file = args[i + 1]
                i += 1
            elif arg == '--optimize' and i + 1 < len(args):
                try:
                    config.optimize = int(args[i + 1])
                except ValueError:
                    pass
                i += 1
            elif arg == '--mem-size' and i + 1 < len(args):
                try:
                    config.mem_size = int(args[i + 1])
                except ValueError:
                    pass
                i += 1
            elif arg == '--max-instructions' and i + 1 < len(args):
                try:
                    config.max_instructions = int(args[i + 1])
                except ValueError:
                    pass
                i += 1
            elif arg == '--cache-size' and i + 1 < len(args):
                try:
                    config.cache_size = int(args[i + 1])
                except ValueError:
                    pass
                i += 1
            elif arg == '--log-level' and i + 1 < len(args):
                config.log_level = args[i + 1]
                i += 1
            elif arg == '--log-file' and i + 1 < len(args):
                config.log_file = args[i + 1]
                i += 1
            elif arg == '--no-io':
                config.allow_io = False
            elif arg == '--strict':
                config.strict_mode = True
            i += 1
        return config
    
    def validate(self) -> None:
        if self.mem_size < 64:
            self.mem_size = 64
        if self.max_instructions < 1:
            self.max_instructions = 1
        if self.optimize < 0:
            self.optimize = 0
        if self.optimize > 3:
            self.optimize = 3
        if self.cache_size < 8:
            self.cache_size = 8

# ==================== Cache System ====================

class CacheLine:
    def __init__(self, tag: int = 0, valid: bool = False, dirty: bool = False):
        self.tag = tag
        self.valid = valid
        self.dirty = dirty
        self.data: Dict[int, int] = {}
        self.last_used: int = 0

class Cache:
    def __init__(self, size: int = 64, assoc: int = 4, line_size: int = 16):
        self.size = size
        self.assoc = assoc
        self.line_size = line_size
        self.num_sets = size // assoc
        
        self.cache: Dict[int, List[CacheLine]] = {}
        self._init_cache()
        
        self.hits = 0
        self.misses = 0
        self.clock = 0
        
        self.memory = None
    
    def _init_cache(self) -> None:
        for set_idx in range(self.num_sets):
            self.cache[set_idx] = [CacheLine() for _ in range(self.assoc)]
    
    def _get_set_index(self, addr: int) -> int:
        return (addr // self.line_size) % self.num_sets
    
    def _get_tag(self, addr: int) -> int:
        return addr // (self.line_size * self.num_sets)
    
    def read(self, addr: int) -> int:
        set_idx = self._get_set_index(addr)
        tag = self._get_tag(addr)
        
        cache_set = self.cache[set_idx]
        
        for line in cache_set:
            if line.valid and line.tag == tag:
                self.hits += 1
                line.last_used = self.clock
                self.clock += 1
                if addr in line.data:
                    return line.data[addr]
                if self.memory:
                    base_addr = (addr // self.line_size) * self.line_size
                    for i in range(self.line_size):
                        line.data[base_addr + i] = self.memory.read_byte(base_addr + i)
                    return line.data[addr]
                return 0
        
        self.misses += 1
        
        evict_idx = 0
        oldest_time = self.clock
        for i, line in enumerate(cache_set):
            if not line.valid:
                evict_idx = i
                break
            if line.last_used < oldest_time:
                oldest_time = line.last_used
                evict_idx = i
        
        evicted = cache_set[evict_idx]
        if evicted.valid and evicted.dirty and self.memory:
            for addr_val, data in evicted.data.items():
                self.memory.write_byte(addr_val, data)
        
        cache_set[evict_idx] = CacheLine(tag=tag, valid=True, dirty=False)
        cache_set[evict_idx].last_used = self.clock
        self.clock += 1
        
        if self.memory:
            base_addr = (addr // self.line_size) * self.line_size
            for i in range(self.line_size):
                cache_set[evict_idx].data[base_addr + i] = self.memory.read_byte(base_addr + i)
            return cache_set[evict_idx].data[addr]
        
        return 0
    
    def write(self, addr: int, value: int) -> None:
        set_idx = self._get_set_index(addr)
        tag = self._get_tag(addr)
        
        cache_set = self.cache[set_idx]
        
        for line in cache_set:
            if line.valid and line.tag == tag:
                line.data[addr] = value
                line.dirty = True
                line.last_used = self.clock
                self.clock += 1
                self.hits += 1
                return
        
        self.misses += 1
        
        evict_idx = 0
        oldest_time = self.clock
        for i, line in enumerate(cache_set):
            if not line.valid:
                evict_idx = i
                break
            if line.last_used < oldest_time:
                oldest_time = line.last_used
                evict_idx = i
        
        evicted = cache_set[evict_idx]
        if evicted.valid and evicted.dirty and self.memory:
            for addr_val, data in evicted.data.items():
                self.memory.write_byte(addr_val, data)
        
        cache_set[evict_idx] = CacheLine(tag=tag, valid=True, dirty=True)
        cache_set[evict_idx].data[addr] = value
        cache_set[evict_idx].last_used = self.clock
        self.clock += 1
    
    def flush(self) -> None:
        if not self.memory:
            return
        
        for cache_set in self.cache.values():
            for line in cache_set:
                if line.valid and line.dirty:
                    for addr_val, data in line.data.items():
                        self.memory.write_byte(addr_val, data)
                    line.dirty = False
    
    def warmup(self, instructions: List[Tuple]) -> None:
        for pc, _ in enumerate(instructions):
            self.read(pc)
    
    def get_stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hits / total if total > 0 else 0,
            'miss_rate': self.misses / total if total > 0 else 0,
            'total_accesses': total
        }

# ==================== Branch Predictor ====================

class BranchPredictor:
    def __init__(self):
        self.saturating_counters: Dict[int, int] = {}
        self.correct_predictions = 0
        self.total_predictions = 0
    
    def predict(self, pc: int) -> bool:
        return self.saturating_counters.get(pc, 2) >= 2
    
    def update(self, pc: int, taken: bool) -> None:
        counter = self.saturating_counters.get(pc, 2)
        if taken:
            counter = min(3, counter + 1)
        else:
            counter = max(0, counter - 1)
        self.saturating_counters[pc] = counter
    
    def record_prediction(self, predicted: bool, actual: bool) -> None:
        self.total_predictions += 1
        if predicted == actual:
            self.correct_predictions += 1
    
    def get_accuracy(self) -> float:
        if self.total_predictions == 0:
            return 1.0
        return self.correct_predictions / self.total_predictions

# ==================== Performance Counters ====================

class PerformanceCounters:
    def __init__(self):
        self.counters = {
            'cycles': 0,
            'instructions': 0,
            'branches': 0,
            'branch_mispredictions': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'memory_reads': 0,
            'memory_writes': 0,
            'stalls': 0,
            'flops': 0
        }
        self.branch_predictor = BranchPredictor()
    
    def record_instruction(self, opcode: str) -> None:
        self.counters['instructions'] += 1
        if opcode in ('JMP', 'JZ', 'JNZ', 'JE', 'JL', 'JG', 'B', 'BL', 'BR', 'BEQ', 'BNE', 'BLT', 'BGE'):
            self.counters['branches'] += 1
        if opcode in ('FADD', 'FSUB', 'FMUL', 'FDIV', 'VADD', 'VSUB', 'VMUL', 'VDIV'):
            self.counters['flops'] += 1
    
    def record_branch_result(self, pc: int, taken: bool, predicted: bool) -> None:
        self.branch_predictor.record_prediction(predicted, taken)
        if taken != predicted:
            self.counters['branch_mispredictions'] += 1
        self.branch_predictor.update(pc, taken)
    
    def record_cache(self, hit: bool) -> None:
        if hit:
            self.counters['cache_hits'] += 1
        else:
            self.counters['cache_misses'] += 1
    
    def record_memory_read(self) -> None:
        self.counters['memory_reads'] += 1
    
    def record_memory_write(self) -> None:
        self.counters['memory_writes'] += 1
    
    def get_ipc(self) -> float:
        if self.counters['cycles'] == 0:
            return 0
        return self.counters['instructions'] / self.counters['cycles']
    
    def get_stats(self) -> Dict[str, Any]:
        stats = self.counters.copy()
        stats['ipc'] = self.get_ipc()
        stats['branch_accuracy'] = self.branch_predictor.get_accuracy()
        total_cache = stats['cache_hits'] + stats['cache_misses']
        stats['cache_hit_rate'] = stats['cache_hits'] / total_cache if total_cache > 0 else 0
        return stats
    
    def display(self, console: Console) -> None:
        stats = self.get_stats()
        table = Table(title="Performance Counters")
        table.add_column("Metric")
        table.add_column("Value")
        
        for key, value in stats.items():
            if key in ('branch_accuracy', 'cache_hit_rate'):
                table.add_row(key.replace('_', ' ').title(), f"{value*100:.1f}%")
            elif key == 'ipc':
                table.add_row("Instructions Per Cycle", f"{value:.2f}")
            else:
                table.add_row(key.replace('_', ' ').title(), str(value))
        console.print(str(table))

# ==================== JIT Compiler ====================

class JITCompiler:
    def __init__(self, cpu: 'CPU'):
        self.cpu = cpu
        self.compiled_blocks: Dict[int, Callable] = {}
        self.block_cache: Dict[int, Tuple[int, int]] = {}
        self.compilation_count = 0
        self.total_calls = 0
        self.cache_hits = 0
        self.hit_rate = 0.0
    
    def compile_block(self, start_pc: int, end_pc: int) -> Optional[Callable]:
        self.total_calls += 1
        
        if start_pc in self.compiled_blocks:
            self.cache_hits += 1
            self.hit_rate = self.cache_hits / self.total_calls
            return self.compiled_blocks[start_pc]
        
        if start_pc >= len(self.cpu.instructions) or end_pc > len(self.cpu.instructions):
            return None
        
        try:
            instructions = self.cpu.instructions[start_pc:end_pc]
            if not instructions:
                return None
            
            source_parts = []
            source_parts.append("def compiled_block(cpu, memory, regs, vec_regs, pstate):")
            source_parts.append(f"    pc = {start_pc}")
            source_parts.append("    regs_list = regs._regs")
            source_parts.append("    try:")
            
            for i, (opcode, args) in enumerate(instructions):
                pc = start_pc + i
                source_parts.append(f"        # pc={pc}: {opcode} {args}")
                code_line = self._gen_instruction_code(opcode, args, pc)
                if code_line:
                    source_parts.append(f"        {code_line}")
                else:
                    return None
            
            source_parts.append("    except Exception as e:")
            source_parts.append("        raise")
            source_parts.append("    return pc")
            source = "\n".join(source_parts)
            
            namespace = {
                'cpu': self.cpu,
                'memory': self.cpu.memory,
                'regs': self.cpu.regs,
                'vec_regs': self.cpu.vec_regs,
                'pstate': self.cpu.pstate
            }
            exec(compile(source, '<JIT>', 'exec'), namespace)
            compiled_func = namespace['compiled_block']
            self.compiled_blocks[start_pc] = compiled_func
            self.block_cache[start_pc] = (start_pc, end_pc)
            self.compilation_count += 1
            return compiled_func
        except Exception as e:
            self.cpu.logger.debug(f"JIT compilation failed for block at {start_pc}: {e}")
            return None
    
    def _gen_instruction_code(self, opcode: str, args: List, pc: int) -> Optional[str]:
        if opcode == 'MOV':
            return self._gen_move(args)
        elif opcode in ('ADD', 'SUB', 'MUL', 'DIV', 'AND', 'OR', 'XOR', 'SHL', 'SHR'):
            return self._gen_binary_op(opcode, args)
        elif opcode == 'INC':
            return self._gen_inc(args)
        elif opcode == 'DEC':
            return self._gen_dec(args)
        elif opcode == 'CMP':
            return self._gen_cmp(args)
        elif opcode in ('JMP', 'JZ', 'JNZ', 'JE', 'JL', 'JG'):
            return self._gen_jump(opcode, args)
        elif opcode == 'PUSH':
            return self._gen_push(args)
        elif opcode == 'POP':
            return self._gen_pop(args)
        elif opcode == 'CALL':
            return self._gen_call(args)
        elif opcode == 'RET':
            return self._gen_ret()
        elif opcode == 'IN':
            return self._gen_in(args)
        elif opcode == 'OUT':
            return self._gen_out(args)
        elif opcode == 'HALT':
            return self._gen_halt()
        elif opcode == 'LOAD':
            return self._gen_load(args)
        elif opcode == 'STORE':
            return self._gen_store(args)
        elif opcode in ('LSL', 'LSR'):
            return self._gen_shift(opcode, args)
        elif opcode == 'LDR':
            return self._gen_ldr(args)
        elif opcode == 'STR':
            return self._gen_str(args)
        elif opcode in ('FADD', 'FSUB', 'FMUL', 'FDIV'):
            return self._gen_float_op(opcode, args)
        elif opcode in ('VADD', 'VSUB', 'VMUL', 'VDIV'):
            return self._gen_vector_op(opcode, args)
        else:
            return None
    
    def _gen_move(self, args: List) -> str:
        rd = args[0][1]
        src = self._get_val_expr(args[1])
        return f"regs_list[{rd}] = {src}"
    
    def _gen_binary_op(self, opcode: str, args: List) -> str:
        rd = args[0][1]
        src = self._get_val_expr(args[1])
        op_map = {
            'ADD': '+', 'SUB': '-', 'MUL': '*', 'DIV': '//',
            'AND': '&', 'OR': '|', 'XOR': '^', 'SHL': '<<', 'SHR': '>>'
        }
        op = op_map.get(opcode, '+')
        return f"regs_list[{rd}] = regs_list[{rd}] {op} {src}"
    
    def _gen_shift(self, opcode: str, args: List) -> str:
        rd = args[0][1]
        rn = args[1][1]
        shift = self._get_val_expr(args[2])
        if opcode == 'LSL':
            return f"regs_list[{rd}] = regs_list[{rn}] << ({shift} & 0x3F)"
        else:
            return f"regs_list[{rd}] = regs_list[{rn}] >> ({shift} & 0x3F)"
    
    def _gen_ldr(self, args: List) -> str:
        rd = args[0][1]
        addr = self._get_val_expr(args[1])
        return f"regs_list[{rd}] = memory.read_dword({addr})"
    
    def _gen_str(self, args: List) -> str:
        rs = args[0][1]
        addr = self._get_val_expr(args[1])
        return f"memory.write_dword({addr}, regs_list[{rs}])"
    
    def _gen_float_op(self, opcode: str, args: List) -> str:
        rd = args[0][1]
        rn = args[1][1]
        rm = args[2][1]
        op_map = {'FADD': '+', 'FSUB': '-', 'FMUL': '*', 'FDIV': '/'}
        op = op_map.get(opcode, '+')
        return f"regs_list[{rd}] = int(float(regs_list[{rn}]) {op} float(regs_list[{rm}]))"
    
    def _gen_vector_op(self, opcode: str, args: List) -> str:
        rd = args[0][1]
        rn = args[1][1]
        rm = args[2][1]
        op_map = {'VADD': '+', 'VSUB': '-', 'VMUL': '*', 'VDIV': '/'}
        op = op_map.get(opcode, '+')
        return f"""
    v1 = vec_regs.read_vector({rn})
    v2 = vec_regs.read_vector({rm})
    vec_regs.write_vector({rd}, [v1[i] {op} v2[i] for i in range(4)])"""
    
    def _gen_inc(self, args: List) -> str:
        rd = args[0][1]
        return f"regs_list[{rd}] = regs_list[{rd}] + 1"
    
    def _gen_dec(self, args: List) -> str:
        rd = args[0][1]
        return f"regs_list[{rd}] = regs_list[{rd}] - 1"
    
    def _gen_cmp(self, args: List) -> str:
        r1 = self._get_val_expr(args[0])
        r2 = self._get_val_expr(args[1])
        return f"""
    result = {r1} - {r2}
    pstate['Z'] = (result == 0)
    pstate['N'] = (result < 0)"""
    
    def _gen_jump(self, opcode: str, args: List) -> str:
        target = self._get_val_expr(args[0])
        if opcode == 'JMP':
            return f"pc = {target}"
        elif opcode == 'JZ':
            return f"if pstate['Z']: pc = {target}"
        elif opcode == 'JNZ':
            return f"if not pstate['Z']: pc = {target}"
        elif opcode == 'JE':
            return f"if pstate['Z']: pc = {target}"
        elif opcode == 'JL':
            return f"if pstate['N']: pc = {target}"
        elif opcode == 'JG':
            return f"if not pstate['Z'] and not pstate['N']: pc = {target}"
        return f"pc = {target}"
    
    def _gen_push(self, args: List) -> str:
        rs = args[0][1]
        return f"""
    cpu.sp -= 1
    memory.write_byte(cpu.sp, regs_list[{rs}])"""
    
    def _gen_pop(self, args: List) -> str:
        rd = args[0][1]
        return f"""
    regs_list[{rd}] = memory.read_byte(cpu.sp)
    cpu.sp += 1"""
    
    def _gen_call(self, args: List) -> str:
        target = self._get_val_expr(args[0])
        return f"""
    cpu.sp -= 1
    memory.write_byte(cpu.sp, pc + 1)
    pc = {target}"""
    
    def _gen_ret(self) -> str:
        return f"""
    pc = memory.read_byte(cpu.sp)
    cpu.sp += 1"""
    
    def _gen_in(self, args: List) -> str:
        rd = args[0][1]
        return f"""
    try: regs_list[{rd}] = int(input())
    except: regs_list[{rd}] = 0"""
    
    def _gen_out(self, args: List) -> str:
        val = self._get_val_expr(args[0])
        return f"print({val})"
    
    def _gen_halt(self) -> str:
        return "return -1"
    
    def _gen_load(self, args: List) -> str:
        rd = args[0][1]
        addr = self._get_val_expr(args[1])
        return f"regs_list[{rd}] = memory.read_dword({addr})"
    
    def _gen_store(self, args: List) -> str:
        rs = args[0][1]
        addr = self._get_val_expr(args[1])
        return f"memory.write_dword({addr}, regs_list[{rs}])"
    
    def _get_val_expr(self, arg: Tuple) -> str:
        if not arg:
            return "0"
        
        arg_type = arg[0]
        if arg_type == 'reg':
            return f"regs_list[{arg[1]}]"
        elif arg_type == 'imm':
            return str(arg[1])
        elif arg_type == 'vec':
            return f"vec_regs.read_vector({arg[1]})[0]"
        elif arg_type == 'mem':
            return f"memory.read_byte({arg[1]})"
        elif arg_type == 'float':
            return str(arg[1])
        elif arg_type == 'label':
            return str(arg[1])
        return "0"
    
    def invalidate_block(self, pc: int) -> None:
        if pc in self.compiled_blocks:
            del self.compiled_blocks[pc]
        if pc in self.block_cache:
            del self.block_cache[pc]
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            'blocks_compiled': self.compilation_count,
            'cached_blocks': len(self.compiled_blocks),
            'cached_ranges': len(self.block_cache),
            'total_calls': self.total_calls,
            'cache_hits': self.cache_hits,
            'hit_rate': self.hit_rate
        }

# ==================== Fast Memory ====================

class FastMemory:
    def __init__(self, size: int = Constants.DEFAULT_MEM_SIZE):
        self._memory = bytearray(size)
        self._size = size
        self._view = memoryview(self._memory)
        self._protection: Dict[int, str] = {}
        self._cache = None
    
    def set_cache(self, cache: 'Cache') -> None:
        self._cache = cache
        cache.memory = self
    
    def set_protection(self, addr: int, perms: str, size: int = 1) -> None:
        for i in range(size):
            self._protection[addr + i] = perms
    
    def check_access(self, addr: int, access: str) -> bool:
        perm = self._protection.get(addr, 'rwx')
        return access in perm
    
    def _check_bounds(self, addr: int, size: int = 1) -> None:
        if not 0 <= addr < self._size:
            raise MemoryError(f"Address {addr:#x} out of bounds")
        if addr + size > self._size:
            raise MemoryError(f"Address {addr:#x} + {size} out of bounds")
    
    def _check_protection(self, addr: int, access: str) -> None:
        if not self.check_access(addr, access):
            raise MemoryError(f"Memory protection violation at {addr:#x} for {access}")
    
    def read_byte(self, addr: int) -> int:
        self._check_bounds(addr)
        self._check_protection(addr, 'r')
        
        if self._cache:
            return self._cache.read(addr)
        
        return self._view[addr]
    
    def write_byte(self, addr: int, value: int) -> None:
        self._check_bounds(addr)
        self._check_protection(addr, 'w')
        
        self._view[addr] = value & 0xFF
        
        if self._cache:
            self._cache.write(addr, value & 0xFF)
    
    def read_word(self, addr: int) -> int:
        return self.read_byte(addr) | (self.read_byte(addr + 1) << 8)
    
    def write_word(self, addr: int, value: int) -> None:
        self.write_byte(addr, value & 0xFF)
        self.write_byte(addr + 1, (value >> 8) & 0xFF)
    
    def read_dword(self, addr: int) -> int:
        return (self.read_byte(addr) | (self.read_byte(addr + 1) << 8) |
                (self.read_byte(addr + 2) << 16) | (self.read_byte(addr + 3) << 24))
    
    def read_dword_fast(self, addr: int) -> int:
        if not 0 <= addr < self._size - 3:
            raise MemoryError(f"Address {addr:#x} out of bounds")
        return struct.unpack_from('<I', self._view, addr)[0]
    
    def write_dword(self, addr: int, value: int) -> None:
        self.write_byte(addr, value & 0xFF)
        self.write_byte(addr + 1, (value >> 8) & 0xFF)
        self.write_byte(addr + 2, (value >> 16) & 0xFF)
        self.write_byte(addr + 3, (value >> 24) & 0xFF)
    
    def write_dword_fast(self, addr: int, value: int) -> None:
        if not 0 <= addr < self._size - 3:
            raise MemoryError(f"Address {addr:#x} out of bounds")
        struct.pack_into('<I', self._view, addr, value & 0xFFFFFFFF)
    
    def read_float(self, addr: int) -> float:
        self._check_bounds(addr, 4)
        return struct.unpack_from('f', self._view, addr)[0]
    
    def write_float(self, addr: int, value: float) -> None:
        self._check_bounds(addr, 4)
        struct.pack_into('f', self._view, addr, value)
    
    def read_block(self, addr: int, size: int) -> bytes:
        self._check_bounds(addr, size)
        return bytes(self._view[addr:addr+size])
    
    def write_block(self, addr: int, data: bytes) -> None:
        self._check_bounds(addr, len(data))
        self._view[addr:addr+len(data)] = data
    
    def __len__(self) -> int:
        return self._size
    
    def display_memory(self, title: str = "Memory Dump", start: int = 0, count: int = 32,
                       console: Optional[Console] = None) -> None:
        if console is None:
            return
        table = Table(title=title)
        table.add_column("Address")
        table.add_column("Hex")
        table.add_column("ASCII")
        table.add_column("Prot")
        end = min(start + count, self._size)
        for i in range(start, end, 16):
            chunk = self._view[i:min(i+16, end)]
            hex_str = ' '.join(f'{b:02X}' for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            perm = self._protection.get(i, 'rwx')
            table.add_row(f"{i:04X}", hex_str, ascii_str, perm)
        console.print(str(table))
    
    def get_memory_snapshot(self, start: int = 0, count: int = -1) -> bytes:
        if count < 0:
            count = self._size - start
        return bytes(self._view[start:start+count])

# ==================== Register System ====================

class RegisterFile:
    def __init__(self, console: Optional[Console] = None, num_regs: int = Constants.NUM_REGISTERS):
        self.console = console or Console()
        self._regs = [0] * num_regs
    
    def read(self, idx: int) -> int:
        if idx == 31:
            return 0
        if not 0 <= idx < len(self._regs):
            raise ValueError(f"Invalid register index: {idx}")
        return self._regs[idx]
    
    def write(self, idx: int, value: int, pc: int = 0) -> None:
        if idx == 31:
            return
        if not 0 <= idx < len(self._regs):
            raise ValueError(f"Invalid register index: {idx}")
        self._regs[idx] = value
    
    def get_all(self) -> List[int]:
        return self._regs.copy()
    
    def display_registers(self, title: str = "Registers", extra_info: Optional[Dict[str, Any]] = None,
                         console: Optional[Console] = None) -> None:
        if console is None:
            console = self.console
        table = Table(title=title)
        table.add_column("Register")
        table.add_column("Value (Dec)")
        table.add_column("Value (Hex)")
        for i in range(16):
            val = self._regs[i]
            table.add_row(f"X{i}", str(val), f"{val:#x}")
        table.add_row("", "", "")
        for i in range(16, 31):
            val = self._regs[i]
            table.add_row(f"X{i}", str(val), f"{val:#x}")
        table.add_row("XZR", "0", "0x0")
        if extra_info:
            for key, value in extra_info.items():
                table.add_row(key, str(value), f"{value:#x}" if isinstance(value, int) else "")
        console.print(str(table))

# ==================== Vector Register System ====================

class VectorRegisterFile:
    def __init__(self, num_regs: int = Constants.NUM_VECTOR_REGISTERS):
        self._regs = [[0.0] * 4 for _ in range(num_regs)]
    
    def read_vector(self, idx: int) -> List[float]:
        if idx == 31:
            return [0.0, 0.0, 0.0, 0.0]
        if not 0 <= idx < len(self._regs):
            raise ValueError(f"Invalid vector register index: {idx}")
        return self._regs[idx].copy()
    
    def write_vector(self, idx: int, values: List[float]) -> None:
        if idx == 31:
            return
        if not 0 <= idx < len(self._regs):
            raise ValueError(f"Invalid vector register index: {idx}")
        if len(values) != 4:
            raise ValueError("Need 4 values")
        self._regs[idx] = values.copy()
    
    def read_scalar(self, idx: int, lane: int = 0) -> float:
        if idx == 31:
            return 0.0
        if not 0 <= idx < len(self._regs):
            raise ValueError(f"Invalid vector register index: {idx}")
        if not 0 <= lane < 4:
            raise ValueError(f"Invalid lane index: {lane}")
        return self._regs[idx][lane]
    
    def write_scalar(self, idx: int, value: float, lane: int = 0) -> None:
        if idx == 31:
            return
        if not 0 <= idx < len(self._regs):
            raise ValueError(f"Invalid vector register index: {idx}")
        if not 0 <= lane < 4:
            raise ValueError(f"Invalid lane index: {lane}")
        self._regs[idx][lane] = value
    
    def display_vector_registers(self, title: str = "Vector Registers", console: Optional[Console] = None) -> None:
        if console is None:
            return
        table = Table(title=title)
        table.add_column("Register")
        table.add_column("Lane 0")
        table.add_column("Lane 1")
        table.add_column("Lane 2")
        table.add_column("Lane 3")
        for i in range(32):
            vec = self._regs[i]
            if any(v != 0.0 for v in vec):
                table.add_row(f"V{i}", f"{vec[0]:.2f}", f"{vec[1]:.2f}", f"{vec[2]:.2f}", f"{vec[3]:.2f}")
        if table.rows:
            console.print(str(table))

# ==================== Statistics ====================

class InstructionProfiler:
    def __init__(self):
        self.cycles: Dict[str, int] = defaultdict(int)
        self.latency: Dict[str, int] = {
            'ADD': 1, 'SUB': 1, 'MUL': 3, 'DIV': 10,
            'LOAD': 4, 'STORE': 4, 'FADD': 3, 'FMUL': 5,
            'FDIV': 10, 'VADD': 2, 'VMUL': 4, 'VDIV': 8,
            'LSL': 1, 'LSR': 1, 'AND': 1, 'OR': 1, 'XOR': 1
        }
    
    def record(self, opcode: str) -> None:
        self.cycles[opcode] += self.latency.get(opcode, 1)
    
    def get_total_cycles(self) -> int:
        return sum(self.cycles.values())
    
    def display_report(self, console: Optional[Console] = None) -> None:
        if console is None:
            return
        total = self.get_total_cycles()
        table = Table(title="Instruction Cycle Profile")
        table.add_column("Instruction")
        table.add_column("Cycles")
        table.add_column("Percentage")
        for op, cycles in sorted(self.cycles.items(), key=lambda x: x[1], reverse=True)[:20]:
            pct = (cycles / total * 100) if total > 0 else 0
            table.add_row(op, str(cycles), f"{pct:.1f}%")
        console.print(str(table))

class Statistics:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.instruction_count = 0
        self.opcode_count: Dict[str, int] = defaultdict(int)
        self.execution_time = 0.0
        self.start_time: Optional[float] = None
        self.memory_reads = 0
        self.memory_writes = 0
        self.jit_blocks_used = 0
        self.jit_blocks_compiled = 0
        self.inst_profiler = InstructionProfiler()
        self.hot_instructions: Dict[str, int] = defaultdict(int)
        self.performance_counters = PerformanceCounters()
    
    def start(self):
        self.start_time = time.time()
    
    def stop(self):
        if self.start_time:
            self.execution_time = time.time() - self.start_time
    
    def record_instruction(self, opcode: str):
        self.instruction_count += 1
        self.opcode_count[opcode] += 1
        self.inst_profiler.record(opcode)
        self.hot_instructions[opcode] += 1
        self.performance_counters.record_instruction(opcode)
    
    def record_memory_read(self):
        self.memory_reads += 1
        self.performance_counters.record_memory_read()
    
    def record_memory_write(self):
        self.memory_writes += 1
        self.performance_counters.record_memory_write()
    
    def record_cache(self, hit: bool):
        self.performance_counters.record_cache(hit)
    
    def record_branch(self, pc: int, taken: bool, predicted: bool):
        self.performance_counters.record_branch_result(pc, taken, predicted)
    
    def get_hot_instructions(self, top_n: int = 10) -> List[Tuple[str, int]]:
        return sorted(self.hot_instructions.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    def display_summary(self, console: Optional[Console] = None, cache_stats: Optional[Dict] = None,
                        jit_stats: Optional[Dict] = None) -> None:
        if console is None:
            return
        
        table = Table(title="Execution Statistics")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Total Instructions", str(self.instruction_count))
        table.add_row("Total Cycles", str(self.inst_profiler.get_total_cycles()))
        table.add_row("CPI (Cycles/Inst)", f"{self.inst_profiler.get_total_cycles() / self.instruction_count:.2f}" if self.instruction_count > 0 else "N/A")
        table.add_row("Execution Time", f"{self.execution_time:.4f}s")
        if self.execution_time > 0:
            table.add_row("Instructions/sec", f"{self.instruction_count / self.execution_time:.2f}")
        table.add_row("Memory Reads", str(self.memory_reads))
        table.add_row("Memory Writes", str(self.memory_writes))
        
        perf_stats = self.performance_counters.get_stats()
        table.add_row("IPC", f"{perf_stats['ipc']:.2f}")
        table.add_row("Branch Accuracy", f"{perf_stats['branch_accuracy']*100:.1f}%")
        table.add_row("Cache Hit Rate", f"{perf_stats['cache_hit_rate']*100:.1f}%")
        
        if cache_stats:
            table.add_row("Cache Hits", str(cache_stats.get('hits', 0)))
            table.add_row("Cache Misses", str(cache_stats.get('misses', 0)))
        
        if jit_stats:
            table.add_row("JIT Calls", str(jit_stats.get('total_calls', 0)))
            table.add_row("JIT Cache Hits", str(jit_stats.get('cache_hits', 0)))
            table.add_row("JIT Hit Rate", f"{jit_stats.get('hit_rate', 0) * 100:.1f}%")
            table.add_row("JIT Blocks Compiled", str(jit_stats.get('blocks_compiled', 0)))
        
        console.print(str(table))
        
        if self.opcode_count:
            op_table = Table(title="Instruction Usage")
            op_table.add_column("Instruction")
            op_table.add_column("Count")
            op_table.add_column("Percentage")
            total = sum(self.opcode_count.values())
            for op, count in sorted(self.opcode_count.items(), key=lambda x: x[1], reverse=True)[:20]:
                pct = (count / total * 100) if total > 0 else 0
                op_table.add_row(op, str(count), f"{pct:.1f}%")
            console.print(str(op_table))
        
        self.inst_profiler.display_report(console)
        self.performance_counters.display(console)

# ==================== Debug Server ====================

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
    
    def record_state(self) -> None:
        snapshot = {
            'pc': self.cpu.pc,
            'regs': self.cpu.regs.get_all(),
            'sp': self.cpu.sp,
            'pstate': self.cpu.pstate.copy(),
            'timestamp': time.time()
        }
        self.execution_history.append(snapshot)
        if len(self.execution_history) > self.history_limit:
            self.execution_history.pop(0)
        self.history_index = len(self.execution_history) - 1
    
    def reverse_step(self) -> bool:
        if self.history_index > 0:
            self.history_index -= 1
            snapshot = self.execution_history[self.history_index]
            self.cpu.pc = snapshot['pc']
            for i, val in enumerate(snapshot['regs']):
                self.cpu.regs.write(i, val)
            self.cpu.sp = snapshot['sp']
            self.cpu.pstate = snapshot['pstate'].copy()
            return True
        return False
    
    def forward_step(self) -> bool:
        if self.history_index < len(self.execution_history) - 1:
            self.history_index += 1
            snapshot = self.execution_history[self.history_index]
            self.cpu.pc = snapshot['pc']
            for i, val in enumerate(snapshot['regs']):
                self.cpu.regs.write(i, val)
            self.cpu.sp = snapshot['sp']
            self.cpu.pstate = snapshot['pstate'].copy()
            return True
        return False
    
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
                        'pstate': self.cpu.pstate.copy()
                    }
                    if eval(bp.condition, {"__builtins__": {}}, namespace):
                        bp.hit_count += 1
                        self.cpu.console.print(f"{Colors.colorize('Conditional breakpoint hit', Colors.YELLOW)} at PC={self.cpu.pc:#x}: {bp.condition}")
                        return True
                except Exception as e:
                    self.cpu.logger.warning(f"Condition evaluation failed: {e}")
        return False
    
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
            if self.reverse_step():
                return "OK: Reversed one step"
            return "ERROR: No history available"
        elif command == 'forward':
            if self.forward_step():
                return "OK: Forward one step"
            return "ERROR: No forward history available"
        elif command == 'break':
            if len(parts) > 1:
                try:
                    addr = int(parts[1])
                    if len(parts) > 2:
                        condition = ' '.join(parts[2:])
                        self.add_conditional_breakpoint(addr, condition)
                        return f"OK: Conditional breakpoint set at {addr:#x}: {condition}"
                    else:
                        self.cpu.add_breakpoint(addr)
                        return f"OK: Breakpoint set at {addr:#x}"
                except ValueError:
                    return "ERROR: Invalid address"
            return "ERROR: Missing address"
        elif command == 'delete':
            if len(parts) > 1:
                try:
                    addr = int(parts[1])
                    self.cpu.remove_breakpoint(addr)
                    self.conditional_breakpoints = [bp for bp in self.conditional_breakpoints if bp.address != addr]
                    return f"OK: Breakpoint removed at {addr:#x}"
                except ValueError:
                    return "ERROR: Invalid address"
            return "ERROR: Missing address"
        elif command == 'watch':
            if len(parts) > 1:
                try:
                    addr = int(parts[1])
                    access = parts[2] if len(parts) > 2 else 'rw'
                    self.cpu.memory.set_protection(addr, access)
                    return f"OK: Watchpoint set at {addr:#x} for {access}"
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
                    addr = int(parts[1])
                    if len(parts) > 2:
                        value = int(parts[2])
                        self.cpu.memory.write_byte(addr, value)
                        return f"OK: mem[{addr:#x}] = {value:#x}"
                    else:
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
                    return self._format_breakpoints()
                elif parts[1] == 'regs':
                    return str(self.cpu.regs.get_all())
                elif parts[1] == 'pc':
                    return f"PC: {self.cpu.pc:#x}"
            return "ERROR: Missing info target"
        elif command == 'quit':
            self.running = False
            return "OK: Quitting"
        else:
            return f"ERROR: Unknown command: {command}"
    
    def _format_breakpoints(self) -> str:
        lines = ["Breakpoints:"]
        for bp in self.cpu.breakpoints:
            lines.append(f"  {bp:#x}")
        for bp in self.conditional_breakpoints:
            lines.append(f"  {bp.address:#x} (cond: {bp.condition}, hits: {bp.hit_count})")
        return "\n".join(lines)

# ==================== CIN Compiler (Fixed - Iterative Parser) ====================

class CINCompiler:
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.lines: List[str] = []
        self.instructions: List[Tuple[str, List[Tuple[str, int]]]] = []
        self.labels: Dict[str, int] = {}
        self.data_labels: Dict[str, int] = {}
        self.variables: Dict[str, Tuple[str, int]] = {}
        self.arrays: Dict[str, Tuple[str, List[int], int]] = {}
        self.string_literals: Dict[str, str] = {}
        self.current_line: int = 0
        self.breakpoints: Set[int] = set()
        self.reg_alloc: Dict[str, int] = {}
        self.next_reg: int = 0
        self.label_count: int = 0
        self.next_data_addr: int = 0
        self.current_function: Optional[str] = None
        self._expr_cache: Dict[str, int] = {}
    
    def compile(self, filename: str) -> Tuple[List[Tuple[str, List[Tuple[str, int]]]], Dict[str, int], Dict[str, int]]:
        self._reset()
        
        with open(filename, 'r', encoding='utf-8') as f:
            self.lines = f.readlines()
        
        self._parse()
        return self.instructions, self.labels, self.data_labels
    
    def _reset(self):
        self.instructions = []
        self.labels = {}
        self.data_labels = {}
        self.variables = {}
        self.arrays = {}
        self.string_literals = {}
        self.current_line = 0
        self.breakpoints = set()
        self.reg_alloc = {}
        self.next_reg = 0
        self.label_count = 0
        self.next_data_addr = 0
        self.current_function = None
        self._expr_cache = {}
    
    def _new_label(self) -> str:
        self.label_count += 1
        return f"_L{self.label_count}"
    
    def _alloc_reg(self, var: str) -> int:
        if var in self.reg_alloc:
            return self.reg_alloc[var]
        reg = self.next_reg
        self.next_reg += 1
        if self.next_reg > 30:
            self.next_reg = 0
        self.reg_alloc[var] = reg
        return reg
    
    def _parse(self):
        i = 0
        while i < len(self.lines):
            raw_line = self.lines[i]
            # Remove inline comments (handle strings properly)
            if '//' in raw_line:
                in_string = False
                escaped = False
                for j, ch in enumerate(raw_line):
                    if ch == '\\':
                        escaped = not escaped
                        continue
                    if ch == '"' and not escaped:
                        in_string = not in_string
                    elif ch == '/' and j + 1 < len(raw_line) and raw_line[j+1] == '/' and not in_string:
                        raw_line = raw_line[:j]
                        break
                    escaped = False
            
            line = raw_line.strip()
            line_num = i + 1
            self.current_line = line_num
            
            if not line or line.startswith('#'):
                i += 1
                continue
            
            if line.startswith('/*'):
                while i < len(self.lines) and not self.lines[i].strip().endswith('*/'):
                    i += 1
                i += 1
                continue
            
            try:
                if re.match(r'^(int|float|char|bool|string|byte|word|dword|qword)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\[', line):
                    self._parse_array(line)
                elif re.match(r'^(int|float|char|bool|string|byte|word|dword|qword)\s+[a-zA-Z_][a-zA-Z0-9_]*', line):
                    self._parse_variable(line)
                elif line.startswith('function ') or re.match(r'^(void|int|float|char|bool)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(', line):
                    self._parse_function(line)
                elif line == 'function main()' or line == 'main()':
                    self.labels['main'] = len(self.instructions)
                    self.current_function = 'main'
                elif line.startswith('if '):
                    self._parse_if(line)
                elif line.startswith('while '):
                    self._parse_while(line)
                elif line.startswith('for '):
                    self._parse_for(line)
                elif line == 'break':
                    self._emit_inst('JMP', [('label', 'break_end')])
                elif line == 'continue':
                    self._emit_inst('JMP', [('label', 'continue_start')])
                elif line == '}':
                    if self.current_function:
                        self._emit_inst('RET', [])
                        self.current_function = None
                elif line.startswith('return '):
                    self._parse_return(line)
                elif '=' in line and not line.startswith('if') and not line.startswith('while') and not line.startswith('for'):
                    self._parse_assignment(line)
                elif line.startswith('print') or line.startswith('println'):
                    self._parse_print(line)
                elif line.startswith('input'):
                    self._parse_input(line)
                else:
                    self._parse_statement(line)
            except Exception as e:
                raise CPUSimulatorError(f"Line {line_num}: {str(e)}")
            
            i += 1
        
        if 'main' not in self.labels and self.instructions:
            self.labels['main'] = 0
    
    def _parse_array(self, line: str):
        line = line.rstrip(';')
        
        array_pattern = r'^(int|float|char|bool|string|byte|word|dword|qword)\s+([a-zA-Z_][a-zA-Z0-9_]*)((?:\[[^\]]*\])+)(?:\s*=\s*(.+))?$'
        match = re.match(array_pattern, line)
        if not match:
            raise CPUSimulatorError(f"Invalid array declaration: {line}")
        
        var_type, var_name, dims_str, init = match.groups()
        
        dim_sizes = []
        for dim in re.findall(r'\[([^\]]*)\]', dims_str):
            dim = dim.strip()
            if dim == '':
                dim_sizes.append(-1)
            else:
                try:
                    dim_sizes.append(int(dim))
                except ValueError:
                    dim_sizes.append(-1)
        
        total_size = 1
        for d in dim_sizes:
            if d > 0:
                total_size *= d
        
        base_addr = self.next_data_addr
        self.next_data_addr += total_size * 4
        
        self.arrays[var_name] = (var_type, dim_sizes, base_addr)
        self.variables[var_name] = (var_type, base_addr)
        
        if init:
            init = init.strip()
            if init.startswith('{') and init.endswith('}'):
                values = init[1:-1].split(',')
                for idx, val_str in enumerate(values):
                    val = self._parse_expression_iterative(val_str.strip())
                    if idx < total_size:
                        addr = base_addr + idx * 4
                        self._emit_inst('MOV', [('reg', 0), ('imm', val)])
                        self._emit_inst('STORE', [('reg', 0), ('imm', addr)])
    
    def _parse_variable(self, line: str):
        line = line.rstrip(';')
        match = re.match(r'^(int|float|char|bool|string|byte|word|dword|qword)\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*=\s*(.+))?$', line)
        if not match:
            raise CPUSimulatorError(f"Invalid variable declaration: {line}")
        
        var_type, var_name, init = match.groups()
        reg = self._alloc_reg(var_name)
        self.variables[var_name] = (var_type, reg)
        
        if init:
            self._emit_assignment(var_name, init)
        else:
            self._emit_inst('MOV', [('reg', reg), ('imm', 0)])
    
    def _parse_function(self, line: str):
        match = re.match(r'^(function|void|int|float|char|bool)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)', line)
        if not match:
            raise CPUSimulatorError(f"Invalid function declaration: {line}")
        
        ret_type, func_name, params_str = match.groups()
        
        self.labels[func_name] = len(self.instructions)
        self.current_function = func_name
        
        params = []
        if params_str.strip():
            for p in params_str.split(','):
                p = p.strip()
                if p:
                    parts = p.split()
                    if len(parts) >= 2:
                        params.append((parts[0], parts[1]))
                    else:
                        params.append(('int', parts[0]))
        
        for param_type, param_name in params:
            reg = self._alloc_reg(param_name)
            self.variables[param_name] = (param_type, reg)
    
    def _parse_if(self, line: str):
        match = re.match(r'if\s*\((.+)\)', line)
        if not match:
            raise CPUSimulatorError(f"Invalid if statement: {line}")
        
        condition = match.group(1)
        else_label = self._new_label()
        end_label = self._new_label()
        
        self._parse_condition(condition, else_label)
        self._emit_inst('JMP', [('label', end_label)])
        self.labels[else_label] = len(self.instructions)
        self.labels[end_label] = len(self.instructions)
    
    def _parse_while(self, line: str):
        match = re.match(r'while\s*\((.+)\)', line)
        if not match:
            raise CPUSimulatorError(f"Invalid while statement: {line}")
        
        condition = match.group(1)
        start_label = self._new_label()
        end_label = self._new_label()
        
        self.labels[start_label] = len(self.instructions)
        self._parse_condition(condition, end_label)
        self._emit_inst('JMP', [('label', start_label)])
        self.labels[end_label] = len(self.instructions)
    
    def _parse_for(self, line: str):
        match = re.match(r'for\s*\(([^;]*);([^;]*);([^)]*)\)', line)
        if not match:
            raise CPUSimulatorError(f"Invalid for statement: {line}")
        
        init, cond, inc = match.groups()
        
        if init.strip():
            self._parse_statement(init.strip())
        
        start_label = self._new_label()
        end_label = self._new_label()
        
        self.labels[start_label] = len(self.instructions)
        self._parse_condition(cond.strip(), end_label)
        if inc.strip():
            self._parse_statement(inc.strip())
        self._emit_inst('JMP', [('label', start_label)])
        self.labels[end_label] = len(self.instructions)
    
    def _parse_return(self, line: str):
        value = line[7:].strip()
        if value:
            val = self._parse_expression_iterative(value)
            self._emit_inst('MOV', [('reg', 0), ('imm', val)])
        self._emit_inst('RET', [])
    
    def _parse_assignment(self, line: str):
        if '[' in line and ']' in line:
            parts = line.split('=', 1)
            if len(parts) != 2:
                raise CPUSimulatorError(f"Invalid array assignment: {line}")
            
            left = parts[0].strip()
            right = parts[1].strip().rstrip(';')
            
            array_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)((?:\[[^\]]*\])+)$', left)
            if array_match:
                arr_name, indices_str = array_match.groups()
                if arr_name in self.arrays:
                    arr_type, dims, base_addr = self.arrays[arr_name]
                    
                    offset = 0
                    index_exprs = re.findall(r'\[([^\]]*)\]', indices_str)
                    for idx, expr in enumerate(index_exprs):
                        idx_val = self._parse_expression_iterative(expr.strip())
                        if idx < len(dims) and dims[idx] > 0:
                            offset = idx_val * 4
                            break
                    
                    addr = base_addr + offset
                    val = self._parse_expression_iterative(right)
                    self._emit_inst('STORE', [('reg', val), ('imm', addr)])
                    return
        
        parts = line.split('=', 1)
        if len(parts) != 2:
            raise CPUSimulatorError(f"Invalid assignment: {line}")
        
        left = parts[0].strip()
        right = parts[1].strip().rstrip(';')
        self._emit_assignment(left, right)
    
    def _emit_assignment(self, left: str, right: str):
        right_val = self._parse_expression_iterative(right)
        
        if left in self.variables:
            var_type, reg = self.variables[left]
            self._emit_inst('MOV', [('reg', reg), ('imm', right_val)])
        else:
            reg = self._alloc_reg(left)
            self.variables[left] = ('int', reg)
            self._emit_inst('MOV', [('reg', reg), ('imm', right_val)])
    
    def _parse_expression_iterative(self, expr: str) -> int:
        """Iterative expression parser to avoid recursion depth issues"""
        expr = expr.strip()
        
        # Cache check
        if expr in self._expr_cache:
            return self._expr_cache[expr]
        
        # String literal
        if expr.startswith('"') and expr.endswith('"'):
            return 0
        
        # Number literal
        if re.match(r'^-?\d+$', expr):
            return int(expr)
        if re.match(r'^-?\d+\.\d+$', expr):
            return int(float(expr))
        
        # Boolean
        if expr in ('true', 'false'):
            return 1 if expr == 'true' else 0
        
        # Simple variable
        if expr in self.variables:
            _, reg = self.variables[expr]
            return reg
        
        # Array access: arr[i]
        array_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)((?:\[[^\]]*\])+)$', expr)
        if array_match:
            arr_name, indices_str = array_match.groups()
            if arr_name in self.arrays:
                arr_type, dims, base_addr = self.arrays[arr_name]
                offset = 0
                index_exprs = re.findall(r'\[([^\]]*)\]', indices_str)
                for idx, expr_str in enumerate(index_exprs):
                    idx_val = self._parse_expression_iterative(expr_str.strip())
                    if idx < len(dims) and dims[idx] > 0:
                        offset = idx_val * 4
                        break
                
                addr = base_addr + offset
                reg = self._alloc_reg(f"_tmp_{expr}")
                self._emit_inst('LOAD', [('reg', reg), ('imm', addr)])
                self._expr_cache[expr] = reg
                return reg
        
        # Parenthesized expression
        if expr.startswith('(') and expr.endswith(')'):
            result = self._parse_expression_iterative(expr[1:-1])
            self._expr_cache[expr] = result
            return result
        
        # Handle expressions with operators - use stack-based approach
        return self._parse_expression_with_stack(expr)

    def _parse_expression_with_stack(self, expr: str) -> int:
        """Parse expression using stack-based approach for better performance"""
        # Define operator precedence
        precedence = {
            '||': 1, '&&': 2,
            '|': 3, '^': 4, '&': 5,
            '==': 6, '!=': 6,
            '<': 7, '>': 7, '<=': 7, '>=': 7,
            '<<': 8, '>>': 8,
            '+': 9, '-': 9,
            '*': 10, '/': 10, '%': 10
        }
        
        # Tokenize the expression
        tokens = self._tokenize_expression(expr)
        if not tokens:
            return 0
        
        # Convert to postfix (RPN) using shunting-yard algorithm
        output_queue = []
        operator_stack = []
        
        for token in tokens:
            if self._is_number(token):
                output_queue.append(('number', int(token)))
            elif token in precedence:
                while (operator_stack and operator_stack[-1] in precedence and 
                       precedence[operator_stack[-1]] >= precedence[token]):
                    output_queue.append(('operator', operator_stack.pop()))
                operator_stack.append(token)
            elif token == '(':
                operator_stack.append(token)
            elif token == ')':
                while operator_stack and operator_stack[-1] != '(':
                    output_queue.append(('operator', operator_stack.pop()))
                if operator_stack and operator_stack[-1] == '(':
                    operator_stack.pop()
            elif token in self.variables:
                _, reg = self.variables[token]
                output_queue.append(('variable', reg))
            else:
                # Try to parse as number or variable
                try:
                    output_queue.append(('number', int(token)))
                except ValueError:
                    # Could be a function call or other identifier
                    if token in self.variables:
                        _, reg = self.variables[token]
                        output_queue.append(('variable', reg))
                    else:
                        return 0
        
        while operator_stack:
            if operator_stack[-1] not in ('(', ')'):
                output_queue.append(('operator', operator_stack.pop()))
            else:
                operator_stack.pop()
        
        # Evaluate postfix expression
        eval_stack = []
        
        for token_type, token_value in output_queue:
            if token_type == 'number':
                eval_stack.append(token_value)
            elif token_type == 'variable':
                eval_stack.append(token_value)
            elif token_type == 'operator':
                if len(eval_stack) < 2:
                    continue
                b = eval_stack.pop()
                a = eval_stack.pop()
                result = self._apply_operator(token_value, a, b)
                eval_stack.append(result)
        
        if eval_stack:
            return eval_stack[-1]
        return 0

    def _tokenize_expression(self, expr: str) -> List[str]:
        """Tokenize expression into tokens"""
        tokens = []
        current = ""
        i = 0
        
        while i < len(expr):
            ch = expr[i]
            
            if ch in '()':
                if current:
                    tokens.append(current)
                    current = ""
                tokens.append(ch)
            elif ch in ' \t':
                if current:
                    tokens.append(current)
                    current = ""
            elif ch in '+-*/%&|^<>':
                # Check for multi-character operators
                op = ch
                if i + 1 < len(expr) and expr[i+1] in '=&|':
                    op += expr[i+1]
                    i += 1
                elif ch == '<' and i + 1 < len(expr) and expr[i+1] == '<':
                    op += expr[i+1]
                    i += 1
                elif ch == '>' and i + 1 < len(expr) and expr[i+1] == '>':
                    op += expr[i+1]
                    i += 1
                elif ch == '=' and i + 1 < len(expr) and expr[i+1] == '=':
                    op += expr[i+1]
                    i += 1
                elif ch == '!' and i + 1 < len(expr) and expr[i+1] == '=':
                    op += expr[i+1]
                    i += 1
                
                if current:
                    tokens.append(current)
                    current = ""
                tokens.append(op)
            elif ch.isalnum() or ch == '_':
                current += ch
            else:
                # Skip unknown characters
                if current:
                    tokens.append(current)
                    current = ""
            
            i += 1
        
        if current:
            tokens.append(current)
        
        return tokens

    def _is_number(self, token: str) -> bool:
        """Check if token is a number"""
        try:
            int(token)
            return True
        except ValueError:
            return False

    def _apply_operator(self, op: str, a: int, b: int) -> int:
        """Apply binary operator"""
        op_map = {
            '+': lambda x, y: x + y,
            '-': lambda x, y: x - y,
            '*': lambda x, y: x * y,
            '/': lambda x, y: x // y if y != 0 else 0,
            '%': lambda x, y: x % y if y != 0 else 0,
            '&': lambda x, y: x & y,
            '|': lambda x, y: x | y,
            '^': lambda x, y: x ^ y,
            '<<': lambda x, y: x << y,
            '>>': lambda x, y: x >> y,
            '==': lambda x, y: 1 if x == y else 0,
            '!=': lambda x, y: 1 if x != y else 0,
            '<': lambda x, y: 1 if x < y else 0,
            '>': lambda x, y: 1 if x > y else 0,
            '<=': lambda x, y: 1 if x <= y else 0,
            '>=': lambda x, y: 1 if x >= y else 0,
            '&&': lambda x, y: 1 if x and y else 0,
            '||': lambda x, y: 1 if x or y else 0,
        }
        return op_map.get(op, lambda x, y: 0)(a, b)
    
    def _parse_condition(self, condition: str, else_label: str):
        condition = condition.strip()
        
        for comp in ['==', '!=', '<', '>', '<=', '>=']:
            if comp in condition:
                left, right = condition.split(comp, 1)
                left_val = self._parse_expression_iterative(left.strip())
                right_val = self._parse_expression_iterative(right.strip())
                self._emit_inst('CMP', [('reg', left_val), ('reg', right_val)])
                
                jump_map = {
                    '==': 'JE', '!=': 'JNZ',
                    '<': 'JL', '>': 'JG',
                    '<=': 'JZ', '>=': 'JZ'
                }
                jump_op = jump_map.get(comp, 'JZ')
                
                if comp == '<=':
                    self._emit_inst('JG', [('label', else_label)])
                elif comp == '>=':
                    self._emit_inst('JL', [('label', else_label)])
                else:
                    self._emit_inst(jump_op, [('label', else_label)])
                return
        
        val = self._parse_expression_iterative(condition)
        if isinstance(val, int):
            if val == 0:
                self._emit_inst('JMP', [('label', else_label)])
            return
        
        self._emit_inst('CMP', [('reg', val), ('imm', 0)])
        self._emit_inst('JE', [('label', else_label)])
    
    def _emit_inst(self, opcode: str, args: List[Tuple[str, Any]]):
        resolved_args = []
        for arg_type, arg_val in args:
            if arg_type == 'label':
                if isinstance(arg_val, str) and arg_val in self.labels:
                    resolved_args.append(('imm', self.labels[arg_val]))
                else:
                    resolved_args.append(('label', arg_val))
            elif arg_type == 'reg':
                resolved_args.append(('reg', arg_val))
            elif arg_type == 'imm':
                resolved_args.append(('imm', arg_val))
            else:
                resolved_args.append((arg_type, arg_val))
        self.instructions.append((opcode, resolved_args))
    
    def _parse_statement(self, line: str):
        if '(' in line and ')' in line:
            match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)$', line)
            if match:
                func_name, args = match.groups()
                self._emit_call(func_name, args)
                return
        
        if ':' in line and not line.startswith(' '):
            label = line.split(':')[0].strip()
            self.labels[label] = len(self.instructions)
            return
    
    def _emit_call(self, func_name: str, args: str) -> int:
        if func_name in ('print', 'println', 'input', 'read', 'write'):
            return self._emit_builtin(func_name, args)
        
        if func_name in self.labels:
            self._emit_inst('CALL', [('label', func_name)])
        else:
            if func_name == 'print':
                self._parse_print(f"print({args})")
            elif func_name == 'println':
                self._parse_print(f"println({args})")
            elif func_name == 'input':
                self._parse_input(f"input({args})")
        
        return 0
    
    def _emit_builtin(self, func: str, args: str) -> int:
        if func == 'print':
            self._parse_print(f"print({args})")
        elif func == 'println':
            self._parse_print(f"println({args})")
        elif func == 'input':
            self._parse_input(f"input({args})")
        return 0
    
    def _parse_print(self, line: str):
        match = re.match(r'(print|println)\s*\(([^)]*)\)', line)
        if match:
            func, args = match.groups()
            if args:
                # Handle multiple arguments separated by commas
                paren_count = 0
                current_arg = ""
                for ch in args:
                    if ch == '(':
                        paren_count += 1
                    elif ch == ')':
                        paren_count -= 1
                    elif ch == ',' and paren_count == 0:
                        if current_arg.strip():
                            val = self._parse_expression_iterative(current_arg.strip())
                            self._emit_inst('OUT', [('reg', val)])
                        current_arg = ""
                        continue
                    current_arg += ch
                if current_arg.strip():
                    val = self._parse_expression_iterative(current_arg.strip())
                    self._emit_inst('OUT', [('reg', val)])
                if func == 'println':
                    self._emit_inst('OUT', [('imm', 10)])
    
    def _parse_input(self, line: str):
        match = re.match(r'input\s*\(([^)]*)\)', line)
        if match:
            var = match.group(1).strip()
            if var in self.variables:
                _, reg = self.variables[var]
                self._emit_inst('IN', [('reg', reg)])
            else:
                reg = self._alloc_reg(var)
                self.variables[var] = ('int', reg)
                self._emit_inst('IN', [('reg', reg)])

# ==================== CPU Class ====================

class CPU:
    def __init__(self, config: Config, filename: str, 
                 crom_file: Optional[str] = None,
                 from_bin: bool = False,
                 console: Optional[Console] = None):
        
        self.console = console or Console()
        self.config = config
        self.filename = filename
        
        self.logger = Logger(self.console, config.log_level)
        if config.log_file:
            self.logger.set_log_file(config.log_file)
        
        self.memory = FastMemory(config.mem_size)
        self.cache = Cache(config.cache_size, config.cache_assoc)
        self.memory.set_cache(self.cache)
        
        self.regs = RegisterFile(self.console)
        self.vec_regs = VectorRegisterFile()
        
        self.pstate = {'N': False, 'Z': False, 'C': False, 'V': False}
        self.pc = 0
        self.sp = config.mem_size - 1
        
        self.instructions: List[Tuple[str, List[Tuple[str, int]]]] = []
        self.labels: Dict[str, int] = {}
        self.data_labels: Dict[str, int] = {}
        self.pl_source: List[str] = []
        
        self.stats = Statistics()
        self.jit = JITCompiler(self) if config.enable_jit else None
        self.profiler = None
        
        self.running = False
        self.is_debugging = False
        self.breakpoints: Set[int] = set()
        self.debug_server: Optional[DebugServer] = None
        
        self._init_dispatch_table()
        self._init_fast_dispatch()
        
        if filename.endswith('.cin'):
            self._compile_and_run(filename)
            return
        
        if from_bin:
            self.load_bin(filename)
        else:
            if crom_file is None:
                base = os.path.splitext(filename)[0]
                crom_file = base + '.crom'
            self.crom_file = crom_file
            self.load_crom(crom_file)
            
            if filename.endswith('.pl'):
                self.assemble_pl(filename)
            else:
                self.assemble(filename)
        
        self.cache.warmup(self.instructions)
        self.logger.info(f"CPU initialized, instructions: {len(self.instructions)}")
    
    def _init_dispatch_table(self):
        self._dispatch_table = {}
        
        self._dispatch_table['MOV'] = self._exec_mov
        self._dispatch_table['LOAD'] = self._exec_load
        self._dispatch_table['STORE'] = self._exec_store
        self._dispatch_table['ADD'] = self._exec_add
        self._dispatch_table['SUB'] = self._exec_sub
        self._dispatch_table['MUL'] = self._exec_mul
        self._dispatch_table['DIV'] = self._exec_div
        self._dispatch_table['AND'] = self._exec_and
        self._dispatch_table['OR'] = self._exec_or
        self._dispatch_table['XOR'] = self._exec_xor
        self._dispatch_table['SHL'] = self._exec_shl
        self._dispatch_table['SHR'] = self._exec_shr
        self._dispatch_table['INC'] = self._exec_inc
        self._dispatch_table['DEC'] = self._exec_dec
        self._dispatch_table['CMP'] = self._exec_cmp
        self._dispatch_table['JMP'] = self._exec_jmp
        self._dispatch_table['JZ'] = self._exec_jz
        self._dispatch_table['JNZ'] = self._exec_jnz
        self._dispatch_table['JE'] = self._exec_je
        self._dispatch_table['JL'] = self._exec_jl
        self._dispatch_table['JG'] = self._exec_jg
        self._dispatch_table['PUSH'] = self._exec_push
        self._dispatch_table['POP'] = self._exec_pop
        self._dispatch_table['CALL'] = self._exec_call
        self._dispatch_table['RET'] = self._exec_ret
        self._dispatch_table['IN'] = self._exec_in
        self._dispatch_table['OUT'] = self._exec_out
        self._dispatch_table['HALT'] = self._exec_halt
        self._dispatch_table['ADDS'] = self._exec_adds
        self._dispatch_table['SUBS'] = self._exec_subs
        self._dispatch_table['LSL'] = self._exec_lsl
        self._dispatch_table['LSR'] = self._exec_lsr
        self._dispatch_table['LDR'] = self._exec_ldr
        self._dispatch_table['STR'] = self._exec_str
        self._dispatch_table['CBZ'] = self._exec_cbz
        self._dispatch_table['CBNZ'] = self._exec_cbnz
        self._dispatch_table['B'] = self._exec_b
        self._dispatch_table['BL'] = self._exec_bl
        self._dispatch_table['BR'] = self._exec_br
        self._dispatch_table['NOP'] = self._exec_nop
        self._dispatch_table['FADD'] = self._exec_fadd
        self._dispatch_table['FSUB'] = self._exec_fsub
        self._dispatch_table['FMUL'] = self._exec_fmul
        self._dispatch_table['FDIV'] = self._exec_fdiv
        self._dispatch_table['FCMP'] = self._exec_fcmp
        self._dispatch_table['LDRS'] = self._exec_ldrs
        self._dispatch_table['STRS'] = self._exec_strs
        self._dispatch_table['VADD'] = self._exec_vadd
        self._dispatch_table['VSUB'] = self._exec_vsub
        self._dispatch_table['VMUL'] = self._exec_vmul
        self._dispatch_table['VDIV'] = self._exec_vdiv
        self._dispatch_table['VLD1'] = self._exec_vld1
        self._dispatch_table['VST1'] = self._exec_vst1
        self._dispatch_table['LB'] = self._exec_lb
        self._dispatch_table['LH'] = self._exec_lh
        self._dispatch_table['LW'] = self._exec_lw
        self._dispatch_table['LD'] = self._exec_ld
        self._dispatch_table['SB'] = self._exec_sb
        self._dispatch_table['SH'] = self._exec_sh
        self._dispatch_table['SW'] = self._exec_sw
        self._dispatch_table['SD'] = self._exec_sd
        self._dispatch_table['ADDI'] = self._exec_addi
        self._dispatch_table['SLTI'] = self._exec_slti
        self._dispatch_table['SLTIU'] = self._exec_sltiu
        self._dispatch_table['XORI'] = self._exec_xori
        self._dispatch_table['ORI'] = self._exec_ori
        self._dispatch_table['ANDI'] = self._exec_andi
        self._dispatch_table['SLLI'] = self._exec_slli
        self._dispatch_table['SRLI'] = self._exec_srli
        self._dispatch_table['SRAI'] = self._exec_srai
        self._dispatch_table['BEQ'] = self._exec_beq
        self._dispatch_table['BNE'] = self._exec_bne
        self._dispatch_table['BLT'] = self._exec_blt
        self._dispatch_table['BGE'] = self._exec_bge
        self._dispatch_table['BLTU'] = self._exec_bltu
        self._dispatch_table['BGEU'] = self._exec_bgeu
        self._dispatch_table['JALR'] = self._exec_jalr
        self._dispatch_table['JAL'] = self._exec_jal
        self._dispatch_table['LUI'] = self._exec_lui
        self._dispatch_table['AUIPC'] = self._exec_auipc
    
    def _init_fast_dispatch(self):
        self._fast_dispatch = {
            'MOV': self._exec_mov,
            'ADD': self._exec_add,
            'SUB': self._exec_sub,
            'MUL': self._exec_mul,
            'DIV': self._exec_div,
            'AND': self._exec_and,
            'OR': self._exec_or,
            'XOR': self._exec_xor,
            'INC': self._exec_inc,
            'DEC': self._exec_dec,
            'CMP': self._exec_cmp,
            'JMP': self._exec_jmp,
            'LOAD': self._exec_load,
            'STORE': self._exec_store,
            'PUSH': self._exec_push,
            'POP': self._exec_pop,
            'CALL': self._exec_call,
            'RET': self._exec_ret,
            'HALT': self._exec_halt
        }
    
    def _compile_and_run(self, filename: str) -> None:
        self.logger.info(f"Compiling CIN: {filename}")
        
        compiler = CINCompiler(self.console)
        
        try:
            self.instructions, self.labels, self.data_labels = compiler.compile(filename)
            self.logger.info(f"CIN compiled: {len(self.instructions)} instructions")
            
            if self.config.compile_to_bin:
                output_file = self.config.output_file or os.path.splitext(filename)[0] + '.bin'
                self.save_bin(output_file)
                self.logger.info(f"Binary saved to {output_file}")
                return
            
            self.cache.warmup(self.instructions)
            self.logger.info("Starting execution")
            
            if 'main' in self.labels:
                self.pc = self.labels['main']
            else:
                self.pc = 0
            
            self.run()
            
        except Exception as e:
            self.logger.error(f"Compilation failed: {e}")
            raise

    # ==================== CROM Operations ====================
    
    def load_crom(self, crom_file: str) -> None:
        if not os.path.exists(crom_file):
            self._create_default_crom(crom_file)
            return
        
        with open(crom_file, 'rb') as f:
            data = f.read()
        
        if len(data) < 8:
            raise CPUSimulatorError(f".crom file too short: {len(data)} bytes")
        
        magic = data[:4]
        if magic == Constants.CROM_MAGIC:
            version = data[4]
            
            if version == 3:
                if len(data) < 16:
                    raise CPUSimulatorError(".crom header incomplete")
                
                mem_size = struct.unpack('<I', data[5:9])[0]
                flags = data[9]
                compressed = bool(flags & 0x01)
                offset = 16
                if compressed:
                    try:
                        decompressed = zlib.decompress(data[offset:])
                        bytes_data = decompressed[:min(mem_size, len(decompressed))]
                    except zlib.error as e:
                        raise CPUSimulatorError(f"Failed to decompress .crom: {e}")
                else:
                    bytes_data = data[offset:offset+mem_size]
                
                for i, byte in enumerate(bytes_data):
                    if i < len(self.memory):
                        self.memory.write_byte(i, byte)
                
                self.logger.info(f"Loaded .crom v3: {len(bytes_data)} bytes, compressed={compressed}")
            else:
                raise CPUSimulatorError(f"Unsupported .crom version: {version}")
        else:
            mem_size = struct.unpack('<I', data[:4])[0]
            bytes_data = data[4:4+mem_size]
            for i, byte in enumerate(bytes_data):
                if i < len(self.memory):
                    self.memory.write_byte(i, byte)
            self.logger.info(f"Loaded .crom (legacy): {len(bytes_data)} bytes")
    
    def _create_default_crom(self, crom_file: str) -> None:
        self.save_crom(crom_file)
        self.logger.info(f"Created default .crom: {crom_file}")
    
    def save_crom(self, crom_file: Optional[str] = None) -> None:
        if crom_file is None:
            crom_file = self.crom_file
        
        self.cache.flush()
        mem_data = bytes(self.memory._memory)
        
        flags = 0
        if self.config.compress_crom:
            flags |= 0x01
        
        data_to_write = mem_data
        if self.config.compress_crom:
            data_to_write = zlib.compress(mem_data, level=6)
        
        with open(crom_file, 'wb') as f:
            f.write(Constants.CROM_MAGIC)
            f.write(struct.pack('<B', Constants.CROM_VERSION))
            f.write(struct.pack('<I', len(mem_data)))
            f.write(struct.pack('<B', flags))
            checksum = zlib.crc32(data_to_write) & 0xFFFFFFFF
            f.write(struct.pack('<I', checksum))
            f.write(b'\x00\x00')
            f.write(data_to_write)
        
        self.logger.info(f".crom saved to {crom_file}")

    # ==================== Assembler ====================
    
    def assemble_pl(self, filename: str) -> None:
        self.pl_source = []
        raw_lines = []
        
        abs_path = os.path.abspath(filename)
        dir_path = os.path.dirname(abs_path)
        
        if not os.path.exists(abs_path):
            raise CPUSimulatorError(f"File '{filename}' not found")
        
        with open(abs_path, 'r', encoding='utf-8') as f:
            for line_num, raw in enumerate(f, 1):
                line = raw
                if '#' in line:
                    line = line[:line.index('#')]
                if '//' in line:
                    line = line[:line.index('//')]
                line = line.strip()
                
                if not line:
                    continue
                
                if line.startswith('#include'):
                    parts = line.split()
                    if len(parts) < 2:
                        raise AssemblerError(line, "#include format error", line_num, filename)
                    inc_file = parts[1].strip('"<>')
                    inc_path = os.path.join(dir_path, inc_file)
                    if not os.path.exists(inc_path):
                        raise AssemblerError(line, f"Include file '{inc_file}' not found", line_num, filename)
                    sub_lines = self._preprocess_pl(inc_path, set())
                    raw_lines.extend(sub_lines)
                else:
                    raw_lines.append((line, line_num, filename))
                    self.pl_source.append(line)
        
        self._assemble_pl_lines(raw_lines, filename)
        self.logger.info(f"PL assembly successful: {len(self.instructions)} instructions")
    
    def _preprocess_pl(self, filename: str, loaded: Set[str]) -> List[Tuple[str, int, str]]:
        if filename in loaded:
            return []
        
        loaded.add(filename)
        abs_path = os.path.abspath(filename)
        dir_path = os.path.dirname(abs_path)
        
        if not os.path.exists(abs_path):
            raise CPUSimulatorError(f"File '{filename}' not found")
        
        lines = []
        with open(abs_path, 'r', encoding='utf-8') as f:
            for line_num, raw in enumerate(f, 1):
                line = raw
                if '#' in line:
                    line = line[:line.index('#')]
                if '//' in line:
                    line = line[:line.index('//')]
                line = line.strip()
                
                if not line:
                    continue
                
                if line.startswith('#include'):
                    parts = line.split()
                    if len(parts) < 2:
                        raise AssemblerError(line, "#include format error", line_num, filename)
                    inc_file = parts[1].strip('"<>')
                    inc_path = os.path.join(dir_path, inc_file)
                    if not os.path.exists(inc_path):
                        raise AssemblerError(line, f"Include file '{inc_file}' not found", line_num, filename)
                    lines.extend(self._preprocess_pl(inc_path, loaded))
                else:
                    lines.append((line, line_num, filename))
        
        return lines
    
    def _assemble_pl_lines(self, lines: List[Tuple[str, int, str]], filename: str) -> None:
        self.instructions = []
        self.labels = {}
        self.data_labels = {}
        
        data_addr = 0
        instr_index = 0
        current_section = 'TEXT'
        parsed_lines = []
        
        i = 0
        while i < len(lines):
            line, line_num, fname = lines[i]
            
            if line.upper() in ['.TEXT', '.CODE', 'TEXT', 'CODE']:
                current_section = 'TEXT'
                i += 1
                continue
            elif line.upper() in ['.DATA', 'DATA']:
                current_section = 'DATA'
                i += 1
                continue
            
            if ':' in line and not line.startswith('.'):
                parts = line.split(':', 1)
                label = parts[0].strip()
                rest = parts[1].strip() if len(parts) > 1 else ''
                
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', label):
                    raise AssemblerError(line, f"Invalid label: {label}", line_num, fname)
                
                if current_section == 'TEXT':
                    self.labels[label] = instr_index
                else:
                    self.data_labels[label] = data_addr
                
                if rest:
                    line = rest
                else:
                    i += 1
                    continue
            
            if current_section == 'DATA':
                self._handle_data_directive_pl(line, line_num, fname, data_addr)
                i += 1
                continue
            
            if line:
                parsed_lines.append((line, instr_index, line_num, fname))
                instr_index += 1
            
            i += 1
        
        for line, idx, line_num, fname in parsed_lines:
            self._parse_pl_instruction(line, idx, line_num, fname)
    
    def _handle_data_directive_pl(self, line: str, line_num: int, fname: str, data_addr: int) -> None:
        parts = line.split()
        if not parts:
            return
        
        directive = parts[0].upper()
        if directive not in Constants.DATA_DIRECTIVES:
            if directive in ['BYTE', 'byte']:
                directive = 'DB'
            elif directive in ['WORD', 'word']:
                directive = 'DW'
            elif directive in ['DWORD', 'dword']:
                directive = 'DD'
            elif directive in ['QWORD', 'qword']:
                directive = 'DQ'
            else:
                raise AssemblerError(line, f"Unknown data directive: {directive}", line_num, fname)
        
        values = []
        for val_str in ' '.join(parts[1:]).split(','):
            val_str = val_str.strip()
            if val_str.startswith('0x'):
                values.append(int(val_str, 16))
            elif val_str.startswith('0b'):
                values.append(int(val_str[2:], 2))
            elif val_str.startswith('0o'):
                values.append(int(val_str[2:], 8))
            elif val_str.startswith("'") and val_str.endswith("'"):
                values.append(ord(val_str[1]))
            elif val_str.startswith('"') and val_str.endswith('"'):
                for ch in val_str[1:-1]:
                    values.append(ord(ch))
                values.append(0)
            else:
                try:
                    values.append(self.parse_immediate(val_str))
                except ValueError:
                    raise AssemblerError(line, f"Invalid data value: {val_str}", line_num, fname)
        
        for val in values:
            if directive == 'DB':
                if data_addr < len(self.memory):
                    self.memory.write_byte(data_addr, val & 0xFF)
                    data_addr += 1
            elif directive == 'DW':
                if data_addr + 1 < len(self.memory):
                    self.memory.write_word(data_addr, val & 0xFFFF)
                    data_addr += 2
            elif directive == 'DD':
                if data_addr + 3 < len(self.memory):
                    self.memory.write_dword(data_addr, val)
                    data_addr += 4
    
    def parse_immediate(self, val: str) -> int:
        val = val.strip()
        if val.startswith('0x') or val.startswith('0X'):
            return int(val, 16)
        if val.startswith('0b') or val.startswith('0B'):
            return int(val[2:], 2)
        if val.startswith('0o') or val.startswith('0O'):
            return int(val[2:], 8)
        try:
            return int(val)
        except ValueError:
            return int(float(val))
    
    def _parse_pl_instruction(self, line: str, idx: int, line_num: int, fname: str) -> None:
        parts = line.split()
        if not parts:
            return
        
        keyword = parts[0].lower()
        
        if keyword in Constants.PL_KEYWORDS:
            opcode = Constants.PL_KEYWORDS[keyword]
        else:
            opcode = keyword.upper()
            if opcode not in Constants.OPCODE_NAME_TO_ENUM:
                if keyword in self.labels:
                    self._parse_pl_instruction(f"{line} {keyword}", idx, line_num, fname)
                    return
                if keyword in self.data_labels:
                    self._parse_pl_instruction(f"{line} {keyword}", idx, line_num, fname)
                    return
                raise AssemblerError(line, f"Unknown instruction or keyword: {keyword}", line_num, fname)
        
        expected_args = Constants.ARG_COUNTS.get(Constants.OPCODE_NAME_TO_ENUM.get(opcode), -1)
        args = []
        i = 1
        
        while i < len(parts):
            arg = parts[i]
            
            if re.match(r'^[xX]([0-9]|[12][0-9]|3[01])$', arg):
                idx_reg = int(arg[1:])
                args.append(('reg', idx_reg if idx_reg != 31 else 31))
            elif re.match(r'^[rR]([0-9]|[12][0-9]|3[01])$', arg):
                idx_reg = int(arg[1:])
                args.append(('reg', idx_reg if idx_reg != 31 else 31))
            elif re.match(r'^[wW]([0-9]|[12][0-9]|3[01])$', arg):
                args.append(('reg', int(arg[1:])))
            elif re.match(r'^[vV]([0-9]|[12][0-9]|3[01])$', arg):
                args.append(('vec', int(arg[1:])))
            elif re.match(r'^[vV]([0-9]|[12][0-9]|3[01])\.([0-3])$', arg):
                m = re.match(r'^[vV]([0-9]|[12][0-9]|3[01])\.([0-3])$', arg)
                args.append(('vec_lane', int(m.group(1)), int(m.group(2))))
            elif arg.upper() in Constants.CONDITIONS:
                args.append(('cond', arg.upper()))
            elif re.match(r'^-?\d+\.\d+$', arg):
                args.append(('float', float(arg)))
            elif arg.startswith('[') and arg.endswith(']'):
                inner = arg[1:-1]
                if re.match(r'^[xXrR]([0-9]|[12][0-9]|3[01])$', inner):
                    args.append(('mem', int(inner[1:])))
                else:
                    try:
                        args.append(('mem', self.parse_immediate(inner)))
                    except ValueError:
                        args.append(('mem', inner))
            elif arg.startswith('#'):
                try:
                    args.append(('imm', self.parse_immediate(arg[1:])))
                except ValueError:
                    args.append(('imm', arg[1:]))
            elif re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', arg):
                if arg in self.labels:
                    args.append(('imm', self.labels[arg]))
                elif arg in self.data_labels:
                    args.append(('imm', self.data_labels[arg]))
                else:
                    args.append(('label', arg))
            elif re.match(r'^-?\d+$', arg):
                args.append(('imm', int(arg)))
            elif arg.startswith('0x') or arg.startswith('0X'):
                args.append(('imm', int(arg, 16)))
            elif arg.startswith('0b') or arg.startswith('0B'):
                args.append(('imm', int(arg[2:], 2)))
            elif arg.startswith('0o') or arg.startswith('0O'):
                args.append(('imm', int(arg[2:], 8)))
            else:
                raise AssemblerError(line, f"Unable to parse operand: {arg}", line_num, fname)
            
            i += 1
        
        if expected_args >= 0 and self.config.strict_mode:
            actual_args = len(args)
            if expected_args != actual_args:
                raise AssemblerError(line, f"Argument count mismatch: expected {expected_args}, got {actual_args}", line_num, fname)
        
        resolved_args = []
        for arg_item in args:
            if len(arg_item) == 2:
                arg_type, arg_val = arg_item
                if arg_type == 'label':
                    if arg_val in self.labels:
                        resolved_args.append(('imm', self.labels[arg_val]))
                    elif arg_val in self.data_labels:
                        resolved_args.append(('imm', self.data_labels[arg_val]))
                    else:
                        resolved_args.append(('imm', 0))
                else:
                    resolved_args.append((arg_type, arg_val))
            else:
                resolved_args.append(arg_item)
        
        self.instructions.append((opcode, resolved_args))
    
    def assemble(self, filename: str) -> None:
        self.logger.info(f"Assembling: {filename}")
        self.assemble_pl(filename)

    # ==================== Binary Operations ====================
    
    def load_bin(self, filename: str) -> None:
        with open(filename, 'rb') as f:
            magic = f.read(5)
            if magic != Constants.MAGIC_NUMBER:
                raise CPUSimulatorError("Invalid binary file")
            version = struct.unpack('<B', f.read(1))[0]
            mem_size = struct.unpack('<I', f.read(4))[0]
            instr_count = struct.unpack('<I', f.read(4))[0]
            entry_pc = struct.unpack('<I', f.read(4))[0]
            f.read(16)
            for i in range(mem_size):
                self.memory.write_byte(i, struct.unpack('<B', f.read(1))[0])
            self.instructions = []
            for _ in range(instr_count):
                data = f.read(Constants.INSTR_SIZE)
                if len(data) < Constants.INSTR_SIZE:
                    break
            self.pc = entry_pc
    
    def save_bin(self, filename: str) -> None:
        with open(filename, 'wb') as f:
            f.write(Constants.MAGIC_NUMBER)
            f.write(struct.pack('<B', Constants.VERSION))
            f.write(struct.pack('<I', len(self.memory)))
            f.write(struct.pack('<I', len(self.instructions)))
            f.write(struct.pack('<I', self.pc))
            f.write(b'\x00' * 16)
            for i in range(len(self.memory)):
                f.write(struct.pack('<B', self.memory.read_byte(i)))
            
            for opcode, args in self.instructions:
                op_idx = Constants.OPCODE_NAME_TO_ENUM.get(opcode, 0xFF)
                argc = len(args)
                f.write(struct.pack('<BBBBIBBBI', op_idx, argc, 0, 0, 0, 0, 0, 0, 0, 0, 0))
        
        self.logger.info(f"Binary saved to {filename}")

    # ==================== Value Helpers ====================
    
    def get_val(self, op: Tuple[str, int]) -> Union[int, float]:
        op_type, value = op
        if op_type == 'reg':
            if value == 31:
                return 0
            return self.regs.read(value)
        elif op_type == 'vec':
            return self.vec_regs.read_vector(value)[0]
        elif op_type == 'float':
            return float(value)
        elif op_type == 'mem':
            return self.memory.read_byte(value)
        elif op_type == 'cond':
            return 1 if self.get_condition(value) else 0
        else:
            return value
    
    def get_condition(self, cond: str) -> bool:
        cond_map = {
            'EQ': self.pstate['Z'],
            'NE': not self.pstate['Z'],
            'CS': self.pstate['C'],
            'CC': not self.pstate['C'],
            'MI': self.pstate['N'],
            'PL': not self.pstate['N'],
            'VS': self.pstate['V'],
            'VC': not self.pstate['V'],
            'HI': self.pstate['C'] and not self.pstate['Z'],
            'LS': not self.pstate['C'] or self.pstate['Z'],
            'GE': self.pstate['N'] == self.pstate['V'],
            'LT': self.pstate['N'] != self.pstate['V'],
            'GT': not self.pstate['Z'] and (self.pstate['N'] == self.pstate['V']),
            'LE': self.pstate['Z'] or (self.pstate['N'] != self.pstate['V']),
            'AL': True,
            'NV': False
        }
        return cond_map.get(cond.upper(), False)
    
    def add_breakpoint(self, addr: int) -> None:
        self.breakpoints.add(addr)
        self.logger.info(f"Breakpoint set at PC={addr:#x}")
    
    def remove_breakpoint(self, addr: int) -> None:
        self.breakpoints.discard(addr)
        self.logger.info(f"Breakpoint removed at PC={addr:#x}")
    
    def _set_pstate(self, result: int, carry: bool = False, overflow: bool = False) -> None:
        self.pstate['Z'] = (result == 0)
        self.pstate['N'] = (result < 0)
        self.pstate['C'] = carry
        self.pstate['V'] = overflow
    
    def _check_stack(self, size: int = 1) -> None:
        if self.sp - size < 0:
            self._extend_stack(size)
            return
        
        if self.sp - size < self.config.mem_size // 4:
            self.logger.warning(f"Stack approaching heap region (sp={self.sp}, size={size})")
    
    def _extend_stack(self, needed: int) -> None:
        new_size = max(self.config.mem_size * 2, self.sp + needed + 1024)
        self.logger.info(f"Extending stack from {self.config.mem_size} to {new_size} bytes")
        self.memory._memory = bytearray(new_size)
        self.memory._size = new_size
        self.memory._view = memoryview(self.memory._memory)
        self.config.mem_size = new_size

    # ==================== Instruction Handlers ====================
    
    def _exec_mov(self, args):
        rd = args[0][1]
        self.regs.write(rd, self.get_val(args[1]), self.pc)
        return True
    
    def _exec_add(self, args):
        rd = args[0][1]
        result = self.regs.read(rd) + self.get_val(args[1])
        self.regs.write(rd, result, self.pc)
        self._set_pstate(result)
        return True
    
    def _exec_sub(self, args):
        rd = args[0][1]
        result = self.regs.read(rd) - self.get_val(args[1])
        self.regs.write(rd, result, self.pc)
        self._set_pstate(result)
        return True
    
    def _exec_mul(self, args):
        rd = args[0][1]
        result = self.regs.read(rd) * self.get_val(args[1])
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_div(self, args):
        rd = args[0][1]
        divisor = self.get_val(args[1])
        if divisor == 0:
            raise ExecutionError("Division by zero")
        result = self.regs.read(rd) // divisor
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_and(self, args):
        rd = args[0][1]
        result = self.regs.read(rd) & self.get_val(args[1])
        self.regs.write(rd, result, self.pc)
        self._set_pstate(result)
        return True
    
    def _exec_or(self, args):
        rd = args[0][1]
        result = self.regs.read(rd) | self.get_val(args[1])
        self.regs.write(rd, result, self.pc)
        self._set_pstate(result)
        return True
    
    def _exec_xor(self, args):
        rd = args[0][1]
        result = self.regs.read(rd) ^ self.get_val(args[1])
        self.regs.write(rd, result, self.pc)
        self._set_pstate(result)
        return True
    
    def _exec_shl(self, args):
        rd = args[0][1]
        result = self.regs.read(rd) << self.get_val(args[1])
        self.regs.write(rd, result, self.pc)
        self._set_pstate(result)
        return True
    
    def _exec_shr(self, args):
        rd = args[0][1]
        result = self.regs.read(rd) >> self.get_val(args[1])
        self.regs.write(rd, result, self.pc)
        self._set_pstate(result)
        return True
    
    def _exec_inc(self, args):
        rd = args[0][1]
        result = self.regs.read(rd) + 1
        self.regs.write(rd, result, self.pc)
        self._set_pstate(result)
        return True
    
    def _exec_dec(self, args):
        rd = args[0][1]
        result = self.regs.read(rd) - 1
        self.regs.write(rd, result, self.pc)
        self._set_pstate(result)
        return True
    
    def _exec_cmp(self, args):
        r1 = self.get_val(args[0])
        r2 = self.get_val(args[1])
        result = r1 - r2
        self._set_pstate(result)
        return True
    
    def _exec_jmp(self, args):
        self.pc = self.get_val(args[0])
        return True
    
    def _exec_jz(self, args):
        if self.pstate['Z']:
            self.pc = self.get_val(args[0])
        return True
    
    def _exec_jnz(self, args):
        if not self.pstate['Z']:
            self.pc = self.get_val(args[0])
        return True
    
    def _exec_je(self, args):
        if self.pstate['Z']:
            self.pc = self.get_val(args[0])
        return True
    
    def _exec_jl(self, args):
        if self.pstate['N']:
            self.pc = self.get_val(args[0])
        return True
    
    def _exec_jg(self, args):
        if not self.pstate['Z'] and not self.pstate['N']:
            self.pc = self.get_val(args[0])
        return True
    
    def _exec_push(self, args):
        rs = args[0][1]
        self._check_stack()
        self.sp -= 1
        self.memory.write_byte(self.sp, self.regs.read(rs))
        return True
    
    def _exec_pop(self, args):
        rd = args[0][1]
        self._check_stack(0)
        if self.sp >= len(self.memory):
            raise ExecutionError("Stack underflow")
        value = self.memory.read_byte(self.sp)
        self.regs.write(rd, value, self.pc)
        self.sp += 1
        return True
    
    def _exec_call(self, args):
        self._check_stack()
        self.sp -= 1
        self.memory.write_byte(self.sp, self.pc + 1)
        self.pc = self.get_val(args[0])
        return True
    
    def _exec_ret(self, args):
        self._check_stack(0)
        if self.sp >= len(self.memory):
            raise ExecutionError("Stack underflow")
        self.pc = self.memory.read_byte(self.sp)
        self.sp += 1
        return True
    
    def _exec_in(self, args):
        if self.config.allow_io:
            rd = args[0][1]
            try:
                val = int(input())
                self.regs.write(rd, val, self.pc)
            except ValueError:
                self.regs.write(rd, 0, self.pc)
        return True
    
    def _exec_out(self, args):
        if self.config.allow_io:
            val = self.get_val(args[0])
            print(val)
        return True
    
    def _exec_halt(self, args):
        return False
    
    def _exec_load(self, args):
        rd = args[0][1]
        addr = self.get_val(args[1])
        self.stats.record_memory_read()
        value = self.memory.read_dword(addr)
        self.regs.write(rd, value, self.pc)
        return True
    
    def _exec_store(self, args):
        rs = args[0][1]
        addr = self.get_val(args[1])
        self.stats.record_memory_write()
        self.memory.write_dword(addr, self.regs.read(rs))
        return True
    
    def _exec_adds(self, args):
        rd, rn, oper2 = args[0][1], args[1][1], args[2]
        val1 = self.regs.read(rn)
        val2 = self.get_val(oper2)
        result = val1 + val2
        self._set_pstate(result, result > 0xFFFFFFFF, False)
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_subs(self, args):
        rd, rn, oper2 = args[0][1], args[1][1], args[2]
        val1 = self.regs.read(rn)
        val2 = self.get_val(oper2)
        result = val1 - val2
        self._set_pstate(result, val1 >= val2, False)
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_lsl(self, args):
        rd, rn, shift = args[0][1], args[1][1], args[2]
        val = self.regs.read(rn)
        shift_amount = self.get_val(shift) & 0x3F
        result = val << shift_amount
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_lsr(self, args):
        rd, rn, shift = args[0][1], args[1][1], args[2]
        val = self.regs.read(rn)
        shift_amount = self.get_val(shift) & 0x3F
        result = val >> shift_amount
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_ldr(self, args):
        rd, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_read()
        value = self.memory.read_dword(address)
        self.regs.write(rd, value, self.pc)
        return True
    
    def _exec_str(self, args):
        rs, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_write()
        self.memory.write_dword(address, self.regs.read(rs))
        return True
    
    def _exec_cbz(self, args):
        rn, label = args[0][1], args[1]
        if self.regs.read(rn) == 0:
            self.pc = self.get_val(label)
        return True
    
    def _exec_cbnz(self, args):
        rn, label = args[0][1], args[1]
        if self.regs.read(rn) != 0:
            self.pc = self.get_val(label)
        return True
    
    def _exec_b(self, args):
        self.pc = self.get_val(args[0])
        return True
    
    def _exec_bl(self, args):
        self._check_stack()
        self.sp -= 1
        self.memory.write_byte(self.sp, self.pc + 1)
        self.pc = self.get_val(args[0])
        return True
    
    def _exec_br(self, args):
        self.pc = self.regs.read(args[0][1])
        return True
    
    def _exec_nop(self, args):
        return True
    
    def _exec_fadd(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        val1 = self.vec_regs.read_scalar(rn)
        val2 = self.vec_regs.read_scalar(rm)
        result = val1 + val2
        self.vec_regs.write_scalar(rd, result)
        return True
    
    def _exec_fsub(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        val1 = self.vec_regs.read_scalar(rn)
        val2 = self.vec_regs.read_scalar(rm)
        result = val1 - val2
        self.vec_regs.write_scalar(rd, result)
        return True
    
    def _exec_fmul(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        val1 = self.vec_regs.read_scalar(rn)
        val2 = self.vec_regs.read_scalar(rm)
        result = val1 * val2
        self.vec_regs.write_scalar(rd, result)
        return True
    
    def _exec_fdiv(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        val1 = self.vec_regs.read_scalar(rn)
        val2 = self.vec_regs.read_scalar(rm)
        if val2 == 0:
            raise ExecutionError("Float division by zero")
        result = val1 / val2
        self.vec_regs.write_scalar(rd, result)
        return True
    
    def _exec_fcmp(self, args):
        rn, rm = args[0][1], args[1][1]
        val1 = self.vec_regs.read_scalar(rn)
        val2 = self.vec_regs.read_scalar(rm)
        diff = val1 - val2
        self.pstate['Z'] = (abs(diff) < 1e-10)
        self.pstate['N'] = (diff < 0)
        self.pstate['C'] = (val1 >= val2)
        return True
    
    def _exec_ldrs(self, args):
        rd, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_read()
        value = self.memory.read_float(address)
        self.vec_regs.write_scalar(rd, value)
        return True
    
    def _exec_strs(self, args):
        rs, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_write()
        value = self.vec_regs.read_scalar(rs)
        self.memory.write_float(address, value)
        return True
    
    def _exec_vadd(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        vec1 = self.vec_regs.read_vector(rn)
        vec2 = self.vec_regs.read_vector(rm)
        result = [vec1[i] + vec2[i] for i in range(4)]
        self.vec_regs.write_vector(rd, result)
        return True
    
    def _exec_vsub(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        vec1 = self.vec_regs.read_vector(rn)
        vec2 = self.vec_regs.read_vector(rm)
        result = [vec1[i] - vec2[i] for i in range(4)]
        self.vec_regs.write_vector(rd, result)
        return True
    
    def _exec_vmul(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        vec1 = self.vec_regs.read_vector(rn)
        vec2 = self.vec_regs.read_vector(rm)
        result = [vec1[i] * vec2[i] for i in range(4)]
        self.vec_regs.write_vector(rd, result)
        return True
    
    def _exec_vdiv(self, args):
        rd, rn, rm = args[0][1], args[1][1], args[2][1]
        vec1 = self.vec_regs.read_vector(rn)
        vec2 = self.vec_regs.read_vector(rm)
        result = []
        for i in range(4):
            if vec2[i] == 0:
                raise ExecutionError("Vector division by zero")
            result.append(vec1[i] / vec2[i])
        self.vec_regs.write_vector(rd, result)
        return True
    
    def _exec_vld1(self, args):
        rd, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_read()
        data = self.memory.read_block(address, 16)
        values = struct.unpack('ffff', data)
        self.vec_regs.write_vector(rd, list(values))
        return True
    
    def _exec_vst1(self, args):
        rs, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_write()
        values = self.vec_regs.read_vector(rs)
        data = struct.pack('ffff', *values)
        self.memory.write_block(address, data)
        return True
    
    def _exec_lb(self, args):
        rd, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_read()
        value = self.memory.read_byte(address)
        if value & 0x80:
            value |= 0xFFFFFF00
        self.regs.write(rd, value, self.pc)
        return True
    
    def _exec_lh(self, args):
        rd, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_read()
        value = self.memory.read_word(address)
        if value & 0x8000:
            value |= 0xFFFF0000
        self.regs.write(rd, value, self.pc)
        return True
    
    def _exec_lw(self, args):
        rd, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_read()
        value = self.memory.read_dword(address)
        self.regs.write(rd, value, self.pc)
        return True
    
    def _exec_ld(self, args):
        rd, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_read()
        value = 0
        for i in range(8):
            value |= self.memory.read_byte(address + i) << (i * 8)
        self.regs.write(rd, value, self.pc)
        return True
    
    def _exec_sb(self, args):
        rs, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_write()
        self.memory.write_byte(address, self.regs.read(rs) & 0xFF)
        return True
    
    def _exec_sh(self, args):
        rs, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_write()
        self.memory.write_word(address, self.regs.read(rs) & 0xFFFF)
        return True
    
    def _exec_sw(self, args):
        rs, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_write()
        self.memory.write_dword(address, self.regs.read(rs))
        return True
    
    def _exec_sd(self, args):
        rs, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_write()
        value = self.regs.read(rs)
        for i in range(8):
            self.memory.write_byte(address + i, (value >> (i * 8)) & 0xFF)
        return True
    
    def _exec_addi(self, args):
        rd, rs1, imm = args[0][1], args[1][1], args[2]
        imm_val = self.get_val(imm) if args[2][0] != 'imm' else args[2][1]
        result = self.regs.read(rs1) + imm_val
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_slti(self, args):
        rd, rs1, imm = args[0][1], args[1][1], args[2]
        imm_val = self.get_val(imm) if args[2][0] != 'imm' else args[2][1]
        result = 1 if self.regs.read(rs1) < imm_val else 0
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_sltiu(self, args):
        rd, rs1, imm = args[0][1], args[1][1], args[2]
        imm_val = self.get_val(imm) if args[2][0] != 'imm' else args[2][1]
        result = 1 if (self.regs.read(rs1) & 0xFFFFFFFF) < (imm_val & 0xFFFFFFFF) else 0
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_xori(self, args):
        rd, rs1, imm = args[0][1], args[1][1], args[2]
        imm_val = self.get_val(imm) if args[2][0] != 'imm' else args[2][1]
        result = self.regs.read(rs1) ^ imm_val
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_ori(self, args):
        rd, rs1, imm = args[0][1], args[1][1], args[2]
        imm_val = self.get_val(imm) if args[2][0] != 'imm' else args[2][1]
        result = self.regs.read(rs1) | imm_val
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_andi(self, args):
        rd, rs1, imm = args[0][1], args[1][1], args[2]
        imm_val = self.get_val(imm) if args[2][0] != 'imm' else args[2][1]
        result = self.regs.read(rs1) & imm_val
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_slli(self, args):
        rd, rs1, shamt = args[0][1], args[1][1], args[2]
        shamt_val = self.get_val(shamt) if args[2][0] != 'imm' else args[2][1]
        result = self.regs.read(rs1) << (shamt_val & 0x1F)
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_srli(self, args):
        rd, rs1, shamt = args[0][1], args[1][1], args[2]
        shamt_val = self.get_val(shamt) if args[2][0] != 'imm' else args[2][1]
        result = (self.regs.read(rs1) & 0xFFFFFFFF) >> (shamt_val & 0x1F)
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_srai(self, args):
        rd, rs1, shamt = args[0][1], args[1][1], args[2]
        shamt_val = self.get_val(shamt) if args[2][0] != 'imm' else args[2][1]
        result = self.regs.read(rs1) >> (shamt_val & 0x1F)
        self.regs.write(rd, result, self.pc)
        return True
    
    def _exec_beq(self, args):
        rs1, rs2, label = args[0][1], args[1][1], args[2]
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        taken = self.regs.read(rs1) == self.regs.read(rs2)
        self.stats.record_branch(self.pc, taken, predicted)
        if taken:
            self.pc = self.get_val(label)
        return True
    
    def _exec_bne(self, args):
        rs1, rs2, label = args[0][1], args[1][1], args[2]
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        taken = self.regs.read(rs1) != self.regs.read(rs2)
        self.stats.record_branch(self.pc, taken, predicted)
        if taken:
            self.pc = self.get_val(label)
        return True
    
    def _exec_blt(self, args):
        rs1, rs2, label = args[0][1], args[1][1], args[2]
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        taken = self.regs.read(rs1) < self.regs.read(rs2)
        self.stats.record_branch(self.pc, taken, predicted)
        if taken:
            self.pc = self.get_val(label)
        return True
    
    def _exec_bge(self, args):
        rs1, rs2, label = args[0][1], args[1][1], args[2]
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        taken = self.regs.read(rs1) >= self.regs.read(rs2)
        self.stats.record_branch(self.pc, taken, predicted)
        if taken:
            self.pc = self.get_val(label)
        return True
    
    def _exec_bltu(self, args):
        rs1, rs2, label = args[0][1], args[1][1], args[2]
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        taken = (self.regs.read(rs1) & 0xFFFFFFFF) < (self.regs.read(rs2) & 0xFFFFFFFF)
        self.stats.record_branch(self.pc, taken, predicted)
        if taken:
            self.pc = self.get_val(label)
        return True
    
    def _exec_bgeu(self, args):
        rs1, rs2, label = args[0][1], args[1][1], args[2]
        predicted = self.stats.performance_counters.branch_predictor.predict(self.pc)
        taken = (self.regs.read(rs1) & 0xFFFFFFFF) >= (self.regs.read(rs2) & 0xFFFFFFFF)
        self.stats.record_branch(self.pc, taken, predicted)
        if taken:
            self.pc = self.get_val(label)
        return True
    
    def _exec_jalr(self, args):
        rd, rs1, offset = args[0][1], args[1][1], args[2]
        offset_val = self.get_val(offset) if args[2][0] != 'imm' else args[2][1]
        target = self.regs.read(rs1) + offset_val
        self.regs.write(rd, self.pc + 1, self.pc)
        self.pc = target
        return True
    
    def _exec_jal(self, args):
        rd, label = args[0][1], args[1]
        self.regs.write(rd, self.pc + 1, self.pc)
        self.pc = self.get_val(label)
        return True
    
    def _exec_lui(self, args):
        rd, imm = args[0][1], args[1]
        imm_val = self.get_val(imm) if args[1][0] != 'imm' else args[1][1]
        self.regs.write(rd, (imm_val & 0xFFFFF) << 12, self.pc)
        return True
    
    def _exec_auipc(self, args):
        rd, imm = args[0][1], args[1]
        imm_val = self.get_val(imm) if args[1][0] != 'imm' else args[1][1]
        self.regs.write(rd, self.pc + ((imm_val & 0xFFFFF) << 12), self.pc)
        return True

    # ==================== Execution ====================

    def execute(self, opcode: str, args: List[Tuple[str, int]]) -> bool:
        self.pc += 1
        
        handler = self._fast_dispatch.get(opcode)
        if handler:
            result = handler(args)
            self.stats.record_instruction(opcode)
            return result
        
        handler = self._dispatch_table.get(opcode)
        if handler:
            result = handler(args)
            self.stats.record_instruction(opcode)
            return result
        else:
            raise ExecutionError(f"Unimplemented instruction: {opcode}")
    
    def execute_with_jit(self) -> bool:
        if not self.jit:
            return self.execute_fallback()
        
        pc = self.pc
        
        if pc in self.breakpoints:
            self.console.print(f"{Colors.colorize('Breakpoint hit', Colors.YELLOW)} at PC={pc:#x}")
            self.is_debugging = True
            self.debug_command_loop()
            return True
        
        if pc in self.jit.block_cache:
            start, end = self.jit.block_cache[pc]
            compiled_func = self.jit.compiled_blocks.get(pc)
            if compiled_func:
                try:
                    new_pc = compiled_func(self, self.memory, self.regs, self.vec_regs, self.pstate)
                    if new_pc == -1:
                        return False
                    self.pc = new_pc
                    for i in range(start, end):
                        if i < len(self.instructions):
                            self.stats.record_instruction(self.instructions[i][0])
                    return True
                except Exception as e:
                    self.logger.debug(f"JIT execution failed: {e}")
                    self.jit.invalidate_block(pc)
                    return self.execute_fallback()
        
        end_pc = pc + 1
        for i in range(pc, min(pc + 32, len(self.instructions))):
            opcode, _ = self.instructions[i]
            if opcode in ('JMP', 'JZ', 'JNZ', 'JE', 'JL', 'JG', 'CALL', 'RET', 'HALT', 'B', 'BL', 'BR'):
                end_pc = i + 1
                break
        
        compiled_func = self.jit.compile_block(pc, end_pc)
        if compiled_func:
            try:
                new_pc = compiled_func(self, self.memory, self.regs, self.vec_regs, self.pstate)
                if new_pc == -1:
                    return False
                self.pc = new_pc
                return True
            except Exception as e:
                self.logger.debug(f"JIT execution failed: {e}")
                self.jit.invalidate_block(pc)
        
        return self.execute_fallback()
    
    def execute_fallback(self) -> bool:
        if self.pc < 0 or self.pc >= len(self.instructions):
            return False
        
        opcode, args = self.instructions[self.pc]
        self.pc -= 1
        return self.execute(opcode, args)
    
    def display_state(self, title: str = "CPU State", opcode: Optional[str] = None, 
                     args: Optional[List[Tuple[str, int]]] = None) -> None:
        self.console.clear()
        self.console.rule(f"{Colors.colorize(title, Colors.MAGENTA, True)}")
        
        if opcode:
            pl_op = Constants.PL_KEYWORDS.get(opcode.lower(), opcode.lower())
            if not pl_op:
                pl_op = opcode.lower()
            instr_text = f"{pl_op} " + " ".join(str(a) for a in args)
            panel = Panel(instr_text, title="Current Instruction")
            self.console.print(str(panel))
        
        reg_info = {
            'PSTATE': ' '.join(f"{k}={v}" for k, v in self.pstate.items()),
            'SP': self.sp,
            'PC': self.pc
        }
        if self.breakpoints:
            reg_info['BREAKPOINTS'] = ', '.join(f"{b:#x}" for b in self.breakpoints)
        self.regs.display_registers("General Registers (X0-X31)", reg_info, self.console)
        
        if self.config.show_vector_regs:
            self.vec_regs.display_vector_registers("Vector Registers (V0-V31)", self.console)
        
        self.memory.display_memory("Memory (first 64 bytes)", 0, 64, self.console)
        
        if self.config.cache_size > 0:
            cache_stats = self.cache.get_stats()
            stats_text = f"Cache: {cache_stats['hits']} hits, {cache_stats['misses']} misses ({cache_stats['hit_rate']*100:.1f}% hit rate)"
            self.console.print(stats_text)
        
        self.console.rule()
    
    def debug_command_loop(self) -> None:
        self.is_debugging = True
        
        if self.debug_server is None:
            self.debug_server = DebugServer(self)
        
        self.console.print(f"{Colors.colorize('Debug mode (type help for commands)', Colors.BLUE, True)}")
        
        while self.is_debugging:
            cmd = input(f"{Colors.colorize('dbg>', Colors.YELLOW)} ").strip()
            if not cmd:
                continue
            
            parts = cmd.split()
            command = parts[0].lower()
            
            if command == 'help':
                self._show_help()
            elif command in ('continue', 'c'):
                self.is_debugging = False
                return
            elif command in ('step', 's'):
                self.debug_server.record_state()
                if not self.step():
                    self.is_debugging = False
                    return
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
                    self.console.print(f"{Colors.colorize('No forward history available', Colors.RED)}")
            elif command in ('print', 'p'):
                if len(parts) > 1:
                    target = parts[1]
                    if target.startswith('X') and len(target) >= 2:
                        try:
                            idx = int(target[1:])
                            self.console.print(f"{target} = {self.regs.read(idx)}")
                        except:
                            self.console.print(f"{Colors.colorize('Invalid register', Colors.RED)}")
                    elif target == 'regs':
                        self.regs.display_registers(console=self.console)
                    elif target == 'mem':
                        if len(parts) > 2:
                            try:
                                addr = int(parts[2])
                                value = self.memory.read_byte(addr)
                                self.console.print(f"mem[{addr}] = {value} (0x{value:02X})")
                            except:
                                self.console.print(f"{Colors.colorize('Invalid address', Colors.RED)}")
                        else:
                            self.memory.display_memory(console=self.console)
                    elif target == 'cache':
                        stats = self.cache.get_stats()
                        self.console.print(f"Cache stats: {stats}")
                    elif target == 'history':
                        self.console.print(f"History size: {len(self.debug_server.execution_history)}")
                    else:
                        self.console.print(f"{Colors.colorize('Unknown target', Colors.RED)}")
                else:
                    self.console.print(f"{Colors.colorize('Missing argument', Colors.RED)}")
            elif command == 'break':
                if len(parts) > 1:
                    try:
                        addr = int(parts[1])
                        if len(parts) > 2:
                            condition = ' '.join(parts[2:])
                            self.debug_server.add_conditional_breakpoint(addr, condition)
                            self.console.print(f"{Colors.colorize(f'Conditional breakpoint set at {addr:#x}: {condition}', Colors.GREEN)}")
                        else:
                            self.add_breakpoint(addr)
                            self.console.print(f"{Colors.colorize(f'Breakpoint set at {addr:#x}', Colors.GREEN)}")
                    except:
                        self.console.print(f"{Colors.colorize('Invalid address', Colors.RED)}")
                else:
                    self.console.print(f"{Colors.colorize('Missing address', Colors.RED)}")
            elif command == 'delete':
                if len(parts) > 1:
                    try:
                        addr = int(parts[1])
                        self.remove_breakpoint(addr)
                        self.console.print(f"{Colors.colorize(f'Breakpoint removed at {addr:#x}', Colors.GREEN)}")
                    except:
                        self.console.print(f"{Colors.colorize('Invalid address', Colors.RED)}")
                else:
                    self.console.print(f"{Colors.colorize('Missing address', Colors.RED)}")
            elif command == 'watch':
                if len(parts) > 1:
                    try:
                        addr = int(parts[1])
                        access = parts[2] if len(parts) > 2 else 'rw'
                        self.memory.set_protection(addr, access)
                        self.console.print(f"{Colors.colorize(f'Watchpoint set at {addr:#x} for {access}', Colors.GREEN)}")
                    except:
                        self.console.print(f"{Colors.colorize('Invalid address', Colors.RED)}")
                else:
                    self.console.print(f"{Colors.colorize('Missing address', Colors.RED)}")
            elif command == 'list':
                self.console.print(f"{Colors.colorize('Breakpoints:', Colors.BOLD)}")
                for addr in sorted(self.breakpoints):
                    self.console.print(f"  {addr:#x}")
                for bp in self.debug_server.conditional_breakpoints:
                    self.console.print(f"  {bp.address:#x} (cond: {bp.condition}, hits: {bp.hit_count})")
            elif command == 'info':
                if len(parts) > 1:
                    if parts[1] == 'break':
                        self.console.print(f"{Colors.colorize('Breakpoints:', Colors.BOLD)}")
                        for addr in sorted(self.breakpoints):
                            self.console.print(f"  {addr:#x}")
                        for bp in self.debug_server.conditional_breakpoints:
                            self.console.print(f"  {bp.address:#x} (cond: {bp.condition}, hits: {bp.hit_count})")
                    elif parts[1] == 'regs':
                        self.regs.display_registers(console=self.console)
                    elif parts[1] == 'pc':
                        self.console.print(f"PC: {self.pc:#x}")
                    else:
                        self.console.print(f"{Colors.colorize('Unknown info target', Colors.RED)}")
                else:
                    self.console.print(f"{Colors.colorize('Missing info target', Colors.RED)}")
            elif command in ('quit', 'q'):
                sys.exit(0)
            else:
                self.console.print(f"{Colors.colorize('Unknown command', Colors.RED)}")
    
    def _show_help(self) -> None:
        help_text = f"""
{Colors.colorize('Debug Commands:', Colors.CYAN, True)}
  {Colors.colorize('continue / c', Colors.GREEN)}  - Continue execution
  {Colors.colorize('step / s', Colors.GREEN)}      - Single step
  {Colors.colorize('reverse', Colors.GREEN)}       - Reverse one step (if history available)
  {Colors.colorize('forward', Colors.GREEN)}       - Forward one step (if history available)
  {Colors.colorize('break <addr>', Colors.GREEN)}  - Set breakpoint at address
  {Colors.colorize('break <addr> <cond>', Colors.GREEN)} - Set conditional breakpoint
  {Colors.colorize('delete <addr>', Colors.GREEN)} - Remove breakpoint
  {Colors.colorize('list', Colors.GREEN)}          - List breakpoints
  {Colors.colorize('watch <addr>', Colors.GREEN)}  - Set watchpoint (rw/r/w)
  {Colors.colorize('print / p <target>', Colors.GREEN)} - Print information
    Supported: X0-X31, regs, mem [addr], cache, history
  {Colors.colorize('info <target>', Colors.GREEN)}  - Show information (break/regs/pc)
  {Colors.colorize('quit / q', Colors.GREEN)}      - Exit simulator
  {Colors.colorize('help', Colors.GREEN)}          - Show this help
        """
        self.console.print(help_text)
    
    def step(self) -> bool:
        if self.pc < 0 or self.pc >= len(self.instructions):
            self.console.print(f"{Colors.colorize('Program counter out of bounds', Colors.RED)}")
            return False
        
        if self.debug_server and self.debug_server.check_conditional_breakpoints():
            self.is_debugging = True
            self.debug_command_loop()
            return True
        
        if self.pc in self.breakpoints:
            self.console.print(f"{Colors.colorize(f'Breakpoint hit at PC={self.pc:#x}', Colors.YELLOW)}")
            self.is_debugging = True
            self.debug_command_loop()
            return True
        
        opcode, args = self.instructions[self.pc]
        self.display_state("Step Execution", opcode, args)
        
        if self.jit:
            return self.execute_with_jit()
        return self.execute(opcode, args)
    
    def run(self) -> None:
        if self.config.debug_mode and self.config.interactive_mode:
            self.debug_command_loop()
        
        self.running = True
        self.stats.start()
        
        self.logger.info("Starting program execution")
        self.display_state("Program Start")
        
        try:
            while self.running:
                if self.pc < 0 or self.pc >= len(self.instructions):
                    self.logger.info("Program ended normally")
                    break
                
                if self.stats.instruction_count >= self.config.max_instructions:
                    self.logger.warning(f"Max instruction limit reached: {self.config.max_instructions}")
                    break
                
                if self.debug_server and self.debug_server.check_conditional_breakpoints():
                    self.is_debugging = True
                    self.debug_command_loop()
                    continue
                
                if self.pc in self.breakpoints:
                    self.console.print(f"{Colors.colorize(f'Breakpoint hit at PC={self.pc:#x}', Colors.YELLOW)}")
                    self.is_debugging = True
                    self.debug_command_loop()
                    continue
                
                if self.jit:
                    continue_exec = self.execute_with_jit()
                else:
                    opcode, args = self.instructions[self.pc]
                    self.pc += 1
                    continue_exec = self.execute(opcode, args)
                
                if not continue_exec:
                    self.logger.info("HALT instruction executed")
                    break
                
                if self.config.step_mode and self.config.interactive_mode:
                    self.display_state("Step Execution")
                    if input(f"{Colors.colorize('Continue execution? (y/n)', Colors.YELLOW)} ").lower() != 'y':
                        break
                
                if not self.config.step_mode and self.config.execution_interval > 0:
                    time.sleep(self.config.execution_interval)
        
        except KeyboardInterrupt:
            self.logger.info("User interrupt")
            self.console.print(f"\n{Colors.colorize('User interrupt', Colors.YELLOW)}")
        
        except Exception as e:
            self.logger.error(f"Execution error: {e}")
            self.console.print(f"{Colors.colorize(f'Execution error: {e}', Colors.RED)}")
            if self.config.debug_mode:
                self.console.print(traceback.format_exc())
        
        finally:
            self.running = False
            self.stats.stop()
            self.cache.flush()
            
            self.logger.info("Program execution finished")
            self.display_state("Execution Complete")
            
            cache_stats = self.cache.get_stats() if self.config.cache_size > 0 else None
            jit_stats = self.jit.get_stats() if self.jit else None
            self.stats.display_summary(self.console, cache_stats, jit_stats)
            
            if self.config.auto_save_crom:
                self.save_crom()

# ==================== Main ====================

def main() -> None:
    console = Console()
    
    console.rule(f"{Colors.colorize('CIN/PL CPU Simulator v4.3', Colors.CYAN, True)}")
    console.print(f"{Colors.colorize('Instructions:', Colors.GREEN)} {len(Constants.OPCODE_NAMES)} (with ARM64 & RISC-V extensions)")
    console.print(f"{Colors.colorize('PL keywords:', Colors.GREEN)} {len(Constants.PL_KEYWORDS)}")
    console.print(f"{Colors.colorize('.crom format:', Colors.GREEN)} {Constants.CROM_MAGIC.decode()} v{Constants.CROM_VERSION} (compressed)")
    console.print(f"{Colors.colorize('Cache:', Colors.GREEN)} Size {Config.cache_size}, Assoc {Config.cache_assoc}")
    console.print(f"{Colors.colorize('JIT:', Colors.GREEN)} {Colors.colorize('Enabled' if Config.enable_jit else 'Disabled', Colors.YELLOW)}")
    console.rule()
    
    if len(sys.argv) < 2:
        console.print(f"""
{Colors.colorize('Usage:', Colors.CYAN, True)}
  python cpu.py <file.cin|.pl|.asm|.bin> [options]
  
{Colors.colorize('CIN Language Example:', Colors.CYAN)}
  function main() {{
      int a = 10
      int b = 20
      int c = a + b
      println(c)
      return 0
  }}
  
{Colors.colorize('Options:', Colors.CYAN, True)}
  {Colors.colorize('--step', Colors.YELLOW)}              Step through execution
  {Colors.colorize('--debug', Colors.YELLOW)}             Debug mode
  {Colors.colorize('--save', Colors.YELLOW)}              Save memory to .crom
  {Colors.colorize('--jit', Colors.YELLOW)}               Enable JIT compilation
  {Colors.colorize('--profile', Colors.YELLOW)}           Enable performance profiling
  {Colors.colorize('--compile', Colors.YELLOW)}           Compile CIN to binary (.bin)
  {Colors.colorize('--output <file>', Colors.YELLOW)}     Output file name
  {Colors.colorize('--optimize <0-3>', Colors.YELLOW)}    Optimization level
  {Colors.colorize('--mem-size <size>', Colors.YELLOW)}   Memory size (default: 1024)
  {Colors.colorize('--cache-size <size>', Colors.YELLOW)} Cache size in lines (default: 64)
  {Colors.colorize('--log-level <level>', Colors.YELLOW)} Log level (DEBUG/INFO/WARNING/ERROR)
  {Colors.colorize('--no-io', Colors.YELLOW)}             Disable I/O instructions
  {Colors.colorize('--strict', Colors.YELLOW)}            Strict mode
  
{Colors.colorize('Debug Commands:', Colors.CYAN, True)}
  {Colors.colorize('step/s', Colors.GREEN)}        Single step
  {Colors.colorize('reverse', Colors.GREEN)}       Reverse one step
  {Colors.colorize('forward', Colors.GREEN)}       Forward one step
  {Colors.colorize('break <addr>', Colors.GREEN)}  Set breakpoint
  {Colors.colorize('watch <addr>', Colors.GREEN)}  Set watchpoint (rw/r/w)
  {Colors.colorize('print/p', Colors.GREEN)}       Print registers/memory/cache/history
  {Colors.colorize('info', Colors.GREEN)}          Show information
  
{Colors.colorize('Examples:', Colors.CYAN, True)}
  python cpu.py program.cin
  python cpu.py program.cin --jit --profile
  python cpu.py program.cin --compile --output program.bin
  python cpu.py program.pl --step
        """)
        sys.exit(1)
    
    filename = sys.argv[1]
    if not os.path.exists(filename):
        console.print(f"{Colors.colorize('Error:', Colors.RED, True)} File '{filename}' not found")
        sys.exit(1)
    
    config = Config.from_args(sys.argv)
    config.validate()
    
    if '--jit' in sys.argv:
        config.enable_jit = True
    if '--profile' in sys.argv:
        config.profile = True
    if '--compile' in sys.argv:
        config.compile_to_bin = True
    
    crom_file = None
    for i, arg in enumerate(sys.argv):
        if arg == '--crom' and i + 1 < len(sys.argv):
            crom_file = sys.argv[i + 1]
            break
    
    from_bin = filename.endswith('.bin')
    
    try:
        cpu = CPU(config, filename, crom_file, from_bin, console)
        if not config.compile_to_bin:
            cpu.run()
    except CPUSimulatorError as e:
        console.print(f"{Colors.colorize('Error:', Colors.RED, True)} {e.message}")
        if e.detail:
            console.print(f"{Colors.colorize('Detail:', Colors.DIM)} {e.detail}")
        sys.exit(1)
    except Exception as e:
        console.print(f"{Colors.colorize('Unexpected error:', Colors.RED, True)} {e}")
        if config.debug_mode:
            console.print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()