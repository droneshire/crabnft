import os
import sys
import typing as T
import logging


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


def get_logging_dir() -> str:
    this_dir = os.path.dirname(os.path.realpath(__file__))
    src_dir = os.path.dirname(this_dir)
    return os.path.join(os.path.dirname(src_dir), "logs")


def is_color_supported() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def make_formatter_printer(
    color: Colors,
    log_level: int = logging.INFO,
    prefix: Prefixes = None,
    return_formatter: bool = False,
) -> T.Callable:
    game_logger = logging.getLogger(__name__)

    def formatter(message, *args, **kwargs):
        if args or kwargs:
            formatted_text = message.format(*args, **kwargs)
        else:
            formatted_text = message

        if prefix is not None:
            formatted_text = prefix + "\t" + formatted_text

        if is_color_supported():
            return color + formatted_text + Colors.ENDC
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
    else:
        return printer


print_ok_blue = make_formatter_printer(Colors.OKBLUE)
print_ok = make_formatter_printer(Colors.OKGREEN)
print_warn = make_formatter_printer(Colors.WARNING)
print_fail = make_formatter_printer(Colors.FAIL)
print_bold = make_formatter_printer(Colors.BOLD)
print_normal = make_formatter_printer(Colors.ENDC)
print_ok_arrow = make_formatter_printer(Colors.OKGREEN, prefix=Prefixes.ARROW)
print_ok_blue_arrow = make_formatter_printer(Colors.OKBLUE, prefix=Prefixes.ARROW)
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
