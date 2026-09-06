from string import Template

from albums.app import Context
from albums.entities import Album, Track
from albums.library.paths import make_template_paths
from albums.tagger import BasicField


def _a1_substitution(artist: str, album: str = "Foo") -> str:
    album_entity = Album(
        path="x",
        tracks=[Track(filename="1.flac", tag={BasicField.ARTIST: artist, BasicField.ALBUM: album})],
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
