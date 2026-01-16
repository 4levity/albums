import click
from simple_term_menu import TerminalMenu


from ..context import AppContext
from ..library import metadata
from ..types import Album
from .base import Check, CheckResult, Fixer
from .normalize_tags import normalized
from prettytable import PrettyTable


VARIOUS_ARTISTS = "Various Artists"


class AlbumArtistFixer(Fixer):
    def __init__(self, ctx: AppContext, album: Album, message: str, candidates: list[str]):
        super(AlbumArtistFixer, self).__init__(True)
        self.ctx = ctx
        self.album = album
        self.message = message
        self.candidates = candidates

    def interactive(self):
        click.echo(f"*** Fixing album artist for {self.album.path}")
        click.echo(f"ISSUE: {self.message}")
        track_list = PrettyTable(["filename", "album tag", "artist", "album artist"], align="l")
        track_list.add_rows(
            [[track.filename, track.tags.get("album"), track.tags.get("artist"), track.tags.get("albumartist")] for track in self.album.tracks]
        )
        click.echo(track_list.get_string(sortby="filename"))

        if (
            len(self.candidates) > 0
            and self.candidates[0] is None  # if the first candidate is None, offer to remove albumartist
            and click.confirm("do you want to remove albumartist or band tags from all tracks?")
        ):
            for track in self.album.tracks:
                file = self.ctx.library_root / self.album.path / track.filename
                if "albumartist" in track.tags:
                    click.echo(f"removing albumartist from {track.filename}")
                    metadata.set_basic_tag(file, "albumartist", None)
                if "band" in track.tags:
                    click.echo(f"removing band from {track.filename}")
                    metadata.set_basic_tag(file, "band", None)
            click.echo("done.")
            return True

        options = sorted(set((v for v in self.candidates if v and v != VARIOUS_ARTISTS))) + [VARIOUS_ARTISTS, "- Enter a different value -"]
        terminal_menu = TerminalMenu(
            options,
            raise_error_on_interrupt=True,
            title=f"Select album artist for all {len(self.album.tracks)} tracks in {self.album.path}",
        )
        option_index = terminal_menu.show()
        if option_index is None:
            click.echo("skipping this album")
            click.pause()
            return False

        if option_index == len(options) - 1:
            value = click.prompt("Enter value for album artist", type=str)
        else:
            value = options[option_index]
        if click.confirm(f"set all tracks to album artist = {value} ?", default=True):
            for track in self.album.tracks:
                if track.tags.get("albumartist", []) != [value]:
                    click.echo(f"setting albumartist on {track.filename}")
                    metadata.set_basic_tag(self.ctx.library_root / self.album.path / track.filename, "albumartist", value)
                if "band" in track.tags:
                    click.echo(f"removing band from {track.filename}")
                    metadata.set_basic_tag(file, "band", None)
            click.echo("done.")
            return True

        return False


class CheckAlbumArtist(Check):
    name = "album_artist"
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

        nonblank_albumartists = list(filter(lambda k: k != "", albumartists.keys()))
        candidates = list(list(artists.keys()) + nonblank_albumartists)
        redundant = (
            len(artists) == 1
            and len(nonblank_albumartists) == 1
            and (list(artists.keys())[0] == nonblank_albumartists[0] or nonblank_albumartists[0] == VARIOUS_ARTISTS)
        )

        results: CheckResult | None = None
        # TODO configurable check for consistent but redundant albumartist setting (artist=albumartist and is the same on all tracks)
        if albumartist_and_band:
            if redundant:
                fixer = AlbumArtistFixer(
                    self.ctx, album, "albumartist and band tags both present and probably neither are needed", [None] + nonblank_albumartists
                )
            else:
                fixer = AlbumArtistFixer(self.ctx, album, "albumartist and band tags both present", candidates)
            results = CheckResult(self.name, fixer.message, fixer, results)

        if len(nonblank_albumartists) > 1:  # distinct album artist values, not including blank
            fixer = AlbumArtistFixer(self.ctx, album, f"multiple album artist values ({nonblank_albumartists[:2]} ...)", candidates)
            results = CheckResult(self.name, fixer.message, fixer, results)
        elif len(albumartists.keys()) == 2:  # some set, some blank
            if redundant:
                fixer = AlbumArtistFixer(
                    self.ctx,
                    album,
                    f"album artist is set inconsistently and probably not needed ({nonblank_albumartists[:2]} ...)",
                    [None] + nonblank_albumartists,
                )
            else:
                fixer = AlbumArtistFixer(
                    self.ctx, album, f"album artist is set on some tracks but not all ({nonblank_albumartists[:2]} ...)", candidates
                )
            results = CheckResult(self.name, fixer.message, fixer, results)

        if len(artists) > 1 and (sum(albumartists.values()) - albumartists.get("", 0)) != len(album.tracks):
            fixer = AlbumArtistFixer(self.ctx, album, f"multiple artists but no album artist ({list(artists.keys())[:2]} ...)", candidates)
            results = CheckResult(self.name, fixer.message, fixer, results)
        return results
