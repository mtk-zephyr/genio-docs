#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MediaTek Inc.
"""Build the test catalogue PDF from genio-test-catalogue.md.

usage: build-catalogue.py [source.md] [output.pdf]

Uses the shared machinery of the user guide (../tools/docbuild.py and
guide.css) and adds:
- test headings: a level-4 heading whose text starts with a test identifier
  (R-01, W1-M2-T01, REL-01, IMG-01, HOST-01) is set as a test heading;
- page references for links whose text is a test identifier;
- the test index: a paragraph that reads TEST-INDEX is replaced with a table
  of every test heading, in document order.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

from bs4 import BeautifulSoup  # noqa: E402

from docbuild import (add_footnotes, chapters, cover_html, docinfo_html,  # noqa: E402
	finish, inline, prepare, render, split_source, toc_html)

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "genio-test-catalogue.md"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "genio-test-catalogue.pdf"

ONE_ID = r"(?:(?:R|REL|IMG|HOST)-\d{2}|W1-[A-Z0-9]+(?:-[A-Z0-9]+)*)"
# an identifier, a list (R-07, R-08) or a range (R-25 to R-34)
TEST_ID = re.compile(rf"^({ONE_ID}(?:(?:, | to ){ONE_ID})*)(?=\s|$)")


def count_ids(ids):
	"""The number of tests that a heading's identifiers stand for."""
	m = re.match(r"^([A-Z]+)-(\d+) to [A-Z]+-(\d+)$", ids)
	if m:
		return int(m.group(3)) - int(m.group(2)) + 1
	return len(ids.split(", "))


def tests_and_index(soup):
	"""Marks the test headings and links, and fills in the test index."""
	tests = []
	for h4 in soup.find_all("h4"):
		m = TEST_ID.match(h4.get_text())
		if not m:
			continue
		h4["class"] = (h4.get("class") or []) + ["test"]
		tests.append((m.group(1), h4.get_text()[len(m.group(1)):].strip(), h4["id"]))

	for a in soup.find_all("a", href=True):
		if a["href"].startswith("#") and TEST_ID.match(a.get_text()):
			a["class"] = "xref"

	for p in soup.find_all("p"):
		if p.get_text(strip=True) == "TEST-INDEX":
			rows = "".join(f'<tr><td><a class="xref" href="#{hid}">{tid}</a></td><td>{name}</td></tr>'
				for tid, name, hid in tests)
			p.replace_with(BeautifulSoup(
				f'<table class="test-index"><thead><tr><th>Test</th><th>Name</th></tr></thead>'
				f'<tbody>{rows}</tbody></table>', "html.parser"))
	return tests


def keep_together(soup):
	"""A paragraph stays with the code block, list or table after it, and a
	test's "Last run." with its "Sources."."""
	for p in soup.find_all("p"):
		nxt = p.find_next_sibling()
		first = p.find("strong")
		label = first is not None and p.get_text(strip=True) == first.get_text(strip=True)
		if (nxt is not None and nxt.name == "pre") or (label and nxt is not None) or \
				p.get_text().startswith("Last run."):
			p["class"] = (p.get("class") or []) + ["lead"]


def main():
	title, meta, body_md, revisions = split_source(SRC.read_text())
	rev = revisions[-1] if revisions else ["", "", ""]
	status = meta.get("Document status", "")
	updated = meta.get("Last updated", "")

	soup = prepare(body_md)
	finish(soup)
	tests = tests_and_index(soup)
	keep_together(soup)
	add_footnotes(soup)
	body, toc = chapters(soup)

	cover = cover_html(
		"MediaTek Genio · Test Catalogue",
		"Genio Jailhouse and Zephyr<br/><b>Test Catalogue</b>",
		"Genio 510 and Genio 700 EVKs<br/>Verification and validation",
		[("Applies to", inline(meta.get("Applies to", ""))),
		 ("Software", inline(meta.get("Software", ""))),
		 ("Revision", f"{rev[0]} · {updated}")],
		"This catalogue describes every test that verifies and validates the Jailhouse "
		"hypervisor and Zephyr on the Genio 510 and Genio 700 EVKs: what each test does, "
		"why it is needed, what it checks, and the output of a passing run, taken from the "
		"test scripts and the board logs.",
		status)
	info = docinfo_html([
		("Title", title), ("Document type", "Test catalogue"), ("Status", status),
		("Revision", rev[0]), ("Applies to", inline(meta.get("Applies to", ""))),
		("Software", inline(meta.get("Software", ""))),
		("Tests", str(sum(count_ids(t[0]) for t in tests))), ("Last updated", updated)], revisions)

	OUT.parent.mkdir(parents=True, exist_ok=True)
	render(OUT, title=title,
		description="Test catalogue: verification and validation of Jailhouse and Zephyr on the "
			"Genio 510 and Genio 700 EVKs.",
		keywords="MediaTek, Genio, Jailhouse, Zephyr, test, regression, watchdog, MT8370, MT8390",
		footer=f"Genio Jailhouse and Zephyr Test Catalogue  ·  {status} · Revision {rev[0]} · {updated}",
		parts=[cover, info, toc_html(toc), str(body)],
		css=[HERE / "catalogue.css"])
	print(f"wrote {OUT} ({sum(count_ids(t[0]) for t in tests)} tests in {len(tests)} entries)")


if __name__ == "__main__":
	main()
