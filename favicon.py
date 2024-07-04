#!/usr/bin/env python

import sys
import re

from pprint import pprint
from dataclasses import dataclass
from enum import Enum

import PIL.Image


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


PALETTE = {
    "background": (0, 0, 0, 0),
    "body": (255, 255, 255, 255),
    "border": (0, 0, 0, 255),
    "border rounding": (127, 127, 127, 255),
    "shadow": (0, 0, 0, 127),
}


def produce_ico_file(source):
    assert source.width == 32 and source.height == 32
    target = PIL.Image.new("RGBA", (32, 32), None)
    for y, row in enumerate(source.data):
        for x, px in enumerate(row):
            value = PALETTE[source.palette[px]]
            target.putpixel((x, y), value)
    target.save("favicon.ico", "ICO")


def main(input_path):
    image = read_image_file(input_path)
    produce_ico_file(image)


if __name__ == "__main__":
    main(*sys.argv[1:])
