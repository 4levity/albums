from pathlib import Path

from albums.app import Context
from albums.checks.check_album_artist import CheckAlbumArtist
from albums.types import Album, Track


class TestCheckAlbumArtist:
    def test_check_needs_albumartist__all(self):
        album = Album(
            "",
            [Track("1.flac", {"artist": ["A"]}), Track("2.flac", {"artist": ["B"]}), Track("3.flac", {"artist": ["B"]})],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "ISSUE: multiple artists but no album artist (['A', 'B'] ...)" in result.message

    def test_check_needs_albumartist__one(self):
        # some tracks with albumartist
        album = Album(
            "",
            [
                Track("1", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2", {"artist": ["B"], "albumartist": ["Foo"]}),
                Track("3", {"artist": ["B"]}),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "ISSUE: multiple artists but no album artist (['A', 'B'] ...)" in result.message

    def test_check_needs_albumartist__fix(self, mocker):
        album = Album(
            "album/",
            [Track("1.flac", {"artist": ["A"]}), Track("2.flac", {"artist": ["B"]}), Track("3.flac", {"artist": ["B"]})],
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckAlbumArtist(ctx).check(album)
        assert result.fixer is not None
        assert result.fixer.has_interactive
        prompt = result.fixer.get_interactive_prompt()
        assert "multiple artists but no album artist" in str(prompt.message)
        assert prompt.option_free_text
        assert not prompt.option_none
        assert prompt.options == ["B", "A", None, "Various Artists"]
        assert prompt.question.startswith("Which album artist to use for all 3 tracks")
        assert prompt.show_table
        assert len(prompt.show_table[1]) == 3  # tracks
        assert len(prompt.show_table[0]) == len(prompt.show_table[1][0])  # headers

        # we select "B" and it is fixed
        mock_set_basic_tag = mocker.patch("albums.checks.check_album_artist.set_basic_tag")
        fix_result = result.fixer.fix_interactive("B")
        assert fix_result
        assert mock_set_basic_tag.call_count == 3
        assert mock_set_basic_tag.call_args.args == (ctx.library_root / album.path / album.tracks[2].filename, "albumartist", "B")

    def test_multiple_albumartist(self):
        album = Album(
            "",
            [
                Track("1", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2", {"artist": ["B"], "albumartist": ["Foo"]}),
                Track("3", {"artist": ["B"], "albumartist": ["Bar"]}),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "ISSUE: multiple album artist values (['Foo', 'Bar'] ...)" in result.message

    def test_multiple_albumartist__same_artist(self):
        album = Album(
            "",
            [
                Track("1", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2", {"artist": ["A"], "albumartist": ["Bar"]}),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "ISSUE: multiple album artist values (['Foo', 'Bar'] ...)" in result.message

    def test_multiple_albumartist__same_artist_2(self):
        album = Album(
            "",
            [
                Track("1", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2", {"artist": ["A"]}),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "ISSUE: album artist is set inconsistently and probably not needed (['Foo'] ...)" in result.message

    def test_albumartist_redundant(self):
        album = Album(
            "",
            [
                Track("1", {"artist": ["Foo"], "albumartist": ["Foo"]}),
                Track("2", {"artist": ["Foo"], "albumartist": ["Foo"]}),
            ],
        )
        ctx = Context()
        ctx.config["checks"] = {"album_artist": {"remove_redundant": True}}
        result = CheckAlbumArtist(ctx).check(album)
        assert "ISSUE: album artist is probably not needed: Foo" in result.message

    def test_albumartist__ok(self):
        album = Album(
            "",
            [
                Track("1", {"artist": ["A"], "albumartist": ["A"]}),
                Track("2", {"artist": ["B"], "albumartist": ["A"]}),
            ],
        )
        checker = CheckAlbumArtist(Context())
        result = checker.check(album)
        assert result is None

        # different artists, all albumartist the same
        album.tracks[1].tags["artist"] = ["A"]
        result = checker.check(album)
        assert result is None
