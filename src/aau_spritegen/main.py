import json
import math
from pathlib import Path
from typing import Annotated

import typer
from pyvips import Image
from pyvips.enums import BlendMode
from typer import Option, Typer

from aau_spritegen.model import Sprite, SpriteIcon
from aau_spritegen.services import EnhancedJSONEncoder

app = Typer()


def __resize(img: Image, max_dim: int):
    return img.resize(max_dim / max(img.width, img.height))  # type: ignore


def __compute_columns(images: int, rows: int | None) -> int:
    if rows is None:
        sqrt = math.sqrt(images)
        return round(sqrt)

    return math.ceil(images / rows)


def __compute_rows(images: int, columns: int) -> int:
    return math.ceil(images / columns)


def __validate_sprite_size(rows: int, columns: int, svg_cnt: int):
    if rows * columns < svg_cnt:
        response: str = typer.prompt(
            f"All icons cannot fit into a {columns} by {rows} sprite, would you like to continue? [Y/n]"
        )
        if response not in {"Y", "Yes", "yes", "YES"}:
            raise typer.Abort()


def __generate_sprite(
    gap: int,
    icon_size: int,
    rows: int,
    columns: int,
    svg_files: list[Path],
    pixel_ratio: float = 1,
) -> Sprite:
    icon_size = round(icon_size * pixel_ratio)

    width = gap + columns * (icon_size + gap)
    height = gap + rows * (icon_size + gap)

    sprite_img = Image.black(width, height, bands=4).copy(interpretation="srgb")  # type: ignore
    print(sprite_img.bands)
    sprite_items: dict[str, SpriteIcon] = {}

    left = gap
    top = gap

    for row in range(rows):
        for column in range(columns):
            i = row * columns + column
            if i >= len(svg_files):
                break

            svg_path = svg_files[i]

            with Image.new_from_file(svg_path.as_posix()) as img:  # type: ignore
                img = __resize(img, icon_size)

                sprite_img = sprite_img.composite(img, BlendMode.OVER, x=left, y=top)
                sprite_item = SpriteIcon(
                    x=left,
                    y=top,
                    width=img.width,  # type: ignore
                    height=img.height,  # type: ignore
                    pixel_ratio=pixel_ratio,
                )
                sprite_items[svg_path.stem] = sprite_item

                left += icon_size + gap
        left = gap
        top += icon_size + gap

    return Sprite(sprite_img, sprite_items)


def __write_sprite(
    sprite: Sprite,
    out: Path,
):
    print(f"Writing {out.name} PNG file...")
    sprite.image.write_to_file(out.with_suffix(".png").as_posix())

    print(f"Writing {out.name} JSON file...")
    out.with_suffix(".json").write_text(
        json.dumps(sprite.icons, cls=EnhancedJSONEncoder)
    )


@app.command()
def main(
    svg_dir: Path,
    out_dir: Path,
    gap: Annotated[int, Option("--gap", "-g", help="Gap between icons")] = 5,
    icon_size: Annotated[int, Option("--icon-size", "-s", help="Icon size")] = 20,
    rows: Annotated[
        int | None,
        Option("--rows", "-r", help="Number of rows, will be calculated if not set"),
    ] = None,
    columns: Annotated[
        int | None,
        Option(
            "--columns", "-c", help="Number of columns, will be calculated if not set"
        ),
    ] = None,
):
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_files = list(svg_dir.glob("*.svg"))

    svg_cnt = len(svg_files)
    if columns is None:
        columns = __compute_columns(svg_cnt, rows)
    if rows is None:
        rows = __compute_rows(svg_cnt, columns)

    __validate_sprite_size(rows, columns, svg_cnt)
    print(f"Creating a {rows} by {columns} sprite from {svg_cnt} SVG files...")
    sprite = __generate_sprite(gap, icon_size, rows, columns, svg_files, pixel_ratio=1)
    __write_sprite(sprite, out_dir.joinpath("sprite"))
    sprite = __generate_sprite(gap, icon_size, rows, columns, svg_files, pixel_ratio=2)
    __write_sprite(sprite, out_dir.joinpath("sprite@2x"))


if __name__ == "__main__":
    app()
