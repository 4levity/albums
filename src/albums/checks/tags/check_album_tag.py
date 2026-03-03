import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from rich.markup import escape

from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import BasicTag
from ...types import Album, CheckResult, Fixer
from ..base_check import Check
from ..helpers import show_tag

logger = logging.getLogger(__name__)


class CheckAlbumTag(Check):
    name = "album-tag"
    default_config = {"enabled": True, "ignore_folders": ["misc"]}

    def init(self, check_config: dict[str, Any]):
        ignore_folders: list[Any] = check_config.get("ignore_folders", CheckAlbumTag.default_config["ignore_folders"])
        if not isinstance(ignore_folders, list) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(f, str) or f == "" for f in ignore_folders
        ):
            logger.warning(f'album-tag.ignore_folders must be a list of folders, ignoring value "{ignore_folders}"')
            ignore_folders = []
        self.ignore_folders = list(str(folder) for folder in ignore_folders)

    def check(self, album: Album):
        folder_str = Path(album.path).name
        if folder_str in self.ignore_folders:
            return None

        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_TAGS) for track in album.tracks):
            return None

        track_album_tags: defaultdict[str, int] = defaultdict(int)
        for track in album.tracks:
            if BasicTag.ALBUM in track.tags:
                for album_tag in track.tags[BasicTag.ALBUM]:
                    track_album_tags[album_tag] += 1
            else:
                track_album_tags[""] += 1

        album_tags = list(track_album_tags.keys())
        candidates = sorted(filter(None, album_tags), key=lambda a: track_album_tags[a], reverse=True)[:12]
        if len(candidates) > 1:  # multiple conflicting album names (not including folder name)
            if folder_str not in candidates:
                candidates.append(folder_str)
            return CheckResult(f"{len(candidates)} conflicting album tag values", self._make_fixer(album, candidates))

        if track_album_tags[""] > 0:  # tracks missing album tag
            if folder_str not in candidates:
                candidates.append(folder_str)
            return CheckResult(f"{track_album_tags['']} tracks missing album tag", self._make_fixer(album, candidates))

        return None

    def _make_fixer(self, album: Album, options: list[str]):
        table = (
            ["filename", "album tag", "artist", "album artist"],
            [
                [
                    escape(track.filename),
                    show_tag(track.tags.get(BasicTag.ALBUM)),
                    show_tag(track.tags.get(BasicTag.ARTIST)),
                    show_tag(track.tags.get(BasicTag.ALBUMARTIST)),
                ]
                for track in album.tracks
            ],
        )
        return Fixer(
            lambda option: self._fix(album, option),
            options,
            True,
            0 if len(options) == 1 else None,
            table,
            f"select album name to use for all {len(album.tracks)} tracks",
        )

    def _fix(self, album: Album, option: str) -> bool:
        changed = False
        for track in album.tracks:
            file = self.ctx.config.library / album.path / track.filename
            if track.tags.get(BasicTag.ALBUM, []) != [option]:
                self.ctx.console.print(f"setting album on {track.filename}")
                self.tagger.get(album.path).set_basic_tags(file, [(BasicTag.ALBUM, option)])
                changed = True
        return changed
