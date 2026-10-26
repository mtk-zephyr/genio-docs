# Genio Jailhouse and Zephyr test catalogue

`genio-test-catalogue.pdf` describes the tests that verify and validate
MediaTek Jailhouse and Zephyr on the Genio 510 and Genio 700 EVKs: what each
test does, why it is needed, what it checks, and the output of a passing
run, taken from the test scripts and the logs of the board runs. This is
revision 1.1, for review (2026-10-26). It covers the release that is now
MediaTek Jailhouse v26.1, with 111 tests in 91 entries.

| File | Purpose |
|---|---|
| `genio-test-catalogue.md` | The text: one entry per test |
| `genio-test-catalogue.pdf` | The PDF of revision 1.1 |
| `build-catalogue.py` | Builds the PDF. On top of `../tools/docbuild.py` it sets the test headings, adds page references to test identifiers, and fills in the test index |
| `catalogue.css` | Additions to `../tools/guide.css`: test headings and the index |

## Building

With the Python environment of [`../tools/README.md`](../tools/README.md)
(`../tools/requirements.txt`):

```bash
python3 build-catalogue.py
```

An optional first argument names another source file, and a second one the
output PDF.

## Where the sources of the tests are

The catalogue cites its sources by path, relative to MediaTek's engineering
workspace for these releases:

- the test scripts: `jailhouse/regression.sh`, `jailhouse/scripts/`, and the
  test inmates and tools in `jailhouse/tools-board/`;
- the board logs: `jailhouse/board-logs/`, cited by number;
- the build records: `iot-yocto/rity-jailhouse-move/README.md` and
  `zephyr/build/rel-1.1/README.md`, with the outputs they quote.

These, and the engineering notes that Section 1.5 names, are internal: they
are not in a public repository. The README that Section 1.5 refers to for
the notes' file names is the internal copy. The software that the tests
cover is public: [MediaTek Jailhouse](https://github.com/mtk-jailhouse/jailhouse),
the [Genio Zephyr tree](https://github.com/mtk-zephyr/mtk-zephyr) and the
[Genio Zephyr samples](https://github.com/mtk-zephyr/samples).

## Statements that do not come from a script or a log

| Where | Statement | Source |
|---|---|---|
| Purpose fields | Why each test is needed | Written for the catalogue from the scripts' comments and the engineering notes; explanations, not quotations |
| Checks of the tests without a coded verdict | The pass criteria | The engineering notes and the scripts' headers, as each entry says |
| Chapter 7 | The status of the scripts | Reading the scripts against the logs; Section 7.4 from the record of the script changes of 2026-10-26 |
| Chapter 8 | The proposed coded criteria | A proposal of 2026-10-26, condensed; not implemented |
| Chapter 6 | Results of the host-side checks | The build records, which quote their outputs |

## License

As for the rest of this repository: the catalogue text and PDF under the
[Creative Commons Attribution 4.0 International License](../LICENSE)
(CC BY 4.0), and the build script and stylesheet under the
[Apache License 2.0](../tools/LICENSE).
