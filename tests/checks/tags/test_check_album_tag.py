import os
from pathlib import Path

from albums.app import Context
from albums.checks.tags.check_album_tag import CheckAlbumTag
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import BasicTag
from albums.types import Album, Track


class TestCheckAlbumTag:
    def test_check_needs_album__all(self):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1.flac"),
                Track(filename="2.flac"),
                Track(filename="3.flac"),
            ],
        )
        result = CheckAlbumTag(Context()).check(album)
        assert "3 tracks missing album tag" in result.message

    def test_check_needs_album__one(self):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicTag.ALBUM: "A"}),
                Track(filename="2.flac", tag={BasicTag.ALBUM: "A"}),
                Track(filename="3.flac"),
            ],
        )
        result = CheckAlbumTag(Context()).check(album)
        assert "1 tracks missing album tag" in result.message

    def test_check_needs_album__conflicting(self):
        album = Album(
            path="A/",
            tracks=[
                Track(filename="1.flac", tag={BasicTag.ALBUM: "A"}),
                Track(filename="2.flac", tag={BasicTag.ALBUM: "A"}),
                Track(filename="3.flac", tag={BasicTag.ALBUM: "B"}),
            ],
        )
        result = CheckAlbumTag(Context()).check(album)
        assert "2 conflicting album tag values" in result.message
        assert result.fixer is not None
        assert result.fixer.options == ["A", "B"]
        assert result.fixer.option_automatic_index is None
        assert result.fixer.option_free_text is not None

    def test_check_needs_album__fix_auto(self, mocker):
        # album can be guessed from folder, no conflicting tags
        album = Album(
            path="Foo" + os.sep,
            tracks=[
                Track(filename="1.flac"),
                Track(filename="2.flac"),
                Track(filename="3.flac"),
            ],
        )
        result = CheckAlbumTag(Context()).check(album)
        assert result.fixer is not None
        assert result.fixer.options[0] == "Foo"
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 3
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[2].filename, [(BasicTag.ALBUM, "Foo")])

    def test_check_needs_album__fix_interactive(self, mocker):
        # not all tracks have album tag, where present it is different than folder name, no automatic fix
        album = Album(
            path="Foo" + os.sep,
            tracks=[
                Track(filename="1.flac", tag={BasicTag.ALBUM: "Bar"}),
                Track(filename="2.flac", tag={BasicTag.ALBUM: "Bar"}),
                Track(filename="3.flac"),
            ],
        )
        result = CheckAlbumTag(Context()).check(album)
        assert "1 tracks missing album tag" in str(result.message)
        assert result.fixer is not None
        assert result.fixer.option_automatic_index is None
        assert result.fixer.option_free_text
        assert result.fixer.options == ["Bar", "Foo"]
        assert "album name to use" in result.fixer.prompt
        assert result.fixer.table
        assert len(result.fixer.get_table()[1]) == 3  # tracks
        assert len(result.fixer.get_table()[0]) == len(result.fixer.get_table()[1][0])  # headers

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[0])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[2].filename, [(BasicTag.ALBUM, "Bar")])
