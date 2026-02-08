from pathlib import Path

from albums.app import Context
from albums.checks.check_single_value_tags import CheckSingleValueTags
from albums.types import Album, Track


def context(checks, db=None):
    ctx = Context()
    ctx.db = db
    ctx.config["checks"] = checks
    return ctx


class TestCheckSingleValueTags:
    def test_single_value_tags_ok(self):
        album = Album(
            "",
            [
                Track("1.flac", {"artist": ["Alice"], "title": ["blue"]}),
                Track("2.flac", {"artist": ["Alice"], "title": ["red"]}),
            ],
        )
        result = CheckSingleValueTags(Context()).check(album)
        assert result is None

    def test_single_value_tags_concat(self, mocker):
        album = Album(
            "",
            [
                Track("1.flac", {"artist": ["Alice", "Bob"], "title": ["blue", "no, yellow"]}),
                Track("2.flac", {"artist": ["Alice"], "title": ["red"]}),
            ],
        )
        result = CheckSingleValueTags(Context()).check(album)
        assert "multiple values for single value tags" in result.message
        assert result.fixer
        assert result.fixer.option_automatic_index is None
        assert not result.fixer.option_free_text
        assert result.fixer.table
        assert result.fixer.options[0] == ">> Concatenate unique values into one with '/' between"

        mock_set_basic_tags = mocker.patch("albums.checks.check_single_value_tags.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[0])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[0].filename,
            [("artist", ["Alice / Bob"]), ("title", ["blue / no, yellow"])],
        )

    def test_single_value_tags_duplicates(self, mocker):
        album = Album("", [Track("1.flac", {"artist": ["Alice", "Alice", "Bob"], "title": ["blue", "blue", "blue"]})])
        result = CheckSingleValueTags(Context()).check(album)
        assert "multiple values for single value tags" in result.message
        assert result.fixer
        assert not result.fixer.option_free_text
        assert result.fixer.table
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.options[0] == ">> Remove duplicate values (preserve unique multiple values)"

        mock_set_basic_tags = mocker.patch("albums.checks.check_single_value_tags.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[0])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[0].filename,
            [("artist", ["Alice", "Bob"]), ("title", ["blue"])],
        )
