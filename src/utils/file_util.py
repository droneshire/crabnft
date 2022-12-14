import os


def make_sure_path_exists(path: str) -> None:
    path = os.path.dirname(path) if os.path.isfile(path) else path

    root = ""
    for directory in path.split("/"):
        section = os.path.join(root, directory)
        root = section

        if not os.path.isdir(section):
            os.mkdir(section)
