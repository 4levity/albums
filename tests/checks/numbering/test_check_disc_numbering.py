import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.numbering.check_disc_numbering import CheckDiscNumbering
from albums.database.models import AlbumEntity, TrackEntity, TrackTagEntity
from albums.tagger.folder import AlbumTagger, TaggerFile
from albums.types import BasicTag


class TestCheckDiscNumbering:
    def test_discnumbering_ok(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(filename="1-01.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")]),
                TrackEntity(filename="1-02.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")]),
                TrackEntity(filename="2-01.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2")]),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert result is None

    def test_disc_numbering_ok_total(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1-01.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="1-02.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="2-01.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                ),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert result is None

    def test_check_disctotal_policy(self):
        # just make sure config works, policy helper has its own tests for fixer
        album_with_all = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="1")]
                ),
                TrackEntity(
                    filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="1")]
                ),
            ],
        )
        album_with_none = AlbumEntity(path="", tracks=[TrackEntity(filename="1.flac"), TrackEntity(filename="2.flac")])
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
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1-01.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="1-02.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="2-01.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="3")]
                ),
                TrackEntity(
                    filename="2-02.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                ),
            ],
        )

        result = CheckDiscNumbering(Context()).check(album)
        assert "inconsistent disc total" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc total = 2", ">> Remove disc total tag"]
        assert result.fixer.option_automatic_index == 0
        mock_set_basic_tags = mocker.patch.object(AlbumTagger, "set_basic_tags")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_set_basic_tags.call_args_list == [call(Path(album.path) / album.tracks[2].filename, [(BasicTag.DISCTOTAL, "2")])]

    def test_check_disctotal_inconsistent(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1-01.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="1-02.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="2-01.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="3"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="3")]
                ),
                TrackEntity(
                    filename="2-02.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="3"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="3")]
                ),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "inconsistent disc total" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Set disc total = 2", ">> Set disc total = 3", ">> Remove disc total tag"]
        assert result.fixer.option_automatic_index is None

    def test_check_discnumber_inconsistent(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(filename="1-1.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")]),
                TrackEntity(filename="1-2.flac"),
                TrackEntity(filename="2-1.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2")]),
                TrackEntity(filename="2-2.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2")]),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "some tracks have disc number and some do not" in result.message
        assert result.fixer is None

    def test_check_discnumber_missing_disc(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(filename="1-1.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")]),
                TrackEntity(filename="1-2.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")]),
                TrackEntity(filename="3-1.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="3")]),
                TrackEntity(filename="3-2.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="3")]),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "missing disc numbers: {2}" in result.message
        assert result.fixer is None

    def test_check_discnumber_unexpected_disc(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1-1.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="2-1.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                ),
                TrackEntity(
                    filename="3-1.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="3"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                ),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert "unexpected disc numbers: {3}" in result.message
        assert result.fixer is None

    def test_check_missing_disc_with_discs_in_separate_folders_default_true(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1-1.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                )
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
        assert result is None

    def test_check_missing_disc_with_discs_in_separate_folders_false(self):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1-1.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2")]
                )
            ],
        )
        ctx = Context()
        ctx.config.checks = {CheckDiscNumbering.name: {"discs_in_separate_folders": False}}
        result = CheckDiscNumbering(ctx).check(album)
        assert "album only has a single disc 1 of 2" in result.message
        assert result.fixer is None

    def test_check_discnumbering_remove_redundant(self, mocker):
        album = AlbumEntity(
            path="foo",
            tracks=[
                TrackEntity(filename="1-01.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")]),
                TrackEntity(filename="1-02.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1")]),
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

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_tag = mocker.patch.object(tagger, "set_tag")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_set_tag.call_count == 2
        assert mock_set_tag.call_args_list == [call(BasicTag.DISCNUMBER, None), call(BasicTag.DISCNUMBER, None)]

    def test_check_discnumbering_remove_redundant_total(self, mocker):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1-01.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="1")]
                ),
                TrackEntity(
                    filename="1-02.flac", tags=[TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"), TrackTagEntity(tag=BasicTag.DISCTOTAL, value="1")]
                ),
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

        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_set_tag = mocker.patch.object(tagger, "set_tag")

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_set_tag.call_count == 4
        assert mock_set_tag.call_args_list == [
            call(BasicTag.DISCNUMBER, None),
            call(BasicTag.DISCTOTAL, None),
            call(BasicTag.DISCNUMBER, None),
            call(BasicTag.DISCTOTAL, None),
        ]
