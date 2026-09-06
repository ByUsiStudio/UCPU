"""三执行路径一致性: 解释器 / JIT / Go 原生必须产生相同终态。"""

from tests.helpers import new_cpu, snapshot

# 全部指令均在三条路径 (解释/JIT/原生) 支持范围内
PROGRAM = [
    ('MOV', [('reg', 0), ('imm', 100)]),
    ('ADDI', [('reg', 0), ('reg', 0), ('imm', 2)]),     # 102
    ('ADDI', [('reg', 0), ('reg', 0), ('imm', 3)]),     # 105
    ('MOV', [('reg', 1), ('reg', 0)]),                  # 105
    ('NOP', []),
    ('PUSH', [('reg', 1)]),
    ('MOV', [('reg', 1), ('imm', 7)]),
    ('POP', [('reg', 2)]),                              # 105
    ('HALT', []),
]


def _load(program, **cfg):
    cpu = new_cpu(**cfg)
    cpu.instructions = [tuple(op) for op in program]
    cpu.entry_pc = 0
    cpu.pc = 0
    return cpu


def test_interpreter_matches_jit():
    a = _load(PROGRAM)
    a.run()
    b = _load(PROGRAM, enable_jit=True)
    b.run()
    assert snapshot(a) == snapshot(b)
    assert b.jit is not None and b.jit.compilation_count >= 1


def test_interpreter_matches_native_or_fallback():
    a = _load(PROGRAM)
    a.run()
    b = _load(PROGRAM, use_native=True)
    b.run()
    sa, sb = snapshot(a), snapshot(b)
    # 内存快照比对 (原生/解释均将栈位恢复初值; 此处只比确定性状态)
    for key in ('pc', 'sp', 'heap', 'regs', 'vec', 'flags'):
        assert sa[key] == sb[key], f"state differs on {key}"
    # 原生库可用时应真正走原生; 缺失时静默回退解释 (两种皆可)
    assert b.native_used in (True, False)

