import os
import re
import sys
from typing import Optional

_ANSI_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


class Colors:
    """ANSI 颜色码。"""

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
    def strip(text: str) -> str:
        return _ANSI_RE.sub('', text)

    @staticmethod
    def colorize(text: str, color: str, bold: bool = False) -> str:
        return f"{Colors.BOLD if bold else ''}{color}{text}{Colors.RESET}"


class Console:
    """控制台输出封装, 非 TTY 环境自动去除 ANSI 码。"""

    def __init__(self, force_color: Optional[bool] = None):
        self.width = 80
        if force_color is None:
            self._color_support = sys.stdout.isatty() or os.environ.get('UCPU_COLOR') == '1'
        else:
            self._color_support = force_color

    @property
    def color_support(self) -> bool:
        return self._color_support

    def print(self, *args, **kwargs):
        text = ' '.join(str(arg) for arg in args)
        if self._color_support:
            print(text)
        else:
            print(Colors.strip(text))

    def clear(self):
        os.system('cls' if sys.platform == 'win32' else 'clear')

    def rule(self, title: str = ""):
        if title:
            clean_title = Colors.strip(title)
            padding = max(0, (50 - len(clean_title) - 2) // 2)
            line = '=' * padding + ' ' + title + ' ' + '=' * padding
            if len(Colors.strip(line)) < 50:
                line = line + '=' * (50 - len(Colors.strip(line)))
            self.print(line)
        else:
            print('=' * 50)

    def clear_line(self):
        print('\r' + ' ' * 80 + '\r', end='')


class Panel:
    """简单边框面板。"""

    def __init__(self, content, title: str = "", border_style: str = "", box=None):
        self.content = content
        self.title = title

    def __str__(self):
        if self.title:
            return (f"┌─ {self.title} ───────────────────────┐\n"
                    f"{self.content}\n"
                    f"└────────────────────────────────────┘")
        return (f"┌────────────────────────────┐\n"
                f"{self.content}\n"
                f"└────────────────────────────┘")


class Table:
    """轻量表格渲染。"""

    def __init__(self, title: str = "", box=None, border_style: str = ""):
        self.title = title
        self.headers = []
        self.rows = []
        self.col_widths = []

    def add_column(self, name, style: str = "", width: int = 0):
        self.headers.append(str(name))
        self.col_widths.append(width if width > 0 else len(str(name)) + 2)

    def add_row(self, *args):
        self.rows.append(tuple(str(a) for a in args))
        for i, val in enumerate(args):
            if i < len(self.col_widths):
                self.col_widths[i] = max(self.col_widths[i],
                                         len(Colors.strip(str(val))) + 2)

    def __str__(self):
        if not self.headers:
            return ""

        lines = []
        if self.title:
            lines.append(f"  {Colors.colorize(self.title, Colors.CYAN, True)}")

        header_parts = [
            Colors.colorize(h, Colors.BOLD).ljust(self.col_widths[i] + len(h) - len(Colors.strip(h)))
            for i, h in enumerate(self.headers)
        ]
        lines.append("  " + " │ ".join(header_parts))
        lines.append("  " + "─┼─".join("─" * w for w in self.col_widths))

        for row in self.rows:
            row_parts = []
            for i, val in enumerate(row):
                if i < len(self.col_widths):
                    pad = self.col_widths[i] + len(val) - len(Colors.strip(val))
                    row_parts.append(val.ljust(pad))
            lines.append("  " + " │ ".join(row_parts))

        return "\n".join(lines)
