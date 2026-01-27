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
        assert "multiple artists but no album artist (['A', 'B'] ...)" in result.message

    def test_check_needs_albumartist__one(self):
        # some tracks with albumartist
        album = Album(
            "",
            [
                Track("1.flac", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2.flac", {"artist": ["B"], "albumartist": ["Foo"]}),
                Track("3.flac", {"artist": ["B"]}),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert result.message == "album artist is set on some tracks but not all (['Foo'] ...)"

    def test_check_needs_albumartist__fix(self, mocker):
        album = Album(
            "album/",
            [Track("1.flac", {"artist": ["A"]}), Track("2.flac", {"artist": ["B"]}), Track("3.flac", {"artist": ["B"]})],
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckAlbumArtist(ctx).check(album)
        assert "multiple artists but no album artist" in result.message
        assert result.fixer is not None
        assert result.fixer.option_free_text
        assert result.fixer.options == ["B", "A", "Various Artists"]
        assert "album artist to use" in result.fixer.prompt
        assert result.fixer.table
        assert len(result.fixer.table[1]) == 3  # tracks
        assert len(result.fixer.table[0]) == len(result.fixer.table[1][0])  # headers

        # we select "B" and it is fixed
        mock_set_basic_tags = mocker.patch("albums.checks.check_album_artist.set_basic_tags")
        fix_result = result.fixer.fix("B")
        assert fix_result
        assert mock_set_basic_tags.call_count == 3
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[2].filename, [("albumartist", "B")])

    def test_check_albumartist_require(self, mocker):
        album_complies = Album(
            "c/", [Track("1.mp3", {"artist": ["A"], "albumartist": ["A"]}), Track("2.mp3", {"artist": ["A"], "albumartist": ["A"]})]
        )
        album_no_auto = Album("b/", [Track("1.mp3", {"artist": ["A"]}), Track("2.mp3", {"artist": ["A"]}), Track("3.mp3", {"artist": ["B"]})])
        album_auto = Album("a/", [Track("1.mp3", {"artist": ["A"]}), Track("2.mp3", {"artist": ["A"]})])

        ctx = Context()
        ctx.config["checks"] = {"album_artist": {"require_redundant": True}}
        ctx.library_root = Path("/path/to/library")
        result = CheckAlbumArtist(ctx).check(album_complies)
        assert result is None

        result = CheckAlbumArtist(ctx).check(album_no_auto)
        assert "multiple artists but no album artist" in result.message
        assert result.fixer is not None
        assert result.fixer.option_automatic_index is None
        assert result.fixer.option_free_text
        assert result.fixer.options == ["A", "B", "Various Artists"]
        assert "album artist to use" in result.fixer.prompt
        assert result.fixer.table
        assert len(result.fixer.table[1]) == 3  # tracks
        assert len(result.fixer.table[0]) == len(result.fixer.table[1][0])  # headers

        result = CheckAlbumArtist(ctx).check(album_auto)
        assert "album artist would be redundant, but it can be set to A" in result.message
        assert result.fixer is not None
        assert result.fixer.option_automatic_index is not None

        # select automatic option and it is fixed
        mock_set_basic_tags = mocker.patch("albums.checks.check_album_artist.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 2
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album_auto.path / album_auto.tracks[1].filename, [("albumartist", "A")])

    def test_check_albumartist_remove(self, mocker):
        album_auto = Album("c/", [Track("1.mp3", {"artist": ["A"], "albumartist": ["A"]}), Track("2.mp3", {"artist": ["A"], "albumartist": ["A"]})])
        album_no_auto = Album("b/", [Track("1.mp3", {"artist": ["A"]}), Track("2.mp3", {"artist": ["A"]}), Track("3.mp3", {"artist": ["B"]})])
        album_complies = Album("a/", [Track("1.mp3", {"artist": ["A"]}), Track("2.mp3", {"artist": ["A"]})])

        ctx = Context()
        ctx.config["checks"] = {"album_artist": {"remove_redundant": True}}
        ctx.library_root = Path("/path/to/library")
        result = CheckAlbumArtist(ctx).check(album_complies)
        assert result is None

        result = CheckAlbumArtist(ctx).check(album_no_auto)
        assert "multiple artists but no album artist" in result.message
        assert result.fixer is not None
        assert result.fixer.option_automatic_index is None
        assert result.fixer.option_free_text
        assert result.fixer.options == ["A", "B", "Various Artists"]
        assert "album artist to use" in result.fixer.prompt
        assert result.fixer.table
        assert len(result.fixer.table[1]) == 3  # tracks
        assert len(result.fixer.table[0]) == len(result.fixer.table[1][0])  # headers

        result = CheckAlbumArtist(ctx).check(album_auto)
        assert "album artist is not needed: A" in result.message
        assert result.fixer is not None
        assert result.fixer.option_automatic_index is not None

        # select automatic option and it is fixed
        mock_set_basic_tags = mocker.patch("albums.checks.check_album_artist.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 2
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album_auto.path / album_auto.tracks[1].filename, [("albumartist", None)])

    def test_multiple_albumartist(self):
        album = Album(
            "B",
            [
                Track("1.flac", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2.flac", {"artist": ["B"], "albumartist": ["Foo"]}),
                Track("3.flac", {"artist": ["B"], "albumartist": ["Bar"]}),
                Track("4.flac", {"artist": ["B"], "albumartist": ["Bar"]}),
                Track("5.flac", {"artist": ["B"], "albumartist": ["Bar"]}),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "multiple album artist values (['Bar', 'Foo'] ...)" in result.message
        assert result.fixer
        assert result.fixer.options == ["B", "Bar", "Foo", "A", "Various Artists"]
        assert result.fixer.option_free_text

    def test_multiple_albumartist__same_artist(self, mocker):
        album = Album(
            "",
            [
                Track("1.flac", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2.flac", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("3.flac", {"artist": ["A"], "albumartist": ["Bar"]}),
            ],
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckAlbumArtist(ctx).check(album)
        assert "multiple album artist values (['Foo', 'Bar'] ...)" in result.message
        assert result.fixer
        assert result.fixer.options == ["A", "Foo", "Bar", "Various Artists", ">> Copy album artist -> artist"]
        assert result.fixer.option_free_text
        assert result.fixer.table
        assert "album artist to use" in result.fixer.prompt

        # we select "copy album artist to artist" and it is fixed
        mock_set_basic_tags = mocker.patch("albums.checks.check_album_artist.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[4])
        assert fix_result
        assert mock_set_basic_tags.call_count == 3
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[2].filename, [("artist", "Bar")])

    def test_multiple_albumartist__same_artist_2(self):
        album = Album(
            "",
            [
                Track("1.flac", {"artist": ["A"], "albumartist": ["Foo"]}),
                Track("2.flac", {"artist": ["A"]}),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "album artist is set inconsistently and probably not needed (['Foo'] ...)" in result.message

    def test_albumartist_redundant(self):
        album = Album(
            "",
            [
                Track("1.flac", {"artist": ["Foo"], "albumartist": ["Foo"]}),
                Track("2.flac", {"artist": ["Foo"], "albumartist": ["Foo"]}),
            ],
        )
        ctx = Context()
        ctx.config["checks"] = {"album_artist": {"remove_redundant": True}}
        result = CheckAlbumArtist(ctx).check(album)
        assert "album artist is not needed: Foo" in result.message

    def test_albumartist__ok(self):
        album = Album(
            "",
            [
                Track("1.flac", {"artist": ["A"], "albumartist": ["A"]}),
                Track("2.flac", {"artist": ["B"], "albumartist": ["A"]}),
            ],
        )
        checker = CheckAlbumArtist(Context())
        result = checker.check(album)
        assert result is None

        # different artists, all albumartist the same
        album.tracks[1].tags["artist"] = ["A"]
        result = checker.check(album)
        assert result is None
