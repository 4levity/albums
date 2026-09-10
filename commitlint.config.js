// Commit message linting, run by the commit-msg git hook
// (hooks/commit-msg) via @commitlint/cli.
//
// Enforces Conventional Commits (https://www.conventionalcommits.org) with a
// 50 character subject limit (commitlint's built-in header-max-length is 100).
// Recommended types are listed in docs/developing.md, "Commit style".
module.exports = {
    extends: ["@commitlint/config-conventional"],
    rules: {
        "header-max-length": [2, "always", 50],
    },
};
