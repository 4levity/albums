from albums.checks.all import ALL_CHECKS, check_run_order, implicitly_ignored_checks, transitive_dependencies, transitive_dependents


class TestAllChecks:
    def test_order_satisfies_must_pass_checks(self):
        # checks run in the order they appear in ALL_CHECKS, so every check must be listed after the checks in its must_pass_checks
        position = {check.name: i for i, check in enumerate(ALL_CHECKS)}
        for check in ALL_CHECKS:
            for dep in sorted(check.must_pass_checks):
                assert dep in position, f"{check.name} depends on {dep}, which is not in ALL_CHECKS"
                assert position[dep] < position[check.name], f"{check.name} must run after {dep}, but is listed first in ALL_CHECKS"


class TestCheckDependencies:
    def test_transitive_dependencies(self):
        # track-filename depends on album-artist, artist, track-numbering and track-title, and transitively on their dependencies too
        assert transitive_dependencies("track-filename") == {
            "album-artist",
            "artist",
            "track-numbering",
            "track-title",
            "legacy-fields",
            "disc-numbering",
            "invalid-track-or-disc-number",
            "disc-in-track-number",
        }
        # a check without dependencies has none
        assert transitive_dependencies("album") == set()

    def test_transitive_dependents(self):
        # every check in the disc numbering chain (and track-filename) depends on disc-in-track-number, directly or transitively
        assert transitive_dependents("disc-in-track-number") == {
            "invalid-track-or-disc-number",
            "disc-numbering",
            "track-numbering",
            "zero-pad-numbers",
            "track-filename",
        }
        # a check nothing depends on has no dependents
        assert transitive_dependents("zero-pad-numbers") == set()

    def test_implicitly_ignored_checks(self):
        # ignoring a check implicitly ignores every check that depends on it, directly or transitively
        assert implicitly_ignored_checks({"disc-in-track-number"}) == {
            "invalid-track-or-disc-number",
            "disc-numbering",
            "track-numbering",
            "zero-pad-numbers",
            "track-filename",
        }
        # ignoring a check that many checks depend on implicitly ignores them all
        assert "disc-in-track-number" in implicitly_ignored_checks({"legacy-fields"})
        assert "album-artist" in implicitly_ignored_checks({"legacy-fields"})
        assert "disc-in-track-number" not in implicitly_ignored_checks({"track-title"})
        assert implicitly_ignored_checks(set()) == set()

    def test_check_run_order(self):
        # checks are ordered by their position in ALL_CHECKS, the order they run in
        order = check_run_order({"track-numbering", "disc-in-track-number", "invalid-track-or-disc-number"})
        assert order == ["disc-in-track-number", "invalid-track-or-disc-number", "track-numbering"]
