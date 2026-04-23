from unittest.mock import call

from albums.app import Context
from albums.checks.tags.check_publisher_tag import AlbumTagger, CheckPublisherTag
from albums.tagger.types import BasicTag, TaggerFile
from albums.types import Album, Track


class TestCheckPublisherTag:
    def test_publisher_ok(self):
        tracks = [Track(filename="1.flac", tag={BasicTag.ORGANIZATION: "ABC"}), Track(filename="2.flac", tag={BasicTag.ORGANIZATION: "ABC"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherTag(Context()).check(album)
        assert result is None

    def test_publisher_ok_none(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherTag(Context()).check(album)
        assert result is None

    def test_publisher_missing(self):
        tracks = [Track(filename="1.flac", tag={BasicTag.ORGANIZATION: "ABC"}), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherTag(Context()).check(album)
        assert result is not None
        assert "organization policy=CONSISTENT but it is on some tracks and not others" in result.message

    def test_publisher_none_policy_always(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        ctx = Context()
        ctx.config.checks[CheckPublisherTag.name]["presence"] = "always"
        result = CheckPublisherTag(ctx).check(album)
        assert result is not None
        assert result.fixer is None
        assert "organization policy=ALWAYS but it is not on all tracks" in result.message

    def test_publisher_different_select(self, mocker):
        tracks = [Track(filename="1.flac", tag={BasicTag.ORGANIZATION: "XYZ"}), Track(filename="2.flac", tag={BasicTag.ORGANIZATION: "ABC"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherTag(Context()).check(album)
        assert result is not None
        assert "multiple values for publisher (organization): ABC, XYZ" in result.message
        assert result.fixer is not None
        assert result.fixer.options == ["ABC", "XYZ", ">> Remove organization (publisher) from all tracks"]
        assert result.fixer.option_automatic_index is None

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_tag = mocker.patch.object(tagger, "set_tag")

        assert result.fixer.fix(result.fixer.options[0])

        assert mock_tagger_open.call_args_list == [call(tracks[0].filename)]
        assert mock_set_tag.call_args_list == [call(BasicTag.ORGANIZATION, "ABC")]

    def test_publisher_different_remove(self, mocker):
        tracks = [Track(filename="1.flac", tag={BasicTag.ORGANIZATION: "XYZ"}), Track(filename="2.flac", tag={BasicTag.ORGANIZATION: "ABC"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckPublisherTag(Context()).check(album)
        assert result is not None
        assert "multiple values for publisher (organization): ABC, XYZ" in result.message
        assert result.fixer is not None
        assert result.fixer.options == ["ABC", "XYZ", ">> Remove organization (publisher) from all tracks"]
        assert result.fixer.option_automatic_index is None

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_tag = mocker.patch.object(tagger, "set_tag")

        assert result.fixer.fix(result.fixer.options[0])

        assert mock_tagger_open.call_args_list == [call(tracks[0].filename)]
        assert mock_set_tag.call_args_list == [call(BasicTag.ORGANIZATION, "ABC")]
