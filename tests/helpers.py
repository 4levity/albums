from pathlib import Path

from click.testing import CliRunner

from albums.cli import entry_point


def init_db(library: Path):
    return CliRunner().invoke(entry_point.albums_group, ["--db-file", str(library / "albums.db"), "init", str(library)])


def run(params: list[str], library: Path):
    return CliRunner().invoke(entry_point.albums_group, ["--db-file", str(library / "albums.db")] + params)
