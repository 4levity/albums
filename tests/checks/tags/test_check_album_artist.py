from pathlib import Path

from albums.app import Context
from albums.checks.tags.check_album_artist import CheckAlbumArtist
from albums.database.models import AlbumEntity, TrackEntity, TrackTagEntity
from albums.tagger.folder import AlbumTagger
from albums.types import BasicTag


class TestCheckAlbumArtist:
    def test_check_needs_albumartist__all(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A")]),
                TrackEntity(filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B")]),
                TrackEntity(filename="3.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B")]),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "multiple artists but no album artist (['A', 'B'] ...)" in result.message

    def test_check_missing_artist(self):
        # missing artist does not count as multiple artists, this passes
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]
                ),
                TrackEntity(filename="3.flac", tags=[TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert result is None

    def test_check_needs_albumartist__one(self):
        # some tracks with albumartist
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]
                ),
                TrackEntity(filename="3.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B")]),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert result.message == "album artist is set on some tracks but not all (['Foo'] ...)"

    def test_check_needs_albumartist__fix(self, mocker):
        album = AlbumEntity(
            path="album/",
            tracks=[
                TrackEntity(filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A")]),
                TrackEntity(filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B")]),
                TrackEntity(filename="3.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B")]),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "multiple artists but no album artist" in result.message
        assert result.fixer is not None
        assert result.fixer.option_free_text
        assert result.fixer.options == ["B", "A", "Various Artists"]
        assert "album artist to use" in result.fixer.prompt
        assert result.fixer.table
        assert len(result.fixer.get_table()[1]) == 3  # tracks
        assert len(result.fixer.get_table()[0]) == len(result.fixer.get_table()[1][0])  # headers

        # we select "B" and it is fixed
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix("B")
        assert fix_result
        assert mock_set_basic_tags.call_count == 3
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[2].filename, [(BasicTag.ALBUMARTIST, "B")])

    def test_check_albumartist_require(self, mocker):
        album_complies = AlbumEntity(
            path="c/",
            tracks=[
                TrackEntity(
                    filename="1.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="A")]
                ),
                TrackEntity(
                    filename="2.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="A")]
                ),
            ],
        )
        album_no_auto = AlbumEntity(
            path="b/",
            tracks=[
                TrackEntity(filename="1.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A")]),
                TrackEntity(filename="2.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A")]),
                TrackEntity(filename="3.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B")]),
            ],
        )
        album_auto = AlbumEntity(
            path="a/",
            tracks=[
                TrackEntity(filename="1.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A")]),
                TrackEntity(filename="2.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A")]),
            ],
        )

        ctx = Context()
        ctx.config.checks = {"album-artist": {"require_redundant": True}}
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
        assert len(result.fixer.get_table()[1]) == 3  # tracks
        assert len(result.fixer.table[0]) == len(result.fixer.get_table()[1][0])  # headers

        result = CheckAlbumArtist(ctx).check(album_auto)
        assert "album artist would be redundant, but it can be set to A" in result.message
        assert result.fixer is not None
        assert result.fixer.option_automatic_index is not None

        # select automatic option and it is fixed
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 2
        assert mock_set_basic_tags.call_args.args == (Path(album_auto.path) / album_auto.tracks[1].filename, [(BasicTag.ALBUMARTIST, "A")])

    def test_check_albumartist_remove(self, mocker):
        album_auto = AlbumEntity(
            path="c/",
            tracks=[
                TrackEntity(
                    filename="1.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="A")]
                ),
                TrackEntity(
                    filename="2.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="A")]
                ),
            ],
        )
        album_no_auto = AlbumEntity(
            path="b/",
            tracks=[
                TrackEntity(filename="1.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A")]),
                TrackEntity(filename="2.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A")]),
                TrackEntity(filename="3.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B")]),
            ],
        )
        album_complies = AlbumEntity(
            path="a/",
            tracks=[
                TrackEntity(filename="1.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A")]),
                TrackEntity(filename="2.mp3", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A")]),
            ],
        )

        ctx = Context()
        ctx.config.checks = {"album-artist": {"remove_redundant": True}}
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
        assert len(result.fixer.get_table()[1]) == 3  # tracks
        assert len(result.fixer.get_table()[0]) == len(result.fixer.get_table()[1][0])  # headers

        result = CheckAlbumArtist(ctx).check(album_auto)
        assert "album artist is not needed: A" in result.message
        assert result.fixer is not None
        assert result.fixer.option_automatic_index is not None

        # select automatic option and it is fixed
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 2
        assert mock_set_basic_tags.call_args.args == (Path(album_auto.path) / album_auto.tracks[1].filename, [(BasicTag.ALBUMARTIST, None)])

    def test_multiple_albumartist(self):
        album = AlbumEntity(
            path="B",
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]
                ),
                TrackEntity(
                    filename="3.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Bar")]
                ),
                TrackEntity(
                    filename="4.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Bar")]
                ),
                TrackEntity(
                    filename="5.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Bar")]
                ),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "multiple album artist values (['Bar', 'Foo'] ...)" in result.message
        assert result.fixer
        assert result.fixer.options == ["B", "Bar", "Foo", "A", "Various Artists"]
        assert result.fixer.option_free_text

    def test_multiple_albumartist__same_artist(self, mocker):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]
                ),
                TrackEntity(
                    filename="3.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Bar")]
                ),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "multiple album artist values (['Foo', 'Bar'] ...)" in result.message
        assert result.fixer
        assert result.fixer.options == ["A", "Foo", "Bar", "Various Artists", ">> Copy album artist -> artist"]
        assert result.fixer.option_free_text
        assert result.fixer.table
        assert "album artist to use" in result.fixer.prompt

        # we select "copy album artist to artist" and it is fixed
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[4])
        assert fix_result
        assert mock_set_basic_tags.call_count == 3
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[2].filename, [(BasicTag.ARTIST, "Bar")])

    def test_multiple_albumartist__same_artist_2(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]
                ),
                TrackEntity(filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A")]),
            ],
        )
        result = CheckAlbumArtist(Context()).check(album)
        assert "album artist is set inconsistently and probably not needed (['Foo'] ...)" in result.message

    def test_albumartist_redundant(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="Foo"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="Foo"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Foo")]
                ),
            ],
        )
        ctx = Context()
        ctx.config.checks = {"album-artist": {"remove_redundant": True}}
        result = CheckAlbumArtist(ctx).check(album)
        assert "album artist is not needed: Foo" in result.message

    def test_albumartist__ok(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="A")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.ARTIST, value="B"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="A")]
                ),
            ],
        )
        checker = CheckAlbumArtist(Context())
        # different artists, all albumartist the same
        result = checker.check(album)
        assert result is None

        # same artists, all albumartist the same
        album.tracks[1].tags = [TrackTagEntity(tag=BasicTag.ARTIST, value="A"), TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="A")]
        result = checker.check(album)
        assert result is None
