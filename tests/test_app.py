import re

import albums


class TestApp:
    def test_app_version(self):
        # version is derived from git tags at install/build time (see scripts/version.py)
        assert re.fullmatch(r"\d+\.\d+\.\d+(?:[.+a-z0-9]+)?", albums.__version__)
