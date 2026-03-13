from dataclasses import dataclass
from typing import Callable, Dict, Sequence, Tuple, Union

from rich.console import RenderableType

type CheckConfiguration = Dict[str, Union[str, int, float, bool, Sequence[str]]]


@dataclass
class Fixer:
    fix: Callable[[str], bool]
    options: Sequence[str]  # at least one option should be provided if "free text" is not an option
    option_free_text: bool = False
    option_automatic_index: int | None = None
    table: Tuple[Sequence[str], Sequence[Sequence[RenderableType]] | Callable[[], Sequence[Sequence[RenderableType]]]] | None = None
    prompt: str = "select an option"  # e.g. "select an album artist for all tracks"

    def get_table(self) -> Tuple[Sequence[str], Sequence[Sequence[RenderableType]]] | None:
        if self.table is None:
            return None
        (headers, get_rows) = self.table
        rows: Sequence[Sequence[RenderableType]] = get_rows if isinstance(get_rows, Sequence) else get_rows()  # pyright: ignore[reportUnknownVariableType]
        return (headers, rows)


@dataclass(frozen=True)
class CheckResult:
    message: str
    fixer: Fixer | None = None
