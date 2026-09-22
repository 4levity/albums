import json
import os
import re
import shutil

import pytest

from albums.entities import Album, PictureFile, Track
from albums.picture import PictureInfo
from albums.tagger import BasicField

from .. import helpers
from ..fixtures.create_library import create_library


def unwrapped(output: str) -> str:
    """Collapse whitespace, so rich line-wrapping doesn't split messages and prevent them from being matched as plain text."""
    return " ".join(output.split())


albums = [
    Album(
        path="foo" + os.sep,
        tracks=[Track(filename="1.mp3", fields={BasicField.TITLE: "1", BasicField.ARTIST: "a"})],
        picture_files=[PictureFile(filename="folder.png", picture_info=PictureInfo("ignored", 400, 400, 24, 0, b""))],
    ),
    Album(
        path="bar" + os.sep,
        tracks=[
            Track(filename="1.flac", fields={BasicField.TITLE: "1"}),
            Track(filename="2.flac", fields={BasicField.TITLE: "2"}),
        ],
    ),
]


class CheckboxListStub:
    """Stand-in for prompt_toolkit's checkboxlist dialog, selecting the presented albums whose paths are in ``select_paths`` (or closing the dialog without a selection)."""

    def __init__(self, select_paths: set[str] | None):
        self.select_paths = select_paths
        self.title: str | None = None
        self.values: list[tuple[int, str]] = []
        self.default_values: list[int] = []

    def __call__(self, title: str, *, values: list[tuple[int, str]], default_values: list[int]):
        self.title = title
        self.values = values
        self.default_values = default_values
        return self

    def run(self) -> list[int] | None:
        if self.select_paths is None:
            return None
        return [album_id for album_id, path in self.values if path in self.select_paths]


class TestCli:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestCli.library = create_library("cli", albums)

    def run(self, params: list[str], init=False):
        if init:
            helpers.init_db_cached(TestCli.library, albums)
        return helpers.run(params, TestCli.library)

    def test_help(self):
        result = self.run(["--help"])
        assert result.exit_code == 0
        assert "Usage: albums [OPTIONS] COMMAND [ARGS]" in result.output

    def test_scan(self):
        result = helpers.init_db(TestCli.library)  # fresh init: this test exercises init itself
        assert result.exit_code == 0
        assert "creating database" in result.output
        result = self.run(["-v", "scan"])
        assert result.exit_code == 0
        assert "scanned 3 folders" in result.output

        result = self.run(["scan"])
        assert result.exit_code == 0
        assert not result.output.startswith("creating database")

    def test_list(self):
        self.run(["scan"], init=True)
        result = self.run(["list", "--order", "tracks", "--reverse"])
        assert result.exit_code == 0
        assert re.search("bar.+00:00.+\\d+ Bytes.+foo.+00:00.+\\d+ Bytes.+total: \\d+.*", result.output, re.MULTILINE | re.DOTALL)

    def test_scan_remove(self):
        result = self.run(["-v", "scan"], init=True)
        assert result.exit_code == 0
        assert "scanned 3 folders" in result.output

        shutil.rmtree(TestCli.library / "foo")

        result = self.run(["-v", "scan"])
        assert "removed: 1" in result.output
        result = self.run(["list"])
        assert "foo" not in result.output

    def test_scan_rescan_always(self, mocker):
        self.run(["config", "settings.rescan=always"], init=True)
        prescan = mocker.patch("albums.cli.entry_point.run_scan")
        scan = mocker.patch("albums.cli.scan.run_scan", return_value=(2, False))
        result = self.run(["scan"])
        assert result.exit_code == 0
        prescan.assert_not_called()  # the automatic prescan is suppressed for the scan command
        scan.assert_called_once()

    def test_list_rescan_always(self, mocker):
        self.run(["config", "settings.rescan=always"], init=True)
        prescan = mocker.patch("albums.cli.entry_point.run_scan")
        scan = mocker.patch("albums.cli.scan.run_scan")
        result = self.run(["list"])
        assert result.exit_code == 0
        prescan.assert_called_once()  # other commands still get the automatic prescan
        scan.assert_not_called()

    def test_check(self):
        result = self.run(["check", "--default", "album"], init=True)
        assert result.exit_code == 0
        assert f'1 track missing album field : "foo{os.sep}"' in result.output
        assert f'2 tracks missing album field : "bar{os.sep}"' in result.output

    def test_check_automatically_enabled_dependencies(self):
        result = self.run(["check", "disc-numbering"], init=True)
        assert result.exit_code == 0
        assert "automatically enabling check invalid-track-or-disc-number" in result.output

    def test_ignore_check(self):
        self.run(["scan"], init=True)
        result = self.run(["-p", "foo" + os.sep, "ignore", "album"])
        assert result.exit_code == 0
        assert f"album foo{os.sep} - ignore album" in result.output

        result = self.run(["check", "--default", "album"])
        assert result.exit_code == 0
        assert "foo" + os.sep not in result.output
        assert f'2 tracks missing album field : "bar{os.sep}"' in result.output

    def test_ignore_check_implicitly_ignored(self):
        self.run(["scan"], init=True)
        self.run(["-p", "foo" + os.sep, "ignore", "legacy-fields"])
        # disc-in-track-number depends on legacy-fields, so it is already implicitly ignored for this album
        result = self.run(["-p", "foo" + os.sep, "ignore", "album", "disc-in-track-number"])
        assert result.exit_code == 0
        assert f"album foo{os.sep} - ignore album" in result.output  # the independent ignore is still applied
        assert (
            "cannot ignore disc-in-track-number for album foo"
            + os.sep
            + ': it is already implicitly ignored because it depends on ignored check "legacy-fields"'
            in unwrapped(result.output)
        )

        # the redundant ignore was not added, and the valid one was
        result = self.run(["-p", "foo" + os.sep, "notice", "--force", "album"])
        assert f"album foo{os.sep} will stop ignoring album" in result.output
        result = self.run(["-p", "foo" + os.sep, "notice", "--force", "disc-in-track-number"])
        assert (
            f'album foo{os.sep} does not explicitly ignore disc-in-track-number: it is implicitly ignored because it depends on ignored check "legacy-fields"'
            in unwrapped(result.output)
        )

    def test_notice_check_not_ignored(self):
        self.run(["scan"], init=True)
        result = self.run(["-rp", "(foo|bar)", "notice", "--force", "album"])  # filtered so that album names will not be suppressed
        assert result.exit_code == 0
        assert f"album foo{os.sep} does not ignore album" in result.output
        assert f"album bar{os.sep} does not ignore album" in result.output

    def test_notice_check(self):
        self.run(["scan"], init=True)
        result = self.run(["check", "--default"])
        assert f'1 track missing album field : "foo{os.sep}"' in result.output
        assert f'2 tracks missing album field : "bar{os.sep}"' in result.output
        self.run(["-p", "foo" + os.sep, "ignore", "album"])
        result = self.run(["check", "--default"])
        assert f'1 track missing album field : "foo{os.sep}"' not in result.output
        assert f'2 tracks missing album field : "bar{os.sep}"' in result.output

        result = self.run(["notice", "--force", "album"])
        assert result.exit_code == 0
        assert f"album foo{os.sep} will stop ignoring album" in result.output

        result = self.run(["check", "--default"])
        assert f'1 track missing album field : "foo{os.sep}"' in result.output
        assert f'2 tracks missing album field : "bar{os.sep}"' in result.output

    def test_check_automatic_fix(self):
        result = self.run(["check", "--automatic", "album"], init=True)
        assert result.exit_code == 0
        assert f'"foo{os.sep}" - 1 track missing album field' in result.output
        assert f'"bar{os.sep}" - 2 tracks missing album field' in result.output
        assert "setting album on 1.flac" in result.output

        result = self.run(["--verbose", "scan"])
        assert result.exit_code == 0
        assert "unchanged: 2" in result.output

        result = self.run(["check", "--automatic", "album"])
        assert result.exit_code == 0
        assert "foo" + os.sep not in result.output
        assert "bar" + os.sep not in result.output
        assert "1.flac" not in result.output

    def test_list_json(self):
        self.run(["scan"], init=True)
        result = self.run(["list", "--json"])
        assert result.exit_code == 0
        result_json = json.loads(result.output)
        assert len(result_json) == 2
        assert result_json[1]["path"] == "foo" + os.sep
        assert len(result_json[1]["tracks"]) == 1
        assert result_json[1]["tracks"][0]["filename"] == "1.mp3"

    def test_list_json_empty(self):
        shutil.rmtree(TestCli.library / albums[0].path)
        shutil.rmtree(TestCli.library / albums[1].path)
        self.run(["scan"], init=True)
        result = self.run(["list", "--json"])
        assert result.exit_code == 0
        obj = json.loads(result.output)
        assert obj == []

    def test_filter_path_regex(self):
        self.run(["scan"], init=True)
        result = self.run(["-rp", ".oo", "list", "--json"])
        assert result.exit_code == 0
        obj = json.loads(result.output)
        assert len(obj) == 1
        assert obj[0]["path"] == "foo" + os.sep

    def test_filter_path_regex_match(self):
        self.run(["scan"], init=True)
        result = self.run(["-m", "path~.oo", "list", "--json"])
        obj = json.loads(result.output)
        assert len(obj) == 1
        assert obj[0]["path"] == "foo" + os.sep

    def test_add_collection(self):
        self.run(["scan"], init=True)
        result = self.run(["-rp", "foo", "add", "test"])
        assert result.exit_code == 0
        assert result.output.startswith(f"added album foo{os.sep} to collection test")

    def test_filter_collection_invert(self):
        self.run(["scan"], init=True)
        result = self.run(["-rp", "foo", "add", "test"])

        result = self.run(["-c", "test", "--invert", "list", "--json"])
        assert result.exit_code == 0
        obj = json.loads(result.output)
        assert len(obj) == 1
        assert obj[0]["path"] == "bar" + os.sep

    def test_filter_collection_match(self):
        self.run(["scan"], init=True)
        result = self.run(["-rp", "foo", "add", "test"])

        result = self.run(["-m", "collection=test", "list", "--json"])
        obj = json.loads(result.output)
        assert len(obj) == 1
        assert obj[0]["path"] == "foo" + os.sep

    def test_remove_collection(self):
        self.run(["scan"], init=True)
        result = self.run(["add", "test"])  # add all
        assert result.exit_code == 0
        assert f"added album foo{os.sep} to collection test" in result.output
        assert f"added album bar{os.sep} to collection test" in result.output

        result = self.run(["-rp", "foo", "remove", "test"])
        assert result.exit_code == 0
        assert f"removed album foo{os.sep} from collection test" in result.output

        result = self.run(["-c", "test", "list", "--json"])
        obj = json.loads(result.output)
        assert len(obj) == 1
        assert obj[0]["path"] == "bar" + os.sep  # foo was removed

    def mock_select_dialog(self, mocker, select_paths: set[str] | None) -> CheckboxListStub:
        dialog = CheckboxListStub(select_paths)
        mocker.patch("albums.cli.collections_select.checkboxlist_dialog", side_effect=dialog)
        return dialog

    def test_collections_select_requires_collection_name(self):
        self.run(["scan"], init=True)
        result = self.run(["select"])
        assert result.exit_code == 1
        assert "must specify at least one collection name" in result.output

    def test_collections_select_add_and_remove(self, mocker):
        self.run(["scan"], init=True)
        self.run(["-rp", "foo", "add", "one", "two"])
        self.run(["-rp", "bar", "add", "one"])

        dialog = self.mock_select_dialog(mocker, {albums[1].path})
        result = self.run(["select", "one", "two"])
        assert result.exit_code == 0
        assert dialog.title == "add albums to: one, two"
        ids_by_path = {path: album_id for album_id, path in dialog.values}
        assert dialog.default_values == [ids_by_path[albums[0].path]]  # only foo is in all the named collections
        assert f"added album {albums[1].path} to collection two" in result.output
        assert f"added album {albums[1].path} to collection one" not in result.output  # bar was already in one
        assert f"removed album {albums[0].path} from collection one" in result.output
        assert f"removed album {albums[0].path} from collection two" in result.output

        # bar is now in both collections, foo is in neither
        one = json.loads(self.run(["-m", "collection=one", "list", "--json"]).output)
        two = json.loads(self.run(["-m", "collection=two", "list", "--json"]).output)
        assert [a["path"] for a in one] == [albums[1].path]
        assert [a["path"] for a in two] == [albums[1].path]

    def test_collections_select_no_change(self, mocker):
        self.run(["scan"], init=True)
        self.run(["-rp", "foo", "add", "one", "two"])
        self.run(["-rp", "bar", "add", "one", "two"])

        dialog = self.mock_select_dialog(mocker, {album.path for album in albums})
        result = self.run(["select", "one", "two"])
        assert result.exit_code == 0
        assert len(dialog.values) == 2
        assert len(dialog.default_values) == 2  # both albums are preselected, and selecting both changes nothing
        assert "added album" not in result.output
        assert "removed album" not in result.output

        one = json.loads(self.run(["-m", "collection=one", "list", "--json"]).output)
        assert [a["path"] for a in one] == [albums[1].path, albums[0].path]

    def test_collections_select_dialog_cancelled(self, mocker):
        self.run(["scan"], init=True)
        self.run(["-rp", "foo", "add", "one"])

        self.mock_select_dialog(mocker, None)  # dialog closed without a selection
        result = self.run(["select", "one", "two"])
        assert result.exit_code == 0
        assert "added album" not in result.output
        assert "removed album" not in result.output

        # membership is unchanged: foo remains in one only
        one = json.loads(self.run(["-m", "collection=one", "list", "--json"]).output)
        two = json.loads(self.run(["-m", "collection=two", "list", "--json"]).output)
        assert [a["path"] for a in one] == [albums[0].path]
        assert two == []

    def test_import_automatic(self):
        self.run(["scan"], init=True)
        result = self.run(["list"])
        assert "baz" not in result.output
        assert "foobar" not in result.output

        new_albums = [
            Album(
                path="foobar" + os.sep,
                tracks=[
                    Track(
                        filename="01.flac",
                        fields={BasicField.TITLE: "1", BasicField.TRACKNUMBER: "01", BasicField.ALBUM: "foobar", BasicField.ARTIST: "baz"},
                    )
                ],
            ),
            Album(
                path="baz" + os.sep,
                tracks=[
                    Track(
                        filename="1.flac",
                        fields={BasicField.TITLE: "1", BasicField.TRACKNUMBER: "01", BasicField.ALBUM: "baz", BasicField.ARTIST: "baz"},
                    )
                ],
            ),
        ]
        src = create_library("cli_import", new_albums)
        result = self.run(["-v", "import", "--automatic", str(src)])
        assert result.exit_code == 0
        assert "automatically fixing track-filename" in result.output
        assert "Copying 1 file" in result.output

        result = self.run(["list"])
        assert "baz" in result.output
        assert "foobar" in result.output

    def test_import_automatic_conflict(self):
        result = self.run(["check", "--automatic", "album"], init=True)
        assert len(json.loads(self.run(["list", "-j"]).output)) == 2

        result = self.run(["list"])
        assert "baz" not in result.output
        assert "foobar" not in result.output

        new_album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(
                    filename="01 one.flac",
                    fields={BasicField.TITLE: "one", BasicField.TRACKNUMBER: "01", BasicField.ALBUM: "foo", BasicField.ARTIST: "a"},
                )
            ],
        )

        src = create_library("cli_import_conflict", [new_album])
        result = self.run(["-v", "import", "--automatic", str(src)])
        assert result.exit_code == 0
        assert "Copying" not in result.output

        assert len(json.loads(self.run(["list", "-j"]).output)) == 2

    def test_import_does_not_rename_source(self):
        self.run(["scan"], init=True)
        new_album = Album(
            path="source" + os.sep,
            tracks=[
                Track(
                    filename="01.flac",
                    fields={BasicField.TITLE: "1", BasicField.TRACKNUMBER: "01", BasicField.ALBUM: "foobar", BasicField.ARTIST: "baz"},
                )
            ],
        )
        src = create_library("cli_import_rename", [new_album])
        result = self.run(["-v", "import", "--automatic", str(src)])
        assert result.exit_code == 0
        assert (src / "source").is_dir()  # the folder-name check must not rename the source folder
        result = self.run(["list"])
        assert "foobar" in result.output

    def test_sql(self):
        self.run(["scan"], init=True)
        result = self.run(["sql", "--json", "SELECT * from album ORDER BY path;"])
        assert result.exit_code == 0
        result = json.loads(result.output)
        assert result[0][1] == "bar" + os.sep
        assert result[1][1] == "foo" + os.sep

        result = self.run(["sql", "SELECT * from album;"])
        assert result.exit_code == 0
        assert "foo" + os.sep in result.output
        assert "album_id" in result.output  # shows column names
        assert "path" in result.output
