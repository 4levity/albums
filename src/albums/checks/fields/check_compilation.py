import logging
from pathlib import Path
from typing import Any, Final, override

from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.checks.helpers import COMPILATION_PARENT_FOLDERS, VARIOUS_ARTISTS
from albums.entities import Album, Track
from albums.tagger import CANONICAL_COMPILATION_VALUE, AlbumTagger, BasicField, Cap

logger: Final = logging.getLogger(__name__)

OPTION_SET_COMPILATION: Final = ">> Set compilation flag on all tracks"
OPTION_REMOVE_COMPILATION: Final = ">> Remove compilation flag from all tracks"


def _flag_matches(track: Track, set_flag: bool) -> bool:
    """Return True when the track's compilation flag matches the expected state: the canonical value on every track, or absent."""
    values = track.get(BasicField.COMPILATION, default=())
    if set_flag:
        return values == (CANONICAL_COMPILATION_VALUE,)
    return not values


class CheckCompilationField(Check):
    """Check that the compilation flag matches the album's artists, and is canonical when present.

    An album is a compilation when:
    - the parent folder containing the album folder matches one of the ``compilation_parent_folders``
      values (case-insensitive), or
    - the album artist is "Various Artists", or
    - the album artist is not set, and the artist is "Various Artists" or there are two or more distinct
      artists, or
    - the album artist values are not consistent across tracks.
    An album with one consistent album artist that is not "Various Artists" is not a compilation, even if
    some tracks have different or additional artists (e.g. guest appearances). The album artist is what
    media players use to group the album, so the flag only has a purpose when the album has no single
    artist of its own.

    The flag must be set to the canonical value on every track of a compilation, or removed from every
    track of any other album.
    """

    name = "compilation"
    default_config = {
        "enabled": True,
        "compilation_parent_folders": list(COMPILATION_PARENT_FOLDERS),
    }
    must_pass_checks = {"artist"}

    def init(self, check_config: dict[str, Any]):
        compilation_parent_folders: list[Any] = check_config.get(
            "compilation_parent_folders", CheckCompilationField.default_config["compilation_parent_folders"]
        )
        if not isinstance(compilation_parent_folders, list) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(f, str) or f == "" for f in compilation_parent_folders
        ):
            logger.warning(f'compilation.compilation_parent_folders must be a list of folders, ignoring value "{compilation_parent_folders}"')
            compilation_parent_folders = []
        self.compilation_parent_folders = set(str.lower(folder) for folder in compilation_parent_folders)

    @override
    def check(self, album: Album) -> CheckResult | None:
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_FIELDS) for track in album.tracks):
            return None  # this check only makes sense for files with common fields

        parent_folder = Path(album.path).parent.name
        if parent_folder and str.lower(parent_folder) in self.compilation_parent_folders:
            set_flag, reason = True, f"parent folder {parent_folder}"
        else:
            set_flag, reason = self._is_compilation(album)

        if all(_flag_matches(track, set_flag) for track in album.tracks):
            return None

        table = (
            ["filename", "artist", "album artist", "compilation"],
            [
                [
                    escape(track.filename),
                    ", ".join(track.get(BasicField.ARTIST, default=[])) or "[italic]none[/italic]",
                    ", ".join(track.get(BasicField.ALBUMARTIST, default=[])) or "[italic]none[/italic]",
                    ", ".join(track.get(BasicField.COMPILATION, default=[])) or "[italic]none[/italic]",
                ]
                for track in sorted(album.tracks)
            ],
        )
        if set_flag:
            message = f"compilation flag should be set on all tracks ({reason})"
        else:
            message = f"compilation flag should be removed from all tracks ({reason})"
        return CheckResult(
            message,
            Fixer(
                lambda _: self._fix(album, set_flag),
                [OPTION_SET_COMPILATION if set_flag else OPTION_REMOVE_COMPILATION],
                False,
                0,
                table,
                "compilation flag",
            ),
        )

    def _is_compilation(self, album: Album) -> tuple[bool, str]:
        """Determine whether the album is a compilation from its album artist and artist values, returning (is_compilation, reason).

        A single consistent, non-Various-Artists album artist means the album is not a compilation, even
        when the artists differ between tracks (e.g. guest appearances). Without an album artist, the
        artists decide: "Various Artists" or two or more distinct artists means a compilation. Inconsistent
        album artist values mean no single artist represents the album.
        """
        album_artists: dict[str, str] = {}
        artists: dict[str, str] = {}
        for track in album.tracks:
            for field, values in ((BasicField.ALBUMARTIST, album_artists), (BasicField.ARTIST, artists)):
                for value in track.get(field, default=[]):
                    name = str.strip(value)
                    if name:
                        values.setdefault(str.lower(name), name)

        if len(album_artists) > 1:
            return True, "inconsistent album artist"
        if len(album_artists) == 1:
            album_artist = next(iter(album_artists.values()))
            if album_artist.lower() == VARIOUS_ARTISTS.lower():
                return True, f"album artist {VARIOUS_ARTISTS}"
            return False, f"album artist {album_artist}"
        if len(artists) > 1:
            return True, f"{len(artists)} distinct artists"
        if len(artists) == 1:
            artist = next(iter(artists.values()))
            if artist.lower() == VARIOUS_ARTISTS.lower():
                return True, f"artist {VARIOUS_ARTISTS}"
            return False, f"single artist: {artist}"
        return False, "no artists"

    def _fix(self, album: Album, set_flag: bool) -> FixResult:
        tagger = self.tagger.get(album.path)
        changed = False
        for track in sorted(album.tracks):
            if set_flag and not _flag_matches(track, True):
                self.ctx.console.print(f"Setting compilation flag on {escape(track.filename)}", highlight=False)
                with tagger.open(track.filename) as tag:
                    tag.set_field(BasicField.COMPILATION, CANONICAL_COMPILATION_VALUE)
                changed = True
            elif not set_flag and track.has(BasicField.COMPILATION):
                self.ctx.console.print(f"Removing compilation flag on {escape(track.filename)}", highlight=False)
                with tagger.open(track.filename) as tag:
                    tag.set_field(BasicField.COMPILATION, None)
                changed = True
        return FixResult.of(changed)
