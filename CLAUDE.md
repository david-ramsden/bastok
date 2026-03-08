# bastok — BBC BASIC V tokenizer/detokenizer

## Project overview

`bastok.py` detokenizes and retokenizes RISC OS BBC BASIC V (`.ffb`, filetype `&FFB`) binary files. The round-trip property — `tokenize(detokenize(data)) == data` — is the core correctness criterion.

## Key commands

```bash
# Run all tests (122 tests, 39 corpus files)
python3 -m pytest tests/test_bastok.py -q

# CLI usage
python3 bastok.py detokenize input,ffb [output.bas]
python3 bastok.py tokenize   input.bas  [output,ffb]
```

## Reference material (cloned locally)

```
/tmp/riscos-basic/          # https://gitlab.riscosopen.org/RiscOS/Sources/Programmer/BASIC
/tmp/riscos-basic-detokenise/  # https://github.com/gerph/riscos-basic-detokenise
/tmp/tokenize/              # https://github.com/steve-fryatt/tokenize
```

Key authoritative files:
- `/tmp/riscos-basic/hdr/Tokens` — complete token table with symbol names
- `/tmp/riscos-basic/s/Lexical` — ARM assembly for MATCH (tokenizer) and TOKOUT (detokenizer)
- `/tmp/tokenize/src/parse.c` — C implementation with full keyword table including abbreviation lengths and action flags

## File format

### Line structure
Each line: `0x0D  hi  lo  length  <payload>`
- `hi`/`lo`: 16-bit line number, big-endian
- `length`: total bytes in this record including the 4 header bytes (so payload = length − 4)
- End of file: `0x0D 0xFF`
- Maximum line number: 65279 (`0xFEFF`); `0xFFFF` is the EOF marker
- Maximum total line length: 255 bytes → maximum payload: 251 bytes

### Token ranges
- Any byte `>= 0x7F` in payload is a token
- `0x8D`: inline line number marker (3 encoded bytes follow, see below)
- Single-byte tokens: `0x7F`–`0xC5`, `0xC9`–`0xFF`
- Two-byte extended tokens: prefix `0xC6`/`0xC7`/`0xC8` + sub-byte `>= 0x8E`

### Single-byte token table (from hdr/Tokens, starting at 0x7F)
```
0x7F OTHERWISE    0x80 AND       0x81 DIV       0x82 EOR       0x83 MOD
0x84 OR           0x85 ERROR     0x86 LINE      0x87 OFF       0x88 STEP
0x89 SPC          0x8A TAB(      0x8B ELSE*     0x8C THEN      0x8D (TCONST)
0x8E OPENIN       0x8F PTR*      0x90 PAGE*     0x91 TIME*     0x92 LOMEM*
0x93 HIMEM*       0x94 ABS       0x95 ACS       0x96 ADVAL     0x97 ASC
0x98 ASN          0x99 ATN       0x9A BGET      0x9B COS       0x9C COUNT
0x9D DEG          0x9E ERL       0x9F ERR       0xA0 EVAL      0xA1 EXP
0xA2 EXT          0xA3 FALSE     0xA4 FN        0xA5 GET       0xA6 INKEY
0xA7 INSTR(       0xA8 INT       0xA9 LEN       0xAA LN        0xAB LOG
0xAC NOT          0xAD OPENUP    0xAE OPENOUT   0xAF PI        0xB0 POINT(
0xB1 POS          0xB2 RAD       0xB3 RND       0xB4 SGN       0xB5 SIN
0xB6 SQR          0xB7 TAN       0xB8 TO        0xB9 TRUE      0xBA USR
0xBB VAL          0xBC VPOS      0xBD CHR$      0xBE GET$      0xBF INKEY$
0xC0 LEFT$(       0xC1 MID$(     0xC2 RIGHT$(   0xC3 STR$      0xC4 STRING$(
0xC5 EOF
0xC6 (TESCFN prefix)  0xC7 (TESCCOM prefix)  0xC8 (TESCSTMT prefix)
0xC9 WHEN         0xCA OF        0xCB ENDCASE   0xCC ELSE†     0xCD ENDIF
0xCE ENDWHILE     0xCF PTR†      0xD0 PAGE†     0xD1 TIME†     0xD2 LOMEM†
0xD3 HIMEM†       0xD4 SOUND     0xD5 BPUT      0xD6 CALL      0xD7 CHAIN
0xD8 CLEAR        0xD9 CLOSE     0xDA CLG       0xDB CLS       0xDC DATA
0xDD DEF          0xDE DIM       0xDF DRAW      0xE0 END       0xE1 ENDPROC
0xE2 ENVELOPE     0xE3 FOR       0xE4 GOSUB     0xE5 GOTO      0xE6 GCOL
0xE7 IF           0xE8 INPUT     0xE9 LET       0xEA LOCAL     0xEB MODE
0xEC MOVE         0xED NEXT      0xEE ON        0xEF VDU       0xF0 PLOT
0xF1 PRINT        0xF2 PROC      0xF3 READ      0xF4 REM       0xF5 REPEAT
0xF6 REPORT       0xF7 RESTORE   0xF8 RETURN    0xF9 RUN       0xFA STOP
0xFB COLOUR       0xFC TRACE     0xFD UNTIL     0xFE WIDTH     0xFF OSCLI
```
`*` = RHS/expression form of dual-context keyword
`†` = LHS/statement-start form of dual-context keyword

### Dual-context tokens
Several keywords have different token values depending on context:

| Keyword | LHS/stmt-start form | RHS/expr form |
|---------|---------------------|---------------|
| ELSE    | 0xCC (line start only) | 0x8B |
| PTR     | 0xCF | 0x8F |
| PAGE    | 0xD0 | 0x90 |
| TIME    | 0xD1 | 0x91 |
| LOMEM   | 0xD2 | 0x92 |
| HIMEM   | 0xD3 | 0x93 |

ELSE is special: 0xCC only when it is the first non-whitespace token on a source line (structured `ELSE` block). When inline (after `:` or inside `IF...THEN...ELSE`), it is 0x8B.

### Two-byte extended token tables
All three prefix bytes index one shared keyword list (`_EXT_KEYWORDS`), each with a different base offset. Sub-byte must be `>= 0x8E`.

```
Prefix 0xC8 (ESCSTMT), base offset 0x8E — sub-bytes:
  0x8E CASE    0x8F CIRCLE   0x90 FILL     0x91 ORIGIN   0x92 POINT
  0x93 RECTANGLE  0x94 SWAP  0x95 WHILE    0x96 WAIT     0x97 MOUSE
  0x98 QUIT    0x99 SYS      0x9A INSTALL* 0x9B LIBRARY  0x9C TINT
  0x9D ELLIPSE 0x9E BEATS    0x9F TEMPO    0xA0 VOICES   0xA1 VOICE
  0xA2 STEREO  0xA3 OVERLAY

Prefix 0xC7 (ESCCOM), base offset 0x78 — sub-bytes:
  0x8E APPEND  0x8F AUTO     0x90 CRUNCH   0x91 DELETE   0x92 EDIT
  0x93 HELP    0x94 LIST     0x95 LOAD     0x96 LVAR     0x97 NEW
  0x98 OLD     0x99 RENUMBER 0x9A SAVE     0x9B TEXTLOAD 0x9C TEXTSAVE
  0x9D TWIN    0x9E TWINO    0x9F INSTALL

Prefix 0xC6 (ESCFN), base offset 0x66 — sub-bytes:
  0x8E SUM     0x8F BEAT
```
`*` = INSTALL at 0xC8 0x9A is a legacy "silly blunder" per the RISC OS source; the canonical INSTALL is 0xC7 0x9F. Both decode to INSTALL; the tokenizer emits 0xC8 0x9A (first in table).

### Inline line numbers
After `GOTO`/`GOSUB`/`RESTORE`/`THEN`/`ELSE`/`ON`, line numbers are packed as `0x8D b0 b1 b2`:
```
encode: b0 = (((N & 0xC0) >> 2) | ((N & 0xC000) >> 12)) ^ 0x54
        b1 = (N & 0x3F) | 0x40        -- low 6 bits of lo byte
        b2 = ((N & 0x3F00) >> 8) | 0x40  -- low 6 bits of hi byte
decode: x  = b0 ^ 0x54
        lo = ((x & 0x30) << 2) | (b1 & 0x3F)
        hi = ((x & 0x0C) << 4) | (b2 & 0x3F)
        N  = (hi << 8) | lo
```
Example: line 139 (`0x008B`) encodes as `0x74 0x4B 0x40`.

All three bytes stay in `0x40`–`0x7F`, avoiding token bytes and `0x0D`. The XOR `0x54` (not `0x40`) packs the top 2 bits of each byte into b0 — it is the CONSTI routine from `s/Lexical` directly. The `0x54` value derives from a 6502 optimization (see xania.org part 2).

Also encoded after: `TRACE`, `LIST`, `DELETE`, `RENUMBER`, `AUTO` (per `s/Lexical` CONSTA flag, action byte bit 4 set). Note: `TRACE` was missing from `_LINENUM_TOKS` in an earlier version of `bastok.py` and has been corrected.

## Tokenizer design

### MATCH routine overview (from `s/Lexical`)
The RISC OS tokenizer walks alphabetical keyword trie tables (`PLEXA`–`PLEXW`). Each keyword entry ends with a token byte followed by an **action byte**:

```
Bit 0: WORDCQ — forward boundary check: reject if next char is A-Z, a-z, 0-9, _, or .
Bit 1: transfer to right/expression mode (MODE=1)
Bit 2: transfer to left mode (MODE=0); OR: two-byte token is a function token
Bit 3: two-byte token — emit prefix (0xC6/C7/C8) before token byte
Bit 4: constants may follow — encode subsequent line numbers as 0x8D packed
Bit 5: give up / literal mode — copy rest of line verbatim (REM, DATA, EDIT)
Bit 6: polymorphic statement — if MODE=0 (left), add offset to get LHS token value
Bit 7: keyword contains own opening bracket (e.g. INSTR(, TAB()
```

### Forward boundary check (WORDCQ)
Keywords with action byte **bit 0 SET** are blocked if the next source character is alphanumeric, `_`, or `.`. Keywords with **bit 0 CLEAR** tokenize unconditionally (even directly before a letter).

**Keywords WITHOUT WORDCQ** (bit 0 clear — no forward boundary check):
`AND`, `OR`, `EOR`, `DIV`, `MOD`, `NOT`, `THEN`, `ELSE`, `OTHERWISE`, `TO`, `STEP`, `OF`, `ON`, `ERROR`, `LINE`, `OFF`, `SPC`, `REPEAT`, `UNTIL`, `RESTORE`, `TRACE`, `DRAW`, `MOVE`, `PLOT`, `CHAIN`, `QUIT`, `ENVELOPE`, `FOR`, `LOCAL`, `WHEN`, `NEXT`, `WIDTH`, `CALL`, `GOSUB`, `GOTO`, `LET`, `PROC`, `IF`, `DIM`, `INPUT`, `PRINT`, `READ`, `COLOUR`, `GCOL`, `MODE`, `SOUND`, `VDU`, `OSCLI`, `ABS`, `ACS`, `ADVAL`, `ASC`, `ASN`, `ATN`, `COS`, `DEG`, `EVAL`, `EXP`, `GET`, `INKEY`, `INT`, `LEN`, `LN`, `LOG`, `OPENIN`, `OPENOUT`, `OPENUP`, `RAD`, `SGN`, `SIN`, `SQR`, `TAN`, `USR`, `VAL`, `REM`, `DATA` — and all keywords ending in `(` or `$` (boundary is irrelevant since those chars aren't ident-starters).

**Keywords WITH WORDCQ** (bit 0 set — blocked before letter/digit/_/.):
`BGET`, `BPUT`, `CLEAR`, `CLG`, `CLOSE`, `CLS`, `COUNT`, `END`, `ENDCASE`, `ENDIF`, `ENDPROC`, `ENDWHILE`, `EOF`, `ERL`, `ERR`, `EXT`, `FALSE`, `HIMEM`, `LOMEM`, `PAGE`, `PI`, `POS`, `PTR`, `REPORT`, `RETURN`, `RND`, `RUN`, `STOP`, `TIME`, `TRUE`, `VPOS`, `WAIT` — plus extended tokens: `HELP`, `LVAR`, `NEW`, `OLD`, `TWIN`.

**Practical effects**: `RUNNING` is `R`+`U`+`N`+`N`+`I`+`N`+`G` (all ASCII), `STOPPER` is `S`+`TO`+`PPER` (TO has no WORDCQ), `UNTILEOF#A%` is `UNTIL`+`EOF`+`#A%` (UNTIL has no WORDCQ).

### Underscore backward boundary
A keyword is blocked if the preceding byte in the output is `_` (ASCII 0x5F). This handles `PROC_ERROR` — the `_ERROR` part stays ASCII because `_` precedes `ERROR`. This check applies to both single-byte and extended tokens.

### No general backward boundary
There is no general backward boundary check. `AND`, `OR`, `EOR`, etc. tokenize after any character except `_`. This is correct: `statnetAND&FF` → `statnet` + `AND`(token) + `&FF`. BBC BASIC uses lowercase for variable names; uppercase keywords after lowercase letters are always valid.

### Special literal modes
- **REM** (0xF4): everything after is literal — emitted byte-for-byte with `\xNN` decoding
- **DATA** (0xDC): unquoted content is literal; quoted strings inside DATA are handled normally
- **Star commands**: `*` at statement start passes the rest of the line raw to the OS
- **Strings**: contents between `"..."` are literal; `\xNN` escapes are decoded
- **EDIT** (0xC7 0x92): has action bit 5 (give up) — rest of line is literal

### High-byte round-trip
Bytes `>= 0x80` and control chars in the binary are represented as `\xNN` in detokenized text. The tokenizer decodes `\xNN` in all literal contexts (REM, strings, DATA, plain ASCII fallback).

### Dual-context tracking
- `line_start`: True until first non-whitespace token on the line → used for ELSE (0xCC at line start, 0x8B inline)
- `stmt_start`: True at start of each statement (after `:` or line start) → used for PTR/PAGE/TIME/LOMEM/HIMEM LHS forms
- `_STMT_INTRO_TOKS`: tokens after which `stmt_start` remains True

In the RISC OS source, this is `MODE`: 0 = left/statement-start, 1 = right/expression. Keywords with action bit 1 set switch to MODE=1; bit 2 switches to MODE=0. Polymorphic keywords (bit 6 set) add `TPTR2 - TPTR = 0x40` to get the LHS token value when MODE=0.

**Known non-conformance**: The correct three-state model (per `s/Lexical` and `tokenize/src/parse.c`) is:
- `transfer_right` (action bit 1): FOR, DIM, PRINT, INPUT, GOSUB, GOTO, ON, TRACE, IF, COLOUR, MODE, etc. → MODE=right
- `transfer_left` (action bit 2): THEN, ELSE, OTHERWISE, ERROR, LET → MODE=left
- **neither**: REPEAT, END, ENDPROC, RETURN, STOP, RUN, CLG, CLS, CLEAR, DATA, DEF, REM etc. → MODE unchanged

`bastok.py` uses a simplified boolean `stmt_start` that sets True for a broad set of keywords (including REPEAT, FOR, PRINT, DIM etc.) rather than the correct three-state. In practice this is harmless — no corpus file has PTR/PAGE/TIME/LOMEM/HIMEM in a context where the difference matters — but future work could implement the three-state model correctly if needed.

### Abbreviation support
A keyword can be abbreviated by typing its unique prefix followed by `.` (e.g. `PR.` = PRINT). The minimum abbreviation length for each keyword is given in `parse.c`. **Not implemented in `bastok.py`** — full keyword names required.

## Test corpus

`tests/corpus/` contains 39 real `.ffb` files from various RISC OS projects. The round-trip test `test_round_trip` verifies each file exactly. Current status: **122 tests pass**.

### Adding new corpus files

Only add files tokenized by the **RISC OS standard tokenizer**. Before adding any file, check whether it was produced by a third-party cruncher/squasher:

- **Crunched/compressed files**: Tools like **StrongBS** (StrongED's squasher), **BasCompress**, and others produce `.ffb` files that look valid but were tokenized with non-standard rules — e.g. no WORDCQ forward boundary check for `RETURN`, `FALSE`, `ENDPROC`. These files will fail round-trip tests and should **not** be added to the corpus or used as test cases.

  Detection clues:
  - First few lines contain `REM Squashed by StrongBS`, `REMProduced by BasCompress`, or similar
  - Very compact code with single-letter variable names, no spaces (even without an identifying REM)
  - A compressed `!RunImage,ffb` alongside an uncompressed `!RunImageU,ffb` — the `U` file is the canonical source, the non-`U` file is the crunched output; **exclude the crunched file**

## Known limitations

These are inherent ambiguities from files compiled by tokenizers with slightly different rules. The corpus (100% pass) takes priority.

1. Keywords with no forward boundary check (e.g. `ON`, `READ`, `TO`) can tokenize inside all-caps identifiers — e.g. `FIONREAD`, `AF_INETOR`. Inherent with no-general-backward-boundary approach.

2. Some older compilers tokenized `THEN` inside `DATA` statement content. `bastok.py` treats DATA as literal (correct for all corpus files).

3. `PROC_ERROR`: underscore check prevents `ERROR`, but `OR` (no WORDCQ) then tokenizes inside the remaining `RROR` suffix.

4. **Crunched/compressed files** (e.g. StrongBS) tokenize `RETURN`, `FALSE`, and `ENDPROC` without WORDCQ — non-standard; excluded from testing.

## Implementation files

- `bastok.py` — main module: `detokenize`, `tokenize`, `tokenize_line`, `encode_linenum`, `decode_linenum`
- `tests/test_bastok.py` — pytest tests (122 tests)
- `tests/corpus/*.ffb` — 39 corpus files of real tokenized BASIC
