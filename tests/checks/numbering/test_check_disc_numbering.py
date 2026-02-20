import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.numbering.check_disc_numbering import CheckDiscNumbering
from albums.types import Album, Track


class TestCheckDiscNumbering:
    def test_disc_numbering_ok(self):
        album = Album(
            "",
            [
                Track("1-01.flac", {"discnumber": ["1"]}),
                Track("1-02.flac", {"discnumber": ["1"]}),
                Track("2-01.flac", {"discnumber": ["2"]}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert result is None

    def test_disc_numbering_ok_total(self):
        album = Album(
            "",
            [
                Track("1-01.flac", {"discnumber": ["1"], "disctotal": ["2"]}),
                Track("1-02.flac", {"discnumber": ["1"], "disctotal": ["2"]}),
                Track("2-01.flac", {"discnumber": ["2"], "disctotal": ["2"]}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert result is None

    def test_check_disctotal_policy(self):
        # just make sure config works, policy helper has its own tests for fixer
        album_with_all = Album(
            "", [Track("1.flac", {"discnumber": ["1"], "disctotal": ["1"]}), Track("2.flac", {"discnumber": ["1"], "disctotal": ["1"]})]
        )
        album_with_none = Album("", [Track("1.flac"), Track("2.flac")])
        ctx = Context()
        ctx.config.checks = {CheckDiscNumbering.name: {"disctotal_policy": "consistent"}}  # default
        check = CheckDiscNumbering(ctx)
        result = check.check(album_with_all)
        assert result is None
        result = check.check(album_with_none)
        assert result is None

        ctx.config.checks = {CheckDiscNumbering.name: {"disctotal_policy": "always"}}
        check = CheckDiscNumbering(ctx)
        assert check.check(album_with_all) is None
        result = check.check(album_with_none)
        assert result
        assert "disctotal policy=ALWAYS but it is not on all tracks" in result.message

        ctx.config.checks = {CheckDiscNumbering.name: {"disctotal_policy": "never"}}
        check = CheckDiscNumbering(ctx)
        assert check.check(album_with_none) is None
        result = check.check(album_with_all)
        assert result
        assert "disctotal policy=NEVER but it appears on tracks" in result.message

    def test_check_disctotal_inconsistent_auto_fixable(self, mocker):
        album = Album(
            "",
            [
                Track("1-01.flac", {"discnumber": ["1"], "disctotal": ["2"]}),
                Track("1-02.flac", {"discnumber": ["1"], "disctotal": ["2"]}),
                Track("2-01.flac", {"discnumber": ["2"], "disctotal": ["3"]}),
                Track("2-02.flac", {"discnumber": ["2"], "disctotal": ["2"]}),
            ],
        )

        result = CheckDiscNumbering(Context()).check(album)
        assert "inconsistent disc total" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc total = 2", ">> Remove disc total tag"]
        assert result.fixer.option_automatic_index == 0
        mock_set_basic_tags = mocker.patch("albums.checks.numbering.check_disc_numbering.set_basic_tags")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_set_basic_tags.call_args_list == [call(Path(album.path) / album.tracks[2].filename, [("disctotal", "2")])]

    def test_check_disctotal_inconsistent(self):
        album = Album(
            "",
            [
                Track("1-01.flac", {"discnumber": ["1"], "disctotal": ["2"]}),
                Track("1-02.flac", {"discnumber": ["1"], "disctotal": ["2"]}),
                Track("2-01.flac", {"discnumber": ["3"], "disctotal": ["3"]}),
                Track("2-02.flac", {"discnumber": ["3"], "disctotal": ["3"]}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "inconsistent disc total" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc total = 2", ">> Set disc total = 3", ">> Remove disc total tag"]
        assert result.fixer.option_automatic_index is None

    def test_check_discnumber_inconsistent(self):
        album = Album(
            "foo" + os.sep,
            [
                Track("1-1.flac", {"discnumber": ["1"]}),
                Track("1-2.flac"),
                Track("2-1.flac", {"discnumber": ["2"]}),
                Track("2-2.flac", {"discnumber": ["2"]}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "some tracks have disc number and some do not" in result.message
        assert result.fixer is None

    def test_check_discnumber_missing_disc(self):
        album = Album(
            "foo" + os.sep,
            [
                Track("1-1.flac", {"discnumber": ["1"]}),
                Track("1-2.flac", {"discnumber": ["1"]}),
                Track("3-1.flac", {"discnumber": ["3"]}),
                Track("3-2.flac", {"discnumber": ["3"]}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "missing disc numbers: {2}" in result.message
        assert result.fixer is None

    def test_check_discnumber_unexpected_disc(self):
        album = Album(
            "foo" + os.sep,
            [
                Track("1-1.flac", {"discnumber": ["1"], "disctotal": ["2"]}),
                Track("2-1.flac", {"discnumber": ["2"], "disctotal": ["2"]}),
                Track("3-1.flac", {"discnumber": ["3"], "disctotal": ["2"]}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "unexpected disc numbers: {3}" in result.message
        assert result.fixer is None

    def test_check_missing_disc_with_discs_in_separate_folders_default_true(self):
        album = Album(
            "foo" + os.sep,
            [Track("1-1.flac", {"discnumber": ["1"], "disctotal": ["2"]})],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert result is None

    def test_check_missing_disc_with_discs_in_separate_folders_false(self):
        album = Album(
            "foo" + os.sep,
            [Track("1-1.flac", {"discnumber": ["1"], "disctotal": ["2"]})],
        )
        ctx = Context()
        ctx.config.checks = {CheckDiscNumbering.name: {"discs_in_separate_folders": False}}
        result = CheckDiscNumbering(ctx).check(album)
        assert "album only has a single disc 1 of 2" in result.message
        assert result.fixer is None
