from .. import app
from ..library.metadata import set_basic_tag
from ..types import Album
from .base_check import Check, CheckResult, Fixer
from .base_fixer import FixerInteractivePrompt
from .normalize_tags import normalized


CHECK_NAME = "album_artist"
VARIOUS_ARTISTS = "Various Artists"


class AlbumArtistFixer(Fixer):
    def __init__(self, ctx: app.Context, album: Album, message: str, candidates: list[str], show_remove_option: bool):
        super(AlbumArtistFixer, self).__init__(CHECK_NAME, ctx, album, True)
        self.message = [f"*** Fixing album artist for {self.album.path}", f"ISSUE: {message}"]
        self.question = f"Which album artist to use for all {len(self.album.tracks)} tracks in {self.album.path}?"
        self.options = candidates + [None, VARIOUS_ARTISTS]
        self.show_remove_option = show_remove_option

    def get_interactive_prompt(self):
        table = (
            ["filename", "album tag", "artist", "album artist"],
            [[track.filename, track.tags.get("album"), track.tags.get("artist"), track.tags.get("albumartist")] for track in self.album.tracks],
        )
        return FixerInteractivePrompt(self.message, self.question, self.options, self.show_remove_option, True, table)

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

            if "band" in track.tags:  # always remove tag named "band"
                self.ctx.console.print(f"removing band from {track.filename}")
                set_basic_tag(file, "band", None)

        self.ctx.console.print("done.")
        return True


class CheckAlbumArtist(Check):
    name = CHECK_NAME
    default_config = "true"

    def check(self, album: Album):
        albumartists: dict[str, int] = {}
        artists: dict[str, int] = {}
        albumartist_and_band = False

        for track in sorted(album.tracks, key=lambda track: track.filename):
            if "albumartist" in track.tags and "band" in track.tags:
                albumartist_and_band = True

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

        # TODO configurable check for consistent but redundant albumartist setting (artist=albumartist and is the same on all tracks)
        redundant = len(artists) == 1 and list(artists.values())[0] == len(album.tracks)  # albumartist maybe not needed?

        results: CheckResult | None = None
        if albumartist_and_band:
            if redundant:
                fixer = AlbumArtistFixer(
                    self.ctx,
                    album,
                    "albumartist and band tags both present and probably neither are needed",
                    nonblank_albumartists,
                    show_remove_option=True,
                )
            else:
                fixer = AlbumArtistFixer(self.ctx, album, "albumartist and band tags both present", candidates, show_remove_option=False)
            results = CheckResult(self.name, fixer.message, fixer, results)

        if len(nonblank_albumartists) > 1:  # distinct album artist values, not including blank
            fixer = AlbumArtistFixer(
                self.ctx, album, f"multiple album artist values ({nonblank_albumartists[:2]} ...)", candidates, show_remove_option=False
            )
            results = CheckResult(self.name, fixer.message, fixer, results)
        elif len(albumartists.keys()) == 2:  # some set, some blank
            if redundant:
                fixer = AlbumArtistFixer(
                    self.ctx,
                    album,
                    f"album artist is set inconsistently and probably not needed ({nonblank_albumartists[:2]} ...)",
                    candidates,
                    show_remove_option=True,
                )
            else:
                fixer = AlbumArtistFixer(
                    self.ctx,
                    album,
                    f"album artist is set on some tracks but not all ({nonblank_albumartists[:2]} ...)",
                    candidates,
                    show_remove_option=False,
                )
            results = CheckResult(self.name, fixer.message, fixer, results)

        if len(artists) > 1 and (sum(albumartists.values()) - albumartists.get("", 0)) != len(album.tracks):
            fixer = AlbumArtistFixer(
                self.ctx, album, f"multiple artists but no album artist ({list(artists.keys())[:2]} ...)", candidates, show_remove_option=False
            )
            results = CheckResult(self.name, fixer.message, fixer, results)

        return results
