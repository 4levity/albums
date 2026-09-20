from itertools import chain
from os import scandir
from shutil import rmtree
from typing import Final, Sequence, override

import humanize
from prompt_toolkit.shortcuts import confirm
from rich.console import RenderableType
from rich.markup import escape
from sqlalchemy import select
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.entities import Album, OtherFile, PictureFile, Track
from albums.tagger import AlbumTaggerProvider
from albums.words import plural

OPTION_DELETE_OTHER: Final = ">> KEEP left (THIS album) and DELETE right (other): "
OPTION_KEEP_OTHER: Final = ">> DELETE left (THIS album) and KEEP right (other): "
# OS housekeeping files that would be deleted with the folder but that never appear in the database
IGNORED_FILES: Final = frozenset({".DS_Store", "Thumbs.db"})


class CheckDuplicateAlbum(Check):
    """Check for albums that duplicate other albums in the library (same artist and album name).

    This check deliberately breaks the stateless check guideline (see docs/developing.md) because
    there is no other practical way to find duplicates: it must compare each album against every
    other album in the library, not just the album passed to ``check()``.

    ``__init__`` builds that comparison in a single grouped query over the track field tables (the
    most common artist and album name of every album), keeping only the albums that form a
    duplicate (artist, album name) group, in ``self._duplicates``. It is done once per check run
    rather than per album, and the check announces it so it can be disabled to skip it.

    The state is defensive only: ``check()`` does not mutate it. It merely looks the album up in
    the in-memory index and queries the database for the duplicate albums to display. The index
    is only mutated, via ``remove()``, when a duplicate is actually deleted in the fix phase.
    """

    name = "duplicate-album"
    default_config = {"enabled": True}
    must_pass_checks = {"album", "artist"}

    def __init__(self, ctx: Context, tagger: AlbumTaggerProvider | None = None, session: Session | None = None):
        super().__init__(ctx, tagger, session)

        from albums.library import DuplicateFinder  # avoid circular import when all checks are imported

        self._duplicates = DuplicateFinder()
        # tell user about the delay so the check can be disabled if unwanted
        with ctx.console.status(f"Initializing [bold]{self.name}[/bold] check [italic](disable check to skip)[/italic]", spinner="bouncingBar"):
            self._duplicates.start(self.session)

    @override
    def check(self, album: Album) -> CheckResult | None:
        if not self.ctx.is_persistent:
            return None

        duplicate_ids = self._duplicates.find(album)
        if not duplicate_ids:
            return None

        other_albums = [a for (a,) in self.session.execute(select(Album).filter(Album.album_id.in_(duplicate_ids))).tuples()]
        if len(other_albums) > 1:
            return CheckResult(f"multiple duplicates: {', '.join(f'"{a.path}"' for a in other_albums)}")

        other = other_albums[0]
        if str.lower(album.path) == str.lower(other.path):
            return CheckResult(f'possible duplicate of "{other.path}" but no automatic fix because paths differ only in case')

        this_tracks = sorted(album.tracks)
        other_tracks = sorted(other.tracks)
        rows: list[list[RenderableType]] = [[*self._summarize(album), *self._summarize(other)], [""] * 4]
        rows.extend(
            [self._filename(this_tracks, ix), self._desc(this_tracks, ix), self._filename(other_tracks, ix), self._desc(other_tracks, ix)]
            for ix in range(0, max(len(this_tracks), len(other_tracks)))
        )
        this_more = sorted(album.picture_files + album.other_files)
        other_more = sorted(other.picture_files + other.other_files)
        if len(this_more) + len(other_more):
            rows.extend([[""] * 4, ["[italic]other files (scanned files only)[/italic]", ""] * 2])
            rows.extend(
                [self._filename(this_more, ix), self._desc(this_more, ix), self._filename(other_more, ix), self._desc(other_more, ix)]
                for ix in range(0, max(len(this_more), len(other_more)))
            )
        table = ([f'This album: "{escape(album.path)}"', "files", f'Other album: "{escape(other.path)}"', "files"], rows)
        options: list[str] = [f"{OPTION_DELETE_OTHER}{other.path}", f"{OPTION_KEEP_OTHER}{other.path}"]
        option_automatic_index = None
        return CheckResult(
            f'possible duplicate of "{other.path}"',
            Fixer(lambda option: self._fix_delete_album(album, other, option), options, False, option_automatic_index, table),
        )

    def _fix_delete_album(self, album: Album, other: Album, option: str) -> FixResult:
        if option == f"{OPTION_DELETE_OTHER}{other.path}":
            if self._delete_album(other):
                return FixResult.CHANGED_OTHER
        elif option == f"{OPTION_KEEP_OTHER}{other.path}":
            if self._delete_album(album):
                return FixResult.DELETED_ALBUM
        else:
            raise ValueError(f"invalid option {option}")
        return FixResult.NO_CHANGE  # deletion was not confirmed

    def _delete_album(self, album: Album) -> bool:
        """Delete the album folder from disk, refusing to delete more than the album.

        Refuses when the folder is a symlink or contains subfolders or symlinks (which may hold other
        albums or data outside the album), and asks for confirmation before deleting files that are
        not in the database. A folder that is already gone is treated as deleted.

        Returns:
            True if the album is gone from disk (deleted here or already absent), else False.
        """
        path = self.ctx.config.library / album.path
        if path.is_symlink():
            self.ctx.console.print(f'Not deleting "{escape(str(path))}": the album folder is a symlink')
            return False
        if not path.is_dir():
            if path.exists():
                self.ctx.console.print(f'Not deleting "{escape(str(path))}": the path exists but is not a folder')
                return False
            # no rmtree, no prompt: the folder is already gone
            self.ctx.console.print(f"[yellow]Warning:[/yellow] {escape(str(path))} does not exist, so the album is already deleted from disk")
            self._duplicates.remove(album)
            return True
        with scandir(path) as it:
            entries = [(e.name, e.is_symlink(), e.is_dir(), e.is_file()) for e in it]
        subfolders = sorted(name for (name, is_symlink, is_dir, _is_file) in entries if is_dir and not is_symlink)
        symlinks = sorted(name for (name, is_symlink, _is_dir, _is_file) in entries if is_symlink)
        if subfolders or symlinks:
            problems: list[str] = []
            if subfolders:
                problems.append(f"subfolders: {', '.join(subfolders)}")
            if symlinks:
                problems.append(f"symlinks: {', '.join(symlinks)}")
            self.ctx.console.print(f'Not deleting "{escape(str(path))}": the folder contains ' + " and ".join(problems))
            return False
        known_files = {file.filename for file in chain(album.tracks, album.picture_files, album.other_files)}
        extra_files = sorted(
            name for (name, _is_symlink, _is_dir, is_file) in entries if is_file and name not in known_files and name not in IGNORED_FILES
        )
        if extra_files and not confirm(
            f"The folder contains {plural(extra_files, 'file')} not in the database: {', '.join(extra_files)}. Delete them too?"
        ):
            return False
        if confirm(f'Are you sure you want to permanently delete "{str(path)}"?'):
            rmtree(path)
            self._duplicates.remove(album)
            self.ctx.console.print(f"Deleted {escape(album.path)}")
            return True
        return False

    def _summarize(self, album: Album) -> tuple[str, str]:
        track_codecs = set(t.stream.codec for t in album.tracks)
        codec = "[bold]multiple codecs[/bold]" if len(track_codecs) > 1 else track_codecs.pop()
        bitrate = f"{int(sum(t.stream.bitrate for t in album.tracks) / len(album.tracks) / 1024)}kbps"

        time = _min_sec(sum(t.stream.length for t in album.tracks))
        size = humanize.naturalsize(sum(f.file_size for f in chain(album.tracks, album.picture_files, album.other_files)))

        return (f"[italic]{len(album.tracks)} tracks {codec} ~{bitrate} {time}[/italic]", size)

    def _filename(self, files: Sequence[Track | PictureFile | OtherFile], ix: int) -> str:
        return escape(files[ix].filename) if ix < len(files) else ""

    def _desc(self, files: Sequence[Track | PictureFile | OtherFile], ix: int) -> str:
        if ix >= len(files):
            return ""

        file = files[ix]
        time = f"{_min_sec(file.stream.length)} " if isinstance(file, Track) else ""
        return f"{time}{humanize.naturalsize(file.file_size)}"


def _min_sec(secs: float | int) -> str:
    return "{:02}m{:02}s".format(*divmod(int(secs), 60))
