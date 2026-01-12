import math
import os


def progress_bar(iterable, get_prefix=lambda: ""):
    item_count = len(iterable)

    def show(iteration):
        prefix = get_prefix()
        try:
            width = max(10, os.get_terminal_size().columns - 8 - len(prefix))
        except OSError:
            width = 80
        fill = int(width * iteration // item_count) if item_count > 0 else width
        percent = math.floor(100 * (iteration / float(item_count))) if item_count > 0 else "100"
        print(f"\r{prefix}[{'#' * fill + '.' * (width - fill)}] {percent}%", end="\r")

    show(0)
    for i, item in enumerate(iterable):
        yield item
        show(i + 1)

    print()
