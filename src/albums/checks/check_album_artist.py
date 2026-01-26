import logging
from pathlib import Path

from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album
from .base_check import Check, CheckResult, Fixer, ProblemCategory


logger = logging.getLogger(__name__)

VARIOUS_ARTISTS = "Various Artists"
OPTION_REMOVE_ALBUM_ARTIST = ">> Remove album artist from all tracks"


class CheckAlbumArtist(Check):
    name = "album_artist"
    default_config = {"enabled": True, "remove_redundant": False, "require_redundant": False}

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None  # this check is currently not valid for files that don't use "album" tag

        remove_redundant = bool(self.check_config.get("remove_redundant", CheckAlbumArtist.default_config["remove_redundant"]))
        require_redundant = bool(self.check_config.get("require_redundant", CheckAlbumArtist.default_config["require_redundant"]))

        if remove_redundant and require_redundant:
            logger.warning("check_album_artist: remove_redundant and require_redundant cannot both be true, ignoring both options")
            remove_redundant = False
            require_redundant = False

        albumartists: dict[str, int] = {}
        artists: dict[str, int] = {}

        for track in sorted(album.tracks, key=lambda track: track.filename):
            if "artist" in track.tags:
                for artist in track.tags["artist"]:
                    artists[artist] = artists.get(artist, 0) + 1

            if "albumartist" in track.tags:
                for albumartist in track.tags["albumartist"]:
                    albumartists[albumartist] = albumartists.get(albumartist, 0) + 1
            else:
                albumartists[""] = albumartists.get("", 0) + 1

        # return top 12 artist/album artist matches by how many times they appear on tracks
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
        message = None
        fixer: Fixer | None = None
        if len(nonblank_albumartists) > 1:  # distinct album artist values, not including blank
            message = f"multiple album artist values ({nonblank_albumartists[:2]} ...)"
            fixer = self._make_fixer(album, candidates_various, show_free_text_option=True)
        elif len(albumartists.keys()) == 2:  # some set, some blank
            if redundant:
                message = f"album artist is set inconsistently and probably not needed ({nonblank_albumartists[:2]} ...)"
                fixer = self._make_fixer(album, candidates_various + remove, show_free_text_option=True)
            else:
                message = f"album artist is set on some tracks but not all ({nonblank_albumartists[:2]} ...)"
                fixer = self._make_fixer(album, candidates_various, show_free_text_option=True)
        # TODO: fixes for remove_redundant and require_redundant can be automatic if you're really sure
        elif redundant and remove_redundant and len(nonblank_albumartists) == 1 and list(artists.keys())[0] == nonblank_albumartists[0]:
            message = f"album artist is probably not needed: {nonblank_albumartists[0]}"
            fixer = self._make_fixer(album, nonblank_albumartists + remove, show_free_text_option=False)
        elif require_redundant and redundant and len(nonblank_albumartists) == 0:
            artist = list(artists.keys())[0]
            message = f"album artist would be redundant, but it can be set to {artist}"
            fixer = self._make_fixer(album, [artist] + remove, show_free_text_option=False)
        elif len(artists) > 1 and (sum(albumartists.values()) - albumartists.get("", 0)) != len(album.tracks):
            message = f"multiple artists but no album artist ({list(artists.keys())[:2]} ...)"
            fixer = self._make_fixer(album, candidates_various, show_free_text_option=True)

        return CheckResult(ProblemCategory.TAGS, message, fixer) if message else None

    def _make_fixer(self, album: Album, options: list[str], show_free_text_option: bool):
        table: tuple[list[str], list[list[str]]] = (
            ["filename", "album tag", "artist", "album artist"],
            [
                [track.filename, str(track.tags.get("album")), str(track.tags.get("artist")), str(track.tags.get("albumartist"))]
                for track in album.tracks
            ],
        )
        return Fixer(
            lambda option: self._fix(album, option), options, show_free_text_option, None, table, "select album artist to use for all tracks"
        )

    def _fix(self, album: Album, album_artist_value: str) -> bool:
        changed = False
        for track in sorted(album.tracks, key=lambda track: track.filename):
            file = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / track.filename
            if album_artist_value == OPTION_REMOVE_ALBUM_ARTIST:
                if "albumartist" in track.tags:
                    self.ctx.console.print(f"removing albumartist from {track.filename}", markup=False)
                    changed |= set_basic_tags(file, [("albumartist", None)])
                # else nothing to remove
            elif track.tags.get("albumartist", []) != [album_artist_value]:
                self.ctx.console.print(f"setting albumartist on {track.filename}", markup=False)
                changed |= set_basic_tags(file, [("albumartist", album_artist_value)])
            # else nothing to set

        self.ctx.console.print("done.")
        return changed
