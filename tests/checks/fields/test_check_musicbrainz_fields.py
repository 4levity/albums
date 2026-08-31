from unittest.mock import call

from albums.app import Context
from albums.checks.fields.check_musicbrainz_fields import AlbumTagger, CheckMusicBrainzFields
from albums.entities import Album, Track
from albums.tagger import BasicField

from ...helpers import MockTagger

UUID0 = "00000000-0000-0000-0000-000000000000"
UUID1 = "11111111-1111-1111-1111-111111111111"


class TestCheckMusicBrainzFields:
    def test_none(self):
        album = Album(path="foo", tracks=[Track(filename="1.flac", tag={BasicField.TITLE: "one"})])
        result = CheckMusicBrainzFields(Context()).check(album)
        assert result is None

    def test_no_deprecated(self):
        album = Album(path="foo", tracks=[Track(filename="1.flac", tag={BasicField.TITLE: "one", BasicField.MUSICBRAINZ_TRACKID: UUID0})])
        result = CheckMusicBrainzFields(Context()).check(album)
        assert result is None

    def test_deprecated_allowed(self):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tag={BasicField.TITLE: "one", BasicField.MUSICBRAINZ_TRACKID: UUID0, BasicField.MUSICBRAINZ_TRMID: UUID0})
            ],
        )
        ctx = Context()
        ctx.config.checks[CheckMusicBrainzFields.name]["remove_deprecated"] = False
        result = CheckMusicBrainzFields(ctx).check(album)
        assert result is None

    def test_deprecated(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tag={BasicField.TITLE: "one", BasicField.MUSICBRAINZ_TRACKID: UUID0, BasicField.MUSICBRAINZ_TRMID: UUID0})
            ],
        )
        result = CheckMusicBrainzFields(Context()).check(album)
        assert result is not None
        assert result.message == "Deprecated MusicBrainz fields found and remove_deprecated is enabled"
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove deprecated MusicBrainz fields"]
        assert result.fixer.option_automatic_index == 0

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_tagger_open.call_args_list == [call(album.tracks[0].filename)]
        assert mock_set_field.call_args_list == [call(BasicField.MUSICBRAINZ_TRMID, None)]

    def test_remove_all(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tag={BasicField.TITLE: "one", BasicField.MUSICBRAINZ_TRACKID: UUID0, BasicField.MUSICBRAINZ_TRMID: UUID0})
            ],
        )
        ctx = Context()
        ctx.config.checks[CheckMusicBrainzFields.name]["remove_all"] = True
        result = CheckMusicBrainzFields(ctx).check(album)
        assert result is not None
        assert result.message == "MusicBrainz fields found and remove_all is enabled"
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove all MusicBrainz fields"]
        assert result.fixer.option_automatic_index == 0

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_tagger_open.call_args_list == [call(album.tracks[0].filename)]
        assert mock_set_field.call_args_list == [call(BasicField.MUSICBRAINZ_TRACKID, None), call(BasicField.MUSICBRAINZ_TRMID, None)]

    def test_some_artist_mbid(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tag={BasicField.TITLE: "one", BasicField.MUSICBRAINZ_ALBUMARTISTID: UUID0}),
                Track(
                    filename="2.flac",
                    tag={BasicField.TITLE: "two", BasicField.MUSICBRAINZ_ALBUMARTISTID: UUID0, BasicField.MUSICBRAINZ_ALBUMID: UUID1},
                ),
            ],
        )
        result = CheckMusicBrainzFields(Context()).check(album)
        assert result is not None
        assert result.message == f"MUSICBRAINZ_ALBUMID is not the same on all tracks (values = {UUID1}, none)"
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove MUSICBRAINZ_ALBUMID fields", ">> Remove all MusicBrainz fields"]
        assert result.fixer.option_automatic_index == 0

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_tagger_open.call_args_list == [call(album.tracks[1].filename)]
        assert mock_set_field.call_args_list == [call(BasicField.MUSICBRAINZ_ALBUMID, None)]

    def test_only_albumrelease_type(self, mocker):
        # an album whose only MB field is album-release-type must not be skipped, and its consistency must be checked
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tag={BasicField.TITLE: "one"}),
                Track(filename="2.flac", tag={BasicField.TITLE: "two", BasicField.MUSICBRAINZ_ALBUMRELEASETYPE: "album"}),
            ],
        )
        result = CheckMusicBrainzFields(Context()).check(album)
        assert result is not None
        assert result.message == "MUSICBRAINZ_ALBUMRELEASETYPE is not the same on all tracks (values = album, none)"
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove MUSICBRAINZ_ALBUMRELEASETYPE fields", ">> Remove all MusicBrainz fields"]
        assert result.fixer.option_automatic_index == 0

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        # removing all MB fields must remove the release type field too
        assert result.fixer.fix(result.fixer.options[1])

        assert mock_tagger_open.call_args_list == [call(album.tracks[1].filename)]
        assert mock_set_field.call_args_list == [call(BasicField.MUSICBRAINZ_ALBUMRELEASETYPE, None)]

    def test_remove_all_includes_albumrelease_type(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(
                    filename="1.flac",
                    tag={
                        BasicField.TITLE: "one",
                        BasicField.MUSICBRAINZ_TRACKID: UUID0,
                        BasicField.MUSICBRAINZ_ALBUMRELEASETYPE: "soundtrack",
                    },
                )
            ],
        )
        ctx = Context()
        ctx.config.checks[CheckMusicBrainzFields.name]["remove_all"] = True
        result = CheckMusicBrainzFields(ctx).check(album)
        assert result is not None
        assert result.message == "MusicBrainz fields found and remove_all is enabled"
        assert result.fixer is not None
        assert result.fixer.option_automatic_index == 0

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_tagger_open.call_args_list == [call(album.tracks[0].filename)]
        assert mock_set_field.call_args_list == [
            call(BasicField.MUSICBRAINZ_ALBUMRELEASETYPE, None),
            call(BasicField.MUSICBRAINZ_TRACKID, None),
        ]

    def test_varying_albumartist_mbid(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(
                    filename="1.flac",
                    tag={BasicField.TITLE: "one", BasicField.MUSICBRAINZ_ALBUMARTISTID: UUID0, BasicField.MUSICBRAINZ_ALBUMID: UUID1},
                ),
                Track(
                    filename="2.flac",
                    tag={BasicField.TITLE: "two", BasicField.MUSICBRAINZ_ALBUMARTISTID: UUID1, BasicField.MUSICBRAINZ_ALBUMID: UUID1},
                ),
            ],
        )
        result = CheckMusicBrainzFields(Context()).check(album)
        assert result is not None
        assert result.message == f"MUSICBRAINZ_ALBUMARTISTID is not the same on all tracks (values = {UUID0}, {UUID1})"
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove MUSICBRAINZ_ALBUMARTISTID fields", ">> Remove all MusicBrainz fields"]
        assert result.fixer.option_automatic_index == 0

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_tagger_open.call_args_list == [call(album.tracks[0].filename), call(album.tracks[1].filename)]
        assert mock_set_field.call_args_list == [call(BasicField.MUSICBRAINZ_ALBUMARTISTID, None), call(BasicField.MUSICBRAINZ_ALBUMARTISTID, None)]

    def test_inconsistent_mbid_remove_all(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tag={BasicField.TITLE: "one", BasicField.MUSICBRAINZ_ALBUMARTISTID: UUID0}),
                Track(
                    filename="2.flac",
                    tag={BasicField.TITLE: "two", BasicField.MUSICBRAINZ_ALBUMARTISTID: UUID0, BasicField.MUSICBRAINZ_ALBUMID: UUID1},
                ),
            ],
        )
        result = CheckMusicBrainzFields(Context()).check(album)
        assert result is not None
        assert result.message == f"MUSICBRAINZ_ALBUMID is not the same on all tracks (values = {UUID1}, none)"
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove MUSICBRAINZ_ALBUMID fields", ">> Remove all MusicBrainz fields"]

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[1])

        assert mock_tagger_open.call_args_list == [call(album.tracks[0].filename), call(album.tracks[1].filename)]
        assert mock_set_field.call_args_list == [
            call(BasicField.MUSICBRAINZ_ALBUMARTISTID, None),
            call(BasicField.MUSICBRAINZ_ALBUMARTISTID, None),
            call(BasicField.MUSICBRAINZ_ALBUMID, None),
        ]
