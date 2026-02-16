import logging
from collections import defaultdict
from typing import Any, List

from rich.console import RenderableType
from rich.markup import escape

from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album, CheckResult, Fixer, ProblemCategory
from .base_check import Check
from .helpers import show_tag

logger = logging.getLogger(__name__)

VARIOUS_ARTISTS = "Various Artists"
OPTION_REMOVE_ALBUM_ARTIST = ">> Remove album artist from all tracks"
OPTION_COPY_ALBUM_ARTIST_TO_ARTIST = ">> Copy album artist -> artist"


class CheckAlbumArtist(Check):
    name = "album_artist"
    default_config = {"enabled": True, "remove_redundant": False, "require_redundant": False}

    def init(self, check_config: dict[str, Any]):
        self.remove_redundant = bool(check_config.get("remove_redundant", CheckAlbumArtist.default_config["remove_redundant"]))
        self.require_redundant = bool(check_config.get("require_redundant", CheckAlbumArtist.default_config["require_redundant"]))
        if self.remove_redundant and self.require_redundant:
            logger.warning("check_album_artist: remove_redundant and require_redundant cannot both be true, ignoring both options")
            self.remove_redundant = False
            self.require_redundant = False

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None  # this check is currently not valid for files that don't use "album" tag

        albumartists: defaultdict[str, int] = defaultdict(int)
        artists: defaultdict[str, int] = defaultdict(int)

        for track in sorted(album.tracks, key=lambda track: track.filename):
            if "artist" in track.tags:
                for artist in track.tags["artist"]:
                    artists[artist] += 1

            if "albumartist" in track.tags:
                for albumartist in track.tags["albumartist"]:
                    albumartists[albumartist] += 1
            else:
                albumartists[""] += 1

        # return top 12 artist/album artist matches sorted by how many times they appear on tracks, largest first
        candidates_scores = artists | albumartists
        candidates = sorted(
            filter(lambda k: k not in ["", VARIOUS_ARTISTS], candidates_scores.keys()), key=lambda a: candidates_scores[a], reverse=True
        )[:12]
        nonblank_albumartists = sorted(
            filter(lambda k: k not in ["", VARIOUS_ARTISTS], albumartists.keys()), key=lambda aa: albumartists[aa], reverse=True
        )[:12]
        candidates_various = candidates + [VARIOUS_ARTISTS]

        redundant = len(artists) == 1 and list(artists.values())[0] == len(album.tracks)  # albumartist maybe not needed?
        remove = [OPTION_REMOVE_ALBUM_ARTIST]
        if len(nonblank_albumartists) > 1:  # distinct album artist values, not including blank
            options = candidates_various
            if len(artists) == 1:
                # multiple album-artist values, and one artist - perhaps wrong tags were used
                # this doesn't fix the problem in one step, but after doing this, run the check again, and then next time select Various Artists
                options.append(OPTION_COPY_ALBUM_ARTIST_TO_ARTIST)
            return CheckResult(
                ProblemCategory.TAGS,
                f"multiple album artist values ({nonblank_albumartists[:2]} ...)",
                self._make_fixer(album, options, show_free_text_option=True),
            )
        if len(albumartists.keys()) == 2:  # some set, some blank
            if redundant:
                return CheckResult(
                    ProblemCategory.TAGS,
                    f"album artist is set inconsistently and probably not needed ({nonblank_albumartists[:2]} ...)",
                    self._make_fixer(album, candidates_various + remove, show_free_text_option=True),
                )
            return CheckResult(
                ProblemCategory.TAGS,
                f"album artist is set on some tracks but not all ({nonblank_albumartists[:2]} ...)",
                self._make_fixer(album, candidates_various, show_free_text_option=True),
            )
        elif redundant and self.remove_redundant and len(nonblank_albumartists) == 1 and list(artists.keys())[0] == nonblank_albumartists[0]:
            return CheckResult(
                ProblemCategory.TAGS,
                f"album artist is not needed: {nonblank_albumartists[0]}",
                self._make_fixer(album, remove + nonblank_albumartists, show_free_text_option=False, option_automatic_index=0),
            )
        elif self.require_redundant and redundant and len(nonblank_albumartists) == 0:
            artist = list(artists.keys())[0]
            return CheckResult(
                ProblemCategory.TAGS,
                f"album artist would be redundant, but it can be set to {artist}",
                self._make_fixer(album, [artist] + remove, show_free_text_option=False, option_automatic_index=0),
            )
        elif len(artists) > 1 and (sum(albumartists.values()) - albumartists.get("", 0)) != len(album.tracks):
            return CheckResult(
                ProblemCategory.TAGS,
                f"multiple artists but no album artist ({list(artists.keys())[:2]} ...)",
                self._make_fixer(album, candidates_various, show_free_text_option=True),
            )

    def _make_fixer(self, album: Album, options: list[str], show_free_text_option: bool, option_automatic_index: int | None = None):
        table: tuple[list[str], List[List[RenderableType]]] = (
            ["filename", "album tag", "artist", "album artist"],
            [
                [
                    escape(track.filename),
                    show_tag(track.tags.get("album")),
                    show_tag(track.tags.get("artist")),
                    show_tag(track.tags.get("albumartist")),
                ]
                for track in album.tracks
            ],
        )
        return Fixer(
            lambda option: self._fix(album, option),
            options,
            show_free_text_option,
            option_automatic_index,
            table,
            "select album artist to use for all tracks",
        )

    def _fix(self, album: Album, album_artist_value: str) -> bool:
        changed = False
        for track in sorted(album.tracks, key=lambda track: track.filename):
            file = self.ctx.config.library / album.path / track.filename
            if album_artist_value == OPTION_REMOVE_ALBUM_ARTIST:
                if "albumartist" in track.tags:
                    self.ctx.console.print(f"removing albumartist from {track.filename}", markup=False)
                    changed |= set_basic_tags(file, [("albumartist", None)])
                # else nothing to remove
            elif album_artist_value == OPTION_COPY_ALBUM_ARTIST_TO_ARTIST:
                if "albumartist" in track.tags:
                    self.ctx.console.print(f"copying albumartist to artist in {track.filename}", markup=False)
                    albumartist = track.tags["albumartist"][0]
                    changed |= set_basic_tags(file, [("artist", albumartist)])
            elif track.tags.get("albumartist", []) != [album_artist_value]:
                self.ctx.console.print(f"setting albumartist on {track.filename}", markup=False)
                changed |= set_basic_tags(file, [("albumartist", album_artist_value)])
            # else nothing to set

        self.ctx.console.print("done.")
        return changed
