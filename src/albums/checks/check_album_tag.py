import logging
from pathlib import Path

from .. import app
from ..library.metadata import set_basic_tag, supports_basic_tags
from ..types import Album
from .base_check import Check, CheckResult
from .base_fixer import Fixer, FixerInteractivePrompt


logger = logging.getLogger(__name__)


CHECK_NAME = "album_tag"


def album_is_taggable(album: Album):
    ok = True
    for track in album.tracks:
        if not supports_basic_tags(track.filename, track.stream.codec):
            ok = False
    return ok


class AlbumTagFixer(Fixer):
    def __init__(self, ctx: app.Context, album: Album, message: str, candidates: list[str]):
        # if there is only one suggestion, enable automatic fix
        automatic = f'set album to "{candidates[0]}"' if len(candidates) == 1 else None

        super(AlbumTagFixer, self).__init__(CHECK_NAME, ctx, album, True, automatic)
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
        changed = self._fix(album_value)
        self.ctx.console.print("done.")
        return changed

    def fix_automatic(self) -> bool:
        return self._fix(self.options[0])

    def _fix(self, album_value: str | None) -> bool:
        tracks = sorted(self.album.tracks, key=lambda track: track.filename)
        changed = False
        for track in tracks:
            if album_value is None:
                raise ValueError("album tag may not be removed")

            file = self.ctx.library_root / self.album.path / track.filename
            if track.tags.get("album", []) != [album_value]:
                self.ctx.console.print(f"setting album on {track.filename}")
                set_basic_tag(file, "album", album_value)
                changed = True
        return changed


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

        album_tags = list(track_album_tags.keys())
        candidates = sorted(filter(None, album_tags), key=lambda a: track_album_tags[a], reverse=True)[:12]
        taggable = album_is_taggable(album)
        taggable_message = "" if taggable else " (cannot tag file type)"
        if len(candidates) > 1:  # multiple conflicting album names (not including folder name)
            if folder_str not in candidates:
                candidates.append(folder_str)
            message = f"{len(candidates)} conflicting album tag values" + taggable_message
            fixer = AlbumTagFixer(self.ctx, album, message, candidates) if taggable else None
            return CheckResult(self.name, message, fixer)

        if track_album_tags[""] > 0:  # tracks missing album tag
            if folder_str not in candidates:
                candidates.append(folder_str)
            message = f"{track_album_tags['']} tracks missing album tag" + taggable_message
            fixer = AlbumTagFixer(self.ctx, album, message, candidates) if taggable else None
            return CheckResult(self.name, message, fixer)

        return None
