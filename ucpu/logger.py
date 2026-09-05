import logging
import os
from typing import Any, Dict, Optional

from rich.logging import RichHandler
from rich.table import Table
from rich.text import Text

from .console import Console

_FORMAT = '%(message)s'


class Logger:

    LEVELS = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}

    def __init__(self, console: Optional[Console] = None, level: str = 'INFO'):
        self.console = console or Console()
        self.level = self._parse_level(level)

        self._log = logging.getLogger('ucpu')
        self._log.propagate = False
        self._log.setLevel(logging.DEBUG)   # handler 负责过滤

        self._handler = RichHandler(
            console=self.console.rich,
            show_time=True,
            show_level=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            markup=False,
            log_time_format='%H:%M:%S',
        )
        self._handler.setFormatter(logging.Formatter(_FORMAT))
        self._handler.setLevel(self._to_logging_level(self.level))
        self._log.addHandler(self._handler)

        self._file_handler: Optional[logging.FileHandler] = None
        self.log_file: Optional[str] = None

    # ---------------- 级别控制 ----------------

    @staticmethod
    def _to_logging_level(ucpu_level: int) -> int:
        # ucpu: DEBUG=0..CRITICAL=4  -> logging: 10..50
        return (ucpu_level + 1) * 10

    def _parse_level(self, level: str) -> int:
        return self.LEVELS.get(str(level).upper(), 1)

    def set_level(self, level: str) -> None:
        self.level = self._parse_level(level)
        self._handler.setLevel(self._to_logging_level(self.level))

    @property
    def is_debug(self) -> bool:
        return self.level <= self.LEVELS['DEBUG']

    def set_log_file(self, filename: str) -> None:
        self.log_file = filename
        if self._file_handler is not None:
            self._log.removeHandler(self._file_handler)
            self._file_handler.close()
        os.makedirs(os.path.dirname(os.path.abspath(filename)) or '.',
                    exist_ok=True)
        fh = logging.FileHandler(filename, mode='w', encoding='utf-8')
        fh.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
        fh.setLevel(logging.DEBUG)          # 文件记录全量
        self._log.addHandler(fh)
        self._file_handler = fh

    # ---------------- 标准级别 ----------------

    def debug(self, msg: str) -> None:
        self._log.debug(msg)

    def info(self, msg: str) -> None:
        self._log.info(msg)

    def warning(self, msg: str) -> None:
        self._log.warning(msg)

    def error(self, msg: str, exc_info: Any = None) -> None:
        self._log.error(msg, exc_info=exc_info)

    def critical(self, msg: str, exc_info: Any = None) -> None:
        self._log.critical(msg, exc_info=exc_info)

    def exception(self, msg: str) -> None:
        """rich 彩色堆栈回溯输出。"""
        self._log.error(msg, exc_info=True)

    # ---------------- 超详细调试辅助 ----------------

    def trace(self, msg: str) -> None:
        """逐指令级追踪 (dim 弱化样式, 仅 DEBUG)。"""
        self._log.debug(Text(msg, style='dim'))

    def dump(self, title: str, fields: Dict[str, Any]) -> None:
        """以 rich 表格输出调试快照 (仅 DEBUG)。"""
        if not self.is_debug:
            return
        t = Table(title=title, box=None, border_style='dim',
                  show_header=False, padding=(0, 1))
        t.add_column('key', style='bold cyan', no_wrap=True)
        t.add_column('value', style='default')
        for k, v in fields.items():
            t.add_row(str(k), str(v))
        self._log.debug(t)

    def hexdump(self, title: str, addr: int, data: bytes,
                width: int = 16) -> None:
        """内存十六进制转储 (仅 DEBUG)。"""
        if not self.is_debug:
            return
        lines = []
        for off in range(0, min(len(data), 256), width):
            chunk = data[off:off + width]
            hexs = ' '.join(f'{b:02x}' for b in chunk)
            asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            lines.append(f'  {addr + off:06x}  {hexs:<{width * 3}}  {asc}')
        if len(data) > 256:
            lines.append(f'  ... ({len(data)} bytes total)')
        self._log.debug(f'{title}\n' + '\n'.join(lines))

    def close(self) -> None:
        if self._file_handler is not None:
            self._log.removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None
