from unittest.mock import call

import pytest

from albums.app import Context
from albums.checks.check_types import CheckResult, FixResult
from albums.checks.fields.check_compilation import CheckCompilationField
from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField

from ...helpers import MockTagger, apply_automatic_fix

OPTION_SET_COMPILATION = ">> Set compilation flag on all tracks"
OPTION_REMOVE_COMPILATION = ">> Remove compilation flag from all tracks"


def _album(tracks: list[Track], path: str = "foo") -> Album:
    return Album(path=path, tracks=tracks)


def _check(album: Album, **check_config: object) -> CheckResult | None:
    ctx = Context()
    if check_config:
        ctx.config.checks = {CheckCompilationField.name: {"enabled": True, **check_config}}
    return CheckCompilationField(ctx).check(album)


class TestCheckCompilationField:
    def test_single_artist_no_flag_ok(self):
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob"}),
            ]
        )
        assert _check(album) is None

    def test_single_artist_flag_removed(self):
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be removed from all tracks (single artist: Bob)" in result.message
        assert result.fixer is not None
        assert result.fixer.options == [OPTION_REMOVE_COMPILATION]
        assert result.fixer.option_free_text is False
        assert result.fixer.option_automatic_index == 0
        assert result.fixer.prompt == "compilation flag"

    def test_single_artist_flag_falsy_removed(self):
        # the flag must be completely removed, a falsy value is not enough
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "0"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "0"}),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be removed from all tracks (single artist: Bob)" in result.message

    def test_multiple_artists_no_album_artist_flag_set(self):
        # no album artist, so the distinct artists decide
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Carol"}),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be set on all tracks (2 distinct artists)" in result.message
        assert result.fixer is not None
        assert result.fixer.options == [OPTION_SET_COMPILATION]
        assert result.fixer.option_free_text is False
        assert result.fixer.option_automatic_index == 0

    def test_multiple_artists_flag_canonical_ok(self):
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Carol", BasicField.COMPILATION: "1"}),
            ]
        )
        assert _check(album) is None

    def test_multiple_artists_flag_wrong_value_set(self):
        # the flag must be the canonical value on every track
        for value in ("0", "false", "yes", "1 "):
            album = _album(
                [
                    Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: value}),
                    Track(filename="2.flac", tag={BasicField.ARTIST: "Carol", BasicField.COMPILATION: value}),
                ]
            )
            result = _check(album)
            assert result is not None
            assert "compilation flag should be set on all tracks (2 distinct artists)" in result.message

    def test_multiple_artists_flag_partial_set(self):
        # the flag must be on every track
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Carol"}),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be set on all tracks (2 distinct artists)" in result.message

    def test_single_artist_flag_partial_removed(self):
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob"}),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be removed from all tracks (single artist: Bob)" in result.message

    def test_artist_various_artists_flag_set(self):
        # no album artist, so artist "Various Artists" decides
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Various Artists"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Various Artists"}),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be set on all tracks (artist Various Artists)" in result.message
        assert result.fixer is not None
        assert result.fixer.options == [OPTION_SET_COMPILATION]
        assert result.fixer.option_automatic_index == 0

    def test_various_artists_canonical_ok(self):
        album = _album([Track(filename="1.flac", tag={BasicField.ARTIST: "Various Artists", BasicField.COMPILATION: "1"})])
        assert _check(album) is None

    def test_no_artists_flag_removed(self):
        # no artist information means not a compilation
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.COMPILATION: "1"}),
                Track(filename="2.flac"),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be removed from all tracks (no artists)" in result.message

    def test_no_artists_no_flag_ok(self):
        album = _album([Track(filename="1.flac"), Track(filename="2.flac")])
        assert _check(album) is None

    def test_artist_case_insensitive_single(self):
        # case differences of the same artist name count as one artist
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "BOB", BasicField.COMPILATION: "1"}),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "single artist: Bob" in result.message

    def test_album_artist_consistent_not_compilation(self):
        # a single consistent, non-Various-Artists album artist wins over diverse track artists
        # (e.g. an artist album with a guest appearance)
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob Dylan", BasicField.ALBUMARTIST: "Bob Dylan"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob Dylan", BasicField.ALBUMARTIST: "Bob Dylan"}),
                Track(
                    filename="3.flac",
                    tag={BasicField.ARTIST: "Bob Dylan and Special Guest", BasicField.ALBUMARTIST: "Bob Dylan"},
                ),
            ]
        )
        assert _check(album) is None

    def test_album_artist_consistent_flag_removed(self):
        album = _album(
            [
                Track(
                    filename="1.flac",
                    tag={BasicField.ARTIST: "Bob Dylan", BasicField.ALBUMARTIST: "Bob Dylan", BasicField.COMPILATION: "1"},
                ),
                Track(
                    filename="2.flac",
                    tag={BasicField.ARTIST: "Bob Dylan and Special Guest", BasicField.ALBUMARTIST: "Bob Dylan", BasicField.COMPILATION: "1"},
                ),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be removed from all tracks (album artist Bob Dylan)" in result.message

    def test_album_artist_soundtrack_cast_not_compilation(self):
        # a soundtrack with a consistent, non-Various-Artists album artist is not a compilation,
        # even though the tracks have different performers
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Alice", BasicField.ALBUMARTIST: "Cast of The Movie"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob", BasicField.ALBUMARTIST: "Cast of The Movie"}),
                Track(
                    filename="3.flac",
                    tag={BasicField.ARTIST: "Cast of The Movie", BasicField.ALBUMARTIST: "Cast of The Movie"},
                ),
            ]
        )
        assert _check(album) is None

    def test_album_artist_soundtrack_cast_flag_removed(self):
        album = _album(
            [
                Track(
                    filename="1.flac",
                    tag={BasicField.ARTIST: "Alice", BasicField.ALBUMARTIST: "Cast of The Movie", BasicField.COMPILATION: "1"},
                ),
                Track(
                    filename="2.flac",
                    tag={BasicField.ARTIST: "Bob", BasicField.ALBUMARTIST: "Cast of The Movie", BasicField.COMPILATION: "1"},
                ),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be removed from all tracks (album artist Cast of The Movie)" in result.message

    def test_album_artist_various_flag_set(self):
        # album artist "Various Artists" decides, even if the artists differ for other reasons
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Alice", BasicField.ALBUMARTIST: "Various Artists"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob", BasicField.ALBUMARTIST: "Various Artists"}),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be set on all tracks (album artist Various Artists)" in result.message

    def test_album_artist_various_case_insensitive(self):
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ALBUMARTIST: "various artists"}),
                Track(filename="2.flac", tag={BasicField.ALBUMARTIST: "VARIOUS ARTISTS"}),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be set on all tracks (album artist Various Artists)" in result.message

    def test_album_artist_inconsistent_flag_set(self):
        # conflicting album artist values mean no single artist represents the album
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.ALBUMARTIST: "Bob"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Carol", BasicField.ALBUMARTIST: "Carol"}),
            ]
        )
        result = _check(album)
        assert result is not None
        assert "compilation flag should be set on all tracks (inconsistent album artist)" in result.message
        assert result.fixer is not None
        assert result.fixer.options == [OPTION_SET_COMPILATION]

    @pytest.mark.parametrize(
        "parent_folder",
        ["compilation", "compilations", "soundtrack", "soundtracks", "various", "various artists"],
    )
    def test_parent_folder_default(self, parent_folder: str):
        # the default parent folders always mean a compilation, whatever the artist values
        album = _album(
            [Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.ALBUMARTIST: "Bob"})],
            path=f"{parent_folder}/Foo",
        )
        result = _check(album)
        assert result is not None
        assert f"compilation flag should be set on all tracks (parent folder {parent_folder})" in result.message

    def test_parent_folder_case_insensitive(self):
        album = _album([Track(filename="1.flac", tag={BasicField.ARTIST: "Bob"})], path="Compilations/Foo")
        result = _check(album)
        assert result is not None
        assert "parent folder Compilations" in result.message

    def test_parent_folder_overrides_artist_values(self):
        # tags alone say this is a normal single-artist album, but the parent folder wins
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.ALBUMARTIST: "Bob"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob", BasicField.ALBUMARTIST: "Bob"}),
            ],
            path="soundtracks/The Movie",
        )
        result = _check(album)
        assert result is not None
        assert "parent folder soundtracks" in result.message

    def test_parent_folder_canonical_ok(self):
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
            ],
            path="various artists/Mixes",
        )
        assert _check(album) is None

    def test_parent_folder_exact_match_only(self):
        # the parent folder name must match exactly (case-insensitively), not as a substring
        for path in ("my compilations/Foo", "soundtracks and more/Foo"):
            album = _album(
                [
                    Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                    Track(filename="2.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                ],
                path=path,
            )
            result = _check(album)
            assert result is not None, f"expected flag removal for {path}"
            assert "single artist: Bob" in result.message

    def test_parent_folder_none(self):
        # an album folder with no parent within the library has no matching parent folder
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
            ],
            path="Foo",
        )
        result = _check(album)
        assert result is not None
        assert "single artist: Bob" in result.message

    def test_parent_folders_config(self):
        # a configured list replaces the default list entirely
        album = _album([Track(filename="1.flac", tag={BasicField.ARTIST: "Bob"})], path="mixes/Foo")
        result = _check(album, compilation_parent_folders=["mixes"])
        assert result is not None
        assert "parent folder mixes" in result.message

        # "compilations" is no longer a compilation parent folder with this configuration
        album = _album([Track(filename="1.flac", tag={BasicField.ARTIST: "Bob"})], path="compilations/Foo")
        assert _check(album, compilation_parent_folders=["mixes"]) is None

    def test_parent_folders_config_invalid(self):
        # an invalid value is ignored, as if the list were empty
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
            ],
            path="compilations/Foo",
        )
        result = _check(album, compilation_parent_folders="compilations")
        assert result is not None
        assert "single artist: Bob" in result.message

    def test_unsupported_tracks_skipped(self):
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob"}),
                Track(filename="cover.jpg"),
            ]
        )
        assert _check(album) is None

    def test_fix_set(self, mocker):
        # tracks that already match the canonical value are not rewritten
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Carol", BasicField.COMPILATION: "0"}),
            ]
        )
        result = _check(album)
        tagger = MockTagger()
        mock_open = mocker.patch.object(AlbumTagger, "open")
        mock_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [call(BasicField.COMPILATION, "1")]

    def test_fix_set_parent_folder(self, mocker):
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.ALBUMARTIST: "Bob"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob", BasicField.ALBUMARTIST: "Bob"}),
            ],
            path="compilations/Foo",
        )
        result = _check(album)
        tagger = MockTagger()
        mock_open = mocker.patch.object(AlbumTagger, "open")
        mock_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [
            call(BasicField.COMPILATION, "1"),
            call(BasicField.COMPILATION, "1"),
        ]

    def test_fix_clear(self, mocker):
        # every track with the field, whatever its value, has it removed
        album = _album(
            [
                Track(filename="1.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "1"}),
                Track(filename="2.flac", tag={BasicField.ARTIST: "Bob", BasicField.COMPILATION: "0"}),
                Track(filename="3.flac", tag={BasicField.ARTIST: "Bob"}),
            ]
        )
        result = _check(album)
        tagger = MockTagger()
        mock_open = mocker.patch.object(AlbumTagger, "open")
        mock_open.return_value.__enter__.return_value = tagger
        mock_set_field = mocker.patch.object(tagger, "set_field")

        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM
        assert mock_set_field.call_args_list == [
            call(BasicField.COMPILATION, None),
            call(BasicField.COMPILATION, None),
        ]
