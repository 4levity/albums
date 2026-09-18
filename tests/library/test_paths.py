from string import Template

from albums.app import Context
from albums.entities import Album, Track
from albums.library.paths import make_template_paths
from albums.tagger import BasicField


def _a1_substitution(artist: str, album: str = "Foo") -> str:
    album_entity = Album(
        path="x",
        tracks=[Track(filename="1.flac", fields={BasicField.ARTIST: artist, BasicField.ALBUM: album})],
    )
    template = Template("$A1/$a1")
    return make_template_paths(Context(), album_entity, template, Template("various"))[0]


class TestMakeTemplatePathsA1:
    def test_first_letter(self):
        assert _a1_substitution("Beatles") == "B/b"

    def test_leading_article_stripped_case_insensitively(self):
        assert _a1_substitution("The Beatles") == "B/b"
        assert _a1_substitution("THE BEATLES") == "B/b"
        # the article must be a whole word
        assert _a1_substitution("Theorem") == "T/t"

    def test_numeric_first_letter(self):
        assert _a1_substitution("1984") == "#/#"

    def test_german_sharp(self):
        # casefold maps "ß" to "ss", so the initial is the single character "s"
        assert _a1_substitution("straße") == "S/s"

    def test_casefold_single_character(self):
        # "İ" lowercases to two code points; the initial must stay a single character
        assert _a1_substitution("İstanbul") == "I/i"


class TestMakeTemplatePathsWarnings:
    def test_unknown_identifier_warns_and_is_ignored(self, caplog):
        caplog.set_level("WARNING")
        album = Album(path="x", tracks=[Track(filename="1.flac", fields={BasicField.ARTIST: "A", BasicField.ALBUM: "B"})])
        paths = make_template_paths(Context(), album, Template("$artist/$unknown/$album"), Template("various"))
        assert paths[0] == "A/$unknown/B"
        assert any("ignoring unknown template identifiers" in record.message for record in caplog.records)

    def test_multiple_album_artists_uses_most_common(self, caplog):
        caplog.set_level("WARNING")
        album = Album(
            path="x",
            tracks=[
                Track(filename="1.flac", fields={BasicField.ARTIST: "A", BasicField.ALBUM: "B", BasicField.ALBUMARTIST: "X"}),
                Track(filename="2.flac", fields={BasicField.ARTIST: "A", BasicField.ALBUM: "B", BasicField.ALBUMARTIST: "Y"}),
            ],
        )
        paths = make_template_paths(Context(), album, Template("$artist/$album"), Template("various"))
        assert paths[0] == "X/B"
        assert any("more than one album artist value" in record.message for record in caplog.records)

    def test_album_artist_with_multiple_artists_is_various(self):
        album = Album(
            path="x",
            tracks=[
                Track(filename="1.flac", fields={BasicField.ARTIST: "A", BasicField.ALBUM: "B", BasicField.ALBUMARTIST: "X"}),
                Track(filename="2.flac", fields={BasicField.ARTIST: "C", BasicField.ALBUM: "B", BasicField.ALBUMARTIST: "X"}),
            ],
        )
        paths = make_template_paths(Context(), album, Template("$artist/$album"), Template("$a1/various"))
        assert paths[0] == "x/various"

    def test_multiple_artists_no_album_artist_is_various(self, caplog):
        caplog.set_level("WARNING")
        album = Album(
            path="x",
            tracks=[
                Track(filename="1.flac", fields={BasicField.ARTIST: "A", BasicField.ALBUM: "B"}),
                Track(filename="2.flac", fields={BasicField.ARTIST: "C", BasicField.ALBUM: "B"}),
            ],
        )
        paths = make_template_paths(Context(), album, Template("$artist/$album"), Template("$a1/various"))
        assert paths[0] == "a/various"
        assert any("no album artist and more than one artist value" in record.message for record in caplog.records)

    def test_no_artist_uses_unknown_album(self, caplog):
        caplog.set_level("WARNING")
        album = Album(path="x", tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: "B"})])
        paths = make_template_paths(Context(), album, Template("$artist/$album"), Template("various"))
        assert paths[0] == "Unknown Album/B"
        assert any("no album artist or artist fields" in record.message for record in caplog.records)

    def test_multiple_albums_uses_most_common(self, caplog):
        caplog.set_level("WARNING")
        album = Album(
            path="x",
            tracks=[
                Track(filename="1.flac", fields={BasicField.ARTIST: "A", BasicField.ALBUM: "B"}),
                Track(filename="2.flac", fields={BasicField.ARTIST: "A", BasicField.ALBUM: "C"}),
            ],
        )
        paths = make_template_paths(Context(), album, Template("$artist/$album"), Template("various"))
        assert paths[0] == "A/B"
        assert any("more than one album value" in record.message for record in caplog.records)

    def test_no_album_uses_unknown_album(self, caplog):
        caplog.set_level("WARNING")
        album = Album(path="x", tracks=[Track(filename="1.flac", fields={BasicField.ARTIST: "A"})])
        paths = make_template_paths(Context(), album, Template("$artist/$album"), Template("various"))
        assert paths[0] == "A/Unknown Album"
        assert any("no album field" in record.message for record in caplog.records)
