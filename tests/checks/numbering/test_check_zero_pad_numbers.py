from pathlib import Path

from albums.app import Context
from albums.checks.numbering.check_zero_pad_numbers import CheckZeroPadNumbers
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import BasicTag
from albums.types import Album, Tag, Track


class TestZeroPadNumbers:
    def test_check_pad_track_if_needed(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicTag.TRACKNUMBER: "1"}),
                Track(filename="2.flac", tag={BasicTag.TRACKNUMBER: "2"}),
                Track(filename="3.flac", tag={BasicTag.TRACKNUMBER: "3"}),
                Track(filename="4.flac", tag={BasicTag.TRACKNUMBER: "4"}),
                Track(filename="5.flac", tag={BasicTag.TRACKNUMBER: "5"}),
                Track(filename="6.flac", tag={BasicTag.TRACKNUMBER: "6"}),
                Track(filename="7.flac", tag={BasicTag.TRACKNUMBER: "7"}),
                Track(filename="8.flac", tag={BasicTag.TRACKNUMBER: "8"}),
                Track(filename="9.flac", tag={BasicTag.TRACKNUMBER: "9"}),
                Track(filename="10.flac", tag={BasicTag.TRACKNUMBER: "10"}),
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
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 9
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[8].filename, [(BasicTag.TRACKNUMBER, "09")])

    def test_check_pad_remove_all_unnecessary(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    tag={
                        BasicTag.TRACKNUMBER: "01",
                        BasicTag.TRACKTOTAL: "02",
                        BasicTag.DISCNUMBER: "01",
                        BasicTag.DISCTOTAL: "01",
                    },
                ),
                Track(
                    filename="2.flac",
                    tag={
                        BasicTag.TRACKNUMBER: "02",
                        BasicTag.TRACKTOTAL: "02",
                        BasicTag.DISCNUMBER: "01",
                        BasicTag.DISCTOTAL: "01",
                    },
                ),
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
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 2
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[1].filename,
            [(BasicTag.TRACKNUMBER, "2"), (BasicTag.TRACKTOTAL, "2"), (BasicTag.DISCNUMBER, "1"), (BasicTag.DISCTOTAL, "1")],
        )

    def test_check_pad_tracknumber_and_discnumber_if_needed(self, mocker):
        album = Album(path="a")
        for discnumber in range(1, 11):
            for tracknumber in range(1, 11):
                album.tracks.append(
                    Track(
                        filename=f"{discnumber}-{tracknumber}.flac",
                        tags=[
                            Tag(tag=BasicTag.DISCNUMBER, value=str(discnumber)),
                            Tag(tag=BasicTag.TRACKNUMBER, value=str(tracknumber)),
                        ],
                    )
                )
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
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 99  # all tracks on discs 1-9 get discnumber padded, 9 tracks on disc 10 get tracknumber padded
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[98].filename, [(BasicTag.TRACKNUMBER, "09")])

    def test_check_pad_two_digit_minimum(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    tag={
                        BasicTag.TRACKNUMBER: "01",
                        BasicTag.TRACKTOTAL: "2",
                        BasicTag.DISCNUMBER: "01",
                        BasicTag.DISCTOTAL: "1",
                    },
                ),
                Track(
                    filename="2.flac",
                    tag={
                        BasicTag.TRACKNUMBER: "2",
                        BasicTag.TRACKTOTAL: "2",
                        BasicTag.DISCNUMBER: "1",
                        BasicTag.DISCTOTAL: "1",
                    },
                ),
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
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_count == 2
        assert mock_set_basic_tags.call_args.args == (
            Path(album.path) / album.tracks[1].filename,
            [(BasicTag.TRACKNUMBER, "02"), (BasicTag.TRACKTOTAL, "02"), (BasicTag.DISCNUMBER, "01"), (BasicTag.DISCTOTAL, "01")],
        )

    def test_check_pad_with_id3(self, mocker):
        album = Album(path="", tracks=[Track(filename="1.mp3", tag={BasicTag.TRACKNUMBER: "01", BasicTag.TRACKTOTAL: "2"})])
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
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_set_basic_tags.call_args.args == (Path(album.path) / album.tracks[0].filename, [(BasicTag.TRACKNUMBER, "1")])
