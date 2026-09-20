"""Measure process memory while running a command, then plot the result.

The capture samples about every 20 ms and writes a CSV with two memory columns:

- ``python_rss_kb``: the largest CPython process in the tree, normally the main albums
  process (identified by its interpreter executable, so process name changes do not
  matter). The tree is walked, so wrapper processes (``uv``, subshells, ...) are skipped
  automatically.
- ``tree_rss_kb``: the total RSS of the launched process plus all of its descendants.
  Plot this instead when the tree has no Python process (e.g. a PyInstaller build).

Basic usage with a real library (capture, then plot):

    uv run python scripts/memtrace.py capture -o before.csv -- uv run albums check
    uv run python scripts/memtrace.py plot before.csv -o before.svg

Compare two runs by passing several CSVs to plot:

    uv run python scripts/memtrace.py plot before.csv after.csv --labels before,after

To capture a process that is already running (e.g. an interactive session), use ``--pid``
with any pid in its process tree (e.g. the uv process of a ``uv run albums`` command).
"""

import argparse
import csv
import html
import math
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

CSV_COLUMNS = ("t_ms", "python_rss_kb", "tree_rss_kb")
MIN_INTERVAL = 0.001
COLORS = ("#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#17becf", "#e377c2")


def read_proc_stat(pid: int) -> tuple[int, str] | None:
    """Return (ppid, process name) for pid, or None if it is gone."""
    try:
        data = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    # The process name is in parens and may contain spaces, so split around the last ")"
    name = data.split("(", 1)[1].rsplit(")", 1)[0]
    return int(data.rsplit(")", 1)[1].split()[1]), name


def read_rss_kb(pid: int) -> int | None:
    """Return the process's resident set size in KB, or None if it is gone."""
    try:
        statm = Path(f"/proc/{pid}/statm").read_text()
    except OSError:
        return None
    return int(statm.split()[1]) * (os.sysconf("SC_PAGE_SIZE") // 1024)


def is_python_process(pid: int, name: str) -> bool:
    """True if the process is a CPython interpreter (checked by exe, since the app renames its process name)."""
    if name.startswith("python"):
        return True
    try:
        exe = os.readlink(f"/proc/{pid}/exe")
    except OSError:
        return False
    return os.path.basename(exe).startswith(("python", "cpython"))


def sample_tree(root: int) -> tuple[int, int]:
    """Return (python_rss_kb, tree_rss_kb) for the process tree rooted at root.

    python_rss_kb is the largest RSS of the CPython processes in the tree (the main
    albums process); tree_rss_kb sums the whole tree. Raises FileNotFoundError if root
    no longer exists.
    """
    names: dict[int, str] = {}
    children: dict[int, list[int]] = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        stat = read_proc_stat(int(entry))
        if stat is None:
            continue
        ppid, name = stat
        names[int(entry)] = name
        children.setdefault(ppid, []).append(int(entry))
    if root not in names:
        raise FileNotFoundError(root)
    tree: list[int] = []
    stack = [root]
    while stack:
        pid = stack.pop()
        if pid not in names:
            continue
        tree.append(pid)
        stack.extend(children.get(pid, ()))
    tree_kb = 0
    python_kb = 0
    for pid in tree:
        rss = read_rss_kb(pid)
        if rss is None:
            continue
        tree_kb += rss
        if is_python_process(pid, names[pid]) and rss > python_kb:
            python_kb = rss
    return python_kb, tree_kb


def write_csv(output: Path, rows: list[tuple[int, int, int]]) -> None:
    with output.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)


def cmd_capture(args: argparse.Namespace) -> int:
    if not os.path.isdir("/proc"):
        print("capture requires Linux (/proc)", file=sys.stderr)
        return 2
    command: list[str] = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if args.pid is not None and command:
        print("use either --pid or a command after --, not both", file=sys.stderr)
        return 2
    child = None
    if args.pid is not None:
        root = args.pid
    elif command:
        child = subprocess.Popen(command)
        root = child.pid
    else:
        print("capture needs a command after -- or --pid", file=sys.stderr)
        return 2
    if read_proc_stat(root) is None:
        print(f"pid {root} does not exist", file=sys.stderr)
        return 2
    output = Path(args.output) if args.output else Path(f"memtrace-{datetime.now(UTC):%Y%m%d-%H%M%S}.csv")
    interval = max(args.interval, MIN_INTERVAL)
    rows: list[tuple[int, int, int]] = []
    start = time.monotonic()
    next_tick = start
    interrupted = False
    try:
        while True:
            if child is not None and child.poll() is not None:
                break
            try:
                sample = sample_tree(root)
            except FileNotFoundError:
                break
            rows.append((int((time.monotonic() - start) * 1000), sample[0], sample[1]))
            # skip over missed ticks instead of bursting, so the cadence never drifts
            while next_tick <= time.monotonic():
                next_tick += interval
            delay = next_tick - time.monotonic()
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt:
        interrupted = True
        if child is not None and child.poll() is None:
            child.kill()
            child.wait()
    finally:
        write_csv(output, rows)
    if child is not None:
        exit_code = child.returncode if child.returncode is not None else 1
    else:
        exit_code = 0
    duration = rows[-1][0] / 1000 if rows else 0.0
    print(f"memtrace: {len(rows)} samples over {duration:.1f}s -> {output}", file=sys.stderr)
    if rows:
        for name, index in (("python", 1), ("tree", 2)):
            values = [row[index] for row in rows]
            print(
                f"memtrace: {name} rss min {min(values) / 1024:.1f} MB, max {max(values) / 1024:.1f} MB, final {values[-1] / 1024:.1f} MB",
                file=sys.stderr,
            )
    else:
        print("memtrace: no samples captured (process exited before the first sample?)", file=sys.stderr)
    if child is not None:
        print(f"memtrace: command exited with code {exit_code}", file=sys.stderr)
    return 130 if interrupted else exit_code


def read_series(path: Path, column: str) -> list[tuple[float, float]]:
    """Return (t_s, rss_mb) points for the column of a captured CSV."""
    with path.open(newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows or column not in rows[0] or "t_ms" not in rows[0]:
        raise ValueError(f"{path} is not a memtrace CSV (needs t_ms and {column} columns)")
    t_index, v_index = rows[0].index("t_ms"), rows[0].index(column)
    points: list[tuple[float, float]] = []
    for row in rows[1:]:
        if len(row) <= max(t_index, v_index):
            continue
        points.append((float(row[t_index]) / 1000.0, float(row[v_index]) / 1024.0))
    return points


def choose_column(files: list[Path], which: str) -> str:
    if which == "python":
        return "python_rss_kb"
    if which == "tree":
        return "tree_rss_kb"
    # auto: prefer the main python process, fall back to the whole tree (no python in it)
    for path in files:
        try:
            if any(point[1] > 0 for point in read_series(path, "python_rss_kb")):
                return "python_rss_kb"
        except ValueError:
            continue
    return "tree_rss_kb"


def nice_step(rough: float) -> float:
    if rough <= 0:
        return 1.0
    magnitude = 10.0 ** math.floor(math.log10(rough))
    for multiplier in (1.0, 2.0, 5.0, 10.0):
        if multiplier * magnitude >= rough:
            return multiplier * magnitude
    return 10.0 * magnitude


def nice_ticks(lo: float, hi: float, target: int = 6) -> list[float]:
    step = nice_step((hi - lo) / target)
    first = math.ceil(lo / step)
    last = math.floor(hi / step) + 1
    return [i * step for i in range(first, last + 1)]


def fmt_num(value: float) -> str:
    return f"{value:g}"


def render_svg(series: list[tuple[str, str, list[tuple[float, float]]]], title: str, y_min: float, output: Path) -> None:
    width, height = 960, 520
    margin_left, margin_right, margin_top, margin_bottom = 72, 24, 52, 60
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    x1 = max((point[0] for _, _, points in series for point in points), default=0.0) or 1.0
    y_max_data = max((point[1] for _, _, points in series for point in points), default=0.0)
    y1 = max(y_max_data * 1.05, y_min + 1.0)
    x_ticks = nice_ticks(0.0, x1)
    y_ticks = nice_ticks(y_min, y1)
    x1, y1 = x_ticks[-1], y_ticks[-1]

    def sx(x: float) -> float:
        return margin_left + (x / x1) * plot_w

    def sy(y: float) -> float:
        return margin_top + (1.0 - (y - y_min) / (y1 - y_min)) * plot_h

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="Helvetica, Arial, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="{width / 2}" y="28" text-anchor="middle" font-size="18">{html.escape(title)}</text>',
    ]
    for tick in x_ticks:
        x = sx(tick)
        parts.append(f'<line x1="{x:.1f}" y1="{margin_top}" x2="{x:.1f}" y2="{margin_top + plot_h}" stroke="#e0e0e0"/>')
        parts.append(f'<text x="{x:.1f}" y="{margin_top + plot_h + 18}" text-anchor="middle" font-size="12" fill="#333">{fmt_num(tick)}</text>')
    for tick in y_ticks:
        y = sy(tick)
        parts.append(f'<line x1="{margin_left}" y1="{y:.1f}" x2="{margin_left + plot_w}" y2="{y:.1f}" stroke="#e0e0e0"/>')
        parts.append(f'<text x="{margin_left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#333">{fmt_num(tick)}</text>')
    parts.append(f'<rect x="{margin_left}" y="{margin_top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#333"/>')
    for label, color, points in series:
        if not points:
            continue
        points_attr = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in points)
        parts.append(f'<polyline points="{points_attr}" fill="none" stroke="{color}" stroke-width="2"/>')
    for index, (label, color, _) in enumerate(series):
        legend_y = margin_top + 16 + index * 18
        legend_x = width - margin_right - 200
        parts.append(f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 18}" y2="{legend_y}" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{legend_x + 24}" y="{legend_y + 4}" font-size="12" fill="#333">{html.escape(label)}</text>')
    parts.append(f'<text x="{margin_left + plot_w / 2}" y="{height - 14}" text-anchor="middle" font-size="13" fill="#333">time (s)</text>')
    parts.append(
        f'<text transform="translate(18 {margin_top + plot_h / 2}) rotate(-90)" text-anchor="middle" font-size="13" fill="#333">memory (MB)</text>'
    )
    parts.append("</svg>")
    output.write_text("\n".join(parts))


def cmd_plot(args: argparse.Namespace) -> int:
    files = [Path(name) for name in args.files]
    for path in files:
        if not path.is_file():
            print(f"no such file: {path}", file=sys.stderr)
            return 2
    labels = [label.strip() for label in args.labels.split(",")] if args.labels else [path.stem for path in files]
    if len(labels) != len(files):
        print("--labels needs one label per file", file=sys.stderr)
        return 2
    column = choose_column(files, args.which)
    if args.which == "auto" and column == "tree_rss_kb":
        print("memtrace: no python process found in the CSVs, plotting tree_rss_kb (use --which to choose)", file=sys.stderr)
    series: list[tuple[str, str, list[tuple[float, float]]]] = []
    for index, (path, label) in enumerate(zip(files, labels)):
        try:
            points = read_series(path, column)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2
        series.append((label, COLORS[index % len(COLORS)], points))
    output = Path(args.output) if args.output else files[0].with_suffix(".svg")
    render_svg(series, args.title, args.y_min, output)
    print(f"memtrace: wrote {output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="sample the memory of a command's process tree into a CSV")
    capture.add_argument("--pid", type=int, help="attach to this pid's process tree instead of launching a command")
    capture.add_argument("-o", "--output", help="CSV output path (default: memtrace-<timestamp>.csv in the current directory)")
    capture.add_argument("--interval", type=float, default=0.02, help="sampling interval in seconds (default: 0.02, i.e. 20 ms)")
    capture.add_argument("command", nargs=argparse.REMAINDER, help="command to run, after -- (required unless --pid is given)")
    capture.set_defaults(func=cmd_capture)

    plot = subparsers.add_parser("plot", help="plot one or more captured CSVs as an SVG chart")
    plot.add_argument("files", nargs="+", help="CSV files written by capture")
    plot.add_argument("-o", "--output", help="SVG output path (default: the first input file's name with a .svg suffix)")
    plot.add_argument("--labels", help="comma-separated series labels (default: the input file names)")
    plot.add_argument("--which", choices=("auto", "python", "tree"), default="auto", help="which CSV column to plot (default: auto)")
    plot.add_argument("--y-min", type=float, default=0.0, help="y-axis starting value in MB (default: 0)")
    plot.add_argument("--title", default="memory usage", help="chart title (default: %(default)s)")
    plot.set_defaults(func=cmd_plot)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
