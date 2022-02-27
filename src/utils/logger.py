import sys
import typing as T
import logging

class Colors:
    """
    ANSI terminal colors.
    See: http://stackoverflow.com/questions/287871/print-in-terminal-with-colors-using-python
    """

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

def is_color_supported() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def make_formatter_printer(color : Colors, prefix=None) -> T.Callable:
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
        game_logger.info(message)
        print(formatter(message, *args, **kwargs))
        sys.stdout.flush()

    return printer


print_ok_blue = make_formatter_printer(Colors.OKBLUE)

print_ok = make_formatter_printer(Colors.OKGREEN)

print_warn = make_formatter_printer(Colors.WARNING)

print_fail = make_formatter_printer(Colors.FAIL)

print_bold = make_formatter_printer(Colors.BOLD)

print_normal = make_formatter_printer(Colors.ENDC)

print_ok_arrow = make_formatter_printer(Colors.OKGREEN, Prefixes.ARROW)
print_fail_arrow = make_formatter_printer(Colors.OKGREEN, Prefixes.ARROW)
