"""命令行入口: 参数解析 -> 加载程序 -> 运行。"""

import os
import sys
from typing import List, Optional

from .config import Config
from .console import Colors, Console, Panel
from .cpu import CPU
from .errors import CPUSimulatorError

HELP_TEXT = f"""
{Colors.colorize(f'UCPU Simulator v5.0', Colors.CYAN, True)}

{Colors.colorize('Usage:', Colors.YELLOW)}
  python cpu.py <program.[cin|pl|asm|bin]> [options]

{Colors.colorize('Options:', Colors.YELLOW)}
  --no-native          禁用 Go 原生库, 强制纯 Python 解释执行
  --jit                启用 Python JIT (基本块动态编译)
  --step               单步执行 (交互式)
  --debug              调试模式 (超详细 rich 追踪: 逐指令/寄存器/内存/栈/缓存)
  --profile            执行后输出性能统计
  --save               执行后保存 .crom 内存镜像
  --no-compress        .crom 不压缩
  --compile            编译为 .bin 字节码后继续执行
  --compile-only       仅编译为 .bin 不执行
  -o, --output <file>  指定输出文件 (.crom/.bin)
  --crom <file>        加载指定 .crom 内存镜像
  --mem-size <bytes>   内存大小 (默认 65536)
  --max-instructions <n>  指令数上限
  --cache-size <n>     缓存行数
  --no-io              禁止 IN/OUT 与宿主 I/O
  --strict             严格汇编模式
  --log-level <level>  DEBUG / INFO / WARNING / ERROR
  --log-file <file>    日志输出到文件
  --help               显示本帮助

{Colors.colorize('Supported formats:', Colors.YELLOW)}
  .cin   CIN 高级语言 (函数/struct/数组/浮点/字符串)
  .pl    UCPU 汇编语言 (PL 关键字风格)
  .asm   UCPU 汇编
  .bin   UCBC 字节码 (由 --compile 生成)
"""


def _extract_option(args: List[str], name: str) -> Optional[str]:
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return None


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or '--help' in args or '-h' in args:
        sys.stdout.write(HELP_TEXT + "\n")
        return 0

    console = Console()

    # 去掉选项及其值后, 第一个位置参数即程序文件
    program_file: Optional[str] = None
    skip_next = False
    value_opts = {'--output', '-o', '--crom', '--mem-size', '--max-instructions',
                  '--cache-size', '--log-level', '--log-file', '--optimize'}
    for i, a in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if a in value_opts:
            skip_next = True
            continue
        if not a.startswith('-'):
            program_file = a
            break

    if not program_file:
        console.print(Panel("No program file specified.\n"
                            "Use --help for usage information.",
                            title="Error", border_style='red'))
        return 1

    config = Config.from_args(['cpu.py'] + args)
    config.validate()

    crom_file = _extract_option(args, '--crom')
    output_file = (config.output_file
                   or os.path.splitext(program_file)[0] + '.bin')

    try:
        cpu = CPU(config, program_file, crom_file=crom_file)
    except CPUSimulatorError as e:
        console.print(Panel(str(e), title="Load Error", border_style='red'))
        return 1
    except Exception as e:
        console.print(Panel(str(e), title="Error", border_style='red'))
        if config.debug_mode:
            # 超详细: rich 彩色完整堆栈
            console.print_exception()
        return 1

    try:
        if config.compile_to_bin or config.compile_only:
            from . import crom as crom_mod
            crom_mod.save_bin(cpu, output_file, logger=cpu.logger)
            console.print(Colors.colorize(
                f"Compiled to {output_file}", Colors.GREEN))
            if config.compile_only:
                return 0

        cpu.run()
    except KeyboardInterrupt:
        pass
    except CPUSimulatorError as e:
        console.print(Panel(str(e), title="Error", border_style='red'))
        if config.debug_mode:
            console.print_exception()
        return 1
    except Exception as e:
        console.print(Panel(str(e), title="Unexpected Error",
                            border_style='red'))
        console.print_exception()
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
