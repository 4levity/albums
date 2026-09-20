"""Benchmark the checks on a synthetic library (empty folders + database rows, no files).

Generates a library of clean albums and runs all enabled checks with timing, measuring the
real clock time of each check's init and per-album pass/fail cost at that library size.
Use it to see how check time scales (e.g. duplicate-album's whole-library init) without
touching a real library:

    uv run python scripts/bench_checks.py 10000
    uv run python scripts/bench_checks.py 100000 --broken-every 100

Every Nth album (--broken-every N) gets a track-numbering gap, so the "problem found"
timing of the checks that catch it is measured too. The generated library is removed
after the run.
"""

import argparse
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.checker import Checker
from albums.database import db_open
from albums.entities import Album, LibraryFolder, Track
from albums.selector import load_album_entities
from albums.tagger import BasicField

TRACK_COUNT = 10
ARTIST = "Artist"
ALBUM_BATCH = 10_000


def track_fields(album: int, track: int) -> dict[BasicField, list[str]]:
    return {
        BasicField.ARTIST: [ARTIST],
        BasicField.ALBUM: [f"Album {album}"],
        BasicField.TITLE: [f"track {track}"],
        BasicField.TRACKNUMBER: [f"{track:02d}"],
        BasicField.TRACKTOTAL: [str(TRACK_COUNT)],
    }


def create_folders(library: Path, n_albums: int) -> None:
    for i in range(1, n_albums + 1):
        os.makedirs(library / ARTIST / f"Album {i}")


def seed_library(session: Session, n_albums: int, broken_every: int) -> None:
    """Insert the album, track and library folder rows directly (much faster than scanning files)."""
    now = int(datetime.now(UTC).timestamp())
    album_paths = [f"{ARTIST}{os.sep}Album {i}{os.sep}" for i in range(1, n_albums + 1)]
    session.execute(insert(Album), [{"path": path, "scanner": 0, "created_at": now, "modified_at": now} for path in album_paths])
    session.flush()
    album_ids = dict((path, album_id) for (album_id, path) in session.execute(select(Album.__table__.c.album_id, Album.__table__.c.path)).tuples())

    track_defaults: dict[str, Any] = {
        "file_size": 0,
        "modify_timestamp": 0,
        "stream_length": 0.0,
        "stream_bitrate": 0,
        "stream_channels": 0,
        "stream_codec": "",
        "stream_sample_rate": 0,
        "stream_bits_per_sample": 0,
        "stream_error": "",
    }
    for start in range(1, n_albums + 1, ALBUM_BATCH):
        stop = min(start + ALBUM_BATCH, n_albums + 1)
        rows: list[dict[str, Any]] = []
        for i in range(start, stop):
            broken = broken_every > 0 and i % broken_every == 0
            for n in range(1, TRACK_COUNT + 1):
                if broken and n % 5 == 0:
                    continue  # leave a gap in the track numbering so track-numbering fails
                rows.append(
                    {
                        "album_id": album_ids[f"{ARTIST}{os.sep}Album {i}{os.sep}"],
                        "filename": f"{n:02d} track {n}.flac",
                        "fields": track_fields(i, n),
                        **track_defaults,
                    }
                )
        session.execute(insert(Track), rows)

    folder_rows: list[dict[str, str]] = [{"parent_path": "", "name": ARTIST, "name_cf": ARTIST.casefold()}]
    folder_rows.extend({"parent_path": f"{ARTIST}{os.sep}", "name": f"Album {i}", "name_cf": f"album {i}"} for i in range(1, n_albums + 1))
    session.execute(insert(LibraryFolder), folder_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("albums", nargs="?", type=int, default=1_000, help="number of albums to generate (default: 1000)")
    parser.add_argument(
        "--broken-every",
        type=int,
        default=0,
        help="give every Nth album a track-numbering gap so the checks find problems (0 = all clean, the default)",
    )
    args = parser.parse_args()
    n_albums = args.albums

    with tempfile.TemporaryDirectory(prefix="albums-bench-") as temp:
        library = Path(temp) / "library"
        start = time.perf_counter()
        create_folders(library, n_albums)
        ctx = Context()
        ctx.config.library = library
        ctx.db = db_open(Path(temp) / "bench.db")
        try:
            with Session(ctx.db) as session:
                seed_library(session, n_albums, args.broken_every)
                session.commit()
                print(f"generated {n_albums} albums in {time.perf_counter() - start:.1f}s")

                ctx.select_album_entities = lambda session, order_by="path": load_album_entities(session)
                start = time.perf_counter()
                checker = Checker(ctx, automatic=False, fix=False, interactive=False, show_ignore_option=False, timing=True)
                issues = checker.run_enabled(session)
                print(f"checked {n_albums} albums, found {issues} issues, in {time.perf_counter() - start:.1f}s")
        finally:
            ctx.db.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
