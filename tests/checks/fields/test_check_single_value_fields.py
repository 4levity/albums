from pathlib import Path

from albums.app import Context
from albums.checks.fields.check_single_value_fields import CheckSingleValueFields
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField


def context(checks, db=None):
    ctx = Context()
    ctx.db = db
    ctx.config.checks = checks
    return ctx


class TestCheckSingleValueFields:
    def test_single_value_fields_ok(self):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicField.ARTIST: "Alice", BasicField.TITLE: "blue"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Alice", BasicField.TITLE: "red"}),
            ],
        )
        result = CheckSingleValueFields(Context()).check(album)
        assert result is None

    def test_single_value_fields_concat(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    tag={
                        BasicField.ARTIST: ["Alice", "Bob"],
                        BasicField.TITLE: ["blue", "no, yellow"],
                    },
                ),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Alice", BasicField.TITLE: "red"}),
            ],
        )
        result = CheckSingleValueFields(Context()).check(album)
        assert "multiple values for single value fields" in result.message
        assert result.fixer
        assert not result.fixer.option_free_text
        assert result.fixer.table
        assert result.fixer.options == [
            '>> Concatenate unique values into one with " / "',
            '>> Concatenate unique values into one with "/"',
            '>> Concatenate unique values into one with " - "',
        ]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_fields.call_count == 1
        assert mock_set_basic_fields.call_args.args == (
            Path(album.path) / album.tracks[0].filename,
            [(BasicField.ARTIST, ["Alice / Bob"]), (BasicField.TITLE, ["blue / no, yellow"])],
        )

    def test_single_value_fields_concat_no_auto(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicField.ARTIST: ["Alice", "Bob"], BasicField.TITLE: ["blue", "no, yellow"]}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Alice", BasicField.TITLE: "red"}),
            ],
        )
        ctx = Context()
        ctx.config.checks[CheckSingleValueFields.name]["automatic_concatenate"] = False
        result = CheckSingleValueFields(ctx).check(album)
        assert "multiple values for single value fields" in result.message
        assert result.fixer
        assert not result.fixer.option_free_text
        assert result.fixer.table
        assert result.fixer.options[1] == '>> Concatenate unique values into one with "/"'
        assert result.fixer.option_automatic_index is None

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = result.fixer.fix(result.fixer.options[1])
        assert fix_result
        assert mock_set_basic_fields.call_count == 1
        assert mock_set_basic_fields.call_args.args == (
            Path(album.path) / album.tracks[0].filename,
            [(BasicField.ARTIST, ["Alice/Bob"]), (BasicField.TITLE, ["blue/no, yellow"])],
        )

    def test_single_value_fields_duplicates(self, mocker):
        album = Album(
            path="",
            tracks=[Track(filename="1.flac", tag={BasicField.ARTIST: ["Alice", "Alice", "Bob"], BasicField.TITLE: ["blue", "blue", "blue"]})],
        )
        result = CheckSingleValueFields(Context()).check(album)
        assert "multiple values for single value fields" in result.message
        assert result.fixer
        assert not result.fixer.option_free_text
        assert result.fixer.table
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.options[0] == ">> Remove duplicate values (preserve unique multiple values)"

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        fix_result = result.fixer.fix(result.fixer.options[0])
        assert fix_result
        assert mock_set_basic_fields.call_count == 1
        assert mock_set_basic_fields.call_args.args == (
            Path(album.path) / album.tracks[0].filename,
            [(BasicField.ARTIST, ["Alice", "Bob"]), (BasicField.TITLE, ["blue"])],
        )
