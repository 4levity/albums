from albums.checks.check_single_value_tags import CheckSingleValueTags
from albums.context import AppContext
from albums.types import Album, Track


def context(checks, db=None):
    ctx = AppContext()
    ctx.db = db
    ctx.config["checks"] = checks
    return ctx


class TestCheckSingleValueTags:
    def test_single_value_tags(self):
        album = Album(
            "",
            [
                Track("1.flac", {"artist": ["Alice", "Bob"], "title": ["blue", "no, yellow"]}),
                Track("2.flac", {"artist": ["Alice"], "title": ["red"]}),
            ],
        )
        ctx = AppContext()
        ctx.config["checks"] = {"single_value_tags": "title"}
        checker = CheckSingleValueTags(ctx)

        result = checker.check(album)
        assert result.message == "conflicting values for single value tags {'title': 1}"

        # fixed
        album.tracks[0].tags["title"] = ["definitely blue"]
        result = checker.check(album)
        assert result is None
