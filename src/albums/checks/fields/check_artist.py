from collections import defaultdict
from pathlib import Path
from typing import Any

from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.checks.helpers import COMPILATION_PARENT_FOLDERS, format_field_values, valid_folder_list
from albums.entities import Album
from albums.tagger import AlbumTagger, BasicField, Cap
from albums.words import plural


class CheckArtistField(Check):
    name = "artist"
    default_config = {
        "enabled": True,
        "ignore_parent_folders": list(COMPILATION_PARENT_FOLDERS),
    }
    must_pass_checks = {"album-artist"}

    def init(self, check_config: dict[str, Any]):
        self.ignore_parent_folders = valid_folder_list(
            check_config, "artist", "ignore_parent_folders", CheckArtistField.default_config["ignore_parent_folders"]
        )

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_FIELDS) for track in album.tracks):
            return None

        artist_values: defaultdict[str, list[str]] = defaultdict(list)
        for track in album.tracks:
            if track.has(BasicField.ARTIST):
                for artist_name in track.get(BasicField.ARTIST):
                    artist_values[artist_name].append(track.filename)
            else:
                artist_values[""].append(track.filename)
            for album_artist_name in track.get(BasicField.ALBUMARTIST, default=[]):
                artist_values[album_artist_name].append(track.filename)

        if not artist_values[""]:  # no tracks missing artist field
            return None

        parent_folder_str = Path(album.path).parent.name
        if parent_folder_str and parent_folder_str.casefold() not in self.ignore_parent_folders:
            artist_values[parent_folder_str] = artist_values.get(parent_folder_str, []) + [parent_folder_str]

        artist_list = list(artist_values.keys())
        candidates = sorted(
            filter(lambda v: v and not v.casefold().startswith("various"), artist_list), key=lambda a: len(artist_values[a]), reverse=True
        )[:6]
        table = (
            ["filename", "album artist", "artist", "proposed artist"],
            [
                [
                    escape(track.filename),
                    format_field_values(track.get(BasicField.ALBUMARTIST, default=None)),
                    format_field_values(track.get(BasicField.ARTIST, default=None)),
                    format_field_values([candidates[0]] if candidates and not track.has(BasicField.ARTIST) else None),
                ]
                for track in sorted(album.tracks)
            ],
        )
        option_free_text = True
        option_automatic_index = 0 if len(candidates) == 1 else None
        return CheckResult(
            f"{plural(artist_values[''], 'track')} missing artist field",
            Fixer(
                lambda option: self._fix(album, option, artist_values[""]),
                candidates,
                option_free_text,
                option_automatic_index,
                table,
                f"select artist name to use for {plural(artist_values[''], 'track')} where it is missing",
            ),
        )

    def _fix(self, album: Album, option: str, filenames: list[str]):
        for filename in filenames:
            file = self.ctx.config.library / album.path / filename
            self.ctx.console.print(f"setting artist on {escape(filename)}", highlight=False)
            self.tagger.get(album.path).set_basic_fields(file, [(BasicField.ARTIST, option)])
        return FixResult.CHANGED_ALBUM
