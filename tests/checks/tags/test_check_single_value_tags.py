from pathlib import Path

from albums.app import Context
from albums.checks.tags.check_single_value_tags import CheckSingleValueTags
from albums.tagger.folder import AlbumTagger
from albums.types import Album, BasicTag, Track


def context(checks, db=None):
    ctx = Context()
    ctx.db = db
    ctx.config.checks = checks
    return ctx


class TestCheckSingleValueTags:
    def test_single_value_tags_ok(self):
        album = Album(
            "",
            [
                Track("1.flac", {BasicTag.ARTIST: ["Alice"], BasicTag.TITLE: ["blue"]}),
                Track("2.flac", {BasicTag.ARTIST: ["Alice"], BasicTag.TITLE: ["red"]}),
            ],
        )
        result = CheckSingleValueTags(Context()).check(album)
        assert result is None

    def test_single_value_tags_concat(self, mocker):
        album = Album(
            "",
            [
                Track("1.flac", {BasicTag.ARTIST: ["Alice", "Bob"], BasicTag.TITLE: ["blue", "no, yellow"]}),
                Track("2.flac", {BasicTag.ARTIST: ["Alice"], BasicTag.TITLE: ["red"]}),
            ],
        )
        result = CheckSingleValueTags(Context()).check(album)
        assert "multiple values for single value tags" in result.message
        assert result.fixer
        assert not result.fixer.option_free_text
        assert result.fixer.table
        assert result.fixer.options == [
            '>> Concatenate unique values into one with " / "',
            '>> Concatenate unique values into one with "/"',
            '>> Concatenate unique values into one with " - "',
        ]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[0].filename,
            [(BasicTag.ARTIST, ["Alice / Bob"]), (BasicTag.TITLE, ["blue / no, yellow"])],
        )

    def test_single_value_tags_concat_no_auto(self, mocker):
        album = Album(
            "",
            [
                Track("1.flac", {BasicTag.ARTIST: ["Alice", "Bob"], BasicTag.TITLE: ["blue", "no, yellow"]}),
                Track("2.flac", {BasicTag.ARTIST: ["Alice"], BasicTag.TITLE: ["red"]}),
            ],
        )
        ctx = Context()
        ctx.config.checks[CheckSingleValueTags.name]["automatic_concatenate"] = False
        result = CheckSingleValueTags(ctx).check(album)
        assert "multiple values for single value tags" in result.message
        assert result.fixer
        assert not result.fixer.option_free_text
        assert result.fixer.table
        assert result.fixer.options[1] == '>> Concatenate unique values into one with "/"'
        assert result.fixer.option_automatic_index is None

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[1])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[0].filename,
            [(BasicTag.ARTIST, ["Alice/Bob"]), (BasicTag.TITLE, ["blue/no, yellow"])],
        )

    def test_single_value_tags_duplicates(self, mocker):
        album = Album("", [Track("1.flac", {BasicTag.ARTIST: ["Alice", "Alice", "Bob"], BasicTag.TITLE: ["blue", "blue", "blue"]})])
        result = CheckSingleValueTags(Context()).check(album)
        assert "multiple values for single value tags" in result.message
        assert result.fixer
        assert not result.fixer.option_free_text
        assert result.fixer.table
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.options[0] == ">> Remove duplicate values (preserve unique multiple values)"

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[0])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[0].filename,
            [(BasicTag.ARTIST, ["Alice", "Bob"]), (BasicTag.TITLE, ["blue"])],
        )
