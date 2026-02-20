from pathlib import Path

from albums.app import Context
from albums.checks.numbering.check_zero_pad_numbers import CheckZeroPadNumbers
from albums.types import Album, Track


class TestZeroPadNumbers:
    def test_check_pad_track_if_needed(self, mocker):
        album = Album(
            "",
            [
                Track("1.flac", {"tracknumber": ["1"]}),
                Track("2.flac", {"tracknumber": ["2"]}),
                Track("3.flac", {"tracknumber": ["3"]}),
                Track("4.flac", {"tracknumber": ["4"]}),
                Track("5.flac", {"tracknumber": ["5"]}),
                Track("6.flac", {"tracknumber": ["6"]}),
                Track("7.flac", {"tracknumber": ["7"]}),
                Track("8.flac", {"tracknumber": ["8"]}),
                Track("9.flac", {"tracknumber": ["9"]}),
                Track("10.flac", {"tracknumber": ["10"]}),
            ],
        )
        ctx = Context()
        ctx.config.checks = {
            "zero-pad-numbers": {
                "enabled": True,
                "tracknumber_pad": "if_needed",
            }
        }
        result = CheckZeroPadNumbers(ctx).check(album)
        assert "incorrect zero padding for 9 track numbers" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Apply policy: tracknumber pad IF_NEEDED"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch("albums.checks.numbering.check_zero_pad_numbers.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 9
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[8].filename, [("tracknumber", "09")])

    def test_check_pad_remove_all_unnecessary(self, mocker):
        album = Album(
            "",
            [
                Track("1.flac", {"tracknumber": ["01"], "tracktotal": ["02"], "discnumber": ["01"], "disctotal": ["01"]}),
                Track("2.flac", {"tracknumber": ["02"], "tracktotal": ["02"], "discnumber": ["01"], "disctotal": ["01"]}),
            ],
        )
        ctx = Context()
        ctx.config.checks = {
            "zero-pad-numbers": {
                "enabled": True,
                "tracknumber_pad": "if_needed",
                "tracktotal_pad": "never",
                "discnumber_pad": "if_needed",
                "disctotal_pad": "never",
            }
        }
        result = CheckZeroPadNumbers(ctx).check(album)
        assert "incorrect zero padding for 2 disc numbers and 2 disc totals and 2 track numbers and 2 track totals" in result.message
        assert result.fixer
        assert result.fixer.options == [
            ">> Apply policy: discnumber pad IF_NEEDED and disctotal pad NEVER and tracknumber pad IF_NEEDED and tracktotal pad NEVER"
        ]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch("albums.checks.numbering.check_zero_pad_numbers.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 2
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[1].filename,
            [("tracknumber", "2"), ("tracktotal", "2"), ("discnumber", "1"), ("disctotal", "1")],
        )

    def test_check_pad_tracknumber_and_discnumber_if_needed(self, mocker):
        album = Album("a")
        for discnumber in range(1, 11):
            for tracknumber in range(1, 11):
                album.tracks.append(Track(f"{discnumber}-{tracknumber}.flac", {"discnumber": [str(discnumber)], "tracknumber": [str(tracknumber)]}))
        assert len(album.tracks) == 100
        ctx = Context()
        ctx.config.checks = {
            "zero-pad-numbers": {
                "enabled": True,
                "tracknumber_pad": "if_needed",
                "discnumber_pad": "if_needed",
            }
        }
        result = CheckZeroPadNumbers(ctx).check(album)
        assert "incorrect zero padding for 90 disc numbers and 90 track numbers" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Apply policy: discnumber pad IF_NEEDED and tracknumber pad IF_NEEDED"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch("albums.checks.numbering.check_zero_pad_numbers.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 99  # all tracks on discs 1-9 get discnumber padded, 9 tracks on disc 10 get tracknumber padded
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[98].filename, [("tracknumber", "09")])

    def test_check_pad_two_digit_minimum(self, mocker):
        album = Album(
            "",
            [
                Track("1.flac", {"tracknumber": ["01"], "tracktotal": ["2"], "discnumber": ["01"], "disctotal": ["1"]}),
                Track("2.flac", {"tracknumber": ["2"], "tracktotal": ["2"], "discnumber": ["1"], "disctotal": ["1"]}),
            ],
        )
        ctx = Context()
        ctx.config.checks = {
            "zero-pad-numbers": {
                "enabled": True,
                "tracknumber_pad": "TWO_DIGIT_MINIMUM",
                "tracktotal_pad": "TWO_DIGIT_MINIMUM",
                "discnumber_pad": "two_digit_minimum",
                "disctotal_pad": "two_digit_minimum",
            }
        }
        result = CheckZeroPadNumbers(ctx).check(album)
        assert "incorrect zero padding for 1 disc numbers and 2 disc totals and 1 track numbers and 2 track totals" in result.message
        assert result.fixer
        assert result.fixer.options == [
            ">> Apply policy: discnumber pad TWO_DIGIT_MINIMUM and disctotal pad TWO_DIGIT_MINIMUM and tracknumber pad TWO_DIGIT_MINIMUM and tracktotal pad TWO_DIGIT_MINIMUM"
        ]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch("albums.checks.numbering.check_zero_pad_numbers.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 2
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[1].filename,
            [("tracknumber", "02"), ("tracktotal", "02"), ("discnumber", "01"), ("disctotal", "01")],
        )

    def test_check_pad_with_id3(self, mocker):
        album = Album("", [Track("1.mp3", {"tracknumber": ["01"], "tracktotal": ["2"]})])
        ctx = Context()
        ctx.config.checks = {
            "zero-pad-numbers": {
                "enabled": True,
                "tracknumber_pad": "if_needed",
                "tracktotal_pad": "never",
                "discnumber_pad": "never",
                "disctotal_pad": "never",
            }
        }
        result = CheckZeroPadNumbers(ctx).check(album)
        assert "incorrect zero padding for 1 track numbers" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Apply policy: tracknumber pad IF_NEEDED"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.table

        # automatically fixed
        mock_set_basic_tags = mocker.patch("albums.checks.numbering.check_zero_pad_numbers.set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[0].filename, [("tracknumber", "1")])
