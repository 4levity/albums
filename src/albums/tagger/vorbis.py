from typing import List, Tuple

from mutagen._vorbis import VCommentDict

from .types import BasicTag


def vorbis_comment_tags(file_tags: VCommentDict) -> Tuple[Tuple[BasicTag, Tuple[str, ...]], ...]:
    tags: list[tuple[BasicTag, tuple[str, ...]]] = []
    for tag in BasicTag:
        if tag != BasicTag.UNKNOWN and tag.value in file_tags:
            values: Tuple[str, ...] = tuple(str(value) for value in file_tags[tag.value])  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
            tags.append((tag, values))
    return tuple(tags)


def vorbis_comment_set_tag(file_tags: VCommentDict, tag: BasicTag, value: str | List[str] | None):
    if value is None:
        if tag != BasicTag.UNKNOWN and tag.value in file_tags:
            del file_tags[tag.value]
    else:
        value_list = value if isinstance(value, List) else [value]
        match tag:
            case BasicTag.UNKNOWN:
                raise ValueError("cannot set tag value UNKNOWN")
            case BasicTag.COMPILATION:
                if value_list and value_list[0]:
                    file_tags[tag.value] = ["1"]
                elif tag.value in file_tags:
                    del file_tags[tag.value]
            case _:
                file_tags[tag.value] = value_list
