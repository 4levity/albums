# shellcheck shell=sh
# Shared helpers for the albums git hooks

# Print an informational line. $1: the text.
hook_note() {
    printf 'albums hook: %s\n' "$1"
}

# Print what failed and how to fix it to stderr, then exit 1.
# $1: what failed (one line). $2: how to fix it (optional, may span lines).
hook_fail() {
    {
        printf '\nalbums hook FAILED: %s\n' "$1"
        if [ -n "${2:-}" ]; then
            printf '\nHow to fix it:\n%s\n' "$2"
        fi
    } >&2
    exit 1
}

# The checks run through the Makefile; fail clearly if make is missing
require_make() {
    command -v make >/dev/null 2>&1 || hook_fail "make is not on PATH" \
        "Install make (or use a toolchain that provides it), then re-run the git command."
}

# For pre-commit: the staged changes are the commit itself, so they are fine.
# Fail if there are unstaged changes or untracked (non-ignored) files.
require_commit_tree_clean() {
    unstaged=$(git diff --name-only)
    untracked=$(git ls-files --others --exclude-standard)
    [ -z "$unstaged" ] && [ -z "$untracked" ] && return 0

    list=""
    [ -n "$unstaged" ] && list="Unstaged changes:
$(printf '%s\n' "$unstaged" | sed 's/^/  - /')"
    [ -n "$untracked" ] && list="${list:+$list
}Untracked files (commit them, delete them, or add them to .gitignore):
$(printf '%s\n' "$untracked" | sed 's/^/  - /')"

    hook_fail "the working tree is not clean" \
"Every change must be staged and no untracked files may be left behind:
$list
  git status
  git add -A
  # re-run the original git commit command"
}

# For pre-commit, run after `make fix static` succeeds: `make fix` may have
# modified tracked files (ruff format/fix, prettier). Stage them so the
# commit includes the fixes - the static checks already ran on the fixed
# tree. (The tree was clean before the hook ran, so any modified tracked
# file was touched by the hook's own make run.) Fails if the hook left
# untracked files behind (unexpected).
stage_auto_fixes() {
    untracked=$(git ls-files --others --exclude-standard)
    if [ -n "$untracked" ]; then
        hook_fail "untracked files appeared while the hook was running" \
"Remove them, add them to .gitignore, or commit them, then re-run the git
commit command:
$(printf '%s\n' "$untracked" | sed 's/^/  - /')"
    fi
    git diff --quiet && return 0
    list=$(git diff --name-only -z | tr '\0' '\n' | sed 's/^/  - /')
    git add -u
    hook_note "pre-commit: make fix changed files; staged them for the commit:
$list"
}

# For pre-push: the tree must be fully clean (nothing staged, unstaged or
# untracked), because the push publishes the current commits.
require_push_tree_clean() {
    dirty=$(git status --porcelain)
    [ -z "$dirty" ] && return 0
    hook_fail "the working tree is not clean" \
"Commit or stash every change before pushing:
$(printf '%s\n' "$dirty" | sed 's/^/  - /')
  git add -A
  git commit -m '<message>'
  # re-run: git push"
}
