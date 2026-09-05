from unittest.mock import call

from albums.app import Context
from albums.checks.check_types import FixResult
from albums.checks.fields.check_extra_whitespace import CheckExtraWhitespace
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField

from ...helpers import MockTagger, apply_automatic_fix


class TestCheckExtraWhitespace:
    def test_whitespace_ok(self):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tag={BasicField.ARTIST: "Alice", BasicField.TITLE: "blue"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Alice", BasicField.TITLE: "red"}),
            ],
        )
        result = CheckExtraWhitespace(Context()).check(album)
        assert result is None

    def test_whitespace_fix(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tag={BasicField.ARTIST: "Alice ", BasicField.TITLE: "blue"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Alice ", BasicField.TITLE: "red "}),
            ],
        )
        result = CheckExtraWhitespace(Context()).check(album)
        assert result is not None
        assert "Extra whitespace present in 2 files in fields: artist, title" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Strip leading and trailing whitespace in fields: artist, title"]
        # the table shows the current and proposed values in double quotes, so the offending
        # leading/trailing whitespace is visible
        (headers, rows) = result.fixer.get_table() or ([], [])
        assert list(headers) == ["filename", "field", "current value", "proposed value"]
        assert [list(row) for row in rows] == [
            ["1.flac", "artist", '"Alice "', '[yellow]"Alice"[/yellow]'],
            ["2.flac", "artist", '"Alice "', '[yellow]"Alice"[/yellow]'],
            ["2.flac", "title", '"red "', '[yellow]"red"[/yellow]'],
        ]

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [
            call(BasicField.ARTIST, ["Alice"]),
            call(BasicField.ARTIST, ["Alice"]),
            call(BasicField.TITLE, ["red"]),
        ]
