import logging
from math import sqrt
from typing import Any, Dict, List, Sequence, Tuple

import humanize
import numpy
from PIL.Image import Image, Resampling
from rich.console import RenderableType
from rich_pixels import Pixels
from skimage.metrics import mean_squared_error  # pyright: ignore[reportUnknownVariableType]

from ..app import Context
from ..library.metadata import read_image
from ..types import Album, Picture

logger = logging.getLogger(__name__)


def render_image_table(
    ctx: Context,
    album: Album,
    pictures: Sequence[Picture | Tuple[Picture, Image, bytes]],  # type: ignore
    picture_sources: Dict[Picture, List[Tuple[str, bool, int]]],
) -> List[List[RenderableType]]:
    pixelses: list[RenderableType] = []
    target_width = int((ctx.console.width - 3) / len(pictures))
    target_height = (ctx.console.height - 10) * 2
    captions: list[RenderableType] = []
    reference_image: numpy.ndarray[Any] | None = None
    reference_width = reference_height = 0
    for cover_ref in pictures:
        if isinstance(cover_ref, Picture):
            cover = cover_ref
            (filename, embedded, embed_ix) = picture_sources[cover][0]
            path = ctx.config.library / album.path / filename
            loaded_image = read_image(path, embedded, embed_ix)
            if loaded_image:
                (image, image_data) = loaded_image
            else:
                image = None
                image_data = b""
        else:
            (cover, image, image_data) = cover_ref

        if image:
            h = (7 / 8) * image.height  # TODO try to determine appropriate height scaling for terminal font or make configurable
            scale = min(target_width, target_height) / max(image.width, h)
            pix_image = image.resize((int(image.width * scale), int(h * scale)), resample=Resampling.LANCZOS)
            pixels = Pixels.from_image(pix_image)
            pixelses.append(pixels)
            caption = f"[{cover.width} x {cover.height}] {humanize.naturalsize(len(image_data), binary=True)}"
            if len(pictures) > 1:
                COMPARISON_BOX_SIZE = 75
                image.thumbnail((COMPARISON_BOX_SIZE, COMPARISON_BOX_SIZE), Resampling.BOX)
                image = image.convert("RGB")
                if reference_image is not None:
                    if image.width != reference_width or image.height != reference_height:
                        caption += " [bold italic]aspect ratio doesn't match[/bold italic]"
                        # TODO: if it's close, stretch and compare
                    else:
                        this_image = numpy.asarray(image)
                        rmse = sqrt(mean_squared_error(reference_image, this_image))
                        caption += f" {_describe_rmse(rmse)}"
                else:
                    reference_image = numpy.asarray(image)
                    (reference_width, reference_height) = image.size
                    caption += " [bold]reference[/bold]"
            captions.append(caption)
    return [pixelses, captions] if captions else [pixelses]


def _describe_rmse(rmse: float) -> str:
    if rmse > 40:
        qualitative = "[bold red]different[/bold red]"
    elif rmse > 10:
        qualitative = "[bold]similar[/bold]"
    elif rmse > 1:
        qualitative = "[bold green]very similar[/bold green]"
    else:
        qualitative = "[bold green]same[/bold green]"
    return f"{qualitative} [italic]RMSE={rmse:.1f}[/italic]"
