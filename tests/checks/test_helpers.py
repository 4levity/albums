from albums.checks.helpers import ordered_tracks, parse_filename
from albums.entities import Album, Track
from albums.tagger import BasicField


class TestOrderedTracks:
    def test_sorts_track_numbers_numerically(self):
        # shuffled 12-track album; string sort would give 1, 10, 11, 12, 2, 3, ...
        album = Album(
            path="foo",
            tracks=[Track(filename=f"t{n:02d}.flac", tag={BasicField.TRACKNUMBER: str(n)}) for n in [10, 1, 12, 2, 11, 3, 4, 5, 6, 7, 8, 9]],
        )
        assert [track.get(BasicField.TRACKNUMBER)[0] for track in ordered_tracks(album)] == [str(n) for n in range(1, 13)]

    def test_sorts_disc_numbers_numerically(self):
        # 11 discs; string sort would put disc 10 before disc 2
        tracks = [Track(filename=f"t{disc}.flac", tag={BasicField.TRACKNUMBER: "1", BasicField.DISCNUMBER: str(disc)}) for disc in [10, 1, 11, 2]]
        album = Album(path="foo", tracks=tracks)
        assert [track.get(BasicField.DISCNUMBER)[0] for track in ordered_tracks(album)] == ["1", "2", "10", "11"]

    def test_sorts_disc_then_track_numerically(self):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="10-1.flac", tag={BasicField.TRACKNUMBER: "1", BasicField.DISCNUMBER: "10"}),
                Track(filename="1-12.flac", tag={BasicField.TRACKNUMBER: "12", BasicField.DISCNUMBER: "1"}),
                Track(filename="2-1.flac", tag={BasicField.TRACKNUMBER: "1", BasicField.DISCNUMBER: "2"}),
                Track(filename="10-2.flac", tag={BasicField.TRACKNUMBER: "2", BasicField.DISCNUMBER: "10"}),
                Track(filename="1-2.flac", tag={BasicField.TRACKNUMBER: "2", BasicField.DISCNUMBER: "1"}),
                Track(filename="1-1.flac", tag={BasicField.TRACKNUMBER: "1", BasicField.DISCNUMBER: "1"}),
            ],
        )
        assert [(track.get(BasicField.DISCNUMBER)[0], track.get(BasicField.TRACKNUMBER)[0]) for track in ordered_tracks(album)] == [
            ("1", "1"),
            ("1", "2"),
            ("1", "12"),
            ("2", "1"),
            ("10", "1"),
            ("10", "2"),
        ]

    def test_zero_padded_numbers_sort_numerically(self):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="02.flac", tag={BasicField.TRACKNUMBER: "02"}),
                Track(filename="010.flac", tag={BasicField.TRACKNUMBER: "010"}),
                Track(filename="001.flac", tag={BasicField.TRACKNUMBER: "001"}),
            ],
        )
        assert [track.get(BasicField.TRACKNUMBER)[0] for track in ordered_tracks(album)] == ["001", "02", "010"]

    def test_non_numeric_numbers_sort_after_numbers_without_error(self):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="one.flac", tag={BasicField.TRACKNUMBER: "one"}),
                Track(filename="2.flac", tag={BasicField.TRACKNUMBER: "2"}),
                Track(filename="11.flac", tag={BasicField.TRACKNUMBER: "11"}),
                Track(filename="b.flac", tag={BasicField.TRACKNUMBER: "b"}),
            ],
        )
        assert [track.get(BasicField.TRACKNUMBER)[0] for track in ordered_tracks(album)] == ["2", "11", "b", "one"]

    def test_falls_back_to_filename_sort_when_track_number_missing(self):
        album = Album(
            path="foo",
            tracks=[
                Track(filename="b.flac"),
                Track(filename="a.flac", tag={BasicField.TRACKNUMBER: "2"}),
                Track(filename="c.flac", tag={BasicField.TRACKNUMBER: "1"}),
            ],
        )
        assert [track.filename for track in ordered_tracks(album)] == ["a.flac", "b.flac", "c.flac"]


class TestParseFilename:
    def test_track_title(self):
        assert parse_filename("01 the title.flac") == (None, 1, "the title")

    def test_track_dot_title(self):
        assert parse_filename("01. the title.mp3") == (None, 1, "the title")

    def test_track_dash_title(self):
        assert parse_filename("01 - the title.mp3") == (None, 1, "the title")

    def test_disc_track_title(self):
        assert parse_filename("1-03 - the title.flac") == (1, 3, "the title")

    def test_title_only(self):
        assert parse_filename("the title.flac") == (None, None, "the title")

    def test_track_number_only(self):
        assert parse_filename("1.flac") == (None, 1, None)

    def test_iso_date_prefix_is_not_a_number(self):
        assert parse_filename("2024-01-05 Live show.mp3") == (None, None, "Live show")

    def test_compact_date_prefix_is_not_a_number(self):
        assert parse_filename("20240105 Live show.mp3") == (None, None, "Live show")

    def test_year_and_month_prefixes_are_not_numbers(self):
        assert parse_filename("2024-01 Live show.mp3") == (None, None, "Live show")
        assert parse_filename("202401 Live show.mp3") == (None, None, "Live show")
        assert parse_filename("2024 Live show.mp3") == (None, None, "Live show")

    def test_date_prefix_with_track_number(self):
        assert parse_filename("2024-01-05 01 Live show.mp3") == (None, 1, "Live show")

    def test_invalid_date_is_not_stripped(self):
        assert parse_filename("2024-13-40 Song.mp3") == (None, None, "2024-13-40 Song")
        assert parse_filename("9999-12-31 Song.mp3") == (None, None, "9999-12-31 Song")

    def test_long_number_is_not_a_track_number(self):
        assert parse_filename("1234 Song.mp3") == (None, None, "1234 Song")
