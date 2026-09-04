from albums.words import move_leading_article


class TestMoveLeadingArticle:
    def test_moves_the(self):
        assert move_leading_article("The Beatles") == "Beatles, The"
        assert move_leading_article("The White Stripes") == "White Stripes, The"

    def test_matches_case_insensitively_but_keeps_case(self):
        assert move_leading_article("the beatles") == "beatles, the"
        assert move_leading_article("THE BEATLES") == "BEATLES, THE"

    def test_moves_a_and_an(self):
        assert move_leading_article("A Tribe") == "Tribe, A"
        assert move_leading_article("An Angel") == "Angel, An"

    def test_no_article_is_unchanged(self):
        assert move_leading_article("Beatles") == "Beatles"

    def test_article_must_be_a_whole_word(self):
        assert move_leading_article("Adele") == "Adele"
        assert move_leading_article("Anya") == "Anya"

    def test_article_only_is_unchanged(self):
        assert move_leading_article("The") == "The"
