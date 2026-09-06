"""测试辅助: 构造指令级程序 / 汇编程序 / 运行 CPU。"""

import os

from ucpu import CPU, Config


def reg(n: int):
    return ('reg', n)


def imm(v: int):
    return ('imm', v)


def mem(base: int, off: int = 0):
    return ('mem', base, off)


def new_cpu(**cfg) -> CPU:
    """空程序 CPU (指令由调用方直接赋值)。"""
    defaults = dict(interactive_mode=False, log_level='ERROR', use_native=False)
    defaults.update(cfg)
    return CPU(Config(**defaults))


def run_program(program, **cfg) -> CPU:
    """运行指令元组程序 (解释路径), 返回执行完的 CPU。"""
    cpu = new_cpu(**cfg)
    cpu.instructions = list(program)
    cpu.entry_pc = 0
    cpu.pc = 0
    cpu.run()
    return cpu


def asm_program(source: str, workdir: str, name: str = 'prog.asm', **cfg) -> CPU:
    """从汇编源码加载 CPU。"""
    path = os.path.join(workdir, name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(source)
    defaults = dict(interactive_mode=False, log_level='ERROR', use_native=False)
    defaults.update(cfg)
    return CPU(Config(**defaults), path)


def snapshot(cpu: CPU) -> dict:
    """执行后的确定性状态 (用于多路径一致性比较)。"""
    return {
        'pc': cpu.pc,
        'sp': cpu.sp,
        'heap': cpu.heap_ptr,
        'regs': cpu.regs.get_all(),
        'vec': cpu.vec_regs.get_all(),
        'flags': dict(cpu.pstate),
        'mem': cpu.memory.get_snapshot(),
    }
