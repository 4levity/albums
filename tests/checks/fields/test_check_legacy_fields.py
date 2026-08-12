from albums.app import Context
from albums.checks.base_check_field_per_album import AlbumTagger
from albums.checks.fields.check_legacy_fields import OPTION_CONVERT_LEGACY, CheckLegacyFields
from albums.entities import Album, Track
from albums.tagger.types import BasicField, TaggerFile


class TestCheckLegacyFields:
    def test_legacy_none(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckLegacyFields(Context()).check(album)
        assert result is None

    def test_legacy_with_standard_fields(self):
        track1 = Track(
            filename="1.flac",
            tag={BasicField.ORGANIZATION: "ABC"},
            legacy_tags=["label"],
        )
        track2 = Track(
            filename="2.flac",
            tag={BasicField.ALBUMARTIST: "Artist X"},
            legacy_tags=["album artist"],
        )
        album = Album(path="foo", tracks=[track1, track2])
        result = CheckLegacyFields(Context()).check(album)

        assert result is not None
        assert "Legacy fields" in result.message
        assert result.fixer is not None
        assert len(result.fixer.options) == 1
        assert result.fixer.options[0] == OPTION_CONVERT_LEGACY
        assert result.fixer.option_automatic_index == 0

    def test_legacy_convert(self, mocker):
        track1 = Track(
            filename="1.flac",
            tag={BasicField.ORGANIZATION: "ABC"},
            legacy_tags=["label"],
        )
        track2 = Track(
            filename="2.flac",
            tag={BasicField.ALBUMARTIST: "Artist X"},
            legacy_tags=["album artist"],
        )
        album = Album(path="foo", tracks=[track1, track2])
        result = CheckLegacyFields(Context()).check(album)

        assert result is not None
        assert result.fixer is not None

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.option_automatic_index == 0
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        # Check that open was called for each track with legacy fields
        assert set(c[0][0] for c in mock_tagger_open.call_args_list) == {"1.flac", "2.flac"}

        # Verify the operations were performed
        set_field_calls = [c[0] for c in mock_set_field.call_args_list]
        assert (BasicField.ORGANIZATION, ["ABC"]) in set_field_calls
        assert ("label", None) in set_field_calls
        assert (BasicField.ALBUMARTIST, ["Artist X"]) in set_field_calls
        assert ("album artist", None) in set_field_calls

    def test_legacy_totaldiscs(self, mocker):
        track1 = Track(
            filename="1.flac",
            tag={BasicField.DISCTOTAL: "2"},
            legacy_tags=["totaldiscs"],
        )
        album = Album(path="foo", tracks=[track1])
        result = CheckLegacyFields(Context()).check(album)

        assert result is not None
        assert result.fixer is not None

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.option_automatic_index == 0
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        # Verify that disctotal was set and totaldiscs removed
        set_field_calls = [c[0] for c in mock_set_field.call_args_list]
        assert (BasicField.DISCTOTAL, ["2"]) in set_field_calls
        assert ("totaldiscs", None) in set_field_calls
