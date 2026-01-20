import logging

from .. import app
from ..library.metadata import set_basic_tag
from ..types import Album
from .base_check import Check, CheckResult, Fixer
from .base_fixer import FixerInteractivePrompt
from .normalize_tags import normalized


logger = logging.getLogger(__name__)


CHECK_NAME = "album_artist"
VARIOUS_ARTISTS = "Various Artists"


class AlbumArtistFixer(Fixer):
    def __init__(
        self, ctx: app.Context, album: Album, message: str, candidates: list[str], show_remove_option: bool, show_free_text_option: bool = True
    ):
        super(AlbumArtistFixer, self).__init__(CHECK_NAME, ctx, album, True)
        self.message = [f"*** Fixing album artist for {self.album.path}", f"ISSUE: {message}"]
        self.question = f"Which album artist to use for all {len(self.album.tracks)} tracks in {self.album.path}?"
        self.options = candidates
        self.show_remove_option = show_remove_option
        self.show_free_text_option = show_free_text_option

    def get_interactive_prompt(self):
        table = (
            ["filename", "album tag", "artist", "album artist"],
            [[track.filename, track.tags.get("album"), track.tags.get("artist"), track.tags.get("albumartist")] for track in self.album.tracks],
        )
        return FixerInteractivePrompt(self.message, self.question, self.options, self.show_remove_option, self.show_free_text_option, table)

    def fix_interactive(self, album_artist_value: str | None) -> bool:
        for track in sorted(self.album.tracks, key=lambda track: track.filename):
            file = self.ctx.library_root / self.album.path / track.filename
            if album_artist_value is None:
                if "albumartist" in track.tags:
                    self.ctx.console.print(f"removing albumartist from {track.filename}")
                    set_basic_tag(file, "albumartist", None)
                # else nothing to remove
            elif track.tags.get("albumartist", []) != [album_artist_value]:
                self.ctx.console.print(f"setting albumartist on {track.filename}")
                set_basic_tag(file, "albumartist", album_artist_value)
            # else nothing to set

        self.ctx.console.print("done.")
        return True


class CheckAlbumArtist(Check):
    name = CHECK_NAME
    default_config = {"enabled": True, "remove_redundant": False, "require_redundant": False}

    def check(self, album: Album):
        remove_redundant = self.config.get("remove_redundant", False)
        require_redundant = self.config.get("require_redundant", False)
        if remove_redundant and require_redundant:
            logger.warning("check_album_artist: remove_redundant and require_redundant cannot both be true, ignoring both options")
            remove_redundant = False
            require_redundant = False

        albumartists: dict[str, int] = {}
        artists: dict[str, int] = {}

        # TODO: don't offer these fixes when some file types cannot have "albumartist" tags written
        # Currently this check and fixes only work for FLAC and MP3+EasyID3
        for track in sorted(album.tracks, key=lambda track: track.filename):
            tags = normalized(track.tags)

            if "artist" in tags:
                for artist in tags["artist"]:
                    artists[artist] = artists.get(artist, 0) + 1

            if "albumartist" in tags:
                for albumartist in tags["albumartist"]:
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
        candidates_various = candidates + ([None, VARIOUS_ARTISTS] if len(candidates) > 0 else [VARIOUS_ARTISTS])

        redundant = len(artists) == 1 and list(artists.values())[0] == len(album.tracks)  # albumartist maybe not needed?

        results: CheckResult | None = None

        if len(nonblank_albumartists) > 1:  # distinct album artist values, not including blank
            fixer = AlbumArtistFixer(
                self.ctx, album, f"multiple album artist values ({nonblank_albumartists[:2]} ...)", candidates_various, show_remove_option=False
            )
            results = CheckResult(self.name, fixer.message, fixer, results)
        elif len(albumartists.keys()) == 2:  # some set, some blank
            if redundant:
                fixer = AlbumArtistFixer(
                    self.ctx,
                    album,
                    f"album artist is set inconsistently and probably not needed ({nonblank_albumartists[:2]} ...)",
                    candidates_various,
                    show_remove_option=True,
                )
            else:
                fixer = AlbumArtistFixer(
                    self.ctx,
                    album,
                    f"album artist is set on some tracks but not all ({nonblank_albumartists[:2]} ...)",
                    candidates_various,
                    show_remove_option=False,
                )
            results = CheckResult(self.name, fixer.message, fixer, results)
        # TODO: fixes for remove_redundant and require_redundant can be automatic if you're really sure
        elif redundant and remove_redundant and len(nonblank_albumartists) == 1 and list(artists.keys())[0] == nonblank_albumartists[0]:
            fixer = AlbumArtistFixer(
                self.ctx,
                album,
                f"album artist is probably not needed: {nonblank_albumartists[0]}",
                nonblank_albumartists,
                show_remove_option=True,
                show_free_text_option=False,
            )
            results = CheckResult(self.name, fixer.message, fixer, results)
        elif require_redundant and redundant and len(nonblank_albumartists) == 0:
            artist = list(artists.keys())[0]
            fixer = AlbumArtistFixer(
                self.ctx,
                album,
                f"album artist would be redundant, but it can be set to {artist}",
                [artist],
                show_remove_option=True,
                show_free_text_option=False,
            )
            results = CheckResult(self.name, fixer.message, fixer, results)

        if len(artists) > 1 and (sum(albumartists.values()) - albumartists.get("", 0)) != len(album.tracks):
            fixer = AlbumArtistFixer(
                self.ctx,
                album,
                f"multiple artists but no album artist ({list(artists.keys())[:2]} ...)",
                candidates_various,
                show_remove_option=False,
            )
            results = CheckResult(self.name, fixer.message, fixer, results)

        return results
