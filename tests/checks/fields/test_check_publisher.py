from unittest.mock import call

from albums.app import Context
from albums.checks.check_types import FixResult
from albums.checks.fields.check_publisher import CheckPublisherField
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField

from ...helpers import MockTagger


class TestCheckPublisherField:
    def test_publisher_ok(self):
        tracks = [Track(filename="1.flac", tag={BasicField.ORGANIZATION: "ABC"}), Track(filename="2.flac", tag={BasicField.ORGANIZATION: "ABC"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherField(Context()).check(album)
        assert result is None

    def test_publisher_ok_none(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherField(Context()).check(album)
        assert result is None

    def test_publisher_missing(self):
        tracks = [Track(filename="1.flac", tag={BasicField.ORGANIZATION: "ABC"}), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherField(Context()).check(album)
        assert result is not None
        assert "organization policy=CONSISTENT but it is on some tracks and not others" in result.message

    def test_publisher_none_policy_always(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        ctx = Context()
        ctx.config.checks[CheckPublisherField.name]["presence"] = "always"
        result = CheckPublisherField(ctx).check(album)
        assert result is not None
        # no value to copy from any track, so offer free text entry rather than no fixer
        assert result.fixer is not None
        assert result.fixer.options == []
        assert result.fixer.option_free_text
        assert result.fixer.option_automatic_index is None
        assert "organization policy=ALWAYS but it is not on all tracks" in result.message

    def test_publisher_different_select(self, mocker):
        tracks = [Track(filename="1.flac", tag={BasicField.ORGANIZATION: "XYZ"}), Track(filename="2.flac", tag={BasicField.ORGANIZATION: "ABC"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherField(Context()).check(album)
        assert result is not None
        assert "multiple values for publisher/organization: ABC, XYZ" in result.message
        assert result.fixer is not None
        assert result.fixer.options == ["ABC", "XYZ", ">> Remove publisher/organization from all tracks"]
        assert result.fixer.option_automatic_index is None

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[0]) == FixResult.CHANGED_ALBUM

        assert mock_tagger_open.call_args_list == [call(tracks[0].filename)]
        assert mock_set_field.call_args_list == [call(BasicField.ORGANIZATION, "ABC")]

    def test_publisher_different_table_escaped(self):
        # filenames and field values containing rich markup must be escaped in the table
        tracks = [
            Track(filename="1 [bold].flac", tag={BasicField.ORGANIZATION: "Label [yellow]"}),
            Track(filename="2.flac", tag={BasicField.ORGANIZATION: "Label [red]"}),
        ]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherField(Context()).check(album)
        assert result is not None
        assert result.fixer is not None
        (headers, rows) = result.fixer.get_table() or ([], [])
        assert list(headers) == ["filename", "publisher/organization"]
        assert [list(row) for row in rows] == [
            ["1 \\[bold].flac", "Label \\[yellow]"],
            ["2.flac", "Label \\[red]"],
        ]

    def test_publisher_missing_table_shows_none(self):
        tracks = [Track(filename="1.flac", tag={BasicField.ORGANIZATION: "ABC"}), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherField(Context()).check(album)
        assert result is not None
        assert result.fixer is not None
        (headers, rows) = result.fixer.get_table() or ([], [])
        # the table has a track number column, and a missing field value is shown as italic "none", not an empty cell
        assert list(headers) == ["track", "filename", "organization"]
        assert [list(row) for row in rows] == [
            ["<no track>", "1.flac", "ABC"],
            ["<no track>", "2.flac", "[italic]none[/italic]"],
        ]

    def test_publisher_different_remove(self, mocker):
        tracks = [Track(filename="1.flac", tag={BasicField.ORGANIZATION: "XYZ"}), Track(filename="2.flac", tag={BasicField.ORGANIZATION: "ABC"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherField(Context()).check(album)
        assert result is not None
        assert "multiple values for publisher/organization: ABC, XYZ" in result.message
        assert result.fixer is not None
        assert result.fixer.options == ["ABC", "XYZ", ">> Remove publisher/organization from all tracks"]
        assert result.fixer.option_automatic_index is None

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[0]) == FixResult.CHANGED_ALBUM

        assert mock_tagger_open.call_args_list == [call(tracks[0].filename)]
        assert mock_set_field.call_args_list == [call(BasicField.ORGANIZATION, "ABC")]
