from pathlib import Path
from typing import Generator, List, Sequence, Tuple

from click.testing import CliRunner

from albums.cli import entry_point
from albums.entities import Track
from albums.tagger import BasicField, Picture, StreamInfo, TaggerFile

from .fixtures.create_library import create_track_file


class MockTagger(TaggerFile):
    """Concrete TaggerFile for tests, whose methods are no-ops unless patched by the test."""

    def get_fields(self) -> Tuple[Tuple[BasicField, Tuple[str, ...]], ...]:
        return ()

    def get_stream_info(self) -> StreamInfo:
        return StreamInfo()

    def get_image_data(self, picture: Picture) -> bytes:
        return b""

    def get_pictures(self) -> Generator[Tuple[Picture, bytes], None, None]:
        yield from ()

    def set_field(self, field: BasicField | str, value: str | List[str] | None) -> None:
        pass

    def add_picture(self, new_picture: Picture, image_data: bytes) -> None:
        pass

    def remove_picture(self, remove_picture: Picture) -> None:
        pass

    def close(self) -> None:
        pass


def init_db(library: Path):
    return CliRunner().invoke(entry_point.albums_group, ["--db-file", str(library / "albums.db"), "init", str(library)])


def run(params: list[str], library: Path):
    return CliRunner().invoke(entry_point.albums_group, ["--db-file", str(library / "albums.db")] + params)


def fake_ffmpeg(args: Sequence[str], cwd: Path) -> None:
    file = Path(args[-1])
    create_track_file(file.parent, Track(filename=file.name))
