from pathlib import Path

from albums.app import Context
from albums.checks.numbering import total_tags
from albums.database.models import AlbumEntity, TrackEntity, TrackTagEntity
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import BasicTag


class TestTotalTags:
    def check(self, album: AlbumEntity, policy: total_tags.Policy):
        return total_tags.check_policy(Context(), AlbumTagger(Path(album.path)), album, policy, BasicTag.TRACKTOTAL, BasicTag.TRACKNUMBER)

    def test_check_total_policy_ok(self):
        album_with_all = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="1")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="1")]
                ),
            ],
        )
        album_with_none = AlbumEntity(path="", tracks=[TrackEntity(filename="1.flac"), TrackEntity(filename="2.flac")])

        result = self.check(album_with_all, total_tags.Policy.CONSISTENT)
        assert result is None
        result = self.check(album_with_none, total_tags.Policy.CONSISTENT)
        assert result is None

        result = self.check(album_with_all, total_tags.Policy.ALWAYS)
        assert result is None

        result = self.check(album_with_none, total_tags.Policy.NEVER)
        assert result is None

    def test_check_total_policy_always(self, mocker):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(filename="1.flac"),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="1")]
                ),
            ],
        )

        result = self.check(album, total_tags.Policy.ALWAYS)
        assert "tracktotal policy=ALWAYS but it is not on all tracks" in result.message
        assert not result.fixer

    def test_check_total_policy_consistent(self, mocker):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(filename="1.flac"),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="1")]
                ),
            ],
        )

        result = self.check(album, total_tags.Policy.CONSISTENT)
        assert "tracktotal policy=CONSISTENT but it is on some tracks and not others" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove tag tracktotal"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[1].filename, [(BasicTag.TRACKTOTAL, None)])

    def test_check_total_policy_never(self, mocker):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="2")]
                ),
            ],
        )

        result = self.check(album, total_tags.Policy.NEVER)
        assert "tracktotal policy=NEVER but it appears on tracks" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove tag tracktotal"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 2
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[1].filename, [(BasicTag.TRACKTOTAL, None)])

    def test_check_total_policy_total_without_index(self, mocker):
        album = AlbumEntity(
            path="",
            tracks=[TrackEntity(filename="1.flac"), TrackEntity(filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="1")])],
        )

        result = self.check(album, total_tags.Policy.ALWAYS)
        assert "tracktotal appears on tracks without tracknumber" in result.message
        assert not result.fixer  # manual fix is required if we can't just remove the tracktotal

        # if policy is never there is an automatic fix, remove the total
        result = self.check(album, total_tags.Policy.NEVER)
        assert "tracktotal appears on tracks without tracknumber" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove tag tracktotal"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[1].filename, [(BasicTag.TRACKTOTAL, None)])
