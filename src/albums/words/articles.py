# Leading articles moved to the end when generating a sort value, e.g. "The Beatles" -> "Beatles, The"
import re
from typing import Final

LEADING_ARTICLES: Final[frozenset[str]] = frozenset({"a", "an", "the"})
_LEADING_ARTICLE_RE: Final = re.compile(
    r"^(?:" + "|".join(re.escape(article) for article in sorted(LEADING_ARTICLES, key=len, reverse=True)) + r")\s+", re.IGNORECASE
)


def move_leading_article(name: str) -> str:
    """Move a leading article to the end of a name, e.g. 'The Beatles' -> 'Beatles, The'; unchanged if the name doesn't start with an article."""
    match = _LEADING_ARTICLE_RE.match(name)
    if not match:
        return name
    return f"{name[match.end() :]}, {name[: match.end()].rstrip()}"
