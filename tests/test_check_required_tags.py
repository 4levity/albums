from albums.app import Context
from albums.checks.check_required_tags import CheckRequiredTags
from albums.types import Album, Track


def context(checks, db=None):
    ctx = Context()
    ctx.db = db
    ctx.config["checks"] = checks
    return ctx


class TestCheckRequiredTags:
    def test_required_tags(self):
        album = Album(
            "",
            [
                Track("1.flac", {"artist": ["Alice"]}),
                Track("2.flac", {}),
            ],
        )
        ctx = Context()
        ctx.config["checks"] = {"required_tags": {"enabled": True, "tags": ["artist", "title"]}}
        checker = CheckRequiredTags(ctx)

        result = checker.check(album)
        assert result.message == "tracks missing required tags {'title': 2, 'artist': 1}"

        # one tag missing from both
        album.tracks[1].tags["artist"] = ["Alice"]
        result = checker.check(album)
        assert result.message == "tracks missing required tags {'title': 2}"

        # no tags missing
        album.tracks[0].tags["title"] = ["one"]
        album.tracks[1].tags["title"] = ["two"]
        result = checker.check(album)
        assert result is None
