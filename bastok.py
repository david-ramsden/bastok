#!/usr/bin/env python3
"""
Detokenize and retokenize RISC OS BBC BASIC V (,ffb) files.

Usage:
  bastok.py [--strip-line-numbers] detokenize <input,ffb> [output.bas]
  bastok.py [--auto-number=N]      tokenize   <input.bas> [output,ffb]

  --strip-line-numbers  Omit line numbers from detokenized output.
  --auto-number=N       Auto-number unnumbered lines with step N (default 10).
                        Numbered lines in the source reset the counter.
"""

import sys
import re

# ── Token tables ──────────────────────────────────────────────────────────────
#
# BBC BASIC V (ARM/RISC OS) token table.
#
# Many keywords have two token values depending on context:
#   - "statement-start" (left-hand side / start of a statement)
#   - "elsewhere" (right-hand side / expression context)
#
# The TOKENS dict maps byte value -> keyword string for the detokenizer.
# For dual-token keywords the elsewhere value is listed in the 0x80-0xBF range
# and the statement-start value in the 0xC9-0xD3 range.
#
# Sources: gerph/riscos-basic-detokenise, steve-fryatt/tokenize
#
TOKENS = {
    # 0x7F = OTHERWISE
    0x7F: 'OTHERWISE',

    # ── Operators / pseudo-variables 0x80–0x8F ────────────────────────────────
    0x80: 'AND',      0x81: 'DIV',      0x82: 'EOR',      0x83: 'MOD',
    0x84: 'OR',       0x85: 'ERROR',    0x86: 'LINE',      0x87: 'OFF',
    0x88: 'STEP',     0x89: 'SPC',      0x8A: 'TAB(',      0x8B: 'ELSE',
    0x8C: 'THEN',
    # 0x8D = inline line number reference (3 bytes follow, handled separately)
    0x8E: 'OPENIN',   0x8F: 'PTR',

    # ── Functions / pseudo-variables 0x90–0xC5 ────────────────────────────────
    # 0x90-0x93: "elsewhere" (RHS/expression) forms of PAGE/TIME/LOMEM/HIMEM
    0x90: 'PAGE',     0x91: 'TIME',     0x92: 'LOMEM',     0x93: 'HIMEM',
    0x94: 'ABS',      0x95: 'ACS',      0x96: 'ADVAL',     0x97: 'ASC',
    0x98: 'ASN',      0x99: 'ATN',      0x9A: 'BGET',
    0x9B: 'COS',      0x9C: 'COUNT',    0x9D: 'DEG',       0x9E: 'ERL',
    0x9F: 'ERR',
    0xA0: 'EVAL',     0xA1: 'EXP',      0xA2: 'EXT',       0xA3: 'FALSE',
    0xA4: 'FN',       0xA5: 'GET',      0xA6: 'INKEY',     0xA7: 'INSTR(',
    0xA8: 'INT',      0xA9: 'LEN',      0xAA: 'LN',        0xAB: 'LOG',
    0xAC: 'NOT',      0xAD: 'OPENUP',   0xAE: 'OPENOUT',   0xAF: 'PI',
    0xB0: 'POINT(',   0xB1: 'POS',      0xB2: 'RAD',       0xB3: 'RND',
    0xB4: 'SGN',      0xB5: 'SIN',      0xB6: 'SQR',       0xB7: 'TAN',
    0xB8: 'TO',       0xB9: 'TRUE',     0xBA: 'USR',       0xBB: 'VAL',
    0xBC: 'VPOS',     0xBD: 'CHR$',     0xBE: 'GET$',      0xBF: 'INKEY$',
    0xC0: 'LEFT$(',   0xC1: 'MID$(',    0xC2: 'RIGHT$(',   0xC3: 'STR$',
    0xC4: 'STRING$(', 0xC5: 'EOF',

    # 0xC6, 0xC7, 0xC8 = two-byte extended token prefixes (handled separately)

    # ── Structured-programming / dual-context tokens 0xC9–0xCF ───────────────
    # WHEN/OF/ENDCASE/ENDIF/ENDWHILE: single token, structured keywords
    # ELSE: 0xCC at statement-start, 0x8B elsewhere
    # PTR:  0xCF at statement-start (LHS assignment), 0x8F elsewhere
    0xC9: 'WHEN',     0xCA: 'OF',       0xCB: 'ENDCASE',
    0xCC: 'ELSE',     0xCD: 'ENDIF',    0xCE: 'ENDWHILE',  0xCF: 'PTR',

    # ── LHS-assignment pseudo-vars 0xD0–0xD3 ─────────────────────────────────
    # PAGE/TIME/LOMEM/HIMEM at statement-start (LHS); RHS forms are 0x90-0x93
    0xD0: 'PAGE',     0xD1: 'TIME',     0xD2: 'LOMEM',     0xD3: 'HIMEM',

    # ── Statement tokens 0xD4–0xFF ────────────────────────────────────────────
    0xD4: 'SOUND',    0xD5: 'BPUT',     0xD6: 'CALL',      0xD7: 'CHAIN',
    0xD8: 'CLEAR',    0xD9: 'CLOSE',    0xDA: 'CLG',       0xDB: 'CLS',
    0xDC: 'DATA',     0xDD: 'DEF',      0xDE: 'DIM',       0xDF: 'DRAW',
    0xE0: 'END',      0xE1: 'ENDPROC',  0xE2: 'ENVELOPE',  0xE3: 'FOR',
    0xE4: 'GOSUB',    0xE5: 'GOTO',     0xE6: 'GCOL',      0xE7: 'IF',
    0xE8: 'INPUT',    0xE9: 'LET',      0xEA: 'LOCAL',     0xEB: 'MODE',
    0xEC: 'MOVE',     0xED: 'NEXT',     0xEE: 'ON',        0xEF: 'VDU',
    0xF0: 'PLOT',     0xF1: 'PRINT',    0xF2: 'PROC',      0xF3: 'READ',
    0xF4: 'REM',      0xF5: 'REPEAT',   0xF6: 'REPORT',    0xF7: 'RESTORE',
    0xF8: 'RETURN',   0xF9: 'RUN',      0xFA: 'STOP',      0xFB: 'COLOUR',
    0xFC: 'TRACE',    0xFD: 'UNTIL',    0xFE: 'WIDTH',     0xFF: 'OSCLI',
}

# ── Extended two-byte tokens ──────────────────────────────────────────────────
# Prefix bytes 0xC6, 0xC7, 0xC8 introduce a two-byte token.
# All three prefixes index into ONE shared keyword table but with different base offsets,
# so each prefix gives access to a different window of the table (from gerph source):
#
#   0xC8 (ESCSTMT): base = 0x8E  → index = sub - 0x8E  (CASE, WHILE, SYS, LIBRARY...)
#   0xC7 (ESCCOM):  base = 0x78  → index = sub - 0x78  (APPEND, AUTO, DELETE, HELP...)
#   0xC6 (ESCFN):   base = 0x66  → index = sub - 0x66  (SUM, BEAT)
#
# Shared keyword table (0-indexed):
_EXT_KEYWORDS = [
    'CASE', 'CIRCLE', 'FILL', 'ORIGIN', 'POINT', 'RECTANGLE', 'SWAP', 'WHILE',  # 0-7
    'WAIT', 'MOUSE', 'QUIT', 'SYS', 'INSTALL', 'LIBRARY', 'TINT', 'ELLIPSE',    # 8-15
    'BEATS', 'TEMPO', 'VOICES', 'VOICE', 'STEREO', 'OVERLAY', 'APPEND', 'AUTO', # 16-23
    'CRUNCH', 'DELETE', 'EDIT', 'HELP', 'LIST', 'LOAD', 'LVAR', 'NEW',          # 24-31
    'OLD', 'RENUMBER', 'SAVE', 'TEXTLOAD', 'TEXTSAVE', 'TWIN', 'TWINO', 'INSTALL', # 32-39
    'SUM', 'BEAT',                                                                # 40-41
]

_EXT_BASE = {0xC8: 0x8E, 0xC7: 0x78, 0xC6: 0x66}


def ext_decode(prefix, sub_byte):
    """Decode a two-byte extended token (prefix=0xC6/C7/C8, sub_byte) to a keyword."""
    base = _EXT_BASE.get(prefix)
    if base is None:
        return f'[{prefix:02x}:{sub_byte:02x}]'
    idx = sub_byte - base
    if 0 <= idx < len(_EXT_KEYWORDS):
        return _EXT_KEYWORDS[idx]
    return f'[{prefix:02x}:{sub_byte:02x}]'


def ext_encode(keyword):
    """Encode a keyword to (prefix, sub_byte) using the canonical prefix.

    Each prefix covers a different range of the shared table:
      0xC8 (ESCSTMT): indices  0-39 → sub 0x8E-0xB5
      0xC7 (ESCCOM):  indices 22-41 → sub 0x8E-0xA1
      0xC6 (ESCFN):   indices 40-41 → sub 0x8E-0x8F

    Use the highest-numbered prefix that still puts the sub_byte in [0x8E, 0xFF],
    i.e. 0xC6 for SUM/BEAT, 0xC7 for APPEND..BEAT, 0xC8 for everything else.
    This matches the natural partition used by the RISC OS tokenizer.
    """
    try:
        idx = _EXT_KEYWORDS.index(keyword)
    except ValueError:
        return None
    # Use 0xC6 if the keyword is in the ESCFN range (index 40+)
    sub6 = idx + 0x66
    if 0x8E <= sub6 <= 0xFF:
        return (0xC6, sub6)
    # Use 0xC7 if in the ESCCOM range (index 22+)
    sub7 = idx + 0x78
    if 0x8E <= sub7 <= 0xFF:
        return (0xC7, sub7)
    # Otherwise use 0xC8 (ESCSTMT)
    sub8 = idx + 0x8E
    if sub8 <= 0xFF:
        return (0xC8, sub8)
    return None


# Reverse lookup for extended keywords: name -> (prefix, sub_byte)
EXT_REV_MAP = {}
for _kw in _EXT_KEYWORDS:
    _enc = ext_encode(_kw)
    if _enc and _kw not in EXT_REV_MAP:
        EXT_REV_MAP[_kw] = _enc

# Sorted longest-first for tokenizer matching
EXT_TOK_REV = sorted(EXT_REV_MAP.items(), key=lambda kv: len(kv[0]), reverse=True)


# ── Internal lookup tables ────────────────────────────────────────────────────

def _build_rev(table):
    """Build reverse lookup sorted longest-first, deduplicating by first occurrence."""
    pairs = sorted(table.items(), key=lambda kv: len(kv[1]), reverse=True)
    seen = set()
    out = []
    for tok, name in pairs:
        if name not in seen:
            seen.add(name)
            out.append((name, tok))
    return out

TOK_REV = _build_rev(TOKENS)

# Token values for keywords that precede inline line numbers
_LINENUM_TOKS = frozenset(
    tok for tok, name in TOKENS.items()
    if name in ('GOTO', 'GOSUB', 'RESTORE', 'THEN', 'ELSE', 'ON', 'TRACE')
)

# Tokens that are immediately followed by a name without a boundary delimiter.
# DEF is followed by PROC or FN; PROC (0xF2, 0x9B) and FN are followed by the name.
# For these, the identifier-continuation boundary check is suppressed.
_NO_BOUNDARY_TOKS = frozenset(
    tok for tok, name in TOKENS.items()
    if name in ('PROC', 'FN', 'DEF')
)

# Tokens for which the FORWARD boundary check (WORDCQ) is suppressed.
# Derived from the RISC OS s/Lexical PLEX table: keywords with action byte bit 0 CLEAR
# have no WORDCQ check and can tokenize even when directly followed by a letter.
# E.g. THENGCOL → THEN + GCOL, IFx% → IF + x%, ONA% → ON + A%, UNTILEOF → UNTIL + EOF.
# Keywords with action byte bit 0 SET do have WORDCQ and must NOT appear here.
_NO_FORWARD_BOUNDARY_TOKS = frozenset(
    tok for tok, name in TOKENS.items()
    if name in (
        # Operators — no boundary check (bit 0 clear in PLEX)
        'AND', 'OR', 'EOR', 'DIV', 'MOD', 'NOT',
        # Flow / structural — no boundary check
        'THEN', 'ELSE', 'OTHERWISE', 'TO', 'STEP', 'OF', 'ON', 'ERROR',
        'LINE', 'OFF', 'SPC', 'REPEAT', 'UNTIL', 'RESTORE', 'TRACE',
        'DRAW', 'MOVE', 'PLOT', 'CHAIN', 'QUIT', 'ENVELOPE',
        'FOR', 'LOCAL', 'WHEN', 'NEXT', 'WIDTH',
        # Statement keywords — no boundary check (bit 0 clear)
        'CALL', 'GOSUB', 'GOTO', 'LET', 'PROC',
        'IF', 'DIM', 'INPUT', 'PRINT', 'READ',
        'COLOUR', 'GCOL', 'MODE', 'SOUND', 'VDU',
        'OSCLI',
        # Function/expression keywords — no boundary check (bit 0 clear)
        'ABS', 'ACS', 'ADVAL', 'ASC', 'ASN', 'ATN',
        'COS', 'DEG', 'EVAL', 'EXP',
        'GET', 'INKEY', 'INT', 'LEN', 'LN', 'LOG',
        'OPENIN', 'OPENOUT', 'OPENUP', 'RAD',
        'SGN', 'SIN', 'SQR', 'TAN', 'USR', 'VAL',
        # REM and DATA — rest of line is literal, no boundary needed
        'REM', 'DATA',
    )
)

# Extended two-byte tokens that have WORDCQ (bit 0 set in PLEX action byte).
# These must not tokenize when directly followed by a letter/digit/underscore/dot.
_EXT_WORDCQ_NAMES = frozenset({'HELP', 'LVAR', 'NEW', 'OLD', 'TWIN', 'WAIT'})


# ── Line number encoding ──────────────────────────────────────────────────────

def encode_linenum(n):
    """Encode a 16-bit line number as the 3 bytes that follow 0x8D.

    Encoding (from RISC OS s/Lexical CONSTI routine and xania.org):
      b0 = (((n & 0xC0) >> 2) | ((n & 0xC000) >> 12)) ^ 0x54
      b1 = (n & 0x3F) | 0x40      -- low 6 bits of lo byte
      b2 = ((n & 0x3F00) >> 8) | 0x40  -- low 6 bits of hi byte
    All three bytes stay in 0x40-0x7F, avoiding token bytes and 0x0D.
    """
    b0 = (((n & 0xC0) >> 2) | ((n & 0xC000) >> 12)) ^ 0x54
    b1 = (n & 0x3F) | 0x40
    b2 = ((n & 0x3F00) >> 8) | 0x40
    return bytes([b0, b1, b2])


def decode_linenum(b0, b1, b2):
    """Decode the 3 bytes following 0x8D to a 16-bit line number."""
    x = b0 ^ 0x54
    lo = ((x & 0x30) << 2) | (b1 & 0x3F)
    hi = ((x & 0x0C) << 4) | (b2 & 0x3F)
    return (hi << 8) | lo


# ── Detokenizer ───────────────────────────────────────────────────────────────

def detokenize(data, strip_line_numbers=False):
    """Convert tokenized BBC BASIC V binary to plain text."""
    lines = []
    i = 0
    while i < len(data):
        if data[i] != 0x0D:
            break
        i += 1
        if i + 2 >= len(data):
            break
        line_num = (data[i] << 8) | data[i + 1]
        i += 2
        if line_num == 0xFFFF:
            break
        length = data[i]
        i += 1
        end = i + length - 4

        text = []
        j = i
        in_string = False
        in_rem = False

        while j < end:
            b = data[j]

            if in_rem:
                text.append(chr(b) if 0x20 <= b < 0x80 else f'\\x{b:02x}')
                j += 1
                continue

            if in_string:
                text.append('"' if b == 0x22 else (chr(b) if 0x20 <= b < 0x80 else f'\\x{b:02x}'))
                if b == 0x22:
                    in_string = False
                j += 1
                continue

            if b == 0x22:
                in_string = True
                text.append('"')
                j += 1
                continue

            if b in (0xC6, 0xC7, 0xC8):  # two-byte extended token
                j += 1
                if j < end:
                    text.append(ext_decode(b, data[j]))
                    j += 1
                continue

            if b == 0x8D:  # inline line number reference
                j += 1
                if j + 2 < end:
                    text.append(str(decode_linenum(data[j], data[j + 1], data[j + 2])))
                    j += 3
                continue

            if b == 0xF4:  # REM — rest of line is literal
                text.append('REM')
                in_rem = True
                j += 1
                continue

            if b >= 0x7F:
                text.append(TOKENS.get(b, f'[{b:02x}]'))
            else:
                text.append(chr(b) if 0x20 <= b < 0x7F else f'\\x{b:02x}')
            j += 1

        lines.append((line_num, ''.join(text)))
        i = end

    if strip_line_numbers:
        return '\n'.join(text for _, text in lines) + '\n'
    return '\n'.join(f'{n} {text}' for n, text in lines) + '\n'


# ── Tokenizer ─────────────────────────────────────────────────────────────────

# Characters that can follow a keyword without it being part of an identifier.
# A keyword match is only valid if NOT followed by an alphanumeric, _ % or $.
# Characters that continue an identifier; a keyword match is only valid if NOT followed by these.
# Note: '$' is excluded — it is a type suffix (e.g. TIME$), not a keyword continuation.
_IDENT_CONT = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_%')
_IDENT_CONT_BYTES = frozenset(ord(c) for c in _IDENT_CONT)
# Backward boundary: only letters/_ can precede a keyword as part of the same identifier.
# Digits are never the start of an identifier, so PRINT1 = PRINT + 1 not P + RINT1.
_IDENT_START = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_')
# Keywords that end with '(' already enclose the argument, so no boundary check needed.
_OPEN_PAREN = frozenset(k for k, _ in TOK_REV if k.endswith('('))


def tokenize_line(content):
    """Tokenize the payload of one BASIC line (everything after the line number)."""
    out = bytearray()
    i = 0
    in_string = False
    in_rem = False
    in_data = False       # True after DATA token; unquoted items are literal
    last_tok = None       # last emitted token value (for line-number context)
    in_linenum_list = False  # True while emitting comma-separated inline line numbers
    # Statement-start context for dual-context keywords.
    #
    # ELSE: 0xCC when it begins a new source line (structured ELSE block),
    #       0x8B when inline (after : or in an IF...THEN...ELSE expression).
    # PTR/PAGE/TIME/LOMEM/HIMEM: statement-start (LHS assignment) forms when
    #       followed by assignment, expression forms on the RHS.
    #
    # We track two states:
    #   line_start: True until first non-space token on the line is emitted.
    #               Used for ELSE: 0xCC only when ELSE is first token on line.
    #   stmt_start: True at the start of each statement (after : or line start).
    #               Used for PTR/PAGE/TIME/LOMEM/HIMEM assignment forms.
    line_start = True   # True until first non-whitespace token on this line
    stmt_start = True   # True at start of each statement (after : or line start)

    # Dual-context keywords: name -> (line_start_tok, stmt_tok, expr_tok)
    # ELSE uses line_start (0xCC) vs elsewhere (0x8B).
    # PTR/PAGE/TIME/LOMEM/HIMEM use stmt_start (LHS form) vs expr (RHS form).
    _DUAL_LINE = {  # 0xCC only when ELSE begins the line
        'ELSE': (0xCC, 0x8B),
    }
    _DUAL_STMT = {  # LHS/stmt form vs expression form
        'PTR':   (0xCF, 0x8F),
        'PAGE':  (0xD0, 0x90),
        'TIME':  (0xD1, 0x91),
        'LOMEM': (0xD2, 0x92),
        'HIMEM': (0xD3, 0x93),
    }

    # Tokens after which stmt_start remains True (they introduce a new statement
    # context — PTR/PAGE/TIME/LOMEM/HIMEM can appear as LHS assignment targets).
    # IF, WHILE, UNTIL, operators etc. introduce expressions, so stmt_start must
    # become False after them.
    _STMT_INTRO_TOKS = frozenset(
        tok for tok, name in TOKENS.items()
        if name in ('THEN', 'ELSE', 'OTHERWISE', 'REPEAT', 'FOR',
                    'DEF', 'LOCAL', 'END', 'ENDPROC', 'RETURN', 'STOP',
                    'RUN', 'CLG', 'CLS', 'CLEAR', 'NEW', 'OLD',
                    'RENUMBER', 'LIST', 'LOAD', 'SAVE', 'CHAIN', 'QUIT',
                    'TRACE', 'DRAW', 'MOVE', 'PLOT', 'ENVELOPE',
                    'RESTORE', 'DATA', 'ON', 'LINE', 'OFF', 'SPC',
                    'COLOUR', 'GCOL', 'MODE', 'SOUND', 'VDU', 'DIM',
                    'INPUT', 'PRINT', 'READ')
    )

    while i < len(content):
        ch = content[i]

        # ── REM: everything is literal ────────────────────────────────────────
        if in_rem:
            if ch == '\\' and i + 3 < len(content) and content[i+1] == 'x' \
                    and all(c in '0123456789abcdefABCDEF' for c in content[i+2:i+4]):
                out.append(int(content[i+2:i+4], 16))
                i += 4
            else:
                out.append(ord(ch) if ord(ch) < 128 else 0x3F)
                i += 1
            continue

        # ── DATA: unquoted items are literal; strings are handled normally ───────
        if in_data and ch != '"':
            # Emit literal byte (with \xNN decoding)
            if ch == '\\' and i + 3 < len(content) and content[i+1] == 'x' \
                    and all(c in '0123456789abcdefABCDEF' for c in content[i+2:i+4]):
                out.append(int(content[i+2:i+4], 16))
                i += 4
            else:
                out.append(ord(ch) if ord(ch) < 128 else 0x3F)
                i += 1
            continue
        # A '"' inside DATA falls through to normal string handling below;
        # in_data stays True so we resume DATA mode after the closing quote.

        # ── String literal ────────────────────────────────────────────────────
        if in_string:
            if ch == '\\' and i + 3 < len(content) and content[i+1] == 'x' \
                    and all(c in '0123456789abcdefABCDEF' for c in content[i+2:i+4]):
                out.append(int(content[i+2:i+4], 16))
                i += 4
            else:
                out.append(ord(ch))
                if ch == '"':
                    in_string = False
                i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ord('"'))
            i += 1
            stmt_start = False
            line_start = False
            continue

        # ── Statement separator ───────────────────────────────────────────────
        if ch == ':':
            out.append(ord(':'))
            i += 1
            stmt_start = True
            line_start = False  # : doesn't reset line_start
            last_tok = None
            in_linenum_list = False
            continue

        # ── Whitespace (doesn't change statement-start or line_start) ──────────
        if ch in (' ', '\t'):
            out.append(ord(ch))
            i += 1
            continue

        # ── Star command: * passes rest of line raw to the OS ────────────────
        # * is a star (OS) command only at statement start; elsewhere it is
        # multiplication and must not suppress keyword tokenization.
        if ch == '*' and stmt_start:
            while i < len(content):
                out.append(ord(content[i]) if ord(content[i]) < 128 else 0x3F)
                i += 1
            break

        # ── Inline line number after a branching keyword ──────────────────────
        # Digits immediately following GOTO/GOSUB/RESTORE/THEN/ELSE/ON are
        # encoded as 0x8D + 3 packed bytes, not as ASCII digits.
        # Also handles comma-separated lists: ON x GOTO 100,200,300
        _want_linenum = (last_tok in _LINENUM_TOKS) or in_linenum_list
        if _want_linenum and ch == ',':
            out.append(ord(','))
            i += 1
            # Don't clear in_linenum_list; the next digit should also be encoded
            continue
        if _want_linenum and ch.isdigit():
            j = i
            while j < len(content) and content[j].isdigit():
                j += 1
            # Only treat as line number if not part of an expression (no operator follows)
            trailing = content[j] if j < len(content) else ''
            if trailing in ('', ':', ' ', '\t', ','):
                n = int(content[i:j])
                out.append(0x8D)
                out.extend(encode_linenum(n))
                i = j
                in_linenum_list = (trailing == ',')
                last_tok = None
                continue
        if in_linenum_list and ch not in (' ', '\t', ',') and not ch.isdigit():
            in_linenum_list = False

        # ── Regular tokens ────────────────────────────────────────────────────
        matched = False
        for name, tok in TOK_REV:
            end_pos = i + len(name)
            if content[i:end_pos] != name:
                continue
            # Boundary check: token must not be a prefix of a longer identifier.
            # Exceptions:
            #   - tokens ending with '(' already have a delimiter
            #   - PROC, FN, DEF are always immediately followed by a name (no delimiter)
            if name not in _OPEN_PAREN and tok not in _NO_BOUNDARY_TOKS:
                if tok not in _NO_FORWARD_BOUNDARY_TOKS:
                    # Forward boundary: token must not be a prefix of a longer identifier.
                    if name[-1] in _IDENT_START:
                        nc = content[end_pos] if end_pos < len(content) else ''
                        if nc in _IDENT_START:
                            continue
                # Underscore backward boundary: '_' is a valid identifier-start char.
                # A keyword must not directly follow '_' in the output buffer, since
                # '_keyword' is a valid identifier/procedure name (e.g. PROC_ERROR).
                if name[0] in _IDENT_START and (out[-1] if out else 0) == ord('_'):
                    continue
            # Dual-context keywords: choose token based on context.
            if name in _DUAL_LINE:
                tok = _DUAL_LINE[name][0] if line_start else _DUAL_LINE[name][1]
            elif name in _DUAL_STMT:
                tok = _DUAL_STMT[name][0] if stmt_start else _DUAL_STMT[name][1]
            out.append(tok)
            i = end_pos
            if tok == 0xF4:  # REM
                in_rem = True
            elif tok == 0xDC:  # DATA
                in_data = True
            last_tok = tok
            stmt_start = tok in _STMT_INTRO_TOKS
            line_start = False
            matched = True
            break
        if matched:
            continue

        # ── Extended two-byte tokens ──────────────────────────────────────────
        for name, (prefix, sub) in EXT_TOK_REV:
            end_pos = i + len(name)
            if content[i:end_pos] != name:
                continue
            # Apply WORDCQ forward boundary check for extended tokens that require it
            if name in _EXT_WORDCQ_NAMES and name[-1] in _IDENT_START:
                nc = content[end_pos] if end_pos < len(content) else ''
                if nc in _IDENT_START:
                    continue
            # Underscore backward boundary
            if name[0] in _IDENT_START and (out[-1] if out else 0) == ord('_'):
                continue
            out.append(prefix)
            out.append(sub)
            i = end_pos
            last_tok = None
            stmt_start = False
            line_start = False
            matched = True
            break
        if matched:
            continue

        # ── Plain ASCII ───────────────────────────────────────────────────────
        if ch == '\\' and i + 3 < len(content) and content[i+1] == 'x' \
                and all(c in '0123456789abcdefABCDEF' for c in content[i+2:i+4]):
            out.append(int(content[i+2:i+4], 16))
            i += 4
        else:
            out.append(ord(ch) if ord(ch) < 128 else 0x3F)
            i += 1
        last_tok = None
        stmt_start = False
        line_start = False

    return bytes(out)


def tokenize(text, auto_number=10):
    """Convert plain-text BBC BASIC to tokenized binary.

    If auto_number is set (default 10), unnumbered lines are assigned line
    numbers automatically starting from auto_number, incrementing by that step.
    Numbered lines reset the counter to their value.
    """
    out = bytearray()
    next_num = auto_number
    for line in text.splitlines():
        if not line.strip():
            continue
        m = re.match(r'^(\d+)\s?(.*)', line)
        if m:
            line_num = int(m.group(1))
            content = m.group(2)
            next_num = line_num + auto_number
        elif auto_number:
            line_num = next_num
            content = line
            next_num += auto_number
        else:
            continue

        payload = tokenize_line(content)
        length = 4 + len(payload)
        if length > 255:
            raise ValueError(f'Line {line_num} too long ({length} bytes, max 255)')
        out.append(0x0D)
        out.append((line_num >> 8) & 0xFF)
        out.append(line_num & 0xFF)
        out.append(length)
        out.extend(payload)

    out.extend(b'\x0D\xFF')
    return bytes(out)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    args = sys.argv[1:]

    strip_line_numbers = '--strip-line-numbers' in args
    args = [a for a in args if a != '--strip-line-numbers']

    auto_number = 10
    for a in args:
        if a.startswith('--auto-number='):
            auto_number = int(a.split('=', 1)[1])
            args = [x for x in args if not x.startswith('--auto-number=')]
            break

    if len(args) < 2 or args[0] not in ('detokenize', 'tokenize'):
        print(__doc__)
        sys.exit(1)

    cmd = args[0]
    infile = args[1]
    outfile = args[2] if len(args) > 2 else None

    if cmd == 'detokenize':
        data = open(infile, 'rb').read()
        result = detokenize(data, strip_line_numbers=strip_line_numbers)
        if outfile:
            open(outfile, 'w', newline='\n').write(result)
        else:
            sys.stdout.write(result)
    else:
        text = open(infile, 'r', newline='').read()
        result = tokenize(text, auto_number=auto_number)
        if outfile:
            open(outfile, 'wb').write(result)
        else:
            sys.stdout.buffer.write(result)
