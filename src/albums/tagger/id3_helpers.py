from typing import Tuple

from mutagen.id3 import ID3
from mutagen.id3._frames import TPOS, TRCK
from mutagen.id3._specs import Encoding


def get_text(id3: ID3 | None, frame_name: str) -> list[str] | None:
    """Return text values from an ID3 frame, or None if the frame is missing."""
    if id3 is None or frame_name not in id3:
        return None
    return must_get_text(id3, frame_name)


def must_get_text(id3: ID3, frame_name: str) -> list[str]:
    """Return text values from an existing ID3 frame."""
    import textwrap

    frame = id3[frame_name]  # pyright: ignore[reportUnknownVariableType]
    if hasattr(frame, "text") and isinstance(frame.text, list) and len(frame.text):  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
        return [str(text) for text in frame.text]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType, reportUnknownMemberType]
    # fallback if this does not look like a text frame
    return [textwrap.shorten(str(frame), width=4096)]  # pyright: ignore[reportUnknownArgumentType]


def parse_numbered_value(value: str | None) -> Tuple[str | None, str | None]:
    """Parse an ID3 numbered-value string like '1/5' into (number, total)."""
    if value is None:
        return (None, None)
    if value.count("/") == 1:
        first, second = value.split("/")
        return (first, second)
    return (value, None)


def format_numbered_value(number: str | None, total: str | None) -> str | None:
    """Format two parts into an ID3 numbered-value string like '1/5'."""
    if number is None and total is None:
        return None
    if total is None:
        return number
    if number is None:
        return f"/{total}"
    return f"{number}/{total}"


def set_numbered_frame(id3: ID3, value: str | None, frame_name: str, factory: type[TPOS] | type[TRCK]) -> None:
    """Update or remove a numbered-value frame (TRCK/TPOS) on an ID3 tag object."""
    if value is None and frame_name in id3:
        del id3[frame_name]
    elif value is not None and frame_name not in id3:
        id3.add(factory(encoding=Encoding.UTF8, text=[value]))  # pyright: ignore[reportUnknownMemberType]
    elif value is not None and id3[frame_name].text != [value]:  # pyright: ignore[reportUnknownMemberType]
        id3[frame_name] = factory(encoding=Encoding.UTF8, text=[value])
