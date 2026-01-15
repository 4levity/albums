from ..types import Album
from .base import Check, CheckResult


class CheckAlbumArtist(Check):
    name = "album_artist"

    def check(self, album: Album):
        albumartists = {}
        artists = {}
        albumartist_and_band = False

        for track in sorted(album.tracks, key=lambda track: track.filename):
            if "artist" in track.tags:
                for artist in track.tags["artist"]:
                    artists[artist] = artists.get(artist, 0) + 1

            if "albumartist" in track.tags and "Band" in track.tags:
                albumartist_and_band = True

            if "albumartist" in track.tags:
                for albumartist in track.tags["albumartist"]:
                    albumartists[albumartist] = albumartists.get(albumartist, 0) + 1
            elif "band" in track.tags:
                for band in track.tags["band"]:
                    albumartists[band] = albumartists.get(track.tags["band"], 0) + 1
            else:
                albumartists[""] = albumartists.get("", 0) + 1

        results: CheckResult | None = None
        if albumartist_and_band:
            results = CheckResult(self.name, "albumartist and band tags both present", False, results)
        if len(albumartists) > 1:
            results = CheckResult(self.name, f"multiple album artist values ({list(albumartists.keys())[:2]} ...)", False, results)
        if len(artists) > 1 and (sum(albumartists.values()) - albumartists.get("", 0)) != len(album.tracks):
            results = CheckResult(self.name, f"multiple artists but no album artist ({list(artists.keys())[:2]} ...)", False, results)
        return results
