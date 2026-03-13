import logging
from collections import defaultdict
from typing import Any

from rich.markup import escape

from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import BasicTag
from ...types import Album, CheckResult, Fixer
from ..base_check import Check
from ..helpers import show_tag

logger = logging.getLogger(__name__)

VARIOUS_ARTISTS = "Various Artists"
OPTION_REMOVE_ALBUM_ARTIST = ">> Remove album artist from all tracks"
OPTION_COPY_ALBUM_ARTIST_TO_ARTIST = ">> Copy album artist -> artist"


class CheckAlbumArtist(Check):
    name = "album-artist"
    default_config = {"enabled": True, "remove_redundant": False, "require_redundant": False}

    def init(self, check_config: dict[str, Any]):
        self.remove_redundant = bool(check_config.get("remove_redundant", CheckAlbumArtist.default_config["remove_redundant"]))
        self.require_redundant = bool(check_config.get("require_redundant", CheckAlbumArtist.default_config["require_redundant"]))
        if self.remove_redundant and self.require_redundant:
            logger.warning("check_album-artist: remove_redundant and require_redundant cannot both be true, ignoring both options")
            self.remove_redundant = False
            self.require_redundant = False

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_TAGS) for track in album.tracks):
            return None

        albumartists: defaultdict[str, int] = defaultdict(int)
        artists: defaultdict[str, int] = defaultdict(int)

        for track in sorted(album.tracks, key=lambda track: track.filename):
            if track.has(BasicTag.ARTIST):
                for artist in track.get(BasicTag.ARTIST):
                    artists[artist] += 1

            if track.has(BasicTag.ALBUMARTIST):
                for albumartist in track.get(BasicTag.ALBUMARTIST):
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
                f"multiple album artist values ({nonblank_albumartists[:2]} ...)",
                self._make_fixer(album, options, show_free_text_option=True),
            )
        if len(albumartists.keys()) == 2:  # some set, some blank
            if redundant:
                return CheckResult(
                    f"album artist is set inconsistently and probably not needed ({nonblank_albumartists[:2]} ...)",
                    self._make_fixer(album, candidates_various + remove, show_free_text_option=True),
                )
            return CheckResult(
                f"album artist is set on some tracks but not all ({nonblank_albumartists[:2]} ...)",
                self._make_fixer(album, candidates_various, show_free_text_option=True),
            )
        elif redundant and self.remove_redundant and len(nonblank_albumartists) == 1 and list(artists.keys())[0] == nonblank_albumartists[0]:
            return CheckResult(
                f"album artist is not needed: {nonblank_albumartists[0]}",
                self._make_fixer(album, remove + nonblank_albumartists, show_free_text_option=False, option_automatic_index=0),
            )
        elif self.require_redundant and redundant and len(nonblank_albumartists) == 0:
            artist = list(artists.keys())[0]
            return CheckResult(
                f"album artist would be redundant, but it can be set to {artist}",
                self._make_fixer(album, [artist] + remove, show_free_text_option=False, option_automatic_index=0),
            )
        elif len(artists) > 1 and (sum(albumartists.values()) - albumartists.get("", 0)) != len(album.tracks):
            return CheckResult(
                f"multiple artists but no album artist ({list(artists.keys())[:2]} ...)",
                self._make_fixer(album, candidates_various, show_free_text_option=True),
            )

    def _make_fixer(self, album: Album, options: list[str], show_free_text_option: bool, option_automatic_index: int | None = None):
        table = (
            ["filename", "album tag", "artist", "album artist"],
            [
                [
                    escape(track.filename),
                    show_tag(track.get(BasicTag.ALBUM, default=None)),
                    show_tag(track.get(BasicTag.ARTIST, default=None)),
                    show_tag(track.get(BasicTag.ALBUMARTIST, default=None)),
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
                if track.has(BasicTag.ALBUMARTIST):
                    self.ctx.console.print(f"removing albumartist from {track.filename}", markup=False)
                    self.tagger.get(album.path).set_basic_tags(file, [(BasicTag.ALBUMARTIST, None)])
                    changed = True
                # else nothing to remove
            elif album_artist_value == OPTION_COPY_ALBUM_ARTIST_TO_ARTIST:
                if track.has(BasicTag.ALBUMARTIST):
                    self.ctx.console.print(f"copying albumartist to artist in {track.filename}", markup=False)
                    albumartist = track.get(BasicTag.ALBUMARTIST)[0]
                    self.tagger.get(album.path).set_basic_tags(file, [(BasicTag.ARTIST, albumartist)])
                    changed = True
            elif track.get(BasicTag.ALBUMARTIST, default=[]) != [album_artist_value]:
                self.ctx.console.print(f"setting albumartist on {track.filename}", markup=False)
                self.tagger.get(album.path).set_basic_tags(file, [(BasicTag.ALBUMARTIST, album_artist_value)])
                changed = True
            # else nothing to set

        self.ctx.console.print("done.")
        return changed
