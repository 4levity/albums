from unittest.mock import call

from albums.app import Context
from albums.checks.tags.check_musicbrainz_tags import AlbumTagger, CheckMusicBrainzTags
from albums.tagger.types import BasicTag, TaggerFile
from albums.types import Album, Track

UUID0 = "00000000-0000-0000-0000-000000000000"


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
