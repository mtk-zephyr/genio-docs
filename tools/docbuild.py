# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MediaTek Inc.

"""Shared PDF build machinery for the docs in this directory tree.

A document is a Markdown file with:
  - the title on its first line, then a document information table;
  - a "## Contents" section (replaced by a contents page with page numbers);
  - chapters "## <n>. <title>" with sections "### <n>.<m> <title>";
  - a "## Revision history" table at the end (moved to the information page).

prepare() turns the body into HTML; a document's own script may then add
figures or tables; finish() applies the rest. assemble() and render() build
the cover, the information page, the contents and the PDF, with guide.css
and any extra stylesheets.

Needs Python packages weasyprint, markdown-it-py, beautifulsoup4 and
pygments, and the Lato and Noto Sans Mono fonts.
"""

import re
from pathlib import Path

import weasyprint
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

HERE = Path(__file__).resolve().parent
GUIDE_CSS = HERE / "guide.css"

NAVY, AMBER, TEAL = "#14365d", "#d9892b", "#1f7a74"
MUTED, RULE, TINT, INK = "#5c6b7c", "#d3dae3", "#f4f6f9", "#1d2733"


def slug(text):
	"""GitHub's heading anchor."""
	text = text.strip().lower().replace("`", "")
	text = re.sub(r"[^\w\- ]", "", text)
	return text.replace(" ", "-")


def _code_highlight(code, lang, attrs):
	try:
		lexer = get_lexer_by_name(lang) if lang else None
	except ClassNotFound:
		lexer = None
	if not lexer:
		return ""	# markdown-it escapes the code itself
	return highlight(code, lexer, HtmlFormatter(nowrap=True))


md = MarkdownIt("commonmark", {"html": True, "highlight": _code_highlight})
md.enable("table")
inline = md.renderInline


# ------------------------------------------------------------------ source

def split_source(text):
	"""Returns the title, the information table, the body and the revisions."""
	lines = text.splitlines()
	title = lines[0].lstrip("# ").strip()

	meta = {}
	for line in lines[1:]:
		if line.startswith("## "):
			break
		m = re.match(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$", line)
		if m and m.group(1) not in ("", "---"):
			meta[m.group(1)] = m.group(2)

	body_start = text.index("\n## 1. ")
	rev_start = text.index("\n## Revision history")
	body = text[body_start:rev_start]

	revisions = []
	for line in text[rev_start:].splitlines():
		cells = [c.strip() for c in line.strip().strip("|").split("|")]
		if len(cells) == 3 and cells[0] != "Revision" and not set(cells[0]) <= set("-"):
			revisions.append(cells)
	return title, meta, body, revisions


# ------------------------------------------------------------ SVG helpers

ARROW_DEFS = f"""
<defs>
  <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="{NAVY}"/>
  </marker>
</defs>"""


def svg_text(x, y, text, size=11, weight=400, fill=INK, anchor="start", spacing=0, family="Lato"):
	return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
		f'fill="{fill}" text-anchor="{anchor}" letter-spacing="{spacing}">{text}</text>')


def figure(svg, number, caption, cls=""):
	return f'<figure class="{cls}">{svg}<figcaption><b>FIGURE {number}</b>&#160;&#160;{caption}</figcaption></figure>'


ICON_NOTE = ('<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="9" fill="none" stroke="#2a6bb0" stroke-width="1.6"/>'
	'<rect x="9" y="8.2" width="2" height="6.6" rx="0.8" fill="#2a6bb0"/><circle cx="10" cy="5.6" r="1.25" fill="#2a6bb0"/></svg>')
ICON_CAUTION = ('<svg viewBox="0 0 20 20"><path d="M10 1.8 L19 17.8 H1 Z" fill="none" stroke="#b8541b" stroke-width="1.6" stroke-linejoin="round"/>'
	'<rect x="9" y="7" width="2" height="6" rx="0.8" fill="#b8541b"/><circle cx="10" cy="15.2" r="1.2" fill="#b8541b"/></svg>')


def cover_band():
	arcs = "".join(f'<circle cx="210" cy="0" r="{r}" fill="none" stroke="#2c5a8c" stroke-width="0.35" opacity="{0.75 - r / 420:.2f}"/>'
		for r in range(36, 260, 14))
	return (f'<svg width="210mm" height="168mm" viewBox="0 0 210 168" xmlns="http://www.w3.org/2000/svg">{arcs}'
		f'<rect x="24" y="128" width="34" height="0.9" fill="{AMBER}"/></svg>')


# ------------------------------------------------------------- transforms

def prepare(body_md):
	"""Markdown body to HTML: heading anchors, code labels, call-outs."""
	soup = BeautifulSoup(md.render(body_md), "html.parser")

	for hr in soup.find_all("hr"):
		hr.decompose()

	for h in soup.find_all(["h2", "h3", "h4"]):
		h["id"] = slug(h.get_text())

	# **Host** / **Board** on its own line labels the code block after it
	for strong in soup.find_all("strong"):
		p = strong.parent
		if p.name != "p" or p.get_text(strip=True) not in ("Host", "Board"):
			continue
		pre = p.find_next_sibling()
		if not pre or pre.name != "pre":
			continue
		kind = p.get_text(strip=True)
		box = soup.new_tag("div", attrs={"class": f"codeblock {kind.lower()}"})
		lab = soup.new_tag("div", attrs={"class": "codelabel"})
		lab.string = kind
		pre.wrap(box)
		box.insert(0, lab)
		p.decompose()

	# > **Note:** / > **Caution:** become call-out boxes
	for bq in soup.find_all("blockquote"):
		boxes = []
		for para in bq.find_all("p", recursive=False):
			first = para.find("strong")
			kind = first.get_text(strip=True).rstrip(":").lower() if first else "note"
			if first and kind in ("note", "caution"):
				first.decompose()
				if para.contents and isinstance(para.contents[0], str):
					para.contents[0].replace_with(para.contents[0].lstrip())
			else:
				kind = "note"
			box = BeautifulSoup(
				f'<div class="callout {kind}"><span class="callout-label">'
				f'{ICON_NOTE if kind == "note" else ICON_CAUTION}{kind}</span></div>', "html.parser").div
			box.append(para.extract())
			boxes.append(box)
		if len(boxes) > 1:
			pair = soup.new_tag("div", attrs={"class": "callout-pair"})
			for box in boxes:
				pair.append(box)
			boxes = [pair]
		for box in reversed(boxes):
			bq.insert_after(box)
		bq.decompose()

	return soup


def finish(soup):
	"""Short tables stay on one page and code blocks with their lead-in; section numbers; page references."""
	for table in soup.find_all("table"):
		if len(table.find_all("tr")) <= 13:
			table["class"] = (table.get("class") or []) + ["keep"]
			lead = table.find_previous_sibling()
			if lead and lead.name == "p":
				lead["class"] = (lead.get("class") or []) + ["lead"]

	# a paragraph that introduces a code block ("...:") stays with it
	for box in soup.find_all("div", class_="codeblock"):
		lead = box.find_previous_sibling()
		if lead and lead.name == "p" and lead.get_text().rstrip().endswith(":"):
			lead["class"] = (lead.get("class") or []) + ["lead"]

	for h3 in soup.find_all("h3"):
		m = re.match(r"^(\d+\.\d+)\s+(.*)$", h3.decode_contents(), re.S)
		if m:
			h3.clear()
			h3.append(BeautifulSoup(f'<span class="secnum">{m.group(1)}</span>{m.group(2)}', "html.parser"))

	for a in soup.find_all("a", href=True):
		if a["href"].startswith("#") and re.match(r"(Section|Table|Figure) ", a.get_text()):
			a["class"] = "xref"
	return soup


def add_footnotes(soup, skip_id=None):
	"""A footnote with the address of each web link, at its first use."""
	seen = set()
	for a in soup.find_all("a", href=True):
		href = a["href"]
		if not href.startswith("http") or a.get_text().strip() == href:
			continue
		if (skip_id and a.find_parent(id=skip_id)) or href in seen:
			continue
		seen.add(href)
		note = soup.new_tag("span", attrs={"class": "footnote"})
		note.string = href
		a.insert_after(note)


def chapters(soup):
	"""Wraps each chapter in a section with an opener; returns it and the TOC."""
	out = BeautifulSoup("", "html.parser")
	toc = []
	section = None
	for node in list(soup.children):
		if getattr(node, "name", None) == "h2":
			m = re.match(r"^(\d+)\.\s+(.*)$", node.get_text())
			num, title = (m.group(1), m.group(2)) if m else ("", node.get_text())
			section = out.new_tag("section", attrs={"class": "chapter"})
			out.append(section)
			section.append(BeautifulSoup(
				f'<div class="chapter-head"><div class="chapter-num">{int(num):02d}</div>'
				f'<h2 id="{node["id"]}" data-label="{num} · {title}">{title}</h2>'
				f'<ul class="chapter-toc"></ul></div>', "html.parser"))
			toc.append((num, title, node["id"], []))
			continue
		if section is not None:
			section.append(node.extract() if hasattr(node, "extract") else node)

	for sec, entry in zip(out.find_all("section"), toc):
		ctoc = sec.find("ul", class_="chapter-toc")
		for h3 in sec.find_all("h3"):
			num = h3.find("span", class_="secnum")
			numtext = num.get_text() if num else ""
			title = h3.get_text()[len(numtext):]
			ctoc.append(BeautifulSoup(f'<li><a href="#{h3["id"]}"><span class="num">{numtext}</span>{title}</a></li>',
				"html.parser"))
			entry[3].append((numtext, title, h3["id"]))
		if not ctoc.find("li"):
			ctoc.decompose()
	return out, toc


def toc_html(toc):
	items = []
	for num, title, hid, subs in toc:
		items.append(f'<li class="toc-chapter"><a href="#{hid}"><span class="num">{num}</span>{title}</a></li>')
		for snum, stitle, sid in subs:
			items.append(f'<li class="toc-section"><a href="#{sid}"><span class="num">{snum}</span>{stitle}</a></li>')
	return '<div class="front toc"><h1 id="contents">Contents</h1><ul>' + "".join(items) + "</ul></div>"


# ---------------------------------------------------------------- assembly

def cover_html(overline, title_html, subtitle_html, meta_rows, abstract, status):
	rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in meta_rows)
	return f"""
<div class="cover">
  <div class="cover-band">{cover_band()}</div>
  <div class="cover-overline">{overline}</div>
  <div class="cover-title">{title_html}</div>
  <div class="cover-subtitle">{subtitle_html}</div>
  <div class="cover-rule"></div>
  <table class="cover-meta">{rows}</table>
  <div class="cover-abstract">{abstract}</div>
  <div class="cover-status">{status}</div>
  <div class="cover-brand">MediaTek <b>Genio</b></div>
</div>"""


def docinfo_html(rows, revisions, extra=""):
	info = "".join(f"<tr><td><b>{k}</b></td><td>{v}</td></tr>" for k, v in rows)
	revs = "".join(f"<tr><td>{r}</td><td>{d}</td><td>{inline(c)}</td></tr>" for r, d, c in revisions)
	return f"""
<div class="front">
  <h1 id="document-information">Document information</h1>
  <table><tbody>{info}</tbody></table>
  {extra}
  <h5>Revision history</h5>
  <table>
    <thead><tr><th style="width:18mm">Revision</th><th style="width:28mm">Date</th><th>Changes</th></tr></thead>
    <tbody>{revs}</tbody>
  </table>
</div>"""


def render(out, *, title, description, keywords, footer, parts, css=()):
	html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<meta name="author" content="MediaTek Inc."/>
<meta name="description" content="{description}"/>
<meta name="keywords" content="{keywords}"/>
</head>
<body data-status="{footer}">
{"".join(parts)}
</body>
</html>"""
	sheets = [weasyprint.CSS(filename=str(GUIDE_CSS))] + [weasyprint.CSS(filename=str(c)) for c in css]
	weasyprint.HTML(string=html, base_url=str(HERE)).write_pdf(out, stylesheets=sheets)
	return html
