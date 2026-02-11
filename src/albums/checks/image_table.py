import io
import logging
from math import sqrt
from pathlib import Path
from typing import Any, List

import humanize
import numpy
from PIL import Image, UnidentifiedImageError
from rich.console import RenderableType
from rich_pixels import Pixels
from skimage.metrics import mean_squared_error  # pyright: ignore[reportUnknownVariableType]

from ..app import Context
from ..library.metadata import get_embedded_image_data
from ..types import Album, Picture

logger = logging.getLogger(__name__)


def render_image_table(
    ctx: Context, album: Album, pictures: list[Picture], picture_sources: dict[Picture, list[tuple[str, bool]]]
) -> List[List[RenderableType]]:
    pixelses: list[RenderableType] = []
    target_width = int((ctx.console.width - 3) / len(pictures))
    target_height = (ctx.console.height - 10) * 2
    captions: list[RenderableType] = []
    reference_image: numpy.ndarray[Any] | None = None
    reference_width = reference_height = 0
    for cover in pictures:
        (filename, embedded) = picture_sources[cover][0]
        path = (ctx.library_root if ctx.library_root else Path(".")) / album.path / filename
        if embedded:
            images = get_embedded_image_data(path)
            image_data = images[cover.embed_ix]
        else:
            with open(path, "rb") as f:
                image_data = f.read()
        try:
            image = Image.open(io.BytesIO(image_data))
        except UnidentifiedImageError as ex:
            logger.error(f"failed to read image {str(path)}: {repr(ex)}")
            image = None

        if image:
            h = (7 / 8) * image.height  # TODO try to determine appropriate height scaling for terminal font or make configurable
            scale = min(target_width, target_height) / max(image.width, h)
            pixels = Pixels.from_image(image, (int(image.width * scale), int(h * scale)))
            pixelses.append(pixels)
            caption = f"[{cover.width} x {cover.height}] {humanize.naturalsize(len(image_data), binary=True)}"
            if len(pictures) > 1:
                COMPARISON_BOX_SIZE = 75
                image.thumbnail((COMPARISON_BOX_SIZE, COMPARISON_BOX_SIZE), Image.Resampling.BOX)
                image = image.convert("RGB")
                if reference_image is not None:
                    if image.width != reference_width or image.height != reference_height:
                        caption += " [bold italic]aspect ratio doesn't match[/bold italic]"
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
