#!/usr/bin/env python3
"""UCPU 模拟器入口。

实现已拆分为 ucpu/ 包:
  ucpu.cli       命令行解析与启动
  ucpu.cpu       CPU 核心 (111 条指令 + SYS 宿主调用)
  ucpu.assembler 汇编器 (.pl/.asm)
  ucpu.cin       CIN 高级语言编译器 (.cin)
  ucpu.native    Go 原生库桥接 (可选加速, Win/Linux/Termux)
  ucpu.crom      CROM 内存镜像 / UCBC 字节码
  ucpu.jit       Python JIT (--jit)
  ucpu.debugger  调试器

用法:
  python cpu.py <program.[cin|pl|asm|bin]> [options]
  python cpu.py --help
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ucpu.cli import main

if __name__ == '__main__':
    sys.exit(main())
