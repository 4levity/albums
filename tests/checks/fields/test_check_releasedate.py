from unittest.mock import call

from albums.app import Context
from albums.checks.base_check_field_per_album import AlbumTagger
from albums.checks.fields.check_releasedate import CheckReleaseDateField
from albums.entities import Album, Track
from albums.tagger import BasicField

from ...helpers import MockTagger


class TestCheckReleaseDateField:
    def test_releasedate_ok(self):
        tracks = [Track(filename="1.flac", tag={BasicField.DATE: "2020"}), Track(filename="2.flac", tag={BasicField.DATE: "2020"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseDateField(Context()).check(album)
        assert result is None

    def test_releasedate_ok_none(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseDateField(Context()).check(album)
        assert result is None

    def test_releasedate_inconsistent_presence(self):
        tracks = [Track(filename="1.flac", tag={BasicField.DATE: "2020"}), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseDateField(Context()).check(album)
        assert result is not None
        assert "date policy=CONSISTENT but it is on some tracks and not others" in result.message
        assert result.fixer is not None
        assert result.fixer.options == ["2020", ">> Remove field date"]
        assert result.fixer.option_automatic_index == 0

    def test_releasedate_policy_always(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        ctx = Context()
        ctx.config.checks[CheckReleaseDateField.name]["presence"] = "always"
        result = CheckReleaseDateField(ctx).check(album)
        assert result is not None
        assert result.fixer is None
        assert "date policy=ALWAYS but it is not on all tracks" in result.message

    def test_releasedate_policy_never(self):
        tracks = [Track(filename="1.flac", tag={BasicField.DATE: "2020"}), Track(filename="2.flac", tag={BasicField.DATE: "2020"})]
        album = Album(path="foo", tracks=tracks)
        ctx = Context()
        ctx.config.checks[CheckReleaseDateField.name]["presence"] = "never"
        result = CheckReleaseDateField(ctx).check(album)
        assert result is not None
        assert "date policy=NEVER but it appears on tracks" in result.message
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove field date"]
        assert result.fixer.option_automatic_index == 0

    def test_releasedate_multiple_values_select(self, mocker):
        tracks = [Track(filename="1.flac", tag={BasicField.DATE: "2020"}), Track(filename="2.flac", tag={BasicField.DATE: "2021"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseDateField(Context()).check(album)
        assert result is not None
        assert result.message == "multiple values for release date: 2020, 2021"
        assert result.fixer is not None
        assert result.fixer.options == ["2020", "2021", ">> Remove release date from all tracks"]
        assert result.fixer.option_free_text is True
        assert result.fixer.option_automatic_index is None

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[0])

        # only the track with a different value is updated
        assert mock_tagger_open.call_args_list == [call(tracks[1].filename)]
        assert mock_set_field.call_args_list == [call(BasicField.DATE, "2020")]

    def test_releasedate_multiple_values_free_text(self, mocker):
        tracks = [Track(filename="1.flac", tag={BasicField.DATE: "2020"}), Track(filename="2.flac", tag={BasicField.DATE: "2021"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseDateField(Context()).check(album)
        assert result is not None
        assert result.fixer is not None

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix("2022-03")

        assert mock_tagger_open.call_args_list == [call(tracks[0].filename), call(tracks[1].filename)]
        assert mock_set_field.call_args_list == [call(BasicField.DATE, "2022-03"), call(BasicField.DATE, "2022-03")]

    def test_releasedate_multiple_values_remove(self, mocker):
        tracks = [Track(filename="1.flac", tag={BasicField.DATE: "2020"}), Track(filename="2.flac", tag={BasicField.DATE: "2021"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseDateField(Context()).check(album)
        assert result is not None
        assert result.fixer is not None

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[-1])

        assert mock_tagger_open.call_args_list == [call(tracks[0].filename), call(tracks[1].filename)]
        assert mock_set_field.call_args_list == [call(BasicField.DATE, None), call(BasicField.DATE, None)]
