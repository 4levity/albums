import logging
from pathlib import Path

from .. import app
from ..library.metadata import set_basic_tag
from ..types import Album
from .base_check import Check, CheckResult
from .base_fixer import Fixer, FixerInteractivePrompt


logger = logging.getLogger(__name__)


CHECK_NAME = "album_tag"


class AlbumTagFixer(Fixer):
    def __init__(self, ctx: app.Context, album: Album, message: str, candidates: list[str]):
        super(AlbumTagFixer, self).__init__(CHECK_NAME, ctx, album, True)
        self.message = [f"*** Fixing album tag for {self.album.path}", f"ISSUE: {message}"]
        self.question = f"Which album name to use for all {len(self.album.tracks)} tracks in {self.album.path}?"
        self.options = candidates

    def get_interactive_prompt(self):
        table = (
            ["filename", "album tag", "artist", "album artist"],
            [[track.filename, track.tags.get("album"), track.tags.get("artist"), track.tags.get("albumartist")] for track in self.album.tracks],
        )
        return FixerInteractivePrompt(self.message, self.question, self.options, table, option_none=False, option_free_text=True)

    def fix_interactive(self, album_value: str | None) -> bool:
        for track in sorted(self.album.tracks, key=lambda track: track.filename):
            if album_value is None:
                raise ValueError("album tag may not be removed")
            file = self.ctx.library_root / self.album.path / track.filename
            if track.tags.get("album", []) != [album_value]:
                self.ctx.console.print(f"setting album on {track.filename}")
                set_basic_tag(file, "album", album_value)

        self.ctx.console.print("done.")
        return True


class CheckAlbumTag(Check):
    name = CHECK_NAME
    default_config = {"enabled": True, "ignore_folders": ["misc"]}

    def check(self, album: Album):
        ignore_folders = self.config.get("ignore_folders", CheckAlbumTag.default_config["ignore_folders"])
        folder_str = Path(album.path).name
        if folder_str in ignore_folders:
            return None

        track_album_tags = {"": 0}
        for track in sorted(album.tracks, key=lambda track: track.filename):
            if "album" in track.tags:
                for album_tag in track.tags["album"]:
                    track_album_tags[album_tag] = track_album_tags.get(album_tag, 0) + 1
            else:
                track_album_tags[""] += 1

        candidates = sorted(filter(None, (album_tag for album_tag in track_album_tags.keys())), key=lambda a: track_album_tags[a], reverse=True)[:12]
        if len(candidates) > 1:  # multiple conflicting album names
            message = f"{len(candidates) - 1} conflicting album tag values"
            fixer = AlbumTagFixer(self.ctx, album, message, candidates)
            return CheckResult(self.name, message, fixer)

        if track_album_tags[""] > 0:  # tracks missing album tag
            if folder_str not in candidates:
                candidates.append(folder_str)
            message = f"{track_album_tags['']} tracks missing album tag"
            fixer = AlbumTagFixer(self.ctx, album, message, candidates)
            return CheckResult(self.name, message, fixer)

        return None
