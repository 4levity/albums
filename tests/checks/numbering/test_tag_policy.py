from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.tag_policy import Policy, check_policy
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import BasicTag
from albums.types import Album, Track


class TestTotalTags:
    def check(self, album: Album, policy: Policy):
        return check_policy(
            Context(), AlbumTagger(Path(album.path)), album, policy, BasicTag.TRACKTOTAL, BasicTag.TRACKNUMBER, policy != Policy.NEVER
        )

    def test_check_tag_policy_ok(self):
        album_with_all = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicTag.TRACKNUMBER: "1", BasicTag.TRACKTOTAL: "1"}),
                Track(filename="2.flac", tag={BasicTag.TRACKNUMBER: "1", BasicTag.TRACKTOTAL: "1"}),
            ],
        )
        album_with_none = Album(path="", tracks=[Track(filename="1.flac"), Track(filename="2.flac")])

        result = self.check(album_with_all, Policy.CONSISTENT)
        assert result is None
        result = self.check(album_with_none, Policy.CONSISTENT)
        assert result is None

        result = self.check(album_with_all, Policy.ALWAYS)
        assert result is None

        result = self.check(album_with_none, Policy.NEVER)
        assert result is None

    def test_check_tag_policy_always_fixable(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicTag.TRACKNUMBER: "1"}),
                Track(filename="2.flac", tag={BasicTag.TRACKNUMBER: "1", BasicTag.TRACKTOTAL: "1"}),
            ],
        )

        result = self.check(album, Policy.ALWAYS)
        assert "tracktotal policy=ALWAYS but it is not on all tracks" in result.message
        assert result.fixer
        assert result.fixer.options == ["1"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.option_free_text

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_set_basic_tags.call_args_list == [call(Path(album.tracks[0].filename), [(BasicTag.TRACKTOTAL, "1")])]

    def test_check_tag_policy_always_unfixable(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac"),
                Track(filename="2.flac", tag={BasicTag.TRACKNUMBER: "1", BasicTag.TRACKTOTAL: "1"}),
            ],
        )

        result = self.check(album, Policy.ALWAYS)
        assert "tracktotal policy=ALWAYS but it is not on all tracks" in result.message
        assert result.fixer is None

    def test_check_tag_policy_consistent(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicTag.TRACKNUMBER: "1"}),
                Track(filename="2.flac", tag={BasicTag.TRACKNUMBER: "1", BasicTag.TRACKTOTAL: "1"}),
            ],
        )

        result = self.check(album, Policy.CONSISTENT)
        assert "tracktotal policy=CONSISTENT but it is on some tracks and not others" in result.message
        assert result.fixer
        assert result.fixer.options == ["1", ">> Remove tag tracktotal"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[0].filename, [(BasicTag.TRACKTOTAL, "1")])

    def test_check_tag_policy_consistent_no_other(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac"),
                Track(filename="2.flac", tag={BasicTag.TRACKNUMBER: "1", BasicTag.TRACKTOTAL: "1"}),
            ],
        )

        result = self.check(album, Policy.CONSISTENT)
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

    def test_check_tag_policy_never(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicTag.TRACKNUMBER: "1", BasicTag.TRACKTOTAL: "2"}),
                Track(filename="2.flac", tag={BasicTag.TRACKNUMBER: "2", BasicTag.TRACKTOTAL: "2"}),
            ],
        )

        result = self.check(album, Policy.NEVER)
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

    def test_check_tag_policy_total_without_index(self, mocker):
        album = Album(path="", tracks=[Track(filename="1.flac"), Track(filename="2.flac", tag={BasicTag.TRACKTOTAL: "1"})])

        result = self.check(album, Policy.ALWAYS)
        assert "tracktotal appears on tracks without tracknumber" in result.message
        assert not result.fixer  # manual fix is required if we can't just remove the tracktotal

        # if policy is never there is an automatic fix, remove the total
        result = self.check(album, Policy.NEVER)
        assert "tracktotal appears on tracks without tracknumber" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove tag tracktotal"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[1].filename, [(BasicTag.TRACKTOTAL, None)])
