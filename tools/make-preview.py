#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MediaTek Inc.
"""Render a preview image of a PDF: a few pages side by side, for READMEs.

usage: make-preview.py <document.pdf> <preview.png> [pages]

pages is a comma-separated list, by default 1,6,18 (for the user guide: the
cover, the system overview and running a Zephyr image). Needs pdftoppm
(poppler-utils) and Pillow.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter

PAGE_HEIGHT = 760
GAP, MARGIN = 44, 56
BACKGROUND = (244, 246, 249)


def page_image(pdf, number, tmp):
	prefix = Path(tmp) / f"p{number}"
	subprocess.run(["pdftoppm", "-png", "-r", "110", "-f", str(number), "-l", str(number), "-singlefile",
		str(pdf), str(prefix)], check=True)
	im = Image.open(f"{prefix}.png").convert("RGB")
	return im.resize((round(im.width * PAGE_HEIGHT / im.height), PAGE_HEIGHT), Image.LANCZOS)


def main():
	pdf, out = Path(sys.argv[1]), Path(sys.argv[2])
	pages = [int(p) for p in (sys.argv[3] if len(sys.argv) > 3 else "1,6,18").split(",")]
	with tempfile.TemporaryDirectory() as tmp:
		ims = [page_image(pdf, n, tmp) for n in pages]

	width = sum(im.width for im in ims) + GAP * (len(ims) - 1) + 2 * MARGIN
	height = PAGE_HEIGHT + 2 * MARGIN
	canvas = Image.new("RGB", (width, height), BACKGROUND)

	# soft drop shadows, then the pages
	shadow = Image.new("L", (width, height), 0)
	x = MARGIN
	for im in ims:
		shadow.paste(70, (x + 6, MARGIN + 10, x + im.width + 6, MARGIN + im.height + 10))
		x += im.width + GAP
	shadow = shadow.filter(ImageFilter.GaussianBlur(14))
	canvas.paste(Image.new("RGB", (width, height), (20, 40, 70)), (0, 0), shadow)
	x = MARGIN
	for im in ims:
		canvas.paste(im, (x, MARGIN))
		x += im.width + GAP

	out.parent.mkdir(parents=True, exist_ok=True)
	canvas.save(out, optimize=True)
	print(f"wrote {out} ({width}x{height})")


if __name__ == "__main__":
	main()
