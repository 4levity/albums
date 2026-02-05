from pathlib import Path

from albums.app import Context
from albums.checks import total_tags
from albums.types import Album, Track


class TestTotalTags:
    def check(self, ctx: Context, album: Album, policy: total_tags.Policy):
        return total_tags.check_policy(ctx, album, policy, "tracktotal", "tracknumber")

    def test_check_total_policy_ok(self):
        album_with_all = Album(
            "", [Track("1.flac", {"tracknumber": ["1"], "tracktotal": ["1"]}), Track("2.flac", {"tracknumber": ["1"], "tracktotal": ["1"]})]
        )
        album_with_none = Album("", [Track("1.flac"), Track("2.flac")])

        result = self.check(Context(), album_with_all, total_tags.Policy.CONSISTENT)
        assert result is None
        result = self.check(Context(), album_with_none, total_tags.Policy.CONSISTENT)
        assert result is None

        result = self.check(Context(), album_with_all, total_tags.Policy.ALWAYS)
        assert result is None

        result = self.check(Context(), album_with_none, total_tags.Policy.NEVER)
        assert result is None

    def test_check_total_policy_always(self, mocker):
        album = Album("", [Track("1.flac"), Track("2.flac", {"tracknumber": ["1"], "tracktotal": ["1"]})])

        result = self.check(Context(), album, total_tags.Policy.ALWAYS)
        assert "tracktotal policy=ALWAYS but it is not on all tracks" in result.message
        assert not result.fixer

    def test_check_total_policy_consistent(self, mocker):
        album = Album("", [Track("1.flac"), Track("2.flac", {"tracknumber": ["1"], "tracktotal": ["1"]})])

        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = self.check(ctx, album, total_tags.Policy.CONSISTENT)
        assert "tracktotal policy=CONSISTENT but it is on some tracks and not others" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove tag tracktotal from all tracks"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch("albums.checks.total_tags.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[1].filename, [("tracktotal", None)])

    def test_check_total_policy_never(self, mocker):
        album = Album(
            "", [Track("1.flac", {"tracknumber": ["1"], "tracktotal": ["2"]}), Track("2.flac", {"tracknumber": ["2"], "tracktotal": ["2"]})]
        )

        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = self.check(ctx, album, total_tags.Policy.NEVER)
        assert "tracktotal policy=NEVER but it appears on tracks" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove tag tracktotal from all tracks"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch("albums.checks.total_tags.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 2
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[1].filename, [("tracktotal", None)])

    def test_check_total_policy_total_without_index(self, mocker):
        album = Album("", [Track("1.flac"), Track("2.flac", {"tracktotal": ["1"]})])

        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = self.check(ctx, album, total_tags.Policy.ALWAYS)
        assert "tracktotal appears on tracks without tracknumber" in result.message
        assert not result.fixer  # manual fix is required if we can't just remove the tracktotal

        # if policy is never there is an automatic fix, remove the total
        result = self.check(ctx, album, total_tags.Policy.NEVER)
        assert "tracktotal appears on tracks without tracknumber" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove tag tracktotal from all tracks"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch("albums.checks.total_tags.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[1].filename, [("tracktotal", None)])
