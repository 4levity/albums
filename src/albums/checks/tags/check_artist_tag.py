import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from rich.markup import escape

from ...database.models import AlbumEntity
from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import BasicTag
from ...types import CheckResult, Fixer
from ..base_check import Check
from ..helpers import show_tag

logger = logging.getLogger(__name__)


class CheckArtistTag(Check):
    name = "artist-tag"
    default_config = {
        "enabled": True,
        "ignore_parent_folders": ["compilation", "compilations", "soundtrack", "soundtracks", "various artists"],
    }
    must_pass_checks = {"album-artist"}

    def init(self, check_config: dict[str, Any]):
        ignore_parent_folders: list[Any] = check_config.get("ignore_parent_folders", CheckArtistTag.default_config["ignore_parent_folders"])
        if not isinstance(ignore_parent_folders, list) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(f, str) or f == "" for f in ignore_parent_folders
        ):
            logger.warning(f'artist-tag.ignore_parent_folders must be a list of folders, ignoring value "{ignore_parent_folders}"')
            ignore_parent_folders = []
        self.ignore_parent_folders = set(str(folder) for folder in ignore_parent_folders)

    def check(self, album: AlbumEntity):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_TAGS) for track in album.tracks):
            return None

        artist_values: defaultdict[str, list[str]] = defaultdict(list)
        for track in album.tracks:
            if track.has(BasicTag.ARTIST):
                for artist_tag in track.get(BasicTag.ARTIST):
                    artist_values[artist_tag].append(track.filename)
            else:
                artist_values[""].append(track.filename)
            for album_artist_tag in track.get(BasicTag.ALBUMARTIST, default=[]):
                artist_values[album_artist_tag].append(track.filename)

        if not artist_values[""]:  # no tracks missing artist tag
            return None

        parent_folder_str = Path(album.path).parent.name
        if parent_folder_str and str.lower(parent_folder_str) not in self.ignore_parent_folders:
            artist_values[parent_folder_str] = artist_values.get(parent_folder_str, []) + [parent_folder_str]

        artist_list = list(artist_values.keys())
        candidates = sorted(
            filter(lambda v: v and not str.lower(v).startswith("various"), artist_list), key=lambda a: len(artist_values[a]), reverse=True
        )[:6]
        table = (
            ["filename", "album artist", "artist", "proposed artist"],
            [
                [
                    escape(track.filename),
                    show_tag(track.get(BasicTag.ALBUMARTIST, default=None)),
                    show_tag(track.get(BasicTag.ARTIST, default=None)),
                    show_tag([candidates[0]] if candidates and not track.has(BasicTag.ARTIST) else None),
                ]
                for track in album.tracks
            ],
        )
        option_free_text = True
        option_automatic_index = 0 if len(candidates) == 1 else None
        return CheckResult(
            f"{len(artist_values[''])} tracks missing artist tag",
            Fixer(
                lambda option: self._fix(album, option, artist_values[""]),
                candidates,
                option_free_text,
                option_automatic_index,
                table,
                f"select artist name to use for {len(artist_values[''])} tracks where it is missing",
            ),
        )

    def _fix(self, album: AlbumEntity, option: str, filenames: list[str]) -> bool:
        for filename in filenames:
            file = self.ctx.config.library / album.path / filename
            self.ctx.console.print(f"setting artist on {filename}")
            self.tagger.get(album.path).set_basic_tags(file, [(BasicTag.ARTIST, option)])
        return True
