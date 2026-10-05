# Building the PDFs

The PDFs are generated from the Markdown sources in this repository. Do not
edit a PDF; change the Markdown and rebuild.

| File | Purpose |
|---|---|
| `build-guide.py` | Builds the user guide: adds its three figures and assembles it with `docbuild.py` |
| `docbuild.py` | The machinery shared by all documents: Markdown, labelled code blocks, call-outs, footnotes, chapters, contents, cover, information page, rendering with WeasyPrint |
| `guide.css` | Print stylesheet (A4, CSS Paged Media) |
| `make-preview.py` | Renders a few pages of a PDF side by side, for the READMEs |
| `requirements.txt` | Python packages, at the tested versions |
| `LICENSE` | Apache License 2.0, for everything in this directory and `.github/` |

## Building locally

On Ubuntu 24.04:

```bash
sudo apt install fonts-lato fonts-noto-mono poppler-utils python3-venv
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements.txt
.venv/bin/python tools/build-guide.py
```

Run the commands from the repository root. The PDF is written to
`build/genio-jailhouse-zephyr-guide.pdf`.

To update the preview image after the guide's cover or layout changed:

```bash
.venv/bin/python tools/make-preview.py build/genio-jailhouse-zephyr-guide.pdf assets/guide-preview.png
```

## What the build expects of the Markdown

- The title on the first line, and the document information table before
  `## Contents`. The `## Contents` section is replaced by a contents page
  with page numbers.
- Chapters as `## <n>. <title>`, sections as `### <n>.<m> <title>`.
- A `## Revision history` table at the end; it moves to the document
  information page.
- `**Host**` or `**Board**` on its own line directly before a code block
  labels that block.
- `> **Note:**` and `> **Caution:**` block quotes become call-out boxes.
- Links to `#<section anchor>` whose text starts with "Section", "Table" or
  "Figure" get a page reference.
- For the user guide, `build-guide.py` places its figures by anchors in the
  text: the diagram in Section 1.3, which contains `Root cell: Linux`, is
  replaced by Figure 2; Figure 1 goes before the paragraph that starts with
  "The generic IoT Yocto steps"; Figure 3 goes after the heading of
  Section 6.8. Keep these anchors, or update the script, when you edit
  those places.
