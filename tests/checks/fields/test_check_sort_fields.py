from unittest.mock import call

from albums.app import Context
from albums.checks.base_check_sort import OPTION_GENERATED_VALUE, make_sort_value
from albums.checks.check_types import FixResult
from albums.checks.fields.check_album_artist_sort import CheckAlbumArtistSort
from albums.checks.fields.check_album_sort import CheckAlbumSort
from albums.checks.fields.check_artist_sort import CheckArtistSort
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField

from ...helpers import MockTagger, apply_automatic_fix


def _album(*tags):
    return Album(path="album", tracks=[Track(filename=f"{n}.flac", tag=tag) for n, tag in enumerate(tags, 1)])


def _run(check_cls, album, presence="consistent"):
    ctx = Context()
    ctx.config.checks[check_cls.name]["presence"] = presence
    return check_cls(ctx).check(album)


def _fix(mocker, result, option: str | None = None):
    """Set up a mock tagger and apply a fix (the automatic option when option is None); return the fix result and the mock set_field."""
    tagger = MockTagger()
    mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
    mock_tagger_open.return_value.__enter__.return_value = tagger
    mock_set_field = mocker.patch.object(tagger, "set_field")
    fix_result = apply_automatic_fix(result) if option is None else result.fixer.fix(option)
    return fix_result, mock_set_field


class TestMakeSortValue:
    def test_single_value_with_article(self):
        assert make_sort_value(["The Beatles"]) == "Beatles, The"

    def test_single_value_without_article(self):
        assert make_sort_value(["Beatles"]) == "Beatles"

    def test_multiple_values_are_concatenated(self):
        assert make_sort_value(["Alice", "Bob"]) == "Alice / Bob"

    def test_multiple_values_with_leading_article(self):
        assert make_sort_value(["The Beatles", "Wings"]) == "Beatles, The / Wings"


class TestAlbumSort:
    def test_must_pass_checks(self):
        assert CheckAlbumSort.must_pass_checks == {"album"}

    def test_ok_value_is_generated_value(self):
        album = _album(
            {BasicField.ALBUM: "The Beatles", BasicField.ALBUMSORT: "Beatles, The"},
            {BasicField.ALBUM: "The Beatles", BasicField.ALBUMSORT: "Beatles, The"},
        )
        assert _run(CheckAlbumSort, album) is None

    def test_ok_missing_and_no_leading_article(self):
        album = _album({BasicField.ALBUM: "Beatles"}, {BasicField.ALBUM: "Beatles"})
        assert _run(CheckAlbumSort, album) is None

    def test_consistent_missing_with_leading_article_sets_generated_value(self, mocker):
        album = _album({BasicField.ALBUM: "The Beatles"}, {BasicField.ALBUM: "The Beatles"})
        result = _run(CheckAlbumSort, album)
        assert "album sort order is not set but it should be" in result.message
        assert result.fixer
        assert result.fixer.options == [OPTION_GENERATED_VALUE, ">> Remove album sort order from all tracks"]
        assert not result.fixer.option_free_text
        assert result.fixer.table

        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ALBUMSORT, "Beatles, The"), call(BasicField.ALBUMSORT, "Beatles, The")]

    def test_always_missing_sets_generated_value(self, mocker):
        album = _album({BasicField.ALBUM: "The Beatles"}, {BasicField.ALBUM: "The Beatles"})
        result = _run(CheckAlbumSort, album, presence="always")
        assert "albumsort policy=ALWAYS but it is not set to the generated value on all tracks" in result.message
        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ALBUMSORT, "Beatles, The"), call(BasicField.ALBUMSORT, "Beatles, The")]

    def test_always_wrong_value_is_fixed(self, mocker):
        # the sort value is the same as the display name (a common incorrect value)
        album = _album(
            {BasicField.ALBUM: "The Beatles", BasicField.ALBUMSORT: "The Beatles"},
            {BasicField.ALBUM: "The Beatles", BasicField.ALBUMSORT: "The Beatles"},
        )
        result = _run(CheckAlbumSort, album, presence="always")
        assert "albumsort policy=ALWAYS but it is not set to the generated value on all tracks" in result.message
        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ALBUMSORT, "Beatles, The"), call(BasicField.ALBUMSORT, "Beatles, The")]

    def test_consistent_wrong_value_is_fixed(self, mocker):
        album = _album(
            {BasicField.ALBUM: "The Beatles", BasicField.ALBUMSORT: "The Beatles"},
            {BasicField.ALBUM: "The Beatles", BasicField.ALBUMSORT: "The Beatles"},
        )
        result = _run(CheckAlbumSort, album)
        assert "incorrect album sort order on 2 tracks" in result.message
        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ALBUMSORT, "Beatles, The"), call(BasicField.ALBUMSORT, "Beatles, The")]

    def test_consistent_mixed_presence_is_fixed(self, mocker):
        album = _album({BasicField.ALBUM: "The Beatles", BasicField.ALBUMSORT: "Beatles, The"}, {BasicField.ALBUM: "The Beatles"})
        result = _run(CheckAlbumSort, album)
        assert "albumsort policy=CONSISTENT but it is on some tracks and not others" in result.message
        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        # only the track without the field is changed
        assert mock_set_field.call_args_list == [call(BasicField.ALBUMSORT, "Beatles, The")]

    def test_never_removes_field(self, mocker):
        album = _album({BasicField.ALBUM: "Beatles", BasicField.ALBUMSORT: "Beatles"}, {BasicField.ALBUM: "Beatles", BasicField.ALBUMSORT: "Beatles"})
        result = _run(CheckAlbumSort, album, presence="never")
        assert "albumsort policy=NEVER but it appears on tracks" in result.message
        assert result.fixer.options == [">> Remove album sort order from all tracks"]
        fix_result, mock_set_field = _fix(mocker, result, result.fixer.options[0])
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ALBUMSORT, None), call(BasicField.ALBUMSORT, None)]

    def test_never_ok_when_absent(self):
        album = _album({BasicField.ALBUM: "Beatles"}, {BasicField.ALBUM: "Beatles"})
        assert _run(CheckAlbumSort, album, presence="never") is None

    def test_sort_without_source_is_removed(self, mocker):
        album = _album({BasicField.ALBUMSORT: "Beatles"}, {BasicField.ALBUMSORT: "Beatles"})
        result = _run(CheckAlbumSort, album)
        assert "albumsort appears on tracks without album" in result.message
        assert result.fixer.options == [">> Remove album sort order from all tracks"]
        fix_result, mock_set_field = _fix(mocker, result, result.fixer.options[0])
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ALBUMSORT, None), call(BasicField.ALBUMSORT, None)]

    def test_ok_when_source_and_sort_are_both_absent(self):
        album = _album({}, {})
        assert _run(CheckAlbumSort, album) is None

    def test_multi_value_source_is_concatenated(self, mocker):
        album = _album({BasicField.ALBUM: ["The Beatles", "Wings"]}, {BasicField.ALBUM: "Alice"})
        result = _run(CheckAlbumSort, album)
        assert "album sort order is not set but it should be" in result.message
        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ALBUMSORT, "Beatles, The / Wings"), call(BasicField.ALBUMSORT, "Alice")]

    def test_fix_remove_option(self, mocker):
        album = _album(
            {BasicField.ALBUM: "The Beatles", BasicField.ALBUMSORT: "The Beatles"},
            {BasicField.ALBUM: "The Beatles", BasicField.ALBUMSORT: "The Beatles"},
        )
        result = _run(CheckAlbumSort, album)
        remove_option = ">> Remove album sort order from all tracks"
        fix_result, mock_set_field = _fix(mocker, result, remove_option)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ALBUMSORT, None), call(BasicField.ALBUMSORT, None)]


class TestAlbumArtistSort:
    def test_must_pass_checks(self):
        assert CheckAlbumArtistSort.must_pass_checks == {"album-artist"}

    def test_ok_value_is_generated_value(self):
        album = _album(
            {BasicField.ALBUMARTIST: "The Beatles", BasicField.ALBUMARTISTSORT: "Beatles, The"},
            {BasicField.ALBUMARTIST: "The Beatles", BasicField.ALBUMARTISTSORT: "Beatles, The"},
        )
        assert _run(CheckAlbumArtistSort, album) is None

    def test_ok_missing_and_no_leading_article(self):
        album = _album({BasicField.ALBUMARTIST: "Beatles"}, {BasicField.ALBUMARTIST: "Beatles"})
        assert _run(CheckAlbumArtistSort, album) is None

    def test_missing_source_is_ok_when_sort_is_absent(self):
        # no albumartist (e.g. redundant with artist), and no albumartistsort: nothing to do;
        # the sort value is never generated from artist
        album = _album({BasicField.ARTIST: "The Beatles"}, {BasicField.ARTIST: "The Beatles"})
        assert _run(CheckAlbumArtistSort, album) is None

    def test_sort_without_albumartist_is_removed(self, mocker):
        album = _album(
            {BasicField.ARTIST: "The Beatles", BasicField.ALBUMARTISTSORT: "Beatles"},
            {BasicField.ARTIST: "The Beatles", BasicField.ALBUMARTISTSORT: "Beatles"},
        )
        result = _run(CheckAlbumArtistSort, album)
        assert "albumartistsort appears on tracks without albumartist" in result.message
        assert result.fixer.options == [">> Remove album-artist sort order from all tracks"]
        fix_result, mock_set_field = _fix(mocker, result, result.fixer.options[0])
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ALBUMARTISTSORT, None), call(BasicField.ALBUMARTISTSORT, None)]

    def test_consistent_missing_with_leading_article_sets_generated_value(self, mocker):
        album = _album({BasicField.ALBUMARTIST: "The Beatles"}, {BasicField.ALBUMARTIST: "The Beatles"})
        result = _run(CheckAlbumArtistSort, album)
        assert "album-artist sort order is not set but it should be" in result.message
        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ALBUMARTISTSORT, "Beatles, The"), call(BasicField.ALBUMARTISTSORT, "Beatles, The")]

    def test_always_missing_source_is_not_fixable(self):
        # the policy wants the field on all tracks, but with no albumartist there is nothing to generate it from
        album = _album({BasicField.ARTIST: "The Beatles"}, {BasicField.ARTIST: "The Beatles"})
        result = _run(CheckAlbumArtistSort, album, presence="always")
        assert "albumartistsort policy=ALWAYS but albumartist is not on all tracks" in result.message
        assert result.fixer is None


class TestArtistSort:
    def test_must_pass_checks(self):
        assert CheckArtistSort.must_pass_checks == {"artist"}

    def test_ok_value_is_generated_value(self):
        album = _album(
            {BasicField.ARTIST: "The Beatles", BasicField.ARTISTSORT: "Beatles, The"},
            {BasicField.ARTIST: "Alice", BasicField.ARTISTSORT: "Alice"},
        )
        assert _run(CheckArtistSort, album) is None

    def test_ok_missing_and_no_leading_article(self):
        album = _album({BasicField.ARTIST: "Alice"}, {BasicField.ARTIST: "Bob"})
        assert _run(CheckArtistSort, album) is None

    def test_consistent_missing_with_leading_article_sets_generated_value_per_track(self, mocker):
        album = _album({BasicField.ARTIST: "The Beatles"}, {BasicField.ARTIST: "Alice"})
        result = _run(CheckArtistSort, album)
        assert "artist sort order is not set but it should be" in result.message
        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ARTISTSORT, "Beatles, The"), call(BasicField.ARTISTSORT, "Alice")]

    def test_always_missing_sets_generated_value(self, mocker):
        album = _album({BasicField.ARTIST: "The Beatles"}, {BasicField.ARTIST: "Alice"})
        result = _run(CheckArtistSort, album, presence="always")
        assert "artistsort policy=ALWAYS but it is not set to the generated value on all tracks" in result.message
        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ARTISTSORT, "Beatles, The"), call(BasicField.ARTISTSORT, "Alice")]

    def test_consistent_wrong_value_is_fixed(self, mocker):
        # the sort value is the same as the display name (a common incorrect value)
        album = _album(
            {BasicField.ARTIST: "The Beatles", BasicField.ARTISTSORT: "The Beatles"},
            {BasicField.ARTIST: "Alice", BasicField.ARTISTSORT: "Alice"},
        )
        result = _run(CheckArtistSort, album)
        assert "incorrect artist sort order on 1 track" in result.message
        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        # only the wrong track is changed
        assert mock_set_field.call_args_list == [call(BasicField.ARTISTSORT, "Beatles, The")]

    def test_consistent_mixed_presence_is_fixed(self, mocker):
        album = _album({BasicField.ARTIST: "The Beatles", BasicField.ARTISTSORT: "Beatles, The"}, {BasicField.ARTIST: "Alice"})
        result = _run(CheckArtistSort, album)
        assert "artistsort policy=CONSISTENT but it is on some tracks and not others" in result.message
        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ARTISTSORT, "Alice")]

    def test_never_removes_field(self, mocker):
        album = _album({BasicField.ARTIST: "The Beatles", BasicField.ARTISTSORT: "Beatles"}, {BasicField.ARTIST: "Alice"})
        result = _run(CheckArtistSort, album, presence="never")
        assert "artistsort policy=NEVER but it appears on tracks" in result.message
        fix_result, mock_set_field = _fix(mocker, result, result.fixer.options[0])
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ARTISTSORT, None)]

    def test_never_ok_when_absent(self):
        album = _album({BasicField.ARTIST: "Alice"}, {BasicField.ARTIST: "Bob"})
        assert _run(CheckArtistSort, album, presence="never") is None

    def test_sort_without_artist_is_removed_when_on_all_tracks(self, mocker):
        # the field is present on a track without a source value, so it can't be correct there and must be removed
        album = _album({BasicField.ARTIST: "The Beatles", BasicField.ARTISTSORT: "Beatles"}, {BasicField.ARTISTSORT: "X"})
        result = _run(CheckArtistSort, album)
        assert "artistsort appears on tracks without artist" in result.message
        fix_result, mock_set_field = _fix(mocker, result, result.fixer.options[0])
        assert fix_result == FixResult.CHANGED_ALBUM
        # removed from all tracks, including the one that had the correct value
        assert mock_set_field.call_args_list == [call(BasicField.ARTISTSORT, None), call(BasicField.ARTISTSORT, None)]

    def test_mixed_presence_with_missing_artist_must_be_removed(self, mocker):
        # the value can't be generated for every track, so the field can't be set on all of them,
        # and a fix that would leave it on some tracks and not others is not acceptable
        album = _album(
            {BasicField.ARTIST: "The Beatles", BasicField.ARTISTSORT: "Beatles"},
            {BasicField.ARTIST: "Alice"},
            {},
        )
        result = _run(CheckArtistSort, album)
        assert "artistsort policy=CONSISTENT but it can't be set on all tracks because artist is not on all tracks" in result.message
        assert result.fixer.options == [">> Remove artist sort order from all tracks"]
        fix_result, mock_set_field = _fix(mocker, result, result.fixer.options[0])
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ARTISTSORT, None)]

    def test_sort_without_artist_is_removed(self, mocker):
        album = _album({BasicField.ARTISTSORT: "X"}, {BasicField.ARTISTSORT: "Y"})
        result = _run(CheckArtistSort, album)
        assert "artistsort appears on tracks without artist" in result.message
        fix_result, mock_set_field = _fix(mocker, result, result.fixer.options[0])
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ARTISTSORT, None), call(BasicField.ARTISTSORT, None)]

    def test_ok_when_artist_and_sort_are_both_absent(self):
        album = _album({}, {})
        assert _run(CheckArtistSort, album) is None

    def test_always_with_missing_artist_is_not_fixable(self):
        album = _album({BasicField.ARTIST: "The Beatles", BasicField.ARTISTSORT: "Beatles"}, {})
        result = _run(CheckArtistSort, album, presence="always")
        assert "artistsort policy=ALWAYS but artist is not on all tracks" in result.message
        assert result.fixer is None

    def test_multi_value_artist_is_concatenated(self, mocker):
        album = _album({BasicField.ARTIST: ["The Beatles", "Wings"]}, {BasicField.ARTIST: "Alice"})
        result = _run(CheckArtistSort, album)
        assert "artist sort order is not set but it should be" in result.message
        fix_result, mock_set_field = _fix(mocker, result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.ARTISTSORT, "Beatles, The / Wings"), call(BasicField.ARTISTSORT, "Alice")]
