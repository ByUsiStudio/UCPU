"""运行配置与命令行参数解析。"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Config:
    mem_size: int = 64 * 1024
    stack_size: int = 1024
    step_mode: bool = False
    debug_mode: bool = False
    auto_save_crom: bool = False
    execution_interval: float = 0.0
    max_execution_time: float = 60.0
    interactive_mode: bool = True
    sandbox_mode: bool = False
    max_instructions: int = 100_000_000
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
    use_native: bool = True          # 允许使用 Go 原生库加速
    cache_size: int = 64
    cache_assoc: int = 4
    profile: bool = False
    compress_crom: bool = True
    compile_to_bin: bool = False
    compile_only: bool = False

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
            elif arg == '--no-native':
                config.use_native = False
            elif arg == '--profile':
                config.profile = True
            elif arg == '--no-compress':
                config.compress_crom = False
            elif arg == '--compile':
                config.compile_to_bin = True
            elif arg == '--compile-only':
                config.compile_only = True
            elif arg in ('--output', '-o') and i + 1 < len(args):
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
        if self.mem_size < 256:
            self.mem_size = 256
        if self.max_instructions < 1:
            self.max_instructions = 1
        if self.optimize < 0:
            self.optimize = 0
        if self.optimize > 3:
            self.optimize = 3
        if self.cache_size < 8:
            self.cache_size = 8
