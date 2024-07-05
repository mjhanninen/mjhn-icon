#!/usr/bin/env python

import re
import math

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

import PIL.Image
import PIL.ImageDraw
import numpy as np


@dataclass
class Image:
    width: int
    height: int
    data: list[str]
    palette: dict[str, str]


class ParsingError(Exception):
    def __init__(self, lineno, line, msg):
        self.lineno = lineno
        self.line = line
        self.msg = msg

    def __str__(self):
        if self.lineno is not None and self.line is not None:
            return f"{self.msg}\n  on line {self.lineno}: {self.line}"
        else:
            return self.msg


class ParserState(Enum):
    SEEKING_DEFS = 1
    READING_DEFS = 2
    SEEKING_IMAGE = 3
    READING_IMAGE = 4
    DONE = 5


DEFS_PATTERN = re.compile(r"^([\x21-\x7F])[ \t]+(\S.*)$")


def read_image_file(path):
    state = ParserState.SEEKING_DEFS
    palette = {}
    width = 0
    data = []

    with open(path, "r") as f:
        for ix, line in enumerate(f):
            line = line.rstrip()

            if state == ParserState.SEEKING_DEFS or state == ParserState.READING_DEFS:
                if line == "":
                    if state == ParserState.READING_DEFS:
                        state = ParserState.SEEKING_IMAGE

                    continue

                if m := re.match(DEFS_PATTERN, line):
                    color = m.group(1)
                    label = m.group(2)

                    if color in palette:
                        raise ParsingError(
                            ix + 1,
                            line,
                            f"multiple definitions for same color: {color}",
                        )

                    palette[color] = label

                    if state == ParserState.SEEKING_DEFS:
                        state = ParserState.READING_DEFS

                    continue

                raise ParsingError(ix + 1, line, "expected definition")

            if state == ParserState.SEEKING_IMAGE or state == ParserState.READING_IMAGE:
                if line == "":
                    if state == ParserState.READING_IMAGE:
                        break
                    else:
                        continue

                for px in line:
                    if px not in palette:
                        raise ParsingError(ix + 1, line, f"undefined color: ${px}")

                if state == ParserState.SEEKING_IMAGE:
                    width = len(line)
                    state = ParserState.READING_IMAGE
                else:
                    if len(line) != width:
                        raise ParsingError(ix + 1, line, "inconsistent image width")

                data.append(line)

    if state != ParserState.READING_IMAGE:
        raise ParsingError(None, None, "incomplete image")

    return Image(
        width=width,
        height=len(data),
        data=data,
        palette=palette,
    )


BROWSER_ICON_PALETTE = {
    "background": (0, 0, 0, 0),
    "body": (255, 255, 255, 255),
    "border": (0, 0, 0, 255),
    "shadow": (0, 0, 0, 127),
}


def produce_browser_icon(source):
    assert source.width <= 16 and source.height <= 16
    x_ofs = (16 - source.width) // 2
    y_ofs = (16 - source.height) // 2
    target = PIL.Image.new("RGBA", (16, 16), BROWSER_ICON_PALETTE["background"])
    for y, row in enumerate(source.data):
        for x, px in enumerate(row):
            value = BROWSER_ICON_PALETTE[source.palette[px]]
            target.putpixel((x + x_ofs, y + y_ofs), value)
    target.save("out/mjhn.ico", "ICO")


class SafeZone(Enum):
    RECTANGLE = 1
    CIRCLE = 2


class Masking(Enum):
    NONE = 1
    MAC_OS = 2


@dataclass
class IconSpec:
    full_size: int
    safe_zone_type: SafeZone
    safe_zone_size: float
    masking: Masking


ICON_SPECS = {
    "mjhn-ios-180.png": IconSpec(
        full_size=180,
        safe_zone_type=SafeZone.RECTANGLE,
        safe_zone_size=0.8,
        masking=Masking.NONE,
    ),
    "mjhn-ios-167.png": IconSpec(
        full_size=167,
        safe_zone_type=SafeZone.RECTANGLE,
        safe_zone_size=0.8,
        masking=Masking.NONE,
    ),
    "mjhn-ios-152.png": IconSpec(
        full_size=152,
        safe_zone_type=SafeZone.RECTANGLE,
        safe_zone_size=0.8,
        masking=Masking.NONE,
    ),
    "mjhn-macos-512.png": IconSpec(
        full_size=512,
        safe_zone_type=SafeZone.RECTANGLE,
        safe_zone_size=0.8,
        masking=Masking.MAC_OS,
    ),
    "mjhn-macos-256.png": IconSpec(
        full_size=256,
        safe_zone_type=SafeZone.RECTANGLE,
        safe_zone_size=0.8,
        masking=Masking.MAC_OS,
    ),
    "mjhn-macos-128.png": IconSpec(
        full_size=128,
        safe_zone_type=SafeZone.RECTANGLE,
        safe_zone_size=0.8,
        masking=Masking.MAC_OS,
    ),
    "mjhn-full-192.png": IconSpec(
        full_size=192,
        safe_zone_type=SafeZone.RECTANGLE,
        safe_zone_size=0.9,
        masking=Masking.NONE,
    ),
    "mjhn-full-512.png": IconSpec(
        full_size=512,
        safe_zone_type=SafeZone.RECTANGLE,
        safe_zone_size=0.9,
        masking=Masking.NONE,
    ),
    "mjhn-maskable-192.png": IconSpec(
        full_size=192,
        safe_zone_type=SafeZone.CIRCLE,
        safe_zone_size=0.8,
        masking=Masking.NONE,
    ),
    "mjhn-maskable-512.png": IconSpec(
        full_size=512,
        safe_zone_type=SafeZone.CIRCLE,
        safe_zone_size=0.8,
        masking=Masking.NONE,
    ),
    "mjhn-github-512.png": IconSpec(
        full_size=512,
        safe_zone_type=SafeZone.CIRCLE,
        safe_zone_size=1,
        masking=Masking.NONE,
    ),
}

APP_ICON_PALETTE = {
    "background": (227, 227, 106, 255),
    "body": (255, 255, 255, 255),
    "border": (0, 0, 0, 255),
    "shadow": (15, 31, 63, 255),
}


def calc_safe_size(source: Image, spec: IconSpec):
    if spec.safe_zone_type == SafeZone.RECTANGLE:
        s = max(source.width, source.height)
        m = round(spec.full_size * spec.safe_zone_size)
        assert s <= m, "no can do"
        f = m // s
        return f, f * source.width, f * source.height
    elif spec.safe_zone_type == SafeZone.CIRCLE:
        s = math.sqrt(1 + (source.height / source.width) ** 2) * source.width
        m = spec.full_size * spec.safe_zone_size
        f = math.floor(m / s)
        return f, f * source.width, f * source.height
    else:
        raise Exception("unreachable")


@dataclass
class Pixel:
    x: int
    y: int
    v: str
    n: str | None
    s: str | None
    e: str | None
    w: str | None


def pixels(source: Image) -> Iterable[Pixel]:
    buffer = [source.palette[value] for row in source.data for value in row]
    for y in range(source.height):
        for x in range(source.width):
            ix = y * source.width + x
            yield Pixel(
                x=x,
                y=y,
                v=buffer[ix],
                n=buffer[ix - source.width] if y > 0 else None,
                s=buffer[ix + source.width] if y < source.height - 1 else None,
                w=buffer[ix - 1] if x > 0 else None,
                e=buffer[ix + 1] if x < source.width - 1 else None,
            )


def tuple_avg(x: tuple[float], y: tuple[float]) -> tuple[float]:
    return tuple(np.add(x, y) // 2)


def produce_icon(source: Image, spec: IconSpec, path: str):
    print(f"- Generating: {path}")
    f, sz_x, sz_y = calc_safe_size(source, spec)
    ofs_x = (spec.full_size - sz_x) // 2
    ofs_y = (spec.full_size - sz_y) // 2
    target = PIL.Image.new(
        "RGBA", (spec.full_size, spec.full_size), APP_ICON_PALETTE["background"]
    )
    draw = PIL.ImageDraw.Draw(target)
    for p in pixels(source):
        x = ofs_x + f * p.x
        y = ofs_y + f * p.y
        p1 = (x, y)
        p2 = (x + f - 1, y)
        p3 = (x + f - 1, y + f - 1)
        p4 = (x, y + f - 1)
        if color := APP_ICON_PALETTE.get(p.v):
            draw.rectangle((p1, p3), color)
        elif p.v == "corner rounding (orientation 1)":
            if p.n is None and p.e is not None:
                v1 = p.e
            elif p.n is not None and p.e is None:
                v1 = p.n
            elif p.n == p.e:
                v1 = p.n
            else:
                v1 = (p.n, p.e)  # indeterminate
            if p.s is None and p.w is not None:
                v2 = p.w
            elif p.s is not None and p.w is None:
                v2 = p.s
            elif p.s == p.w:
                v2 = p.s
            else:
                v2 = (p.s, p.w)  # indeterminate
            if type(v1) is tuple and type(v2) is tuple:
                raise Exception(f"cannot determine corner rounding: {p}")
            elif type(v1) is tuple:
                v1 = v1[0] if v1[0] != v2 else v1[1]
            elif type(v2) is tuple:
                v2 = v2[0] if v2[0] != v1 else v2[1]
            c1 = APP_ICON_PALETTE[v1]
            c2 = APP_ICON_PALETTE[v2]
            c3 = tuple_avg(c1, c2)
            draw.rectangle((p1, p3), c2)
            draw.polygon((p1, p2, p3), c1)
            draw.line((p1, p3), c3)
        elif p.v == "corner rounding (orientation 2)":
            if p.n is None and p.w is not None:
                v1 = p.w
            elif p.n is not None and p.w is None:
                v1 = p.n
            elif p.n == p.w:
                v1 = p.n
            else:
                v1 = (p.n, p.w)  # indeterminate
            if p.s is None and p.e is not None:
                v2 = p.e
            elif p.s is not None and p.e is None:
                v2 = p.s
            elif p.s == p.e:
                v2 = p.s
            else:
                v2 = (p.s, p.e)  # indeterminate
            if type(v1) is tuple and type(v2) is tuple:
                raise Exception(f"cannot determine corner rounding: {p}")
            elif type(v1) is tuple:
                v1 = v1[0] if v1[0] != v2 else v1[1]
            elif type(v2) is tuple:
                v2 = v2[0] if v2[0] != v1 else v2[1]
            c1 = APP_ICON_PALETTE[v1]
            c2 = APP_ICON_PALETTE[v2]
            c3 = tuple_avg(c1, c2)
            draw.rectangle((p1, p3), c1)
            draw.polygon((p3, p4, p2), c2)
            draw.line((p4, p2), c3)
        else:
            raise Exception(f"unhandle: {p.v}")
    target.save(f"out/{path}", "PNG")


def main():
    master_tiny = read_image_file("./mjhn-icon-tiny.txt")
    master_normal = read_image_file("./mjhn-icon.txt")
    produce_browser_icon(master_tiny)
    for path, spec in ICON_SPECS.items():
        produce_icon(master_normal, spec, path)


if __name__ == "__main__":
    main()
