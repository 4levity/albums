from pathlib import Path
from typing import Sequence

from click.testing import CliRunner

from albums.cli import entry_point
from albums.types import Track

from .fixtures.create_library import create_track_file


def init_db(library: Path):
    return CliRunner().invoke(entry_point.albums_group, ["--db-file", str(library / "albums.db"), "init", str(library)])


def run(params: list[str], library: Path):
    return CliRunner().invoke(entry_point.albums_group, ["--db-file", str(library / "albums.db")] + params)


def fake_ffmpeg(args: Sequence[str], cwd: Path) -> None:
    file = Path(args[-1])
    create_track_file(file.parent, Track(filename=file.name))
