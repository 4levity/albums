from albums.checks.all import ALL_CHECKS


class TestAllChecks:
    def test_order_satisfies_must_pass_checks(self):
        # checks run in the order they appear in ALL_CHECKS, so every check must be listed after the checks in its must_pass_checks
        position = {check.name: i for i, check in enumerate(ALL_CHECKS)}
        for check in ALL_CHECKS:
            for dep in sorted(check.must_pass_checks):
                assert dep in position, f"{check.name} depends on {dep}, which is not in ALL_CHECKS"
                assert position[dep] < position[check.name], f"{check.name} must run after {dep}, but is listed first in ALL_CHECKS"
