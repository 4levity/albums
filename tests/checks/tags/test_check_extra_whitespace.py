from unittest.mock import call

from albums.app import Context
from albums.checks.tags.check_extra_whitespace import CheckExtraWhitespace
from albums.tagger.folder import AlbumTagger, TaggerFile
from albums.tagger.types import BasicTag
from albums.types import Album, Tag, Track


class TestCheckExtraWhitespace:
    def test_whitespace_ok(self):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tags=[Tag(tag=BasicTag.ARTIST, value="Alice"), Tag(tag=BasicTag.TITLE, value="blue")]),
                Track(filename="2.flac", tags=[Tag(tag=BasicTag.ARTIST, value="Alice"), Tag(tag=BasicTag.TITLE, value="red")]),
            ],
        )
        result = CheckExtraWhitespace(Context()).check(album)
        assert result is None

    def test_whitespace_fix(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1.flac", tags=[Tag(tag=BasicTag.ARTIST, value="Alice "), Tag(tag=BasicTag.TITLE, value="blue")]),
                Track(filename="2.flac", tags=[Tag(tag=BasicTag.ARTIST, value="Alice "), Tag(tag=BasicTag.TITLE, value="red ")]),
            ],
        )
        result = CheckExtraWhitespace(Context()).check(album)
        assert result is not None
        assert "Extra whitespace present in 2 files in tags: artist, title" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Strip leading and trailing whitespace in tags: artist, title"]
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_tag = mocker.patch.object(tagger, "set_tag")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_set_tag.call_args_list == [call(BasicTag.ARTIST, ["Alice"]), call(BasicTag.ARTIST, ["Alice"]), call(BasicTag.TITLE, ["red"])]
