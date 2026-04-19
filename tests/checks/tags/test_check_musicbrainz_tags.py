from unittest.mock import call

from albums.app import Context
from albums.checks.tags.check_musicbrainz_tags import AlbumTagger, CheckMusicBrainzTags
from albums.tagger.types import BasicTag, TaggerFile
from albums.types import Album, Track

UUID0 = "00000000-0000-0000-0000-000000000000"
UUID1 = "11111111-1111-1111-1111-111111111111"


class TestCheckMusicBrainzTags:
    def test_none(self):
        album = Album(path="foo", tracks=[Track(filename="1.flac", tag={BasicTag.TITLE: "one"})])
        result = CheckMusicBrainzTags(Context()).check(album)
        assert result is None

    def test_no_deprecated(self):
        album = Album(path="foo", tracks=[Track(filename="1.flac", tag={BasicTag.TITLE: "one", BasicTag.MUSICBRAINZ_TRACKID: UUID0})])
        result = CheckMusicBrainzTags(Context()).check(album)
        assert result is None

    def test_deprecated_allowed(self):
        album = Album(
            path="foo",
            tracks=[Track(filename="1.flac", tag={BasicTag.TITLE: "one", BasicTag.MUSICBRAINZ_TRACKID: UUID0, BasicTag.MUSICBRAINZ_TRMID: UUID0})],
        )
        ctx = Context()
        ctx.config.checks[CheckMusicBrainzTags.name]["remove_deprecated"] = False
        result = CheckMusicBrainzTags(ctx).check(album)
        assert result is None

    def test_deprecated(self, mocker):
        album = Album(
            path="foo",
            tracks=[Track(filename="1.flac", tag={BasicTag.TITLE: "one", BasicTag.MUSICBRAINZ_TRACKID: UUID0, BasicTag.MUSICBRAINZ_TRMID: UUID0})],
        )
        result = CheckMusicBrainzTags(Context()).check(album)
        assert result is not None
        assert result.message == "Deprecated MusicBrainz tags found and remove_deprecated is enabled"
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove deprecated MusicBrainz tags"]
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_tag = mocker.patch.object(tagger, "set_tag")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_tagger_open.call_args_list == [call(album.tracks[0].filename)]
        assert mock_set_tag.call_args_list == [call(BasicTag.MUSICBRAINZ_TRMID, None)]

    def test_remove_all(self, mocker):
        album = Album(
            path="foo",
            tracks=[Track(filename="1.flac", tag={BasicTag.TITLE: "one", BasicTag.MUSICBRAINZ_TRACKID: UUID0, BasicTag.MUSICBRAINZ_TRMID: UUID0})],
        )
        ctx = Context()
        ctx.config.checks[CheckMusicBrainzTags.name]["remove_all"] = True
        result = CheckMusicBrainzTags(ctx).check(album)
        assert result is not None
        assert result.message == "MusicBrainz tags found and remove_all is enabled"
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove all MusicBrainz tags"]
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_tag = mocker.patch.object(tagger, "set_tag")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_tagger_open.call_args_list == [call(album.tracks[0].filename)]
        assert mock_set_tag.call_args_list == [call(BasicTag.MUSICBRAINZ_TRACKID, None), call(BasicTag.MUSICBRAINZ_TRMID, None)]

    def test_some_artist_mbid(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tag={BasicTag.TITLE: "one", BasicTag.MUSICBRAINZ_ALBUMARTISTID: UUID0}),
                Track(filename="2.flac", tag={BasicTag.TITLE: "two", BasicTag.MUSICBRAINZ_ALBUMARTISTID: UUID0, BasicTag.MUSICBRAINZ_ALBUMID: UUID1}),
            ],
        )
        result = CheckMusicBrainzTags(Context()).check(album)
        assert result is not None
        assert result.message == f"MUSICBRAINZ_ALBUMID is not the same on all tracks (values = {UUID1}, none)"
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove MUSICBRAINZ_ALBUMID tags", ">> Remove all MusicBrainz tags"]
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_tag = mocker.patch.object(tagger, "set_tag")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_tagger_open.call_args_list == [call(album.tracks[1].filename)]
        assert mock_set_tag.call_args_list == [call(BasicTag.MUSICBRAINZ_ALBUMID, None)]

    def test_varying_albumartist_mbid(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tag={BasicTag.TITLE: "one", BasicTag.MUSICBRAINZ_ALBUMARTISTID: UUID0, BasicTag.MUSICBRAINZ_ALBUMID: UUID1}),
                Track(filename="2.flac", tag={BasicTag.TITLE: "two", BasicTag.MUSICBRAINZ_ALBUMARTISTID: UUID1, BasicTag.MUSICBRAINZ_ALBUMID: UUID1}),
            ],
        )
        result = CheckMusicBrainzTags(Context()).check(album)
        assert result is not None
        assert result.message == f"MUSICBRAINZ_ALBUMARTISTID is not the same on all tracks (values = {UUID0}, {UUID1})"
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove MUSICBRAINZ_ALBUMARTISTID tags", ">> Remove all MusicBrainz tags"]
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_tag = mocker.patch.object(tagger, "set_tag")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_tagger_open.call_args_list == [call(album.tracks[0].filename), call(album.tracks[1].filename)]
        assert mock_set_tag.call_args_list == [call(BasicTag.MUSICBRAINZ_ALBUMARTISTID, None), call(BasicTag.MUSICBRAINZ_ALBUMARTISTID, None)]

    def test_inconsistent_mbid_remove_all(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tag={BasicTag.TITLE: "one", BasicTag.MUSICBRAINZ_ALBUMARTISTID: UUID0}),
                Track(filename="2.flac", tag={BasicTag.TITLE: "two", BasicTag.MUSICBRAINZ_ALBUMARTISTID: UUID0, BasicTag.MUSICBRAINZ_ALBUMID: UUID1}),
            ],
        )
        result = CheckMusicBrainzTags(Context()).check(album)
        assert result is not None
        assert result.message == f"MUSICBRAINZ_ALBUMID is not the same on all tracks (values = {UUID1}, none)"
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove MUSICBRAINZ_ALBUMID tags", ">> Remove all MusicBrainz tags"]

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_tag = mocker.patch.object(tagger, "set_tag")

        assert result.fixer.fix(result.fixer.options[1])

        assert mock_tagger_open.call_args_list == [call(album.tracks[0].filename), call(album.tracks[1].filename)]
        assert mock_set_tag.call_args_list == [
            call(BasicTag.MUSICBRAINZ_ALBUMARTISTID, None),
            call(BasicTag.MUSICBRAINZ_ALBUMARTISTID, None),
            call(BasicTag.MUSICBRAINZ_ALBUMID, None),
        ]
