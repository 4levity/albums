from albums.entities import OtherFile, PictureFile, Track
from albums.library.rescan import _SCANNER_VERSION_CHANGES, SCANNER_VERSION, needs_rescan
from albums.library.scanner_types import ALL_FILE_ASPECTS, FileAspect, TargetRescan


class TestNeedsRescan:
    def test_current_version(self):
        track = Track(filename="1.flac")
        assert needs_rescan(SCANNER_VERSION, track) is None
        assert needs_rescan(SCANNER_VERSION + 1, track) is None  # newer-than-current versions are not rescanned

    def test_scanner_versions(self):
        track = Track(filename="1.flac")
        expectations: dict[int, TargetRescan | None] = {
            0: TargetRescan(track, aspects=ALL_FILE_ASPECTS),  # versions before 7 assume everything changed
            1: TargetRescan(track, aspects=ALL_FILE_ASPECTS),
            6: TargetRescan(track, aspects=ALL_FILE_ASPECTS),
            7: TargetRescan(track, aspects=frozenset({FileAspect.FIELDS, FileAspect.STREAMS})),
            8: TargetRescan(track, aspects=frozenset({FileAspect.FIELDS, FileAspect.STREAMS})),
            9: TargetRescan(track, aspects=frozenset({FileAspect.FIELDS})),
        }
        for scanner, expected in expectations.items():
            assert needs_rescan(scanner, track) == expected, scanner

    def test_file_types(self):
        picture_file = PictureFile(filename="cover.jpg")
        other_file = OtherFile(filename="notes.txt")
        for file in [picture_file, other_file]:
            result = needs_rescan(9, file)
            assert result is not None
            assert result.source is file
            assert result.aspects == frozenset({FileAspect.FIELDS})

    def test_bump_scanner_version(self, mocker):
        track = Track(filename="1.flac")
        mocker.patch("albums.library.rescan.SCANNER_VERSION", 11)
        changes = dict(_SCANNER_VERSION_CHANGES)
        changes[11] = frozenset({FileAspect.IMAGES})
        mocker.patch("albums.library.rescan._SCANNER_VERSION_CHANGES", changes)

        assert needs_rescan(10, track) == TargetRescan(track, aspects=frozenset({FileAspect.IMAGES}))
        assert needs_rescan(9, track) == TargetRescan(track, aspects=frozenset({FileAspect.FIELDS, FileAspect.IMAGES}))

        # forgetting to record the new version's changes conservatively falls back to a full rescan
        del changes[11]
        assert needs_rescan(10, track) == TargetRescan(track, aspects=ALL_FILE_ASPECTS)
