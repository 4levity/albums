from pathlib import Path

from albums.app import Context
from albums.checks.check_album_tag import CheckAlbumTag
from albums.types import Album, Stream, Track


class TestCheckAlbumTag:
    def test_check_needs_album__all(self):
        album = Album(
            "Foo/",
            [
                Track("1.flac", stream=Stream(codec="FLAC")),
                Track("2.flac", stream=Stream(codec="FLAC")),
                Track("3.flac", stream=Stream(codec="FLAC")),
            ],
        )
        result = CheckAlbumTag(Context()).check(album)
        assert "3 tracks missing album tag" in result.message

    def test_check_needs_album__one(self):
        album = Album(
            "",
            [
                Track("1.flac", {"album": ["A"]}, stream=Stream(codec="FLAC")),
                Track("2.flac", {"album": ["A"]}, stream=Stream(codec="FLAC")),
                Track("3.flac", stream=Stream(codec="FLAC")),
            ],
        )
        result = CheckAlbumTag(Context()).check(album)
        assert "1 tracks missing album tag" in result.message

    def test_check_needs_album__fix_auto(self, mocker):
        # album can be guessed from folder, no conflicting tags
        album = Album(
            "Foo/",
            [
                Track("1.flac", stream=Stream(codec="FLAC")),
                Track("2.flac", stream=Stream(codec="FLAC")),
                Track("3.flac", stream=Stream(codec="FLAC")),
            ],
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckAlbumTag(ctx).check(album)
        assert result.fixer is not None
        assert result.fixer.describe_automatic == 'set album to "Foo"'

        mock_set_basic_tag = mocker.patch("albums.checks.check_album_tag.set_basic_tag")
        fix_result = result.fixer.fix_automatic()
        assert fix_result
        assert mock_set_basic_tag.call_count == 3
        assert mock_set_basic_tag.call_args.args == (ctx.library_root / album.path / album.tracks[2].filename, "album", "Foo")

    def test_check_needs_album__fix_interactive(self, mocker):
        # not all tracks have album tag, where present it is different than folder name, no automatic fix
        album = Album(
            "Foo/",
            [
                Track("1.flac", {"album": ["Bar"]}, stream=Stream(codec="FLAC")),
                Track("2.flac", {"album": ["Bar"]}, stream=Stream(codec="FLAC")),
                Track("3.flac", stream=Stream(codec="FLAC")),
            ],
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckAlbumTag(ctx).check(album)
        assert result.fixer is not None
        assert result.fixer.describe_automatic is None
        assert result.fixer.has_interactive

        prompt = result.fixer.get_interactive_prompt()
        assert "1 tracks missing album tag" in str(prompt.message)
        assert prompt.option_free_text
        assert not prompt.option_none
        assert prompt.options == ["Bar", "Foo"]
        assert prompt.question.startswith("Which album name to use for all 3 tracks")
        assert prompt.show_table
        assert len(prompt.show_table[1]) == 3  # tracks
        assert len(prompt.show_table[0]) == len(prompt.show_table[1][0])  # headers
