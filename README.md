# bastok

[![CI](https://github.com/david-ramsden/bastok/actions/workflows/ci.yml/badge.svg)](https://github.com/david-ramsden/bastok/actions/workflows/ci.yml)

A tokenizer and detokenizer for RISC OS BBC BASIC V (`.ffb`, filetype `&FFB`) files.

The core correctness criterion is the round-trip property:
`tokenize(detokenize(data)) == data`

> All code in this repository was written by [Claude](https://claude.ai/) (Anthropic), with direction and oversight from the repository owner.

## Requirements

Python 3.10 or later. No dependencies beyond the standard library.

## Usage

```bash
# Detokenize a BBC BASIC binary to plain text
python3 bastok.py detokenize input,ffb [output.bas]

# Tokenize plain text back to a BBC BASIC binary
python3 bastok.py tokenize input.bas [output,ffb]
```

### Options

| Option | Command | Description |
|---|---|---|
| `--strip-line-numbers` | `detokenize` | Omit line numbers from detokenized output |
| `--auto-number=N` | `tokenize` | Auto-number unnumbered lines with step N (default 10); numbered lines in the source reset the counter |

If no output file is given, output goes to stdout (detokenize) or stdout in hex (tokenize).

## Format

BBC BASIC V files use a compact binary format:

- Each line: `0x0D  hi  lo  length  <payload>`
- End of file: `0x0D 0xFF`
- Any payload byte `>= 0x7F` is a token
- Three two-byte extended token prefixes: `0xC6` (functions), `0xC7` (commands), `0xC8` (statements)
- Inline line numbers (after `GOTO`, `GOSUB`, `THEN`, `ELSE`, etc.) are packed as `0x8D b0 b1 b2`

See [CLAUDE.md](CLAUDE.md) for a full format reference including the complete token table, dual-context token rules, inline line number encoding, and tokenizer design notes.

## VS Code workflow

A convenient way to work with BBC BASIC sources is to edit detokenized `.bas` files in VS Code and automatically retokenize them on save using the [Run on Save](https://marketplace.visualstudio.com/items?itemName=emeraldwalk.RunOnSave) extension (`emeraldwalk.runonsave`).

**1. Detokenize once to create the editable source:**

```bash
python3 bastok.py --strip-line-numbers detokenize MyProgram,ffb MyProgram.bas
```

**2. Configure Run on Save** in `.vscode/settings.json` to retokenize whenever the `.bas` file is saved:

```json
{
  "emeraldwalk.runonsave": {
    "isEnabled": true,
    "commands": [
      {
        "match": "\\.bas$",
        "cmd": "python3 ${workspaceFolder}/bastok.py tokenize \"${file}\" \"${fileDirname}/${fileBasenameNoExt},ffb\""
      }
    ]
  }
}
```

Each time you save `MyProgram.bas`, the tokenized `MyProgram,ffb` is updated alongside it, ready to transfer to RISC OS.

## Tests

```bash
python3 -m pytest tests/ -q
```

122 tests across 39 real-world corpus files from various RISC OS open-source projects, plus unit tests covering token encoding, boundary rules, inline line numbers, and extended token prefixes.

## Known limitations

A small number of files tokenized by non-standard tokenizers (StrongED's StrongBS compressor, some older RISC OS tools) will not round-trip correctly. These involve:

- Keywords with no forward boundary check (e.g. `TO`, `OR`) tokenizing inside all-caps identifiers
- `THEN` tokenized inside `DATA` statement content by older compilers
- Compressed/crunched BASIC files, which do not use the standard BBC BASIC V tokenized format

See [CLAUDE.md](CLAUDE.md) for details.

## Reference material

Token tables and tokenizer behaviour cross-referenced against:

- [RiscOS/Sources/Programmer/BASIC](https://gitlab.riscosopen.org/RiscOS/Sources/Programmer/BASIC) — ARM assembly source (authoritative)
- [gerph/riscos-basic-detokenise](https://github.com/gerph/riscos-basic-detokenise) — Justin Fletcher, 1997
- [steve-fryatt/tokenize](https://github.com/steve-fryatt/tokenize) — Stephen Fryatt, 2014
- [xania.org: BBC BASIC V format](https://xania.org/200711/bbc-basic-v-format) — Matt Godbolt, 2007

## License

[zlib](LICENSE)
