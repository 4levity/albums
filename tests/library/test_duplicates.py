import os

from sqlalchemy.orm import Session

from albums.database import MEMORY, db_open
from albums.entities import Album, Track
from albums.library.duplicates import DuplicateFinder
from albums.tagger import BasicField


def make_album(path: str, artist: str, album: str) -> Album:
    return Album(path=path + os.sep, tracks=[Track(filename="1.flac", fields={BasicField.ALBUM: album, BasicField.ARTIST: artist})])


class TestDuplicateFinder:
    def test_start_finds_duplicate_groups(self):
        albums = [
            make_album("One", "Foo", "The One"),
            make_album("One (2001)", "Foo", "The One"),
            make_album("Two", "Foo", "The Two"),
            make_album("Other", "Bar", "Other"),
        ]
        with Session(db_open(MEMORY)) as session:
            session.add_all(albums)
            session.flush()

            finder = DuplicateFinder().start(session)
            # path order: "One (2001)/" < "One/"; only the first album of a group is a duplicate, unique albums are not
            assert finder.find(albums[1]) == [albums[0].album_id]
            assert not finder.find(albums[0])
            assert not finder.find(albums[2])
            assert not finder.find(albums[3])

    def test_start_case_insensitive(self):
        # note: "GRÜSSE".lower() is "grüsse", not "grüße" - ß/SS case folding is not a duplicate match
        albums = [
            make_album("Grüße", "Foo", "Grüße"),
            make_album("Grüße (2001)", "foo", "grüße"),
        ]
        with Session(db_open(MEMORY)) as session:
            session.add_all(albums)
            session.flush()

            finder = DuplicateFinder().start(session)
            assert finder.find(albums[1]) == [albums[0].album_id]

    def test_start_most_common_tie_broken_by_value(self):
        # album one has artist B once and A once: tied counts, "A" wins; album two uses A, so they group
        albums = [
            Album(
                path="One" + os.sep,
                tracks=[
                    Track(filename="1.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "B"}),
                    Track(filename="2.flac", fields={BasicField.ALBUM: "The One", BasicField.ARTIST: "A"}),
                ],
            ),
            make_album("One (2001)", "A", "The One"),
        ]
        with Session(db_open(MEMORY)) as session:
            session.add_all(albums)
            session.flush()

            finder = DuplicateFinder().start(session)
            # path order: "One (2001)/" < "One/", so the single-track album is the first of the group
            assert finder.find(albums[1]) == [albums[0].album_id]

    def test_remove(self):
        albums = [
            make_album("One", "Foo", "The One"),
            make_album("One (2001)", "Foo", "The One"),
            make_album("Other", "Bar", "Other"),
        ]
        with Session(db_open(MEMORY)) as session:
            session.add_all(albums)
            session.flush()

            finder = DuplicateFinder().start(session)
            assert finder.find(albums[1]) == [albums[0].album_id]
            finder.remove(albums[1])
            # the remaining album is no longer a duplicate
            assert not finder.find(albums[0])
            # removing an album that is not in the index is an error
            try:
                finder.remove(albums[2])
                assert False, "expected ValueError"
            except ValueError:
                pass
