import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.check_types import FixResult
from albums.checks.numbering.check_disc_numbering import CheckDiscNumbering
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField

from ...helpers import MockTagger


class TestCheckDiscNumbering:
    def test_discnumbering_ok(self):
        album = Album(
            path="",
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="1-02.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="2-01.flac", tag={BasicField.DISCNUMBER: "2"}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert result is None

    def test_disc_numbering_ok_total(self):
        album = Album(
            path="",
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="1-02.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="2-01.flac", tag={BasicField.DISCNUMBER: "2", BasicField.DISCTOTAL: "2"}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert result is None

    def test_check_disctotal_policy(self):
        # just make sure config works, policy helper has its own tests for fixer
        album_with_all = Album(
            path="",
            tracks=[
                Track(filename="1.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "1"}),
                Track(filename="2.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "1"}),
            ],
        )
        album_with_none = Album(path="", tracks=[Track(filename="1.flac"), Track(filename="2.flac")])
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
            path="",
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="1-02.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="2-01.flac", tag={BasicField.DISCNUMBER: "2", BasicField.DISCTOTAL: "3"}),
                Track(filename="2-02.flac", tag={BasicField.DISCNUMBER: "2", BasicField.DISCTOTAL: "2"}),
            ],
        )

        result = CheckDiscNumbering(Context()).check(album)
        assert "inconsistent disc total" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc total = 2", ">> Remove disc total field"]
        assert result.fixer.option_automatic_index == 0
        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_set_basic_fields.call_args_list == [call(Path(album.path) / album.tracks[2].filename, [(BasicField.DISCTOTAL, "2")])]

    def test_check_disctotal_inconsistent(self):
        album = Album(
            path="",
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="1-02.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="2-01.flac", tag={BasicField.DISCNUMBER: "3", BasicField.DISCTOTAL: "3"}),
                Track(filename="2-02.flac", tag={BasicField.DISCNUMBER: "3", BasicField.DISCTOTAL: "3"}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "inconsistent disc total" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc total = 2", ">> Set disc total = 3", ">> Remove disc total field"]
        assert result.fixer.option_automatic_index is None

    def test_check_disctotal_inconsistent_free_text(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="1-02.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="2-01.flac", tag={BasicField.DISCNUMBER: "2", BasicField.DISCTOTAL: "3"}),
                Track(filename="2-02.flac", tag={BasicField.DISCNUMBER: "2", BasicField.DISCTOTAL: "2"}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "inconsistent disc total" in result.message
        assert result
        fixer = result.fixer
        assert fixer
        assert fixer.option_free_text

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        # a decimal value entered via ">> Enter Text" is used as the new disc total
        assert fixer.fix("3")
        assert mock_set_basic_fields.call_args_list == [
            call(Path(album.path) / album.tracks[0].filename, [(BasicField.DISCTOTAL, "3")]),
            call(Path(album.path) / album.tracks[1].filename, [(BasicField.DISCTOTAL, "3")]),
            call(Path(album.path) / album.tracks[3].filename, [(BasicField.DISCTOTAL, "3")]),
        ]
        # invalid free text does not crash and leaves the album unchanged
        assert fixer.fix("0") == FixResult.NO_CHANGE
        assert fixer.fix("banana") == FixResult.NO_CHANGE

    def test_check_discnumber_inconsistent_fix_from_filename(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-1.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="1-2.flac"),
                Track(filename="2-1.flac", tag={BasicField.DISCNUMBER: "2"}),
                Track(filename="2-2.flac", tag={BasicField.DISCNUMBER: "2"}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "some tracks have disc number and some do not (1 track without disc number)" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc number from filename on 1 track"]
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.option_free_text
        table = result.fixer.get_table()
        assert table is not None
        (headers, rows) = table
        assert headers == ["track", "filename", "discnumber", "disctotal"]
        assert [list(row)[2] for row in rows] == ["1", "", "2", "2"]
        assert [list(row)[3] for row in rows] == ["", "", "", ""]

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        # only the track without a disc number is fixed, from its filename
        assert mock_set_basic_fields.call_args_list == [call(Path("foo") / "1-2.flac", [(BasicField.DISCNUMBER, "1")])]

    def test_check_discnumber_inconsistent_set_from_filename_multidisc(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="1-02.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="2-01.flac", tag={BasicField.DISCTOTAL: "2"}),
                Track(filename="2-02.flac", tag={BasicField.DISCTOTAL: "2"}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "some tracks have disc number and some do not (2 tracks without disc number)" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc number from filename on 2 tracks"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_set_basic_fields.call_args_list == [
            call(Path("foo") / "2-01.flac", [(BasicField.DISCNUMBER, "2")]),
            call(Path("foo") / "2-02.flac", [(BasicField.DISCNUMBER, "2")]),
        ]

    def test_check_discnumber_inconsistent_filename_fix_not_beyond_total(self):
        # filenames suggest a disc beyond the disc total: offer the filename fix but not automatic
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="2-01.flac", tag={BasicField.DISCTOTAL: "2"}),
                Track(filename="3-01.flac", tag={BasicField.DISCTOTAL: "2"}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "some tracks have disc number and some do not (2 tracks without disc number)" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc number from filename on 2 tracks"]
        assert result.fixer.option_automatic_index is None

    def test_check_discnumber_inconsistent_filename_conflict(self, mocker):
        # the filename of a numbered track disagrees with its disc number, so filenames can't be trusted
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="2-01.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="02.flac"),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "some tracks have disc number and some do not (1 track without disc number)" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc number = 1 on 1 track", ">> Remove disc number 1 from all tracks"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_set_basic_fields.call_args_list == [call(Path("foo") / "02.flac", [(BasicField.DISCNUMBER, "1")])]

    def test_check_discnumber_inconsistent_fill_disc_1(self, mocker):
        # only disc 1 is present, no disc numbers in filenames: fill in or remove, filling is automatic by default
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="01.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="02.flac"),
                Track(filename="03.flac"),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "some tracks have disc number and some do not (2 tracks without disc number)" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc number = 1 on 2 tracks", ">> Remove disc number 1 from all tracks"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_set_basic_fields.call_args_list == [
            call(Path("foo") / "02.flac", [(BasicField.DISCNUMBER, "1")]),
            call(Path("foo") / "03.flac", [(BasicField.DISCNUMBER, "1")]),
        ]

    def test_check_discnumber_inconsistent_remove_disc_1(self, mocker):
        # only disc 1 is present and remove_redundant_discnumber: remove is offered first and automatic
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="01.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "1"}),
                Track(filename="02.flac", tag={BasicField.DISCTOTAL: "1"}),
                Track(filename="03.flac", tag={BasicField.DISCTOTAL: "1"}),
            ],
        )
        ctx = Context()
        ctx.config.checks[CheckDiscNumbering.name]["discs_in_separate_folders"] = False
        ctx.config.checks[CheckDiscNumbering.name]["remove_redundant_discnumber"] = True
        result = CheckDiscNumbering(ctx).check(album)
        assert "some tracks have disc number and some do not (2 tracks without disc number)" in result.message
        assert result.fixer
        assert result.fixer.options == [
            ">> Remove disc number 1 and disc total 1 from all tracks",
            ">> Set disc number = 1 on 2 tracks",
        ]
        assert result.fixer.option_automatic_index == 0

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_set_field.call_args_list == [
            call(BasicField.DISCNUMBER, None),
            call(BasicField.DISCTOTAL, None),
            call(BasicField.DISCTOTAL, None),
            call(BasicField.DISCTOTAL, None),
        ]

    def test_check_discnumber_inconsistent_fill_disc_1_from_filename(self, mocker):
        # only disc 1 is present and the filenames of the unnumbered tracks confirm disc 1
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="1-02.flac"),
                Track(filename="1-03.flac"),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "some tracks have disc number and some do not (2 tracks without disc number)" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc number = 1 on 2 tracks", ">> Remove disc number 1 from all tracks"]
        assert result.fixer.option_automatic_index == 0

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_set_basic_fields.call_args_list == [
            call(Path("foo") / "1-02.flac", [(BasicField.DISCNUMBER, "1")]),
            call(Path("foo") / "1-03.flac", [(BasicField.DISCNUMBER, "1")]),
        ]

    def test_check_discnumber_inconsistent_free_text(self, mocker):
        # no disc numbers can be guessed from filenames, but the user can enter one
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="01.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="02.flac", tag={BasicField.DISCNUMBER: "2"}),
                Track(filename="03.flac"),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "some tracks have disc number and some do not (1 track without disc number)" in result.message
        assert result.fixer
        assert result.fixer.options == []
        assert result.fixer.option_free_text
        assert result.fixer.option_automatic_index is None

        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        assert result.fixer.fix("2")
        assert mock_set_basic_fields.call_args_list == [call(Path("foo") / "03.flac", [(BasicField.DISCNUMBER, "2")])]
        # invalid free text does not crash and leaves the album unchanged
        assert result.fixer.fix("0") == FixResult.NO_CHANGE
        assert result.fixer.fix("banana") == FixResult.NO_CHANGE

    def test_check_discnumber_missing_disc(self):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-1.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="1-2.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="3-1.flac", tag={BasicField.DISCNUMBER: "3"}),
                Track(filename="3-2.flac", tag={BasicField.DISCNUMBER: "3"}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "missing disc number: {2}" in result.message
        assert result.fixer is None

    def test_check_discnumber_unexpected_disc(self):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-1.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"}),
                Track(filename="2-1.flac", tag={BasicField.DISCNUMBER: "2", BasicField.DISCTOTAL: "2"}),
                Track(filename="3-1.flac", tag={BasicField.DISCNUMBER: "3", BasicField.DISCTOTAL: "2"}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "unexpected disc number: {3}" in result.message
        assert result.fixer is None

    def test_check_missing_disc_with_discs_in_separate_folders_default_true(self):
        album = Album(
            path="foo" + os.sep,
            tracks=[Track(filename="1-1.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"})],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert result is None

    def test_check_missing_disc_with_discs_in_separate_folders_false(self):
        album = Album(
            path="foo" + os.sep,
            tracks=[Track(filename="1-1.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "2"})],
        )
        ctx = Context()
        ctx.config.checks = {CheckDiscNumbering.name: {"discs_in_separate_folders": False}}
        result = CheckDiscNumbering(ctx).check(album)
        assert "album only has a single disc 1 of 2" in result.message
        assert result.fixer is None

    def test_check_discnumbering_remove_redundant(self, mocker):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="1-02.flac", tag={BasicField.DISCNUMBER: "1"}),
            ],
        )
        ctx = Context()
        ctx.config.checks[CheckDiscNumbering.name]["discs_in_separate_folders"] = False
        ctx.config.checks[CheckDiscNumbering.name]["remove_redundant_discnumber"] = True
        result = CheckDiscNumbering(ctx).check(album)
        assert "redundant disc number" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove disc number 1 from all tracks"]
        assert result.fixer.option_automatic_index == 0

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_set_field.call_count == 2
        assert mock_set_field.call_args_list == [call(BasicField.DISCNUMBER, None), call(BasicField.DISCNUMBER, None)]

    def test_check_discnumbering_remove_redundant_total(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "1"}),
                Track(filename="1-02.flac", tag={BasicField.DISCNUMBER: "1", BasicField.DISCTOTAL: "1"}),
            ],
        )
        ctx = Context()
        ctx.config.checks[CheckDiscNumbering.name]["discs_in_separate_folders"] = False
        ctx.config.checks[CheckDiscNumbering.name]["remove_redundant_discnumber"] = True
        result = CheckDiscNumbering(ctx).check(album)
        assert "redundant disc number 1 and disc total 1" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove disc number 1 and disc total 1 from all tracks"]
        assert result.fixer.option_automatic_index == 0

        tagger = MockTagger()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_set_field.call_count == 4
        assert mock_set_field.call_args_list == [
            call(BasicField.DISCNUMBER, None),
            call(BasicField.DISCTOTAL, None),
            call(BasicField.DISCNUMBER, None),
            call(BasicField.DISCTOTAL, None),
        ]

    def test_check_discnumbering_redundant_offer_not_automatic(self):
        # discs in one folder and remove_redundant_discnumber is off: offer to remove redundant disc 1, but not automatic
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="1-02.flac", tag={BasicField.DISCNUMBER: "1"}),
            ],
        )
        ctx = Context()
        ctx.config.checks[CheckDiscNumbering.name]["discs_in_separate_folders"] = False
        result = CheckDiscNumbering(ctx).check(album)
        assert "redundant disc number" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove disc number 1 from all tracks"]
        assert result.fixer.option_automatic_index is None
        assert result.fixer.get_table() is not None

    def test_check_discnumbering_redundant_separate_folders_ok(self):
        # discs in separate folders: disc 1 might be part of a multi-disc set, so no issue
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1-01.flac", tag={BasicField.DISCNUMBER: "1"}),
                Track(filename="1-02.flac", tag={BasicField.DISCNUMBER: "1"}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert result is None
