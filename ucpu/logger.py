import sys
import time
from typing import Optional

from .console import Console, Colors


class Logger:
    LEVELS = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}

    def __init__(self, console: Optional[Console] = None, level: str = 'INFO'):
        self.console = console or Console()
        self.level = self._parse_level(level)
        self.log_file = None
        self._color_support = sys.stdout.isatty()

    def _parse_level(self, level: str) -> int:
        return self.LEVELS.get(level.upper(), 1)

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
