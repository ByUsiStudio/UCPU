#!/usr/bin/env python3
# cpu.py - Complete CPU Simulator with CIN/PL/ASM Support
# Enhanced with performance optimizations, JIT compilation,
# type system, RISC-V support, and improved error handling
# Version: 2.0

from typing import List, Tuple, Optional, Dict, Set, Any, Union, Callable, TypeAlias, Generic, TypeVar, Protocol
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict
from pathlib import Path
import sys
import re
import time
import os
import struct
import traceback
import math
import subprocess
import json
import zlib
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.layout import Layout
from rich.live import Live

# ==================== Type System ====================

T = TypeVar('T')
RegisterIndex: TypeAlias = int
MemoryAddress: TypeAlias = int
Instruction: TypeAlias = Tuple[str, List[Tuple[str, Any]]]

class Result(Generic[T]):
    """Rust-style Result type for better error handling"""
    
    def __init__(self, value: Optional[T] = None, error: Optional[Exception] = None):
        self._value = value
        self._error = error
        self._is_ok = error is None
    
    @classmethod
    def ok(cls, value: T) -> 'Result[T]':
        return cls(value=value)
    
    @classmethod
    def err(cls, error: Exception) -> 'Result[T]':
        return cls(error=error)
    
    def is_ok(self) -> bool:
        return self._is_ok
    
    def is_err(self) -> bool:
        return not self._is_ok
    
    def unwrap(self) -> T:
        if self._is_ok:
            return self._value
        raise self._error
    
    def unwrap_or(self, default: T) -> T:
        if self._is_ok:
            return self._value
        return default
    
    def expect(self, msg: str) -> T:
        if self._is_ok:
            return self._value
        raise type(self._error)(f"{msg}: {self._error}")
    
    def map(self, func: Callable[[T], T]) -> 'Result[T]':
        if self._is_ok:
            return Result.ok(func(self._value))
        return self
    
    def map_err(self, func: Callable[[Exception], Exception]) -> 'Result[T]':
        if self._is_err:
            return Result.err(func(self._error))
        return self

# ==================== Enums ====================

class Opcode(Enum):
    """Instruction opcodes as enums"""
    # Base instructions (0-27)
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
    
    # ARM64 base instructions (28-55)
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
    
    # ARM64 data processing (55-66)
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
    
    # Floating point instructions (68-77)
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
    
    # SIMD instructions (78-83)
    VADD = 78
    VSUB = 79
    VMUL = 80
    VDIV = 81
    VLD1 = 82
    VST1 = 83
    
    # RISC-V instructions (84-111)
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

class OperandType(Enum):
    """Operand types"""
    REGISTER = auto()
    IMMEDIATE = auto()
    MEMORY = auto()
    LABEL = auto()
    VECTOR = auto()
    FLOAT = auto()
    CONDITION = auto()
    VECTOR_LANE = auto()

class DataDirective(Enum):
    """Data directives"""
    DB = auto()
    DW = auto()
    DD = auto()
    DQ = auto()

# ==================== Constants ====================

class Constants:
    """Constants definition"""
    NUM_REGISTERS: int = 32
    NUM_VECTOR_REGISTERS: int = 32
    INSTR_SIZE: int = 16
    DEFAULT_MEM_SIZE: int = 1024
    MAGIC_NUMBER: bytes = b'CPUSA'
    CROM_MAGIC: bytes = b'CROM'
    CROM_VERSION: int = 3  # Incremented for new format
    VERSION: int = 2
    MAX_INSTRUCTIONS: int = 100000
    STACK_RESERVED: int = 128
    
    # Complete instruction set with ARM64 and RISC-V extensions
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
    
    # Argument counts per instruction
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
        Opcode.BEQ: 2, Opcode.BNE: 2,
        Opcode.BLT: 2, Opcode.BGE: 2,
        Opcode.BLTU: 2, Opcode.BGEU: 2,
        Opcode.JALR: 2, Opcode.JAL: 1,
        Opcode.LUI: 2, Opcode.AUIPC: 2
    }
    
    # Condition codes
    CONDITIONS: Set[str] = {
        'EQ', 'NE', 'CS', 'CC', 'MI', 'PL', 'VS', 'VC',
        'HI', 'LS', 'GE', 'LT', 'GT', 'LE', 'AL', 'NV'
    }
    
    # Data directives
    DATA_DIRECTIVES: Set[str] = {'DB', 'DW', 'DD', 'DQ'}
    
    # PL language keywords
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
        # RISC-V keywords
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
    
    OPCODE_TO_PL: Dict[str, str] = {v: k for k, v in PL_KEYWORDS.items()}
    
    # CIN keywords
    CIN_KEYWORDS: Set[str] = {
        'if', 'else', 'while', 'for', 'do', 'switch', 'case', 'default',
        'break', 'continue', 'return', 'goto',
        'int', 'float', 'char', 'bool', 'void', 'string',
        'function', 'procedure', 'method', 'constructor', 'destructor',
        'print', 'println', 'input', 'read', 'write',
        'sin', 'cos', 'tan', 'sqrt', 'pow', 'abs',
        'strlen', 'strcmp', 'strcpy', 'strcat',
        'exit', 'system', 'time', 'rand', 'srand'
    }

# ==================== Type System ====================

class TypeSystem:
    """Type system for CIN compiler"""
    
    def __init__(self):
        self.types = {
            'int': 'int32_t',
            'float': 'float',
            'double': 'double',
            'char': 'char',
            'bool': 'bool',
            'string': 'std::string',
            'void': 'void',
            'byte': 'uint8_t',
            'word': 'uint16_t',
            'dword': 'uint32_t',
            'qword': 'uint64_t'
        }
        self.type_sizes = {
            'int': 4, 'float': 4, 'double': 8,
            'char': 1, 'bool': 1, 'byte': 1,
            'word': 2, 'dword': 4, 'qword': 8
        }
        self.type_defaults = {
            'int': 0, 'float': 0.0, 'double': 0.0,
            'char': '\0', 'bool': False, 'string': '',
            'byte': 0, 'word': 0, 'dword': 0, 'qword': 0
        }
        self._structs: Dict[str, Dict[str, str]] = {}
        self._arrays: Dict[str, Tuple[str, int]] = {}
    
    def get_type(self, name: str) -> str:
        """Get C++ type name"""
        return self.types.get(name, 'auto')
    
    def get_size(self, name: str) -> int:
        """Get type size in bytes"""
        if name in self._structs:
            return sum(self.type_sizes.get(t, 4) for t in self._structs[name].values())
        if name in self._arrays:
            return self.type_sizes.get(self._arrays[name][0], 4) * self._arrays[name][1]
        return self.type_sizes.get(name, 4)
    
    def add_struct(self, name: str, fields: Dict[str, str]) -> None:
        """Add a struct definition"""
        self._structs[name] = fields
    
    def add_array(self, name: str, elem_type: str, size: int) -> None:
        """Add an array definition"""
        self._arrays[name] = (elem_type, size)
    
    def is_struct(self, name: str) -> bool:
        return name in self._structs
    
    def is_array(self, name: str) -> bool:
        return name in self._arrays
    
    def get_struct_fields(self, name: str) -> Dict[str, str]:
        return self._structs.get(name, {})
    
    def get_array_info(self, name: str) -> Tuple[str, int]:
        return self._arrays.get(name, ('int', 0))

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

class CompileError(CPUSimulatorError):
    def __init__(self, message: str, detail: Optional[Any] = None, line_num: Optional[int] = None):
        self.line_num = line_num
        prefix = f"Line {line_num}: " if line_num else ""
        super().__init__(f"{prefix}{message}", detail)

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
    
    def _parse_level(self, level: str) -> int:
        levels = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}
        return levels.get(level.upper(), 1)
    
    def set_log_file(self, filename: str) -> None:
        self.log_file = open(filename, 'w', encoding='utf-8')
    
    def _log(self, message: str, level: str, color: str) -> None:
        if self._parse_level(level) >= self.level:
            timestamp = time.strftime("%H:%M:%S")
            formatted = f"[{timestamp}] [{level}] {message}"
            if self.log_file:
                self.log_file.write(formatted + "\n")
                self.log_file.flush()
            if self.console:
                self.console.print(f"[{color}]{formatted}[/{color}]")
    
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
    compile_only: bool = False
    output_file: Optional[str] = None
    no_compile: bool = False
    optimize: int = 0
    target: str = 'native'
    enable_jit: bool = False
    cache_size: int = 64
    cache_assoc: int = 4
    profile: bool = False
    compress_crom: bool = True  # New: Compress CROM files
    
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
            elif arg == '--compile-only':
                config.compile_only = True
            elif arg == '--no-compile':
                config.no_compile = True
            elif arg == '--jit':
                config.enable_jit = True
            elif arg == '--profile':
                config.profile = True
            elif arg == '--no-compress':
                config.compress_crom = False
            elif arg == '--output' and i + 1 < len(args):
                config.output_file = args[i + 1]
                i += 1
            elif arg == '--optimize' and i + 1 < len(args):
                try:
                    config.optimize = int(args[i + 1])
                except ValueError:
                    pass
                i += 1
            elif arg == '--target' and i + 1 < len(args):
                config.target = args[i + 1]
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
    """Single cache line"""
    def __init__(self, tag: int = 0, valid: bool = False, dirty: bool = False):
        self.tag = tag
        self.valid = valid
        self.dirty = dirty
        self.data: Dict[int, int] = {}
        self.last_used: int = 0

class Cache:
    """Simple cache system with LRU replacement"""
    
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
        
        self.memory = None  # Will be set by CPU
    
    def _init_cache(self) -> None:
        """Initialize cache sets"""
        for set_idx in range(self.num_sets):
            self.cache[set_idx] = [CacheLine() for _ in range(self.assoc)]
    
    def _get_set_index(self, addr: int) -> int:
        """Get set index from address"""
        return (addr // self.line_size) % self.num_sets
    
    def _get_tag(self, addr: int) -> int:
        """Get tag from address"""
        return addr // (self.line_size * self.num_sets)
    
    def _get_line_offset(self, addr: int) -> int:
        """Get offset within cache line"""
        return addr % self.line_size
    
    def read(self, addr: int) -> Result[int]:
        """Read from cache"""
        set_idx = self._get_set_index(addr)
        tag = self._get_tag(addr)
        offset = self._get_line_offset(addr)
        
        cache_set = self.cache[set_idx]
        
        # Search for tag in set
        for line in cache_set:
            if line.valid and line.tag == tag:
                self.hits += 1
                line.last_used = self.clock
                self.clock += 1
                if addr in line.data:
                    return Result.ok(line.data[addr])
                # Fetch from memory if not in line data
                if self.memory:
                    base_addr = (addr // self.line_size) * self.line_size
                    for i in range(self.line_size):
                        line.data[base_addr + i] = self.memory.read_byte(base_addr + i)
                    return Result.ok(line.data[addr])
                return Result.ok(0)
        
        # Cache miss
        self.misses += 1
        
        # Find empty line or evict LRU
        evict_idx = 0
        oldest_time = self.clock
        for i, line in enumerate(cache_set):
            if not line.valid:
                evict_idx = i
                break
            if line.last_used < oldest_time:
                oldest_time = line.last_used
                evict_idx = i
        
        # Evict line
        evicted = cache_set[evict_idx]
        if evicted.valid and evicted.dirty and self.memory:
            # Write back dirty data
            for addr_val, data in evicted.data.items():
                self.memory.write_byte(addr_val, data)
        
        # Load from memory
        cache_set[evict_idx] = CacheLine(tag=tag, valid=True, dirty=False)
        cache_set[evict_idx].last_used = self.clock
        self.clock += 1
        
        if self.memory:
            base_addr = (addr // self.line_size) * self.line_size
            for i in range(self.line_size):
                cache_set[evict_idx].data[base_addr + i] = self.memory.read_byte(base_addr + i)
            return Result.ok(cache_set[evict_idx].data[addr])
        
        return Result.ok(0)
    
    def write(self, addr: int, value: int) -> Result[None]:
        """Write to cache (write-back)"""
        set_idx = self._get_set_index(addr)
        tag = self._get_tag(addr)
        
        cache_set = self.cache[set_idx]
        
        # Search for tag in set
        for line in cache_set:
            if line.valid and line.tag == tag:
                line.data[addr] = value
                line.dirty = True
                line.last_used = self.clock
                self.clock += 1
                self.hits += 1
                return Result.ok(None)
        
        # Cache miss - need to allocate
        self.misses += 1
        
        # Find empty line or evict LRU
        evict_idx = 0
        oldest_time = self.clock
        for i, line in enumerate(cache_set):
            if not line.valid:
                evict_idx = i
                break
            if line.last_used < oldest_time:
                oldest_time = line.last_used
                evict_idx = i
        
        # Evict line
        evicted = cache_set[evict_idx]
        if evicted.valid and evicted.dirty and self.memory:
            for addr_val, data in evicted.data.items():
                self.memory.write_byte(addr_val, data)
        
        # Allocate new line
        cache_set[evict_idx] = CacheLine(tag=tag, valid=True, dirty=True)
        cache_set[evict_idx].data[addr] = value
        cache_set[evict_idx].last_used = self.clock
        self.clock += 1
        
        return Result.ok(None)
    
    def flush(self) -> None:
        """Flush all dirty lines to memory"""
        if not self.memory:
            return
        
        for cache_set in self.cache.values():
            for line in cache_set:
                if line.valid and line.dirty:
                    for addr_val, data in line.data.items():
                        self.memory.write_byte(addr_val, data)
                    line.dirty = False
    
    def warmup(self, instructions: List[Tuple]) -> None:
        """Preload instructions into cache"""
        for pc, (opcode, args) in enumerate(instructions):
            self.read(pc)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.hits + self.misses
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hits / total if total > 0 else 0,
            'miss_rate': self.misses / total if total > 0 else 0,
            'total_accesses': total
        }

# ==================== JIT Compiler ====================

class JITCompiler:
    """Simple JIT compiler that compiles instruction sequences to Python callables"""
    
    def __init__(self, cpu: 'CPU'):
        self.cpu = cpu
        self.compiled_blocks: Dict[int, Callable] = {}
        self.block_cache: Dict[int, Tuple[int, int]] = {}
        self.compilation_count = 0
        self.total_calls = 0
        self.cache_hits = 0
        self.hit_rate = 0.0
        self.instruction_latency: Dict[str, int] = {
            'ADD': 1, 'SUB': 1, 'MUL': 3, 'DIV': 10,
            'LOAD': 4, 'STORE': 4, 'FADD': 3, 'FMUL': 5,
            'FDIV': 10, 'VADD': 2, 'VMUL': 4, 'VDIV': 8
        }
        
    def compile_block(self, start_pc: int, end_pc: int) -> Optional[Callable]:
        """Compile a block of instructions to a Python function"""
        self.total_calls += 1
        
        if start_pc in self.compiled_blocks:
            self.cache_hits += 1
            self.hit_rate = self.cache_hits / self.total_calls
            return self.compiled_blocks[start_pc]
        
        if start_pc >= len(self.cpu.instructions) or end_pc > len(self.cpu.instructions):
            return None
        
        instructions = self.cpu.instructions[start_pc:end_pc]
        if not instructions:
            return None
        
        # Generate Python source code for the block
        source_parts = []
        source_parts.append("def compiled_block(cpu, memory, regs, vec_regs, pstate):")
        source_parts.append(f"    pc = {start_pc}")
        
        # Pre-cache register file reference for faster access
        source_parts.append("    regs_list = regs._regs")
        
        for i, (opcode, args) in enumerate(instructions):
            pc = start_pc + i
            source_parts.append(f"    # pc={pc}: {opcode} {args}")
            
            # Generate code for each instruction
            code_line = self._gen_instruction_code(opcode, args, pc)
            if code_line:
                source_parts.append(f"    {code_line}")
        
        source_parts.append("    return pc")
        source = "\n".join(source_parts)
        
        try:
            namespace = {
                'cpu': self.cpu,
                'memory': self.cpu.memory,
                'regs': self.cpu.regs,
                'vec_regs': self.cpu.vec_regs,
                'pstate': self.cpu.pstate
            }
            exec(source, namespace)
            compiled_func = namespace['compiled_block']
            self.compiled_blocks[start_pc] = compiled_func
            self.block_cache[start_pc] = (start_pc, end_pc)
            self.compilation_count += 1
            return compiled_func
        except Exception as e:
            self.cpu.logger.debug(f"JIT compilation failed for block at {start_pc}: {e}")
            return None
    
    def _gen_instruction_code(self, opcode: str, args: List[Tuple[str, int]], pc: int) -> str:
        """Generate Python code for a single instruction"""
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
        """Get Python expression for value access"""
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
        """Invalidate compiled block at PC"""
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

# ==================== Memory System ====================

class Memory:
    def __init__(self, console: Optional[Console] = None, size: int = Constants.DEFAULT_MEM_SIZE):
        self.console = console or Console()
        self._size = size
        self._memory = bytearray(size)
        self._protection: Dict[int, str] = {}  # addr -> 'r', 'w', 'x'
        self._watchpoints: Dict[int, Dict[str, int]] = {}
        self._cache = None
        self._page_size = 4096
        self._pages: Dict[int, bytearray] = {}
    
    def set_cache(self, cache: 'Cache') -> None:
        """Set cache reference for coherent access"""
        self._cache = cache
        cache.memory = self
    
    def set_protection(self, addr: int, perms: str, size: int = 1) -> None:
        """Set memory protection for a range"""
        for i in range(size):
            self._protection[addr + i] = perms
    
    def check_access(self, addr: int, access: str) -> bool:
        """Check if access is allowed"""
        perm = self._protection.get(addr, 'rwx')
        return access in perm
    
    def __len__(self) -> int:
        return self._size
    
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
        
        # Check cache if available
        if self._cache:
            result = self._cache.read(addr)
            if result.is_ok():
                return result.unwrap()
        
        return self._memory[addr]
    
    def write_byte(self, addr: int, value: int) -> None:
        self._check_bounds(addr)
        self._check_protection(addr, 'w')
        
        self._memory[addr] = value & 0xFF
        
        # Invalidate cache if available
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
    
    def write_dword(self, addr: int, value: int) -> None:
        self.write_byte(addr, value & 0xFF)
        self.write_byte(addr + 1, (value >> 8) & 0xFF)
        self.write_byte(addr + 2, (value >> 16) & 0xFF)
        self.write_byte(addr + 3, (value >> 24) & 0xFF)
    
    def read_float(self, addr: int) -> float:
        self._check_bounds(addr, 4)
        return struct.unpack('f', self._memory[addr:addr+4])[0]
    
    def write_float(self, addr: int, value: float) -> None:
        self._check_bounds(addr, 4)
        self._memory[addr:addr+4] = struct.pack('f', value)
    
    def read_unaligned_dword(self, addr: int) -> int:
        """Read unaligned dword (slower but supports non-4-byte aligned addresses)"""
        value = 0
        for i in range(4):
            value |= self.read_byte(addr + i) << (i * 8)
        return value
    
    def write_unaligned_dword(self, addr: int, value: int) -> None:
        for i in range(4):
            self.write_byte(addr + i, (value >> (i * 8)) & 0xFF)
    
    def display_memory(self, title: str = "Memory Dump", start: int = 0, count: int = 32) -> None:
        table = Table(title=title, box=box.ROUNDED, border_style="blue")
        table.add_column("Address", style="cyan", width=10)
        table.add_column("Hex", style="green", width=50)
        table.add_column("ASCII", style="yellow")
        table.add_column("Prot", style="red", width=6)
        end = min(start + count, self._size)
        for i in range(start, end, 16):
            chunk = self._memory[i:min(i+16, end)]
            hex_str = ' '.join(f'{b:02X}' for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            perm = self._protection.get(i, 'rwx')
            table.add_row(f"{i:04X}", hex_str, ascii_str, perm)
        self.console.print(table)
    
    def get_memory_snapshot(self, start: int = 0, count: int = -1) -> bytes:
        """Get a snapshot of memory as bytes"""
        if count < 0:
            count = self._size - start
        return bytes(self._memory[start:start+count])

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
    
    def display_registers(self, title: str = "Registers", extra_info: Optional[Dict[str, Any]] = None) -> None:
        table = Table(title=title, box=box.ROUNDED, border_style="cyan")
        table.add_column("Register", style="bold")
        table.add_column("Value (Dec)", style="green")
        table.add_column("Value (Hex)", style="yellow")
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
        self.console.print(table)

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
        table = Table(title=title, box=box.ROUNDED, border_style="magenta")
        table.add_column("Register", style="bold")
        table.add_column("Lane 0", style="green")
        table.add_column("Lane 1", style="green")
        table.add_column("Lane 2", style="green")
        table.add_column("Lane 3", style="green")
        for i in range(32):
            vec = self._regs[i]
            if any(v != 0.0 for v in vec):
                table.add_row(f"V{i}", f"{vec[0]:.2f}", f"{vec[1]:.2f}", f"{vec[2]:.2f}", f"{vec[3]:.2f}")
        if table.row_count > 0:
            console.print(table)

# ==================== Statistics ====================

class InstructionProfiler:
    """Instruction-level performance profiler"""
    
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
        table = Table(title="Instruction Cycle Profile", box=box.ROUNDED)
        table.add_column("Instruction", style="bold")
        table.add_column("Cycles", style="yellow")
        table.add_column("Percentage", style="green")
        for op, cycles in sorted(self.cycles.items(), key=lambda x: x[1], reverse=True)[:20]:
            pct = (cycles / total * 100) if total > 0 else 0
            table.add_row(op, str(cycles), f"{pct:.1f}%")
        console.print(table)

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
    
    def record_memory_read(self):
        self.memory_reads += 1
    
    def record_memory_write(self):
        self.memory_writes += 1
    
    def get_hot_instructions(self, top_n: int = 10) -> List[Tuple[str, int]]:
        return sorted(self.hot_instructions.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    def display_summary(self, console: Optional[Console] = None, cache_stats: Optional[Dict] = None,
                        jit_stats: Optional[Dict] = None) -> None:
        if console is None:
            return
        
        table = Table(title="Execution Statistics", box=box.ROUNDED, border_style="cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="green")
        table.add_row("Total Instructions", str(self.instruction_count))
        table.add_row("Total Cycles", str(self.inst_profiler.get_total_cycles()))
        table.add_row("CPI (Cycles/Inst)", f"{self.inst_profiler.get_total_cycles() / self.instruction_count:.2f}" if self.instruction_count > 0 else "N/A")
        table.add_row("Execution Time", f"{self.execution_time:.4f}s")
        if self.execution_time > 0:
            table.add_row("Instructions/sec", f"{self.instruction_count / self.execution_time:.2f}")
        table.add_row("Memory Reads", str(self.memory_reads))
        table.add_row("Memory Writes", str(self.memory_writes))
        
        if cache_stats:
            table.add_row("Cache Hits", str(cache_stats.get('hits', 0)))
            table.add_row("Cache Misses", str(cache_stats.get('misses', 0)))
            table.add_row("Cache Hit Rate", f"{cache_stats.get('hit_rate', 0) * 100:.1f}%")
        
        if jit_stats:
            table.add_row("JIT Calls", str(jit_stats.get('total_calls', 0)))
            table.add_row("JIT Cache Hits", str(jit_stats.get('cache_hits', 0)))
            table.add_row("JIT Hit Rate", f"{jit_stats.get('hit_rate', 0) * 100:.1f}%")
            table.add_row("JIT Blocks Compiled", str(jit_stats.get('blocks_compiled', 0)))
        
        console.print(table)
        
        if self.opcode_count:
            op_table = Table(title="Instruction Usage", box=box.ROUNDED, border_style="green")
            op_table.add_column("Instruction", style="bold")
            op_table.add_column("Count", style="yellow")
            op_table.add_column("Percentage", style="green")
            total = sum(self.opcode_count.values())
            for op, count in sorted(self.opcode_count.items(), key=lambda x: x[1], reverse=True)[:20]:
                pct = (count / total * 100) if total > 0 else 0
                op_table.add_row(op, str(count), f"{pct:.1f}%")
            console.print(op_table)
        
        # Display instruction profile
        self.inst_profiler.display_report(console)

# ==================== CIN Compiler ====================

class TypeInference:
    """Type inference for CIN expressions"""
    
    def __init__(self, variables: Dict[str, Tuple[str, str]], type_system: TypeSystem):
        self.variables = variables
        self.type_system = type_system
    
    def infer_type(self, expr: str) -> str:
        """Infer type of an expression"""
        expr = expr.strip()
        
        if re.match(r'^-?\d+$', expr):
            return 'int'
        if re.match(r'^-?\d+\.\d+$', expr):
            return 'float'
        if expr.startswith('"') and expr.endswith('"'):
            return 'string'
        if expr in ('true', 'false'):
            return 'bool'
        if expr in self.variables:
            return self.variables[expr][0]
        if expr.startswith('(') and expr.endswith(')'):
            return self.infer_type(expr[1:-1])
        
        # Handle function calls
        func_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', expr)
        if func_match:
            func_name = func_match.group(1)
            # Built-in functions return types
            builtin_returns = {
                'sin': 'float', 'cos': 'float', 'tan': 'float',
                'sqrt': 'float', 'pow': 'float', 'abs': 'int',
                'strlen': 'int', 'strcmp': 'int', 'rand': 'int',
                'time': 'int'
            }
            return builtin_returns.get(func_name, 'int')
        
        # Handle array access
        if '[' in expr and ']' in expr:
            var = expr[:expr.index('[')]
            if var in self.variables:
                return self.variables[var][0]
        
        return 'int'  # Default
    
    def can_convert(self, from_type: str, to_type: str) -> bool:
        """Check if type conversion is possible"""
        if from_type == to_type:
            return True
        numeric_types = {'int', 'float', 'double', 'byte', 'word', 'dword', 'qword'}
        if from_type in numeric_types and to_type in numeric_types:
            return True
        if from_type == 'int' and to_type == 'bool':
            return True
        if from_type == 'bool' and to_type == 'int':
            return True
        if from_type == 'char' and to_type == 'int':
            return True
        return False

class CINCompiler:
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.type_system = TypeSystem()
        self.type_inference = None
        self.lines: List[str] = []
        self.cpp_lines: List[str] = []
        self.indent: int = 0
        self.temp_count: int = 0
        self.label_count: int = 0
        self.functions: Dict[str, Dict] = {}
        self.variables: Dict[str, Tuple[str, str]] = {}  # name -> (type, cpp_type)
        self.string_literals: Dict[str, str] = {}
        self.string_count: int = 0
        self.current_function: Optional[str] = None
        self.function_code: List[str] = []
        self.global_code: List[str] = []
        self.in_function: bool = False
        self.structs: Dict[str, Dict[str, str]] = {}
        self.current_line: int = 0
        self.breakpoints: Set[int] = set()
        
        # Built-in function mappings
        self.builtins = {
            'print': 'std::cout << {args}',
            'println': 'std::cout << {args} << std::endl',
            'input': 'std::cin >> {args}',
            'read': 'std::cin >> {args}',
            'write': 'std::cout << {args}',
            'sin': 'std::sin({args})',
            'cos': 'std::cos({args})',
            'tan': 'std::tan({args})',
            'sqrt': 'std::sqrt({args})',
            'pow': 'std::pow({args})',
            'abs': 'std::abs({args})',
            'strlen': 'std::strlen({args})',
            'strcmp': 'std::strcmp({args})',
            'strcpy': 'std::strcpy({args})',
            'strcat': 'std::strcat({args})',
            'exit': 'std::exit({args})',
            'system': 'std::system({args})',
            'time': 'std::time({args})',
            'rand': 'std::rand()',
            'srand': 'std::srand({args})'
        }
        
        # CPU instruction to C++ mapping
        self.instruction_map = {
            'MOV': '{dest} = {src};',
            'ADD': '{dest} = {dest} + {src};',
            'SUB': '{dest} = {dest} - {src};',
            'MUL': '{dest} = {dest} * {src};',
            'DIV': '{dest} = {dest} / {src};',
            'AND': '{dest} = {dest} & {src};',
            'OR': '{dest} = {dest} | {src};',
            'XOR': '{dest} = {dest} ^ {src};',
            'SHL': '{dest} = {dest} << {src};',
            'SHR': '{dest} = {dest} >> {src};',
            'INC': '{dest} = {dest} + 1;',
            'DEC': '{dest} = {dest} - 1;',
            'LOAD': '{dest} = memory[{src}];',
            'STORE': 'memory[{dest}] = {src};',
            'PUSH': 'memory[--sp] = {src};',
            'POP': '{dest} = memory[sp++];'
        }
    
    def compile(self, filename: str) -> Tuple[str, str]:
        """Compile CIN file to C++"""
        self._reset()
        
        # Read source
        with open(filename, 'r', encoding='utf-8') as f:
            self.lines = f.readlines()
        
        # Initialize type inference
        self.type_inference = TypeInference(self.variables, self.type_system)
        
        # Parse and generate C++
        self._parse()
        cpp_code = self._generate_cpp()
        
        # Write output
        base = os.path.splitext(filename)[0]
        output_file = base + '.cpp'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(cpp_code)
        
        return output_file, cpp_code
    
    def _reset(self):
        self.cpp_lines = []
        self.functions = {}
        self.variables = {}
        self.string_literals = {}
        self.function_code = []
        self.global_code = []
        self.indent = 0
        self.temp_count = 0
        self.label_count = 0
        self.string_count = 0
        self.current_function = None
        self.in_function = False
        self.structs = {}
        self.current_line = 0
        self.breakpoints = set()
    
    def _indent_str(self) -> str:
        return '    ' * self.indent
    
    def _new_temp(self) -> str:
        self.temp_count += 1
        return f'_tmp_{self.temp_count}'
    
    def _new_label(self) -> str:
        self.label_count += 1
        return f'_label_{self.label_count}'
    
    def _parse(self):
        i = 0
        while i < len(self.lines):
            line = self.lines[i].strip()
            line_num = i + 1
            self.current_line = line_num
            
            # Skip empty lines and comments
            if not line or line.startswith('//') or line.startswith('#'):
                i += 1
                continue
            
            # Skip block comments
            if line.startswith('/*'):
                while i < len(self.lines) and not self.lines[i].strip().endswith('*/'):
                    i += 1
                i += 1
                continue
            
            try:
                # Struct definition
                if line.startswith('struct '):
                    self._parse_struct(line, line_num)
                # Function definition
                elif re.match(r'^(function|void|int|float|char|bool|string|double)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(', line):
                    self._parse_function(line)
                # Variable declaration - support multi-dimensional arrays
                elif re.match(r'^(int|float|char|bool|string|double|byte|word|dword|qword|var)\s+[a-zA-Z_][a-zA-Z0-9_]*', line):
                    self._parse_variable(line)
                # Control flow
                elif line.startswith('if '):
                    self._parse_if(line)
                elif line.startswith('while '):
                    self._parse_while(line)
                elif line.startswith('for '):
                    self._parse_for(line)
                elif line == 'break':
                    self._emit('break;')
                elif line == 'continue':
                    self._emit('continue;')
                elif line == '}':
                    self.indent -= 1
                    self._emit('}')
                    if self.in_function and self.indent == 0:
                        self._close_function()
                elif line.startswith('return '):
                    self._parse_return(line)
                # Assignment or expression
                elif '=' in line and not line.startswith('if') and not line.startswith('while') and not line.startswith('for'):
                    self._parse_assignment(line)
                # Function call or instruction
                else:
                    self._parse_statement(line)
            except Exception as e:
                raise CompileError(str(e), line_num)
            
            i += 1
        
        # Close any open function
        if self.in_function:
            self._close_function()
    
    def _parse_struct(self, line: str, line_num: int):
        """Parse struct definition"""
        match = re.match(r'struct\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*{', line)
        if not match:
            raise CompileError(f"Invalid struct declaration: {line}")
        
        struct_name = match.group(1)
        fields = {}
        
        # Collect fields until closing brace
        current_line = line_num
        while current_line < len(self.lines):
            field_line = self.lines[current_line].strip()
            if field_line == '}':
                break
            if field_line and not field_line.startswith('//'):
                # Handle field declarations
                field_match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*=\s*[^;]+)?(?:;)?$', field_line)
                if field_match:
                    field_type, field_name = field_match.groups()
                    # Check if it's an array type
                    if '[' in field_type and ']' in field_type:
                        array_match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\[([0-9]+)\]', field_type)
                        if array_match:
                            base_type, size = array_match.groups()
                            fields[field_name] = f"{base_type}[{size}]"
                    else:
                        fields[field_name] = field_type
            current_line += 1
        
        self.structs[struct_name] = fields
        self.type_system.add_struct(struct_name, fields)
    
    def _parse_function(self, line: str):
        match = re.match(r'^(function|void|int|float|char|bool|string|double)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)', line)
        if not match:
            raise CompileError(f"Invalid function declaration: {line}")
        
        ret_type, func_name, params_str = match.groups()
        
        params = []
        if params_str.strip():
            for p in params_str.split(','):
                p = p.strip()
                if p:
                    # Handle array parameters
                    if '[]' in p:
                        parts = p.split()
                        if len(parts) >= 2:
                            param_type = parts[0].replace('[]', '')
                            param_name = parts[1]
                            params.append({'type': param_type, 'name': param_name, 'is_array': True})
                        else:
                            params.append({'type': 'int', 'name': parts[0], 'is_array': True})
                    else:
                        parts = p.split()
                        if len(parts) >= 2:
                            params.append({'type': parts[0], 'name': parts[1], 'is_array': False})
                        else:
                            params.append({'type': 'int', 'name': parts[0], 'is_array': False})
        
        self.current_function = func_name
        self.functions[func_name] = {'ret_type': ret_type, 'params': params}
        self.function_code = []
        self.in_function = True
        self.indent = 0
        
        # Generate C++ signature
        cpp_ret_type = self.type_system.get_type(ret_type)
        param_parts = []
        for p in params:
            if p.get('is_array', False):
                param_parts.append(f'{self.type_system.get_type(p["type"])}* {p["name"]}')
            else:
                param_parts.append(f'{self.type_system.get_type(p["type"])} {p["name"]}')
        param_str = ', '.join(param_parts)
        sig = f'{cpp_ret_type} {func_name}({param_str})'
        self.function_code.append(sig + ' {')
        self.indent += 1
    
    def _parse_variable(self, line: str):
        """Parse variable declaration with support for multi-dimensional arrays"""
        # Check for multi-dimensional array declaration
        array_match = re.match(
            r'^(int|float|char|bool|string|double|byte|word|dword|qword|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)(\[[^\]]+\])+(?:\s*=\s*(.+))?$',
            line
        )
        if array_match:
            var_type, var_name, dims, init = array_match.groups()
            cpp_type = self.type_system.get_type(var_type)
            if not init:
                self._emit(f'{cpp_type} {var_name}{dims};')
            else:
                init_expr = init.strip()
                self._emit(f'{cpp_type} {var_name}{dims} = {init_expr};')
            self.variables[var_name] = (var_type, f'{cpp_type}{dims}')
            return
        
        # Check for single array declaration
        array_match = re.match(
            r'^(int|float|char|bool|string|double|byte|word|dword|qword|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\[([0-9]+)\](?:\s*=\s*(.+))?$',
            line
        )
        if array_match:
            var_type, var_name, size, init = array_match.groups()
            cpp_type = self.type_system.get_type(var_type)
            if not init:
                self._emit(f'{cpp_type} {var_name}[{size}];')
            else:
                init_expr = init.strip()
                if init_expr.startswith('{'):
                    self._emit(f'{cpp_type} {var_name}[{size}] = {init_expr};')
                else:
                    self._emit(f'{cpp_type} {var_name}[{size}] = {init_expr};')
            self.variables[var_name] = (var_type, f'{cpp_type}[{size}]')
            return
        
        # Regular variable declaration
        match = re.match(r'^(int|float|char|bool|string|double|byte|word|dword|qword|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*=\s*(.+))?$', line)
        if not match:
            raise CompileError(f"Invalid variable declaration: {line}")
        
        var_type, var_name, init = match.groups()
        
        cpp_type = self.type_system.get_type(var_type)
        
        if init:
            self._emit(f'{cpp_type} {var_name} = {self._parse_expression(init)};')
        else:
            default = self.type_system.type_defaults.get(var_type, 0)
            if var_type == 'string':
                self._emit(f'{cpp_type} {var_name};')
            else:
                self._emit(f'{cpp_type} {var_name} = {default};')
        
        self.variables[var_name] = (var_type, cpp_type)
    
    def _parse_if(self, line: str):
        match = re.match(r'if\s*\((.+)\)', line)
        if not match:
            raise CompileError(f"Invalid if statement: {line}")
        
        condition = match.group(1)
        self._emit(f'if ({self._parse_expression(condition)}) {{')
        self.indent += 1
    
    def _parse_while(self, line: str):
        match = re.match(r'while\s*\((.+)\)', line)
        if not match:
            raise CompileError(f"Invalid while statement: {line}")
        
        condition = match.group(1)
        self._emit(f'while ({self._parse_expression(condition)}) {{')
        self.indent += 1
    
    def _parse_for(self, line: str):
        match = re.match(r'for\s*\(([^;]*);([^;]*);([^)]*)\)', line)
        if not match:
            raise CompileError(f"Invalid for statement: {line}")
        
        init, cond, inc = match.groups()
        self._emit(f'for ({init.strip()}; {cond.strip()}; {inc.strip()}) {{')
        self.indent += 1
    
    def _parse_return(self, line: str):
        value = line[7:].strip()
        if value:
            self._emit(f'return {self._parse_expression(value)};')
        else:
            self._emit('return;')
    
    def _parse_assignment(self, line: str):
        parts = line.split('=', 1)
        if len(parts) != 2:
            raise CompileError(f"Invalid assignment: {line}")
        
        left = parts[0].strip()
        right = self._parse_expression(parts[1].strip().rstrip(';'))
        
        # Check if it's array assignment
        if '[' in left and ']' in left:
            var = left[:left.index('[')]
            idx = left[left.index('[')+1:left.index(']')]
            self._emit(f'{var}[{idx}] = {right};')
        elif left in self.structs:
            self._emit(f'{left} = {right};')
        else:
            self._emit(f'{left} = {right};')
    
    def _parse_statement(self, line: str):
        # Check if it's a function call
        if '(' in line and ')' in line:
            match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)', line)
            if match:
                func_name, args = match.groups()
                if func_name in self.builtins:
                    self._emit(self._gen_builtin(func_name, args))
                else:
                    self._emit(f'{func_name}({self._parse_args(args)});')
                return
        
        # Check if it's a CPU instruction
        parts = line.split()
        if parts and parts[0].upper() in Constants.OPCODE_NAME_TO_ENUM:
            self._emit(self._gen_instruction(parts))
            return
        
        # Check for label
        if ':' in line and not line.startswith(' '):
            label = line.split(':')[0].strip()
            self._emit(f'{label}:')
            return
        
        # Otherwise treat as expression
        self._emit(self._parse_expression(line) + ';')
    
    def _parse_expression(self, expr: str) -> str:
        """Parse CIN expression to C++"""
        # Handle string concatenation with +
        if '+' in expr and ('"' in expr or "'" in expr):
            parts = expr.split('+')
            result = []
            for part in parts:
                part = part.strip()
                if (part.startswith('"') and part.endswith('"')) or \
                   (part.startswith("'") and part.endswith("'")):
                    if part in self.variables and self.variables[part][1] == 'std::string':
                        result.append(part)
                    else:
                        result.append(f'std::string({part})')
                else:
                    result.append(part)
            return ' + '.join(result)
        
        # Handle function calls in expression
        for func in self.builtins:
            pattern = rf'{func}\s*\(([^)]*)\)'
            if re.search(pattern, expr):
                match = re.search(pattern, expr)
                args = match.group(1)
                replacement = self._gen_builtin(func, args)
                expr = re.sub(pattern, replacement, expr)
        
        # Replace variable names
        for var, (var_type, cpp_type) in self.variables.items():
            if var in expr:
                expr = expr.replace(var, var)
        
        return expr
    
    def _parse_args(self, args: str) -> str:
        if not args.strip():
            return ''
        parts = [self._parse_expression(p.strip()) for p in args.split(',')]
        return ', '.join(parts)
    
    def _gen_builtin(self, func: str, args: str) -> str:
        template = self.builtins.get(func, '')
        if not template:
            return f'{func}({self._parse_args(args)})'
        return template.format(args=self._parse_args(args))
    
    def _gen_instruction(self, parts: List[str]) -> str:
        opcode = parts[0].upper()
        
        if opcode == 'JMP':
            return f'goto {parts[1]};'
        elif opcode == 'JZ':
            return f'if (z_flag) goto {parts[1]};'
        elif opcode == 'JNZ':
            return f'if (!z_flag) goto {parts[1]};'
        elif opcode == 'JE':
            return f'if (z_flag) goto {parts[1]};'
        elif opcode == 'JL':
            return f'if (n_flag) goto {parts[1]};'
        elif opcode == 'JG':
            return f'if (!z_flag && !n_flag) goto {parts[1]};'
        elif opcode == 'CALL':
            return f'{parts[1]}();'
        elif opcode == 'CMP':
            return f'z_flag = ({parts[1]} == {parts[2]}); n_flag = ({parts[1]} < {parts[2]});'
        elif opcode == 'HALT':
            return 'return 0;'
        elif opcode == 'RET':
            return 'return;'
        elif opcode == 'IN':
            return f'std::cin >> {parts[1]};'
        elif opcode == 'OUT':
            return f'std::cout << {parts[1]};'
        elif opcode in self.instruction_map:
            template = self.instruction_map[opcode]
            if len(parts) >= 3:
                if opcode == 'STORE':
                    return template.format(dest=parts[1], src=parts[2])
                elif opcode in ['MOV', 'ADD', 'SUB', 'MUL', 'DIV', 'AND', 'OR', 'XOR', 'SHL', 'SHR']:
                    return template.format(dest=parts[1], src=parts[2])
                elif opcode == 'LOAD':
                    return template.format(dest=parts[1], src=parts[2])
                else:
                    return template.format(dest=parts[1], src=parts[2])
            elif len(parts) == 2:
                if opcode in ['INC', 'DEC', 'PUSH', 'POP']:
                    return template.format(dest=parts[1], src=parts[1])
            return f'// Unsupported: {opcode}'
        
        return f'// Unsupported: {opcode}'
    
    def _emit(self, code: str):
        if self.in_function and self.function_code is not None:
            self.function_code.append(self._indent_str() + code)
        else:
            self.global_code.append(self._indent_str() + code)
    
    def _close_function(self):
        if self.in_function and self.function_code is not None:
            if self.function_code and self.function_code[-1].strip() != '}':
                self.indent -= 1
                self.function_code.append('}')
            self.cpp_lines.extend(self.function_code)
            self.cpp_lines.append('')
            self.function_code = []
            self.in_function = False
            self.current_function = None
    
    def _generate_cpp(self) -> str:
        cpp = []
        
        # Headers
        cpp.append('#include <iostream>')
        cpp.append('#include <string>')
        cpp.append('#include <cmath>')
        cpp.append('#include <cstdlib>')
        cpp.append('#include <cstring>')
        cpp.append('#include <vector>')
        cpp.append('#include <map>')
        cpp.append('')
        cpp.append('using namespace std;')
        cpp.append('')
        
        # CPU state
        cpp.append('// CPU State')
        cpp.append('vector<unsigned char> memory(1024, 0);')
        cpp.append('vector<int> regs(32, 0);')
        cpp.append('int sp = 1023;')
        cpp.append('bool z_flag = false;')
        cpp.append('bool n_flag = false;')
        cpp.append('bool c_flag = false;')
        cpp.append('bool v_flag = false;')
        cpp.append('')
        
        # Struct definitions
        for struct_name, fields in self.structs.items():
            cpp.append(f'struct {struct_name} {{')
            for field_name, field_type in fields.items():
                # Handle array fields
                if '[' in field_type and ']' in field_type:
                    array_match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\[([0-9]+)\]', field_type)
                    if array_match:
                        base_type, size = array_match.groups()
                        cpp_type = self.type_system.get_type(base_type)
                        cpp.append(f'    {cpp_type} {field_name}[{size}];')
                else:
                    cpp.append(f'    {self.type_system.get_type(field_type)} {field_name};')
            cpp.append('};')
            cpp.append('')
        
        # Global variables
        cpp.append('// Global variables')
        for var, (var_type, cpp_type) in self.variables.items():
            if var not in self.functions:
                default = self.type_system.type_defaults.get(var_type, 0)
                if var_type == 'string':
                    cpp.append(f'{cpp_type} {var};')
                else:
                    cpp.append(f'{cpp_type} {var} = {default};')
        cpp.append('')
        
        # String literals
        for name, value in self.string_literals.items():
            cpp.append(f'const char* {name} = "{value}";')
        if self.string_literals:
            cpp.append('')
        
        # Global code
        cpp.extend(self.global_code)
        if self.global_code:
            cpp.append('')
        
        # Functions
        cpp.extend(self.cpp_lines)
        
        # Main function if not present
        if 'main' not in self.functions:
            cpp.append('int main() {')
            cpp.append('    return 0;')
            cpp.append('}')
        
        return '\n'.join(cpp)

# ==================== Profiler ====================

class Profiler:
    """Performance profiler for CPU execution"""
    
    def __init__(self):
        self.profile_data: Dict[str, float] = {}
        self.call_stack: List[Tuple[str, float]] = []
        self.instruction_counts: Dict[str, int] = defaultdict(int)
        self.start_time: Optional[float] = None
        self.block_times: Dict[str, float] = {}
        self.block_start: Optional[float] = None
    
    def start_session(self) -> None:
        """Start profiling session"""
        self.start_time = time.time()
        self.profile_data.clear()
        self.call_stack.clear()
        self.instruction_counts.clear()
        self.block_times.clear()
    
    def start_function(self, name: str) -> None:
        """Start profiling a function"""
        self.call_stack.append((name, time.time()))
    
    def end_function(self, name: str) -> None:
        """End profiling a function"""
        if self.call_stack:
            func_name, start_time = self.call_stack.pop()
            if func_name == name:
                elapsed = time.time() - start_time
                self.profile_data[name] = self.profile_data.get(name, 0) + elapsed
    
    def start_block(self, block_id: str) -> None:
        """Start profiling a basic block"""
        self.block_start = time.time()
    
    def end_block(self, block_id: str) -> None:
        """End profiling a basic block"""
        if self.block_start is not None:
            elapsed = time.time() - self.block_start
            self.block_times[block_id] = self.block_times.get(block_id, 0) + elapsed
            self.block_start = None
    
    def record_instruction(self, opcode: str) -> None:
        """Record executed instruction"""
        self.instruction_counts[opcode] += 1
    
    def generate_report(self) -> str:
        """Generate performance report"""
        total_time = time.time() - self.start_time if self.start_time else 0
        total_inst = sum(self.instruction_counts.values())
        
        report = []
        report.append("=" * 50)
        report.append("PROFILE REPORT")
        report.append("=" * 50)
        report.append(f"Total time: {total_time:.4f}s")
        report.append(f"Total instructions: {total_inst}")
        report.append(f"Instructions/sec: {total_inst / total_time:.2f}" if total_time > 0 else "")
        report.append("")
        
        # Function timing
        if self.profile_data:
            report.append("Function Timing:")
            report.append("-" * 40)
            sorted_funcs = sorted(self.profile_data.items(), key=lambda x: x[1], reverse=True)
            for name, elapsed in sorted_funcs[:20]:
                pct = (elapsed / total_time * 100) if total_time > 0 else 0
                report.append(f"  {name}: {elapsed:.4f}s ({pct:.1f}%)")
            report.append("")
        
        # Basic block timing
        if self.block_times:
            report.append("Basic Block Timing:")
            report.append("-" * 40)
            sorted_blocks = sorted(self.block_times.items(), key=lambda x: x[1], reverse=True)
            for block_id, elapsed in sorted_blocks[:20]:
                pct = (elapsed / total_time * 100) if total_time > 0 else 0
                report.append(f"  {block_id}: {elapsed:.4f}s ({pct:.1f}%)")
            report.append("")
        
        # Instruction counts
        if self.instruction_counts:
            report.append("Instruction Usage:")
            report.append("-" * 40)
            sorted_inst = sorted(self.instruction_counts.items(), key=lambda x: x[1], reverse=True)
            for opcode, count in sorted_inst[:20]:
                pct = (count / total_inst * 100) if total_inst > 0 else 0
                report.append(f"  {opcode}: {count} ({pct:.1f}%)")
        
        return "\n".join(report)
    
    def display_report(self, console: Optional[Console] = None) -> None:
        """Display profile report"""
        if console is None:
            console = Console()
        report = self.generate_report()
        console.print(Panel(report, title="Profiler", border_style="cyan"))

# ==================== Debug Server ====================

class DebugServer:
    """Remote debug server with GDB-style protocol"""
    
    def __init__(self, cpu: 'CPU', port: int = 1234):
        self.cpu = cpu
        self.port = port
        self.socket = None
        self.connected = False
        self.running = False
    
    def start(self) -> None:
        """Start debug server"""
        import socket
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
        """Handle debug connection"""
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
        """Process debug command"""
        cmd = data.decode().strip()
        parts = cmd.split()
        
        if not parts:
            return "ERROR: Empty command"
        
        command = parts[0].lower()
        
        if command == 'step':
            self.cpu.step()
            return "OK: Stepped"
        elif command == 'continue':
            self.cpu.running = True
            return "OK: Continuing"
        elif command == 'break':
            if len(parts) > 1:
                try:
                    addr = int(parts[1])
                    self.cpu.breakpoints.add(addr)
                    return f"OK: Breakpoint set at {addr:#x}"
                except ValueError:
                    return "ERROR: Invalid address"
            return "ERROR: Missing address"
        elif command == 'delete':
            if len(parts) > 1:
                try:
                    addr = int(parts[1])
                    self.cpu.breakpoints.discard(addr)
                    return f"OK: Breakpoint removed at {addr:#x}"
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
                    value = self.cpu.memory.read_byte(addr)
                    return f"mem[{addr:#x}] = {value:#x}"
                except ValueError:
                    return "ERROR: Invalid address"
            return "ERROR: Missing address"
        elif command == 'quit':
            self.running = False
            return "OK: Quitting"
        else:
            return f"ERROR: Unknown command: {command}"

# ==================== CPU Core ====================

class CPU:
    def __init__(self, config: Config, filename: str, 
                 crom_file: Optional[str] = None,
                 from_bin: bool = False,
                 console: Optional[Console] = None):
        
        self.console = console or Console()
        self.config = config
        self.filename = filename
        
        # Logger
        self.logger = Logger(self.console, config.log_level)
        if config.log_file:
            self.logger.set_log_file(config.log_file)
        
        # Memory with cache
        self.memory = Memory(self.console, config.mem_size)
        self.cache = Cache(config.cache_size, config.cache_assoc)
        self.memory.set_cache(self.cache)
        
        # Registers
        self.regs = RegisterFile(self.console)
        self.vec_regs = VectorRegisterFile()
        
        # State
        self.pstate = {'N': False, 'Z': False, 'C': False, 'V': False}
        self.pc = 0
        self.sp = config.mem_size - 1
        
        # Instructions
        self.instructions: List[Tuple[str, List[Tuple[str, int]]]] = []
        self.labels: Dict[str, int] = {}
        self.data_labels: Dict[str, int] = {}
        self.pl_source: List[str] = []
        
        # Statistics
        self.stats = Statistics()
        
        # JIT Compiler
        self.jit = JITCompiler(self) if config.enable_jit else None
        
        # Profiler
        self.profiler = Profiler() if config.profile else None
        
        # Running state
        self.running = False
        self.is_debugging = False
        
        # Breakpoints
        self.breakpoints: Set[int] = set()
        
        # Debug server
        self.debug_server: Optional[DebugServer] = None
        
        # Instruction handler dispatch table for fast execution
        self._init_dispatch_table()
        
        # Fast dispatch table for frequently used instructions
        self._fast_dispatch = {}
        self._init_fast_dispatch()
        
        # Check if .cin file - compile it
        if filename.endswith('.cin') and not self.config.no_compile:
            self._compile_and_build(filename)
            return
        
        # Load program
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
            elif filename.endswith('.cin'):
                self._load_compiled(filename)
            else:
                self.assemble(filename)
        
        # Warm up cache
        self.cache.warmup(self.instructions)
        
        self.logger.info(f"CPU initialized, instructions: {len(self.instructions)}")
    
    def _init_dispatch_table(self):
        """Initialize instruction handler dispatch table for fast execution"""
        self._dispatch_table = {}
        
        # Base instructions
        self._dispatch_table['MOV'] = self._exec_mov
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
        self._dispatch_table['LOAD'] = self._exec_load
        self._dispatch_table['STORE'] = self._exec_store
        
        # ARM64 instructions
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
        
        # Floating point
        self._dispatch_table['FADD'] = self._exec_fadd
        self._dispatch_table['FSUB'] = self._exec_fsub
        self._dispatch_table['FMUL'] = self._exec_fmul
        self._dispatch_table['FDIV'] = self._exec_fdiv
        self._dispatch_table['FCMP'] = self._exec_fcmp
        self._dispatch_table['LDRS'] = self._exec_ldrs
        self._dispatch_table['STRS'] = self._exec_strs
        
        # Vector
        self._dispatch_table['VADD'] = self._exec_vadd
        self._dispatch_table['VSUB'] = self._exec_vsub
        self._dispatch_table['VMUL'] = self._exec_vmul
        self._dispatch_table['VDIV'] = self._exec_vdiv
        self._dispatch_table['VLD1'] = self._exec_vld1
        self._dispatch_table['VST1'] = self._exec_vst1
        
        # RISC-V
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
        """Initialize fast dispatch table for common instructions"""
        self._fast_dispatch['MOV'] = self._exec_mov
        self._fast_dispatch['ADD'] = self._exec_add
        self._fast_dispatch['SUB'] = self._exec_sub
        self._fast_dispatch['MUL'] = self._exec_mul
        self._fast_dispatch['DIV'] = self._exec_div
        self._fast_dispatch['AND'] = self._exec_and
        self._fast_dispatch['OR'] = self._exec_or
        self._fast_dispatch['XOR'] = self._exec_xor
        self._fast_dispatch['INC'] = self._exec_inc
        self._fast_dispatch['DEC'] = self._exec_dec
        self._fast_dispatch['CMP'] = self._exec_cmp
        self._fast_dispatch['JMP'] = self._exec_jmp
        self._fast_dispatch['LOAD'] = self._exec_load
        self._fast_dispatch['STORE'] = self._exec_store
        self._fast_dispatch['PUSH'] = self._exec_push
        self._fast_dispatch['POP'] = self._exec_pop
        self._fast_dispatch['CALL'] = self._exec_call
        self._fast_dispatch['RET'] = self._exec_ret
        self._fast_dispatch['HALT'] = self._exec_halt
    
    def _fast_get_val(self, op: Tuple[str, int]) -> int:
        """Fast value access with minimal type checking"""
        if op[0] == 'reg':
            idx = op[1]
            if idx == 31:
                return 0
            return self.regs._regs[idx]
        elif op[0] == 'imm':
            return op[1]
        elif op[0] == 'mem':
            return self.memory.read_byte(op[1])
        else:
            return self.get_val(op)
    
    def parse_immediate(self, val: str) -> int:
        """Parse immediate value with support for multiple bases"""
        val = val.strip()
        if val.startswith('0x') or val.startswith('0X'):
            return int(val, 16)
        if val.startswith('0b') or val.startswith('0B'):
            return int(val, 2)
        if val.startswith('0o') or val.startswith('0O'):
            return int(val, 8)
        try:
            return int(val)
        except ValueError:
            return int(float(val))
    
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
    
    # ARM64 handlers
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
    
    # Floating point handlers
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
    
    # Vector handlers
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
        data = self.memory._memory[address:address + 16]
        values = struct.unpack('ffff', data)
        self.vec_regs.write_vector(rd, list(values))
        return True
    
    def _exec_vst1(self, args):
        rs, addr = args[0][1], args[1]
        address = self.get_val(addr)
        self.stats.record_memory_write()
        values = self.vec_regs.read_vector(rs)
        data = struct.pack('ffff', *values)
        self.memory._memory[address:address + 16] = data
        return True
    
    # RISC-V handlers
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
        if self.regs.read(rs1) == self.regs.read(rs2):
            self.pc = self.get_val(label)
        return True
    
    def _exec_bne(self, args):
        rs1, rs2, label = args[0][1], args[1][1], args[2]
        if self.regs.read(rs1) != self.regs.read(rs2):
            self.pc = self.get_val(label)
        return True
    
    def _exec_blt(self, args):
        rs1, rs2, label = args[0][1], args[1][1], args[2]
        if self.regs.read(rs1) < self.regs.read(rs2):
            self.pc = self.get_val(label)
        return True
    
    def _exec_bge(self, args):
        rs1, rs2, label = args[0][1], args[1][1], args[2]
        if self.regs.read(rs1) >= self.regs.read(rs2):
            self.pc = self.get_val(label)
        return True
    
    def _exec_bltu(self, args):
        rs1, rs2, label = args[0][1], args[1][1], args[2]
        if (self.regs.read(rs1) & 0xFFFFFFFF) < (self.regs.read(rs2) & 0xFFFFFFFF):
            self.pc = self.get_val(label)
        return True
    
    def _exec_bgeu(self, args):
        rs1, rs2, label = args[0][1], args[1][1], args[2]
        if (self.regs.read(rs1) & 0xFFFFFFFF) >= (self.regs.read(rs2) & 0xFFFFFFFF):
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
    
    def _set_pstate(self, result: int, carry: bool = False, overflow: bool = False) -> None:
        self.pstate['Z'] = (result == 0)
        self.pstate['N'] = (result < 0)
        self.pstate['C'] = carry
        self.pstate['V'] = overflow
    
    def _check_stack(self, size: int = 1) -> None:
        """Check if stack has enough space"""
        if self.sp - size < 0:
            raise ExecutionError("Stack overflow")
        if self.sp - size < self.config.mem_size // 4:
            self.logger.warning("Stack approaching heap region")
    
    def _compile_and_build(self, filename: str) -> None:
        """Compile CIN file and build executable"""
        self.logger.info(f"Compiling CIN: {filename}")
        
        compiler = CINCompiler(self.console)
        
        try:
            cpp_file, cpp_code = compiler.compile(filename)
            self.logger.info(f"C++ generated: {cpp_file}")
            
            if self.config.compile_only:
                self.logger.info("Compilation complete (--compile-only)")
                return
            
            output_bin = self.config.output_file or os.path.splitext(filename)[0]
            if sys.platform == 'win32' and not output_bin.endswith('.exe'):
                output_bin += '.exe'
            
            self._compile_cpp(cpp_file, output_bin)
            
        except Exception as e:
            self.logger.error(f"Compilation failed: {e}")
            raise
    
    def _compile_cpp(self, cpp_file: str, output_file: str) -> None:
        """Compile C++ to binary"""
        compiler = 'g++' if sys.platform != 'win32' else 'g++.exe'
        optimize = f'-O{self.config.optimize}' if self.config.optimize > 0 else ''
        target = f'-march={self.config.target}' if self.config.target != 'native' else ''
        
        cmd = [compiler, cpp_file, '-o', output_file, '-std=c++17']
        if optimize:
            cmd.append(optimize)
        if target:
            cmd.append(target)
        
        self.logger.info(f"Executing: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Compilation failed:\n{result.stderr}")
                raise CPUSimulatorError(f"Compilation failed: {result.stderr}")
            
            self.logger.info(f"Build successful: {output_file}")
            
        except FileNotFoundError:
            raise CPUSimulatorError(f"Compiler '{compiler}' not found")
        except Exception as e:
            raise CPUSimulatorError(f"Compilation error: {e}")
    
    def _load_compiled(self, filename: str) -> None:
        """Load compiled CIN file for simulation"""
        base = os.path.splitext(filename)[0]
        pl_file = base + '.pl'
        asm_file = base + '.asm'
        
        if os.path.exists(pl_file):
            self.assemble_pl(pl_file)
        elif os.path.exists(asm_file):
            self.assemble(asm_file)
        else:
            raise CPUSimulatorError(f"No source file found: {base}.pl or {base}.asm")
    
    def load_crom(self, crom_file: str) -> None:
        """Load .crom file with support for new format"""
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
            
            if version == 3:  # New compressed format
                if len(data) < 16:
                    raise CPUSimulatorError(".crom header incomplete")
                
                # Read header
                mem_size = struct.unpack('<I', data[5:9])[0]
                flags = data[9]
                compressed = bool(flags & 0x01)
                checksum = data[10:14]
                reserved = data[14:16]
                
                # Read data
                offset = 16
                if compressed:
                    # Decompress data
                    try:
                        decompressed = zlib.decompress(data[offset:])
                        if len(decompressed) != mem_size:
                            self.logger.warning(f"Decompressed size mismatch: {len(decompressed)} vs {mem_size}")
                        bytes_data = decompressed[:min(mem_size, len(decompressed))]
                    except zlib.error as e:
                        raise CPUSimulatorError(f"Failed to decompress .crom: {e}")
                else:
                    bytes_data = data[offset:offset+mem_size]
                
                # Load into memory
                for i, byte in enumerate(bytes_data):
                    if i < len(self.memory):
                        self.memory.write_byte(i, byte)
                
                self.logger.info(f"Loaded .crom v3: {len(bytes_data)} bytes, compressed={compressed}")
                
            elif version == 1 or version == 2:  # Legacy format
                if len(data) < 10:
                    raise CPUSimulatorError(".crom header incomplete")
                mem_size = struct.unpack('<I', data[5:9])[0]
                bytes_data = data[9:9+mem_size]
                
                for i, byte in enumerate(bytes_data):
                    if i < len(self.memory):
                        self.memory.write_byte(i, byte)
                
                self.logger.info(f"Loaded .crom v{version}: {len(bytes_data)} bytes")
            else:
                raise CPUSimulatorError(f"Unsupported .crom version: {version}")
        else:
            # Legacy format (no magic)
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
        """Save .crom file with compression support"""
        if crom_file is None:
            crom_file = self.crom_file
        
        # Flush cache first
        self.cache.flush()
        
        # Get memory snapshot
        mem_data = bytes(self.memory._memory)
        
        # Build header
        flags = 0
        if self.config.compress_crom:
            flags |= 0x01  # Compression flag
        
        # Compress data if enabled
        data_to_write = mem_data
        if self.config.compress_crom:
            data_to_write = zlib.compress(mem_data, level=6)
        
        # Write file
        with open(crom_file, 'wb') as f:
            f.write(Constants.CROM_MAGIC)
            f.write(struct.pack('<B', Constants.CROM_VERSION))
            f.write(struct.pack('<I', len(mem_data)))
            f.write(struct.pack('<B', flags))
            # Simple checksum (CRC32 of compressed data)
            checksum = zlib.crc32(data_to_write) & 0xFFFFFFFF
            f.write(struct.pack('<I', checksum))
            f.write(b'\x00\x00')  # Reserved
            f.write(data_to_write)
        
        self.logger.info(f".crom saved to {crom_file} (v{Constants.CROM_VERSION}, compressed={self.config.compress_crom})")
    
    def assemble_pl(self, filename: str) -> None:
        """Assemble .pl file"""
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
        
        # Validate instructions
        self._validate_instructions()
    
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
    
    def _validate_instructions(self) -> None:
        """Validate all instructions after assembly"""
        for pc, (opcode, args) in enumerate(self.instructions):
            expected = Constants.ARG_COUNTS.get(
                Constants.OPCODE_NAME_TO_ENUM.get(opcode), -1
            )
            if expected >= 0 and len(args) != expected:
                self.logger.warning(f"Instruction {opcode} at PC={pc} has {len(args)} args, expected {expected}")
            
            # Validate register ranges
            for arg in args:
                if arg[0] == 'reg' and arg[1] > 31:
                    self.logger.warning(f"Invalid register {arg[1]} at PC={pc}")
                if arg[0] == 'imm' and abs(arg[1]) > 0xFFFFFFFF:
                    self.logger.warning(f"Immediate value too large at PC={pc}: {arg[1]}")
    
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
        """Assemble .asm file"""
        self.logger.info(f"Assembling: {filename}")
        self.assemble_pl(filename)
    
    def load_bin(self, filename: str) -> None:
        """Load binary .bin file"""
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
        """Save binary .bin file"""
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
    
    def get_float_val(self, op: Tuple[str, int]) -> float:
        return float(self.get_val(op))
    
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
        """Add a breakpoint at the given address"""
        self.breakpoints.add(addr)
        self.logger.info(f"Breakpoint set at PC={addr:#x}")
    
    def remove_breakpoint(self, addr: int) -> None:
        """Remove a breakpoint at the given address"""
        self.breakpoints.discard(addr)
        self.logger.info(f"Breakpoint removed at PC={addr:#x}")
    
    def execute(self, opcode: str, args: List[Tuple[str, int]]) -> bool:
        """Execute instruction using dispatch table"""
        self.pc += 1
        
        # Use fast dispatch if available
        handler = self._fast_dispatch.get(opcode)
        if handler:
            result = handler(args)
            self.stats.record_instruction(opcode)
            
            if self.profiler:
                self.profiler.record_instruction(opcode)
            
            return result
        
        # Fall back to full dispatch table
        handler = self._dispatch_table.get(opcode)
        if handler:
            result = handler(args)
            self.stats.record_instruction(opcode)
            
            if self.profiler:
                self.profiler.record_instruction(opcode)
            
            return result
        else:
            raise ExecutionError(f"Unimplemented instruction: {opcode}")
    
    def execute_with_jit(self) -> bool:
        """Execute using JIT compilation for the current block"""
        if not self.jit:
            return self.execute_fallback()
        
        pc = self.pc
        
        # Check breakpoints
        if pc in self.breakpoints:
            self.console.print(f"[yellow]Breakpoint hit at PC={pc:#x}[/yellow]")
            self.is_debugging = True
            self.debug_command_loop()
            return True
        
        # Try to find compiled block starting at current PC
        if pc in self.jit.block_cache:
            start, end = self.jit.block_cache[pc]
            compiled_func = self.jit.compiled_blocks.get(pc)
            if compiled_func:
                try:
                    if self.profiler:
                        self.profiler.start_block(f"JIT_{pc:#x}")
                    new_pc = compiled_func(self, self.memory, self.regs, self.vec_regs, self.pstate)
                    if self.profiler:
                        self.profiler.end_block(f"JIT_{pc:#x}")
                    if new_pc == -1:
                        return False
                    self.pc = new_pc
                    # Record instructions for statistics
                    for i in range(start, end):
                        if i < len(self.instructions):
                            self.stats.record_instruction(self.instructions[i][0])
                    return True
                except Exception as e:
                    self.logger.debug(f"JIT execution failed: {e}")
                    self.jit.invalidate_block(pc)
                    return self.execute_fallback()
        
        # Compile a block of instructions
        end_pc = pc + 1
        for i in range(pc, min(pc + 32, len(self.instructions))):
            opcode, _ = self.instructions[i]
            if opcode in ('JMP', 'JZ', 'JNZ', 'JE', 'JL', 'JG', 'CALL', 'RET', 'HALT', 'B', 'BL', 'BR'):
                end_pc = i + 1
                break
        
        compiled_func = self.jit.compile_block(pc, end_pc)
        if compiled_func:
            try:
                if self.profiler:
                    self.profiler.start_block(f"JIT_{pc:#x}")
                new_pc = compiled_func(self, self.memory, self.regs, self.vec_regs, self.pstate)
                if self.profiler:
                    self.profiler.end_block(f"JIT_{pc:#x}")
                if new_pc == -1:
                    return False
                self.pc = new_pc
                return True
            except Exception as e:
                self.logger.debug(f"JIT execution failed: {e}")
                self.jit.invalidate_block(pc)
        
        return self.execute_fallback()
    
    def execute_fallback(self) -> bool:
        """Fall back to interpreted execution"""
        if self.pc < 0 or self.pc >= len(self.instructions):
            return False
        
        opcode, args = self.instructions[self.pc]
        self.pc -= 1
        return self.execute(opcode, args)
    
    def display_state(self, title: str = "CPU State", opcode: Optional[str] = None, 
                     args: Optional[List[Tuple[str, int]]] = None) -> None:
        self.console.clear()
        self.console.rule(f"[bold magenta]{title}[/bold magenta]")
        
        if opcode:
            pl_op = Constants.OPCODE_TO_PL.get(opcode, opcode.lower())
            instr_text = f"{pl_op} " + " ".join(str(a) for a in args)
            panel = Panel(f"[bold green]{instr_text}[/bold green]", title="Current Instruction", border_style="green", box=box.DOUBLE)
            self.console.print(panel)
        
        reg_info = {
            'PSTATE': ' '.join(f"{k}={v}" for k, v in self.pstate.items()),
            'SP': self.sp,
            'PC': self.pc
        }
        if self.breakpoints:
            reg_info['BREAKPOINTS'] = ', '.join(f"{b:#x}" for b in self.breakpoints)
        self.regs.display_registers("General Registers (X0-X31)", reg_info)
        
        if self.config.show_vector_regs:
            self.vec_regs.display_vector_registers("Vector Registers (V0-V31)", self.console)
        
        self.memory.display_memory("Memory (first 64 bytes)", 0, 64)
        
        # Show cache stats if enabled
        if self.config.cache_size > 0:
            cache_stats = self.cache.get_stats()
            stats_text = f"Cache: {cache_stats['hits']} hits, {cache_stats['misses']} misses ({cache_stats['hit_rate']*100:.1f}% hit rate)"
            self.console.print(f"[dim]{stats_text}[/dim]")
        
        self.console.rule()
    
    def debug_command_loop(self) -> None:
        self.is_debugging = True
        self.console.print("[bold blue]Debug mode (type help for commands)[/bold blue]")
        
        while self.is_debugging:
            cmd = Prompt.ask("[yellow]dbg>[/yellow]").strip()
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
                if not self.step():
                    self.is_debugging = False
                    return
            elif command in ('print', 'p'):
                if len(parts) > 1:
                    target = parts[1]
                    if target.startswith('X') and len(target) >= 2:
                        try:
                            idx = int(target[1:])
                            self.console.print(f"{target} = {self.regs.read(idx)}")
                        except:
                            self.console.print("[red]Invalid register[/red]")
                    elif target == 'regs':
                        self.regs.display_registers()
                    elif target == 'mem':
                        if len(parts) > 2:
                            try:
                                addr = int(parts[2])
                                value = self.memory.read_byte(addr)
                                self.console.print(f"mem[{addr}] = {value} (0x{value:02X})")
                            except:
                                self.console.print("[red]Invalid address[/red]")
                        else:
                            self.memory.display_memory()
                    elif target == 'cache':
                        stats = self.cache.get_stats()
                        self.console.print(f"Cache stats: {stats}")
                    else:
                        self.console.print("[red]Unknown target[/red]")
                else:
                    self.console.print("[red]Missing argument[/red]")
            elif command == 'break':
                if len(parts) > 1:
                    try:
                        addr = int(parts[1])
                        self.add_breakpoint(addr)
                        self.console.print(f"[green]Breakpoint set at {addr:#x}[/green]")
                    except:
                        self.console.print("[red]Invalid address[/red]")
                else:
                    self.console.print("[red]Missing address[/red]")
            elif command == 'delete':
                if len(parts) > 1:
                    try:
                        addr = int(parts[1])
                        self.remove_breakpoint(addr)
                        self.console.print(f"[green]Breakpoint removed at {addr:#x}[/green]")
                    except:
                        self.console.print("[red]Invalid address[/red]")
                else:
                    self.console.print("[red]Missing address[/red]")
            elif command == 'list':
                for addr in sorted(self.breakpoints):
                    self.console.print(f"  {addr:#x}")
            elif command in ('quit', 'q'):
                sys.exit(0)
            else:
                self.console.print("[red]Unknown command[/red]")
    
    def _show_help(self) -> None:
        help_text = """
[bold cyan]Debug Commands:[/bold cyan]
  [green]continue / c[/green]  - Continue execution
  [green]step / s[/green]      - Single step
  [green]break <addr>[/green]  - Set breakpoint at address
  [green]delete <addr>[/green] - Remove breakpoint
  [green]list[/green]          - List breakpoints
  [green]print / p <target>[/green] - Print information
    Supported: X0-X31, regs, mem [addr], cache
  [green]quit / q[/green]      - Exit simulator
  [green]help[/green]          - Show this help
        """
        self.console.print(Markdown(help_text))
    
    def step(self) -> bool:
        if self.pc < 0 or self.pc >= len(self.instructions):
            self.console.print("[red]Program counter out of bounds[/red]")
            return False
        
        # Check breakpoints
        if self.pc in self.breakpoints:
            self.console.print(f"[yellow]Breakpoint hit at PC={self.pc:#x}[/yellow]")
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
        
        if self.profiler:
            self.profiler.start_session()
        
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
                
                # Check breakpoints
                if self.pc in self.breakpoints:
                    self.console.print(f"[yellow]Breakpoint hit at PC={self.pc:#x}[/yellow]")
                    self.is_debugging = True
                    self.debug_command_loop()
                    continue
                
                # Use JIT if enabled
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
                    if not Confirm.ask("[yellow]Continue execution?[/yellow]", default=True):
                        break
                
                if not self.config.step_mode and self.config.execution_interval > 0:
                    time.sleep(self.config.execution_interval)
        
        except KeyboardInterrupt:
            self.logger.info("User interrupt")
            self.console.print("\n[yellow]User interrupt[/yellow]")
        
        except Exception as e:
            self.logger.error(f"Execution error: {e}")
            self.console.print(f"[red]Execution error: {e}[/red]")
            if self.config.debug_mode:
                self.console.print(traceback.format_exc())
        
        finally:
            self.running = False
            self.stats.stop()
            self.cache.flush()
            
            self.logger.info("Program execution finished")
            self.display_state("Execution Complete")
            
            # Display statistics
            cache_stats = self.cache.get_stats() if self.config.cache_size > 0 else None
            jit_stats = self.jit.get_stats() if self.jit else None
            self.stats.display_summary(self.console, cache_stats, jit_stats)
            
            # Display profile if enabled
            if self.profiler:
                self.profiler.display_report(self.console)
            
            if self.config.auto_save_crom:
                self.save_crom()

# ==================== Main ====================

def main() -> None:
    console = Console()
    
    console.rule("[bold cyan]CIN/PL CPU Simulator v2.0[/bold cyan]")
    console.print(f"Instructions: {len(Constants.OPCODE_NAMES)} (with ARM64 & RISC-V extensions)")
    console.print(f"PL keywords: {len(Constants.PL_KEYWORDS)}")
    console.print(f".crom format: {Constants.CROM_MAGIC.decode()} v{Constants.CROM_VERSION} (compressed)")
    console.print(f"Cache: Size {Config.cache_size}, Assoc {Config.cache_assoc}")
    console.print(f"JIT: {'Enabled' if Config.enable_jit else 'Disabled'}")
    console.rule()
    
    if len(sys.argv) < 2:
        console.print("""
[bold]Usage:[/bold]
  python cpu.py <file.cin|.pl|.asm|.bin> [options]
  
[bold]CIN Language Example:[/bold]
  function main() {
      int a = 10
      int b = 20
      int c = a + b
      println(c)
      return 0
  }
  
[bold]Options:[/bold]
  --step              Step through execution
  --debug             Debug mode
  --save              Save memory to .crom
  --compile-only      Generate C++ only, no compilation
  --no-compile        Skip compilation, run in interpreter
  --jit               Enable JIT compilation
  --profile           Enable performance profiling
  --no-compress       Disable CROM compression
  --output <file>     Output file name
  --optimize <0-3>    Optimization level
  --target <arch>     Target architecture (native, x86-64, arm64)
  --mem-size <size>   Memory size (default: 1024)
  --cache-size <size> Cache size in lines (default: 64)
  --log-level <level> Log level (DEBUG/INFO/WARNING/ERROR)
  --no-io             Disable I/O instructions
  --strict            Strict mode
  
[bold]Examples:[/bold]
  python cpu.py program.cin
  python cpu.py program.cin --jit --profile
  python cpu.py program.cin --optimize 2 --output myapp
  python cpu.py program.pl --step --cache-size 128
        """)
        sys.exit(1)
    
    filename = sys.argv[1]
    if not os.path.exists(filename):
        console.print(f"[red]Error: File '{filename}' not found[/red]")
        sys.exit(1)
    
    config = Config.from_args(sys.argv)
    config.validate()
    
    # Enable JIT from command line if requested
    if '--jit' in sys.argv:
        config.enable_jit = True
    if '--profile' in sys.argv:
        config.profile = True
    if '--no-compress' in sys.argv:
        config.compress_crom = False
    
    crom_file = None
    for i, arg in enumerate(sys.argv):
        if arg == '--crom' and i + 1 < len(sys.argv):
            crom_file = sys.argv[i + 1]
            break
    
    from_bin = filename.endswith('.bin')
    
    try:
        cpu = CPU(config, filename, crom_file, from_bin, console)
        cpu.run()
    except CPUSimulatorError as e:
        console.print(f"[red]Error: {e.message}[/red]")
        if e.detail:
            console.print(f"[dim]Detail: {e.detail}[/dim]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if config.debug_mode:
            console.print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()