from pathlib import Path
from albums.app import Context
from albums.types import Album, Track
from albums.checks.check_disctotal_presence import CheckDiscTotalPresence
from albums.checks.check_tracktotal_presence import CheckTrackTotalPresence


class TestCheckTotalTags:
    def test_check_disctotal_presence_ok(self):
        album_with_all = Album("", [Track("1.flac", {"disctotal": ["1"]}), Track("2.flac", {"disctotal": ["1"]})])
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
        album_with_all = Album("", [Track("1.flac", {"tracktotal": ["1"]}), Track("2.flac", {"tracktotal": ["1"]})])
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
        album = Album("", [Track("1.flac"), Track("2.flac", {"tracktotal": ["1"]})])

        ctx = Context()
        ctx.config["checks"] = {"tracktotal_presence": {"policy": "always"}}
        result = CheckTrackTotalPresence(ctx).check(album)
        assert "tracktotal policy ALWAYS but not on all tracks" in result.message
        assert not result.fixer

    def test_check_tracktotal_presence_consistent(self, mocker):
        album = Album("", [Track("1.flac"), Track("2.flac", {"tracktotal": ["1"]})])

        ctx = Context()
        ctx.config["checks"] = {"tracktotal_presence": {"policy": "consistent"}}
        ctx.library_root = Path("/path/to/library")
        result = CheckTrackTotalPresence(ctx).check(album)
        assert "tracktotal policy CONSISTENT but it is on some tracks and not others" in result.message
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
