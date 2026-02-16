from pathlib import Path

from click.testing import CliRunner

from albums.cli import entry_point


def run(params: list[str], library: Path, init=False):
    return CliRunner().invoke(
        entry_point.albums_group,
        ["--db-file", library / "albums.db"] + (["--library", library] if init else []) + params,
    )
