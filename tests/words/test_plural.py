from albums.words import a_plural, count_phrase, plural, pluralize


class TestPluralize:
    def test_singular(self):
        assert pluralize("cat", 1) == "cat"

    def test_plural(self):
        assert pluralize("cat", 2) == "cats"

    def test_y_to_ies(self):
        assert pluralize("story", 2) == "stories"

    def test_sized_input_singular(self):
        assert pluralize("cat", [1]) == "cat"

    def test_sized_input_plural(self):
        assert pluralize("cat", [1, 2]) == "cats"


class TestPlural:
    def test_singular(self):
        assert plural(1, "track") == "1 track"

    def test_plural(self):
        assert plural(2, "track") == "2 tracks"

    def test_sized_input(self):
        assert plural(["a", "b"], "file") == "2 files"


class TestCountPhrase:
    def test_singular(self):
        assert count_phrase(1, "album") == "is 1 album"

    def test_plural(self):
        assert count_phrase(2, "album") == "are 2 albums"

    def test_sized_input(self):
        assert count_phrase(["a", "b"], "file") == "are 2 files"


class TestAPhrase:
    def test_a(self):
        assert a_plural(1, "album") == "an album"

    def test_a_consonant(self):
        assert a_plural(1, "cover") == "a cover"

    def test_plural(self):
        assert a_plural(2, "album") == "albums"

    def test_zero(self):
        assert a_plural(0, "album") == "albums"
