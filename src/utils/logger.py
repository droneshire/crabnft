from __future__ import annotations

import collections
import logging
import os
import sys
import time
import typing as T

from utils.file_util import make_sure_path_exists


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[31m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class Prefixes:
    ARROW = chr(10236)


class MultiHandler(logging.Handler):
    """
    Create a special logger that logs to per-thread-name files
    I'm not confident the locking strategy here is correct, I think this is
    a global lock and it'd be OK to just have a per-thread or per-file lock.
    """

    def __init__(self, dirname, block_list_prefixes: list[str] | None = None):
        super().__init__()
        self.files: dict[str, T.TextIO] = {}
        self.dirname = dirname
        self.block_list_prefixes = (
            [] if block_list_prefixes is None else block_list_prefixes
        )
        if not os.access(dirname, os.W_OK):
            raise Exception(f"Directory {dirname} not writeable")

    def flush(self):
        self.acquire()
        try:
            for file_pointer in self.files.values():
                file_pointer.flush()
        finally:
            self.release()

    def _get_or_open(self, key):
        "Get the file pointer for the given key, or else open the file"
        self.acquire()
        try:
            if key in self.files:
                return self.files[key]

            file_pointer = open(  # pylint: disable=consider-using-with
                os.path.join(self.dirname, f"{key}.log"), "a", encoding="utf-8"
            )
            self.files[key] = file_pointer
            return file_pointer
        finally:
            self.release()

    def emit(self, record):
        # No lock here; following code for StreamHandler and FileHandler
        try:
            name = record.threadName
            if any(  # pylint: disable=use-a-generator
                [n for n in self.block_list_prefixes if name.startswith(n)]
            ):
                return
            file_pointer = self._get_or_open(name)
            msg = self.format(record)
            file_pointer.write(f"{msg.encode('utf-8')}\n")
        except (KeyboardInterrupt, SystemExit):
            raise
        except:  # pylint: disable=bare-except
            self.handleError(record)


def setup_log(log_level: str, log_dir: str, id_string: str) -> None:
    if log_level == "NONE":
        return

    log_name = (
        time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time()))
        + f"_{id_string}.log"
    )

    log_file = os.path.join(log_dir, log_name)

    make_sure_path_exists(log_dir)

    logging.basicConfig(
        filename=log_file,
        level=logging.getLevelName(log_level),
        format="[%(levelname)s][%(asctime)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filemode="w",
    )


def get_lifetime_game_stats(log_dir: str, user: str) -> str:
    return os.path.join(
        log_dir, "stats", user.lower() + "_lifetime_game_bot_stats.json"
    )


def get_logging_dir(name: str, create_if_not_exist: bool = True) -> str:
    this_dir = os.path.dirname(os.path.realpath(__file__))
    src_dir = os.path.dirname(this_dir)
    log_dir = os.path.join(os.path.dirname(src_dir), "logs", name)

    if not os.path.isdir(log_dir) and create_if_not_exist:
        make_sure_path_exists(log_dir)

    return log_dir


def is_color_supported() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def make_formatter_printer(
    color: str,
    log_level: int = logging.INFO,
    prefix: str = "",
    return_formatter: bool = False,
) -> collections.abc.Callable:
    game_logger = logging.getLogger(__name__)

    def formatter(message, *args, **kwargs):
        if args or kwargs:
            formatted_text = message.format(*args, **kwargs)
        else:
            formatted_text = message

        if prefix and sys.platform.lower() == "linux":
            formatted_text = prefix + "\t" + formatted_text

        if is_color_supported():
            try:
                return (
                    str(color + formatted_text + Colors.ENDC)
                    .encode("utf-8")
                    .decode(sys.stdout.encoding, errors="ignore")
                )
            except UnicodeEncodeError:
                return formatted_text

        try:
            return formatted_text.encode("utf-8").decode(
                sys.stdout.encoding, errors="ignore"
            )
        except TypeError:
            return formatted_text

    def printer(message, *args, **kwargs):
        if log_level == logging.DEBUG:
            game_logger.debug(message)
        elif log_level == logging.ERROR:
            game_logger.critical(message)
        elif log_level == logging.INFO:
            game_logger.info(message)

        print(formatter(message, *args, **kwargs))
        sys.stdout.flush()

    if return_formatter:
        return formatter

    return printer


print_ok_blue = make_formatter_printer(Colors.OKBLUE)
print_ok = make_formatter_printer(Colors.OKGREEN)
print_warn = make_formatter_printer(Colors.WARNING, log_level=logging.ERROR)
print_fail = make_formatter_printer(Colors.FAIL, log_level=logging.ERROR)
print_bold = make_formatter_printer(Colors.BOLD)
print_normal = make_formatter_printer(Colors.ENDC)
print_ok_arrow = make_formatter_printer(Colors.OKGREEN, prefix=Prefixes.ARROW)
print_ok_blue_arrow = make_formatter_printer(
    Colors.OKBLUE, prefix=Prefixes.ARROW
)
print_fail_arrow = make_formatter_printer(Colors.FAIL, prefix=Prefixes.ARROW)

format_ok_blue = make_formatter_printer(Colors.OKBLUE, return_formatter=True)
format_ok = make_formatter_printer(Colors.OKGREEN, return_formatter=True)
format_warn = make_formatter_printer(Colors.WARNING, return_formatter=True)
format_fail = make_formatter_printer(Colors.FAIL, return_formatter=True)
format_bold = make_formatter_printer(Colors.BOLD, return_formatter=True)
format_normal = make_formatter_printer(Colors.ENDC, return_formatter=True)
format_ok_arrow = make_formatter_printer(
    Colors.OKGREEN, prefix=Prefixes.ARROW, return_formatter=True
)
format_ok_blue_arrow = make_formatter_printer(
    Colors.OKBLUE, prefix=Prefixes.ARROW, return_formatter=True
)
format_fail_arrow = make_formatter_printer(
    Colors.FAIL, prefix=Prefixes.ARROW, return_formatter=True
)
