import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Final

from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.checks.helpers import format_field_values
from albums.entities import Album
from albums.tagger.folder import AlbumTagger, Cap
from albums.tagger.types import BasicField
from albums.words import plural, pluralize

logger: Final = logging.getLogger(__name__)


class CheckAlbumField(Check):
    name = "album"
    default_config = {"enabled": True, "ignore_folders": ["misc"]}

    def init(self, check_config: dict[str, Any]):
        ignore_folders: list[Any] = check_config.get("ignore_folders", CheckAlbumField.default_config["ignore_folders"])
        if not isinstance(ignore_folders, list) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(f, str) or f == "" for f in ignore_folders
        ):
            logger.warning(f'album.ignore_folders must be a list of folders, ignoring value "{ignore_folders}"')
            ignore_folders = []
        self.ignore_folders = list(str(folder) for folder in ignore_folders)

    def check(self, album: Album):
        folder_str = Path(album.path).name
        if folder_str in self.ignore_folders:
            return None

        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_FIELDS) for track in album.tracks):
            return None

        track_album_fields: defaultdict[str, int] = defaultdict(int)
        for track in album.tracks:
            if track.has(BasicField.ALBUM):
                for album_field in track.get(BasicField.ALBUM):
                    track_album_fields[album_field] += 1
            else:
                track_album_fields[""] += 1

        album_fields = list(track_album_fields.keys())
        candidates = sorted(filter(None, album_fields), key=lambda a: track_album_fields[a], reverse=True)[:12]
        if len(candidates) > 1:  # multiple conflicting album names (not including folder name)
            if folder_str not in candidates:
                candidates.append(folder_str)
            return CheckResult(f"{len(candidates)} conflicting album field {pluralize('value', candidates)}", self._make_fixer(album, candidates))

        if track_album_fields[""] > 0:  # tracks missing album field
            if folder_str not in candidates:
                candidates.append(folder_str)
            return CheckResult(f"{plural(track_album_fields[''], 'track')} missing album field", self._make_fixer(album, candidates))

        return None

    def _make_fixer(self, album: Album, options: list[str]):
        table = (
            ["filename", "album", "artist", "album artist"],
            [
                [
                    escape(track.filename),
                    format_field_values(track.get(BasicField.ALBUM, default=None)),
                    format_field_values(track.get(BasicField.ARTIST, default=None)),
                    format_field_values(track.get(BasicField.ALBUMARTIST, default=None)),
                ]
                for track in sorted(album.tracks)
            ],
        )
        return Fixer(
            lambda option: self._fix(album, option),
            options,
            True,
            0 if len(options) == 1 else None,
            table,
            f"select album name to use for {plural(album.tracks, 'track')}",
        )

    def _fix(self, album: Album, option: str):
        changed = False
        for track in sorted(album.tracks):
            file = self.ctx.config.library / album.path / track.filename
            if track.get(BasicField.ALBUM, default=[]) != (option,):
                self.ctx.console.print(f"setting album on {escape(track.filename)}", highlight=False)
                self.tagger.get(album.path).set_basic_fields(file, [(BasicField.ALBUM, option)])
                changed = True
        return FixResult.of(changed)
