#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MediaTek Inc.
"""Build the PDF edition of the Genio Jailhouse/Zephyr user guide.

The Markdown guide is the single source. The shared machinery is in
docbuild.py; this script adds the guide's three figures and assembles it.

usage: build-guide.py [guide.md] [guide.pdf]

By default it reads guide/genio-jailhouse-zephyr-guide.md and writes
build/genio-jailhouse-zephyr-guide.pdf.
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

from docbuild import (AMBER, ARROW_DEFS, MUTED, NAVY, RULE, TINT, add_footnotes, chapters,
	cover_html, docinfo_html, figure, finish, inline, prepare, render, split_source, svg_text,
	toc_html)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "guide" / "genio-jailhouse-zephyr-guide.md"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build" / "genio-jailhouse-zephyr-guide.pdf"


# ----------------------------------------------------------------- figures

def figure_workflow():
	steps = [
		("Build Linux", ["IoT Yocto with", "meta-mediatek-experimental"], "Chapter 3"),
		("Flash the board", ["genio-flash with the", "Jailhouse overlay"], "Chapter 4"),
		("Build Zephyr", ["west workspace and", "the Genio samples"], "Chapter 5"),
		("Run under Jailhouse", ["enable, create a cell,", "load and start Zephyr"], "Chapter 6"),
	]
	w, gap, h = 142, 24, 112
	parts = [f'<svg viewBox="0 0 640 {h + 4}" xmlns="http://www.w3.org/2000/svg">', ARROW_DEFS]
	for i, (title, sub, chap) in enumerate(steps):
		x = i * (w + gap)
		parts.append(f'<rect x="{x + 0.5}" y="0.5" width="{w}" height="{h}" rx="6" fill="{TINT}" stroke="{RULE}"/>')
		parts.append(f'<rect x="{x + 0.5}" y="0.5" width="4" height="{h}" fill="{AMBER}"/>')
		parts.append(f'<circle cx="{x + 24}" cy="24" r="11" fill="{NAVY}"/>')
		parts.append(svg_text(x + 24, 28.5, str(i + 1), 12, 700, "#ffffff", "middle"))
		parts.append(svg_text(x + 14, 56, title, 12.5, 700, NAVY))
		for j, line in enumerate(sub):
			parts.append(svg_text(x + 14, 73 + j * 13, line, 9.6, 400, MUTED))
		parts.append(svg_text(x + 14, 104, chap.upper(), 8, 700, AMBER, spacing=1.2))
		if i < len(steps) - 1:
			parts.append(f'<line x1="{x + w + 5}" y1="{h / 2}" x2="{x + w + gap - 4}" y2="{h / 2}" '
				f'stroke="{NAVY}" stroke-width="1.6" marker-end="url(#arr)"/>')
	parts.append("</svg>")
	return "".join(parts)


def figure_architecture():
	p = ['<svg viewBox="0 0 640 352" xmlns="http://www.w3.org/2000/svg">']

	def cell(x, w, colour, fill, head, lines):
		p.append(f'<rect x="{x + 0.6}" y="0.6" width="{w - 1.2}" height="152" rx="6" fill="{fill}" stroke="{colour}" stroke-width="1.2"/>')
		p.append(f'<path d="M{x + 0.6},30 V6.6 a6,6 0 0 1 6,-6 H{x + w - 6.6} a6,6 0 0 1 6,6 V30 z" fill="{colour}"/>')
		p.append(svg_text(x + 14, 20.5, head, 12, 700, "#ffffff"))
		for i, line in enumerate(lines):
			y = 56 + i * 24
			p.append(f'<circle cx="{x + 18}" cy="{y - 4}" r="2.2" fill="{colour}"/>')
			p.append(svg_text(x + 28, y, line, 11))

	cell(0, 412, NAVY, "#eef3f9", "Root cell: Linux (IoT Yocto)", [
		"All CPUs and devices that no cell takes",
		"Manages Jailhouse: enable, cell create, load, start",
		"Console on UART0",
		"Jailhouse driver and tools",
	])
	cell(428, 212, AMBER, "#fdf4ea", "Inmate cell: Zephyr", [
		"1 or 2 dedicated CPUs",
		"8 MiB of RAM at 0x8000",
		"UART1, GPIO 38/40 (+ AFE)",
		"Console on UART1 (CN3201)",
	])

	p.append(f'<rect x="0" y="168" width="640" height="70" rx="6" fill="{NAVY}"/>')
	p.append(svg_text(18, 193, "Jailhouse hypervisor", 15, 700, "#ffffff"))
	p.append(svg_text(18, 211, "Partitions CPUs, memory and interrupts between the cells", 10.6, 400, "#c9d6e6"))
	p.append(svg_text(18, 227, "Mediates the shared GPIO, EINT and clock gate registers, per pin", 10.6, 400, "#c9d6e6"))

	p.append(svg_text(0, 262, "CPUS OF THE GENIO 510 EVK WITH THE DEFAULT ZEPHYR CELL", 8.6, 700, MUTED, spacing=1.1))
	cpus = [("CPU 0", "Cortex-A55", 0), ("CPU 1", "Cortex-A55", 0), ("CPU 2", "Cortex-A55", 0),
		("CPU 3", "Cortex-A55", 1), ("CPU 4", "Cortex-A78", 0), ("CPU 5", "Cortex-A78", 0)]
	bw, bg = 100, 8
	for i, (name, core, zephyr) in enumerate(cpus):
		x = i * (bw + bg)
		colour = AMBER if zephyr else NAVY
		p.append(f'<rect x="{x}" y="270" width="{bw}" height="48" rx="5" fill="{colour}"/>')
		p.append(svg_text(x + bw / 2, 291, name, 12.5, 700, "#ffffff", "middle"))
		p.append(svg_text(x + bw / 2, 307, core, 9.8, 400, "#ffffff", "middle"))
	p.append(f'<rect x="0" y="334" width="11" height="11" rx="2" fill="{NAVY}"/>')
	p.append(svg_text(17, 343.5, "Linux (root cell)", 10, 400, MUTED))
	p.append(f'<rect x="130" y="334" width="11" height="11" rx="2" fill="{AMBER}"/>')
	p.append(svg_text(147, 343.5, "Zephyr cell", 10, 400, MUTED))
	p.append("</svg>")
	return "".join(p)


def figure_lifecycle():
	p = ['<svg viewBox="0 0 640 196" xmlns="http://www.w3.org/2000/svg">', ARROW_DEFS]
	states = [("Linux only", "Jailhouse disabled", 0, "#ffffff", NAVY),
		("Root cell", "Jailhouse enabled", 170, "#eef3f9", NAVY),
		("Cell shut down", "created, or stopped", 340, "#fdf4ea", AMBER),
		("Cell running", "Zephyr executes", 512, AMBER, AMBER)]
	for name, sub, x, fill, stroke in states:
		text = "#ffffff" if fill == AMBER else NAVY
		subc = "#fff3e3" if fill == AMBER else MUTED
		p.append(f'<rect x="{x + 0.6}" y="44" width="126.8" height="52" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
		p.append(svg_text(x + 64, 66, name, 12, 700, text, "middle"))
		p.append(svg_text(x + 64, 83, sub, 9.6, 400, subc, "middle"))

	def arrow(x1, y1, x2, y2):
		p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{NAVY}" stroke-width="1.4" marker-end="url(#arr)"/>')

	def label(x, y, text, anchor="middle"):
		p.append(f'<text x="{x}" y="{y}" font-family="Noto Sans Mono" font-size="9.4" fill="{NAVY}" text-anchor="{anchor}">{text}</text>')

	arrow(130, 62, 167, 62); label(148, 38, "jailhouse"); label(148, 50, "enable")
	arrow(300, 62, 337, 62); label(318, 38, "cell"); label(318, 50, "create")
	arrow(470, 58, 509, 58); label(490, 38, "cell"); label(490, 50, "start")
	arrow(509, 80, 470, 80); label(490, 106, "cell"); label(490, 118, "shutdown")
	# reload while shut down
	p.append(f'<path d="M384,44 C384,12 424,12 424,44" fill="none" stroke="{NAVY}" stroke-width="1.4" marker-end="url(#arr)"/>')
	label(404, 10, "cell load")
	# destroy: back to the root cell
	p.append(f'<path d="M620,96 C620,170 250,170 250,99" fill="none" stroke="{NAVY}" stroke-width="1.4" stroke-dasharray="4 3" marker-end="url(#arr)"/>')
	label(436, 188, "cell destroy: resources return to Linux")
	# disable
	p.append(f'<path d="M200,96 C200,142 64,142 64,99" fill="none" stroke="{NAVY}" stroke-width="1.4" stroke-dasharray="4 3" marker-end="url(#arr)"/>')
	label(132, 158, "jailhouse disable")
	p.append("</svg>")
	return "".join(p)


def add_figures(soup):
	for pre in soup.find_all("pre"):
		if "Root cell: Linux" in pre.get_text():
			pre.replace_with(BeautifulSoup(figure(figure_architecture(), 2,
				"System overview: Linux and Zephyr run side by side, partitioned by the Jailhouse hypervisor.",
				"narrow"), "html.parser"))
	for para in soup.find_all("p"):
		if para.get_text().startswith("The generic IoT Yocto steps"):
			para.insert_before(BeautifulSoup(figure(figure_workflow(), 1,
				"The workflow of this guide, and the chapters that describe each step."), "html.parser"))
			break
	h = soup.find(id="68-stopping-and-restarting-a-cell")
	if h:
		h.insert_after(BeautifulSoup(figure(figure_lifecycle(), 3,
			"Life cycle of a Zephyr cell, with the <code>jailhouse</code> commands that change its state."),
			"html.parser"))


def main():
	title, meta, body_md, revisions = split_source(SRC.read_text())
	rev = revisions[-1] if revisions else ["", "", ""]
	status = meta.get("Document status", "")
	updated = meta.get("Last updated", "")

	soup = prepare(body_md)
	add_figures(soup)
	finish(soup)
	add_footnotes(soup)
	body, toc = chapters(soup)

	cover = cover_html(
		"MediaTek Genio · User Guide",
		"Running Zephyr alongside Linux with <b>Jailhouse</b>",
		"on the Genio 510 and Genio 700 Evaluation Kits<br/>"
		"Building, flashing and running Linux, the Jailhouse hypervisor and Zephyr",
		[("Applies to", inline(meta.get("Applies to", ""))),
		 ("Software", inline(meta.get("Software", ""))),
		 ("Revision", f"{rev[0]} · {updated}")],
		"This guide describes how to build an IoT Yocto image with the Jailhouse partitioning "
		"hypervisor, flash it to a Genio 510 or Genio 700 EVK, build Zephyr applications, and run "
		"Zephyr on dedicated CPU cores next to Linux: on a Cortex-A55, a Cortex-A78, two cores, or "
		"with the audio front end.",
		status)
	info = docinfo_html([
		("Title", title), ("Document type", "User guide"), ("Status", status),
		("Revision", rev[0]), ("Applies to", inline(meta.get("Applies to", ""))),
		("Software", inline(meta.get("Software", ""))), ("License", inline(meta.get("License", ""))),
		("Last updated", updated)], revisions)

	OUT.parent.mkdir(parents=True, exist_ok=True)
	render(OUT, title=title,
		description="User guide: building, flashing and running Linux, the Jailhouse hypervisor and "
			"Zephyr on the Genio 510 and Genio 700 EVKs.",
		keywords="MediaTek, Genio, Jailhouse, Zephyr, Yocto, MT8370, MT8390",
		footer=f"Jailhouse and Zephyr on Genio EVKs  ·  {status} · Revision {rev[0]} · {updated}",
		parts=[cover, info, toc_html(toc), str(body)])
	print(f"wrote {OUT}")


if __name__ == "__main__":
	main()
