from pathlib import Path

from albums.app import Context
from albums.checks.check_disctotal_presence import CheckDiscTotalPresence
from albums.checks.check_tracktotal_presence import CheckTrackTotalPresence
from albums.types import Album, Track


class TestCheckTotalTags:
    def test_check_disctotal_presence_ok(self):
        album_with_all = Album(
            "", [Track("1.flac", {"discnumber": ["1"], "disctotal": ["1"]}), Track("2.flac", {"discnumber": ["1"], "disctotal": ["1"]})]
        )
        album_with_none = Album("", [Track("1.flac"), Track("2.flac")])
        ctx = Context()
        ctx.config["checks"] = {"disctotal_presence": {"policy": "consistent"}}
        check = CheckDiscTotalPresence(ctx)
        result = check.check(album_with_all)
        assert result is None
        result = check.check(album_with_none)
        assert result is None

        ctx.config["checks"] = {"disctotal_presence": {"policy": "always"}}
        result = CheckDiscTotalPresence(ctx).check(album_with_all)
        assert result is None

        ctx.config["checks"] = {"disctotal_presence": {"policy": "never"}}
        result = CheckDiscTotalPresence(ctx).check(album_with_none)
        assert result is None

    def test_check_tracktotal_presence_ok(self):
        album_with_all = Album(
            "", [Track("1.flac", {"tracknumber": ["1"], "tracktotal": ["1"]}), Track("2.flac", {"tracknumber": ["1"], "tracktotal": ["1"]})]
        )
        album_with_none = Album("", [Track("1.flac"), Track("2.flac")])
        ctx = Context()
        ctx.config["checks"] = {"tracktotal_presence": {"policy": "consistent"}}
        check = CheckDiscTotalPresence(ctx)
        result = check.check(album_with_all)
        assert result is None
        result = check.check(album_with_none)
        assert result is None

        ctx.config["checks"] = {"tracktotal_presence": {"policy": "always"}}
        result = CheckDiscTotalPresence(ctx).check(album_with_all)
        assert result is None

        ctx.config["checks"] = {"tracktotal_presence": {"policy": "never"}}
        result = CheckDiscTotalPresence(ctx).check(album_with_none)
        assert result is None

    def test_check_tracktotal_presence_always(self, mocker):
        album = Album("", [Track("1.flac"), Track("2.flac", {"tracknumber": ["1"], "tracktotal": ["1"]})])

        ctx = Context()
        ctx.config["checks"] = {"tracktotal_presence": {"policy": "always"}}
        result = CheckTrackTotalPresence(ctx).check(album)
        assert "tracktotal policy=ALWAYS but it is not on all tracks" in result.message
        assert not result.fixer

    def test_check_tracktotal_presence_consistent(self, mocker):
        album = Album("", [Track("1.flac"), Track("2.flac", {"tracknumber": ["1"], "tracktotal": ["1"]})])

        ctx = Context()
        ctx.config["checks"] = {"tracktotal_presence": {"policy": "consistent"}}
        ctx.library_root = Path("/path/to/library")
        result = CheckTrackTotalPresence(ctx).check(album)
        assert "tracktotal policy=CONSISTENT but it is on some tracks and not others" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove tag tracktotal from all tracks"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch("albums.checks.base_check_total_tag.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[1].filename, [("tracktotal", None)])

    def test_check_tracktotal_presence_never(self, mocker):
        album = Album(
            "", [Track("1.flac", {"tracknumber": ["1"], "tracktotal": ["2"]}), Track("2.flac", {"tracknumber": ["2"], "tracktotal": ["2"]})]
        )

        ctx = Context()
        ctx.config["checks"] = {"tracktotal_presence": {"policy": "never"}}
        ctx.library_root = Path("/path/to/library")
        result = CheckTrackTotalPresence(ctx).check(album)
        assert "tracktotal policy=NEVER but it appears on tracks" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove tag tracktotal from all tracks"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch("albums.checks.base_check_total_tag.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 2
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[1].filename, [("tracktotal", None)])

    def test_check_tracktotal_presence_total_without_index(self, mocker):
        album = Album("", [Track("1.flac"), Track("2.flac", {"tracktotal": ["1"]})])

        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        ctx.config["checks"] = {"tracktotal_presence": {"policy": "always"}}
        result = CheckTrackTotalPresence(ctx).check(album)
        assert "tracktotal appears on tracks without tracknumber" in result.message
        assert not result.fixer  # manual fix is required if we can't just remove the tracktotal

        # if policy is never there is an automatic fix, remove the total
        ctx.config["checks"] = {"tracktotal_presence": {"policy": "never"}}
        result = CheckTrackTotalPresence(ctx).check(album)
        assert "tracktotal appears on tracks without tracknumber" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove tag tracktotal from all tracks"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_tags = mocker.patch("albums.checks.base_check_total_tag.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[1].filename, [("tracktotal", None)])
