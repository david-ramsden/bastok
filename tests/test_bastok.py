"""
Tests for bastok.py — BBC BASIC V (ARM/RISC OS) tokenizer/detokenizer.

Round-trip tests: for each tokenized binary in tests/corpus/, verify that
    detokenize(original) |> tokenize() == original
on a line-by-line basis.

Corpus sources (all tokenized .ffb binaries committed verbatim):
  ReadEase_RunImage.ffb        rjw57/ReadEase                              (reading-age calculator)
  Lander_arthur.ffb            markmoxon/lander-source-code-acorn-archimedes (Arthur build)
  Lander_disc.ffb              markmoxon/lander-source-code-acorn-archimedes (disc image)
  arcbbs_Gate.ffb              hfiennes/arcbbs                             (!Gate desktop app)
  arcbbs_TestDoor.ffb          hfiennes/arcbbs                             (!TestDoor)
  zap_DeDupe.ffb               jaylett/zap                                 (filter: remove duplicate lines)
  zap_Filt_Shell.ffb           jaylett/zap                                 (filter shell template)
  zap_FilterLib.ffb            jaylett/zap                                 (filter library)
  zap_E_Library.ffb            jaylett/zap                                 (editor extension library)
  zapfonts_R_Library.ffb       jaylett/zap                                 (ZapFonts library)
  zap_FontTest.ffb             jaylett/zap sources                         (!ZapSource font test)
  zap_KeyTest.ffb              jaylett/zap sources                         (!ZapSource key test)
  zap_KeyTestUD.ffb            jaylett/zap sources                         (!ZapSource key test UD)
  zap_ConvFont.ffb             jaylett/zap sources                         (!ZapRedraw font converter)
  zap_ConvKeys.ffb             jaylett/zap sources                         (!ZapBASIC key converter)
  zap_AddSprites.ffb           jaylett/zap dists                           (!ZapSpell sprite adder)
  zap_Eval.ffb                 jaylett/zap dists                           (filter: EVAL expression)
  zap_Sort.ffb                 jaylett/zap dists                           (filter: sort lines)
  zap_Untab.ffb                jaylett/zap dists                           (filter: expand tabs)
  zap_Format.ffb               jaylett/zap dists                           (filter: reformat)
  zap_MakeRes.ffb              jaylett/zap dists                           (resource-file builder)
  zap_FlashSrc.ffb             jaylett/zap dists                           (FlashCar extension source)
  zap_Rebinder.ffb             jaylett/zap dists                           (LineEditor key rebinder)
  zapfonts_AddPath.ffb         jaylett/zap fonts dist                      (ZapFonts path setter)
  zapfonts_FontUtils.ffb       jaylett/zap fonts dist                      (ZapFonts utility library)
  zap_BasicToAsm.ffb           jaylett/zap sources                         (!ZapSource BASIC→ASM)
  zap_Diff.ffb                 jaylett/zap sources                         (!ZapSource diff tool)
  zap_MCopy.ffb                jaylett/zap sources                         (!ZapSource mass copy)
  zap_StoH.ffb                 jaylett/zap sources                         (!ZapSource S→H converter)
  zap_Demo.ffb                 jaylett/zap sources                         (!ZapBASIC demo)
  privateeye_PhotoCheck.ffb    dpt/PrivateEye                              (!PrivatEye PhotoCheck)
  privateeye_ResFind.ffb       dpt/PrivateEye                              (!PrivatEye ResFind)
  tagcloud_ResFind.ffb         dpt/PrivateEye                              (!TagCloud ResFind)
  acorn_metapply.ffb           grz0zrg/acorn-computers-dev                 (metapply script)
  acorn_landConf.ffb           grz0zrg/acorn-computers-dev                 (DotVox256 landscape config)
  PhotoFiler_Load.ffb          dpt/PhotoFiler                              (!PhotoFilr/WimpSWIVe/Load)
  ddeutilsjf_VersionBas.ffb    gerph/ddeutilsjf                            (version number utility)
  rma_RunImage.ffb             nemo20000/rma                               (RMA module browser)
"""

import pathlib
import pytest
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from bastok import detokenize, tokenize, tokenize_line, encode_linenum

CORPUS = pathlib.Path(__file__).parent / "corpus"


def _parse_lines(data: bytes) -> dict:
    """Parse tokenized BASIC into {line_number: payload_bytes}."""
    lines = {}
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
        lines[line_num] = data[i:end]
        i = end
    return lines


def _corpus_files():
    return sorted(CORPUS.glob("*.ffb"))


@pytest.mark.parametrize("path", _corpus_files(), ids=lambda p: p.name)
def test_round_trip(path):
    """Detokenize then re-tokenize must reproduce the original binary line-for-line."""
    original = path.read_bytes()
    assert original[0] == 0x0D, \
        f"{path.name} does not start with 0x0D — not a tokenized BASIC file"

    text = detokenize(original)
    retokenized = tokenize(text)

    orig_lines = _parse_lines(original)
    retok_lines = _parse_lines(retokenized)

    diffs = []
    for line_num, orig_payload in sorted(orig_lines.items()):
        retok_payload = retok_lines.get(line_num)
        if orig_payload != retok_payload:
            diffs.append(
                f"  line {line_num}:\n"
                f"    orig = {orig_payload.hex()}\n"
                f"    ours = {(retok_payload or b'').hex()}"
            )

    assert not diffs, \
        f"{path.name}: {len(diffs)} line(s) differ after round-trip:\n" + "\n".join(diffs)


# ── Helpers ───────────────────────────────────────────────────────────────────

def tok(line: str) -> str:
    """Tokenize a single line body (no line number) and return the payload as hex."""
    return tokenize_line(line).hex()


# ── Star commands ─────────────────────────────────────────────────────────────

class TestStarCommands:
    """* at statement start passes the rest of the line raw to the OS."""

    def test_star_close(self):
        # CLOSE is a keyword but must not be tokenized after *
        assert tok("*CLOSE") == "2a434c4f5345"

    def test_star_run(self):
        # RUN is a keyword
        assert tok("*RUN &.GAME.GAMECODE") == "2a52554e20262e47414d452e47414d45434f4445"

    def test_star_quit(self):
        # QUIT is an extended token but must stay as ASCII after *
        assert tok("*QUIT") == "2a51554954"

    def test_star_filer_run(self):
        # No BASIC keywords, just confirms * suppresses all tokenizing
        assert tok("*Filer_Run <ReadEase$Dir>.Manual") == \
            "2a46696c65725f52756e203c5265616445617365244469723e2e4d616e75616c"

    def test_star_after_colon(self):
        # * after : (new statement) is also a star command
        # e0=END, 3a=':', then '*CLOSE' as ASCII
        assert tok("END:*CLOSE") == "e03a2a434c4f5345"

    def test_star_multiply_does_not_suppress(self):
        # * in an expression is multiplication, not a star command
        result = tok("IF LEN(text$)*16>sx% THEN sx%=1")
        assert "8c" in result          # 0x8C = THEN token present
        assert "5448454e" not in result  # "THEN" as ASCII must NOT appear


# ── UNTIL forward boundary ────────────────────────────────────────────────────

class TestUntilBoundary:
    """UNTIL can directly precede a keyword/function with no space."""

    def test_until_eof_no_space(self):
        # UNTILEOF#A% — fd=UNTIL, c5=EOF, 23='#', 41='A', 25='%'
        assert tok("UNTILEOF#A%") == "fdc5234125"

    def test_until_with_space(self):
        assert tok("UNTIL EOF#A%") == "fd20c5234125"

    def test_until_expression(self):
        result = tok("UNTIL x%=0")
        assert result.startswith("fd")  # fd=UNTIL


# ── Dual-context tokens ───────────────────────────────────────────────────────

class TestDualContextTokens:
    """Some keywords have different token values depending on context."""

    def test_else_inline(self):
        # Inline ELSE uses 0x8B
        result = tok("IF x% THEN y%=1 ELSE y%=0")
        assert "8b" in result
        assert not result.startswith("cc")

    def test_else_statement_start(self):
        # ELSE at line start uses 0xCC
        assert tok("ELSE y%=0").startswith("cc")

    def test_ptr_lhs(self):
        # PTR# on LHS uses 0xCF
        assert tok("PTR#f%=0").startswith("cf")

    def test_ptr_rhs(self):
        # PTR# in expression uses 0x8F
        assert "8f" in tok("x%=PTR#f%")

    def test_time_lhs(self):
        assert tok("TIME=0").startswith("d1")

    def test_time_rhs(self):
        assert "91" in tok("x%=TIME")

    def test_page_lhs(self):
        assert tok("PAGE=&8000").startswith("d0")

    def test_page_rhs(self):
        assert "90" in tok("x%=PAGE")


# ── Inline line numbers ───────────────────────────────────────────────────────

class TestInlineLineNumbers:
    """GOTO/GOSUB/etc encode target line numbers as packed 3-byte sequences."""

    def test_goto(self):
        result = tok("GOTO 100")
        # e5=GOTO, 20=space, 8d=inline-linenum-prefix, then 3 packed bytes
        assert result == "e5" + "20" + "8d" + encode_linenum(100).hex()

    def test_gosub(self):
        result = tok("GOSUB 200")
        assert result == "e4" + "20" + "8d" + encode_linenum(200).hex()

    def test_then_line_number(self):
        assert encode_linenum(500).hex() in tok("IF x% THEN 500")

    def test_on_goto_list(self):
        result = tok("ON x% GOTO 100,200,300")
        assert encode_linenum(100).hex() in result
        assert encode_linenum(200).hex() in result
        assert encode_linenum(300).hex() in result

    def test_restore(self):
        assert encode_linenum(50).hex() in tok("RESTORE 50")

    def test_trace_line_number(self):
        # TRACE n encodes n as 0x8D + 3 packed bytes (PLEX action bit 4 set)
        result = tok("TRACE 100")
        # fc=TRACE, 20=space, 8d=inline-linenum-prefix, then 3 packed bytes
        assert result == "fc" + "20" + "8d" + encode_linenum(100).hex()

    def test_trace_line_number_no_space(self):
        result = tok("TRACE100")
        assert result == "fc" + "8d" + encode_linenum(100).hex()

    def test_trace_line_number_round_trip(self):
        # Build a binary line with TRACE + space + encoded line number 200
        from bastok import encode_linenum as enc
        payload = bytes([0xFC, 0x20, 0x8D]) + enc(200)
        data = _make_line(10, payload)
        assert tokenize(detokenize(data)) == data


# ── Token boundary ────────────────────────────────────────────────────────────

class TestTokenBoundary:
    """Keywords must not match as prefixes of longer identifiers."""

    def test_proc_name_not_tokenized(self):
        # PROCfoo: PROC is tokenized (f2), then 'foo'
        assert tok("PROCfoo").startswith("f2")

    def test_and_not_in_variable(self):
        # 'andval%' starts with AND but is a variable name
        assert tok("andval%=1") == "616e6476616c253d31"

    def test_for_not_in_variable(self):
        # 'format%' starts with FOR but is a variable name — must be plain ASCII
        result = tok("format%=1")
        assert result == "666f726d6174253d31"

    def test_print_not_in_identifier(self):
        # 'printer%' should not start with PRINT token
        result = tok("printer%=1")
        assert not result.startswith("f1")  # f1=PRINT


# ── Extended tokens ───────────────────────────────────────────────────────────

class TestExtendedTokens:
    """Two-byte extended tokens (0xC6/C7/C8 prefix)."""

    def test_sys(self):
        assert tok('SYS "OS_Write0",addr%').startswith("c899")

    def test_while(self):
        assert tok("WHILE x%>0").startswith("c895")

    def test_endwhile(self):
        assert tok("ENDWHILE").startswith("ce")  # single-byte 0xCE

    def test_case(self):
        assert tok("CASE x% OF").startswith("c88e")

    def test_mouse(self):
        # MOUSE = 0xC8 0x97
        assert tok("MOUSE x%,y%,b%").startswith("c897")

    def test_sum_escfn(self):
        # SUM uses the ESCFN (0xC6) prefix
        assert "c68e" in tok("x%=SUM(arr%())")

    def test_beat_escfn(self):
        assert "c68f" in tok("x%=BEAT")


# ── Detokenizer ───────────────────────────────────────────────────────────────

class TestDetokenize:
    """Detokenizer-specific behaviour."""

    def test_rem_is_literal(self):
        text = detokenize(tokenize("10 REM hello GOTO 100\n"))
        assert "hello GOTO 100" in text

    def test_string_literal_not_tokenized(self):
        text = detokenize(tokenize('10 PRINT "GOTO 100"\n'))
        assert '"GOTO 100"' in text

    def test_strip_line_numbers(self):
        data = tokenize("10 PRINT 1\n20 PRINT 2\n")
        text = detokenize(data, strip_line_numbers=True)
        for line in text.splitlines():
            if line:
                assert not line[0].isdigit()

    def test_line_numbers_present_by_default(self):
        data = tokenize("10 PRINT 1\n20 PRINT 2\n")
        assert detokenize(data).startswith("10 ")

    def test_eof_marker(self):
        data = tokenize("10 END\n")
        assert data.endswith(b'\x0d\xff')

    def test_line_length_limit(self):
        import pytest
        long_line = "10 REM " + "x" * 300 + "\n"
        with pytest.raises(ValueError, match="too long"):
            tokenize(long_line)


# ── Auto-numbering ────────────────────────────────────────────────────────────

class TestAutoNumbering:
    """Unnumbered lines are assigned line numbers automatically."""

    def test_unnumbered_lines(self):
        data = tokenize("PRINT 1\nPRINT 2\n")
        text = detokenize(data)
        lines = [l for l in text.splitlines() if l]
        assert lines[0].startswith("10 ")
        assert lines[1].startswith("20 ")

    def test_numbered_lines_reset_counter(self):
        data = tokenize("100 PRINT 1\nPRINT 2\n")
        text = detokenize(data)
        lines = [l for l in text.splitlines() if l]
        assert lines[0].startswith("100 ")
        assert lines[1].startswith("110 ")

    def test_custom_step(self):
        data = tokenize("PRINT 1\nPRINT 2\n", auto_number=5)
        text = detokenize(data)
        lines = [l for l in text.splitlines() if l]
        assert lines[0].startswith("5 ")
        assert lines[1].startswith("10 ")


# ── High-byte round-trip ───────────────────────────────────────────────────────

def _make_line(line_num: int, payload: bytes) -> bytes:
    """Build a single tokenized BASIC line with EOF marker."""
    length = 4 + len(payload)
    return (bytes([0x0D, (line_num >> 8) & 0xFF, line_num & 0xFF, length])
            + payload + b'\x0d\xff')


class TestHighByteRoundTrip:
    """Bytes >= 0x80 and control chars must survive detokenize→tokenize intact."""

    def test_high_bytes_in_rem(self):
        # REM comment containing bytes 0xa0 0xb0 0xc0
        data = _make_line(10, bytes([0xf4, 0xa0, 0xb0, 0xc0]))
        assert detokenize(data) == "10 REM\\xa0\\xb0\\xc0\n"
        assert tokenize(detokenize(data)) == data

    def test_high_bytes_in_string(self):
        # PRINT "£<high>" — 0xa9 and 0x8f inside a string literal
        data = _make_line(20, bytes([0xf1, 0x20, 0x22, 0xa9, 0x8f, 0x22]))
        assert '\\xa9\\x8f' in detokenize(data)
        assert tokenize(detokenize(data)) == data

    def test_control_char_outside_string(self):
        # PRINT <TAB=0x09> 1 — control char in plain code
        data = _make_line(30, bytes([0xf1, 0x09, 0x31]))
        assert '\\x09' in detokenize(data)
        assert tokenize(detokenize(data)) == data

    def test_rem_no_space(self):
        # REMfoo — REM with no space before the comment body
        assert tok("REMhello world").startswith("f4")  # f4 = REM

    def test_rem_no_space_round_trip(self):
        data = _make_line(40, bytes([0xf4]) + b"hello world")
        assert tokenize(detokenize(data)) == data

    def test_high_byte_in_data_raw(self):
        # DATA with high bytes in the unquoted item
        assert tok("DATA \\xa0\\xb0,123") == "dc20a0b02c313233"

    def test_high_byte_in_data_string(self):
        # DATA with high bytes inside a quoted string
        assert tok('DATA "\\xa9hello"') == "dc2022a968656c6c6f22"

    def test_trailing_spaces_preserved(self):
        # A line with only spaces must preserve all four spaces
        assert tok("    ") == "20202020"

    def test_trailing_spaces_round_trip(self):
        data = _make_line(50, b"    ")
        assert tokenize(detokenize(data)) == data


# ── Additional boundary and context tests ─────────────────────────────────────

class TestBoundaryFixes:
    """Regression tests for boundary and context bugs fixed alongside high-byte support."""

    def test_sys_before_digit(self):
        # SYS followed directly by a numeric argument (no space)
        assert tok("SYS35,N$").startswith("c899")   # c8 99 = SYS

    def test_while_before_identifier(self):
        # WHILE followed directly by a variable (no space)
        assert tok("WHILEA%>0").startswith("c895")  # c8 95 = WHILE

    def test_if_himem_is_rhs(self):
        # HIMEM after IF is in an expression — must use RHS token 0x93, not LHS 0xd3
        result = tok("IF HIMEM>0")
        assert "93" in result   # 0x93 = HIMEM (expression form)
        assert "d3" not in result

    def test_data_does_not_tokenize_keywords(self):
        # DEF/FOR/IF etc. inside DATA unquoted items must stay as plain bytes
        result = tok("DATA aABCDEF")
        assert "dd" not in result   # 0xdd = DEF token must not appear
        assert "e3" not in result   # 0xe3 = FOR token must not appear


# ── WORDCQ forward boundary ───────────────────────────────────────────────────

class TestWordcq:
    """Keywords with WORDCQ (action bit 0) must not match before a letter/digit/_/."""

    def test_run_blocked_before_letter(self):
        # RUN has WORDCQ — RUNNING must stay entirely as ASCII
        assert tok("RUNNING") == "52554e4e494e47"

    def test_stop_blocked_before_letter(self):
        # STOP has WORDCQ — STOPPER: S + TO(no WORDCQ) + PPER
        result = tok("STOPPER")
        assert result == "53" + "b8" + "50504552"  # S, TO, PPER

    def test_end_blocked_before_letter(self):
        # END has WORDCQ — ENDGAME must not start with END token (0xe0)
        result = tok("ENDGAME")
        assert not result.startswith("e0")

    def test_false_blocked_before_letter(self):
        # FALSE has WORDCQ — the FALSE token (0xa3) must not appear in FALSETTO
        result = tok("FALSETTO")
        assert "a3" not in result   # 0xa3 = FALSE token must not appear

    def test_return_blocked_before_letter(self):
        # RETURN has WORDCQ — RETURNS stays entirely as ASCII
        assert tok("RETURNS") == bytes("RETURNS", "ascii").hex()

    def test_clear_blocked_before_letter(self):
        # CLEAR has WORDCQ
        assert tok("CLEARLY") == bytes("CLEARLY", "ascii").hex()

    def test_keyword_with_wordcq_matches_before_percent(self):
        # % is not a WORDCQ character — CLEAR% should tokenize CLEAR
        result = tok("CLEAR%")
        assert result.startswith("d8")  # 0xd8 = CLEAR

    def test_to_no_wordcq_matches_in_word(self):
        # TO has no WORDCQ — STOPPER: S + TO + PPER
        assert tok("STOPPER").startswith("53" + "b8")  # S=0x53, TO=0xb8

    def test_until_no_wordcq_before_keyword(self):
        # UNTIL has no WORDCQ — UNTILEOF must tokenize both
        assert tok("UNTILEOF#A%") == "fd" + "c5" + "234125"  # UNTIL+EOF+#A%

    def test_and_no_wordcq_after_lowercase(self):
        # AND has no WORDCQ and no backward boundary (only _ blocks)
        # statnetAND&FF → statnet (ASCII) + AND (token) + &FF
        result = tok("statnetAND&FF")
        assert "80" in result   # 0x80 = AND token


# ── Underscore backward boundary ─────────────────────────────────────────────

class TestUnderscoreBoundary:
    """A keyword must not tokenize when immediately preceded by _ in the output."""

    def test_proc_underscore_error(self):
        # PROC_ERROR: PROC tokenizes, then _ERROR stays ASCII (underscore blocks ERROR)
        # f2=PROC, 5f=_, then E R R O R as ASCII... but OR (no WORDCQ) matches RROR
        # This is the known TalkerD/FTPc limitation — OR tokenizes inside RROR
        result = tok("PROC_ERROR")
        assert result.startswith("f2")        # PROC tokenized
        assert result[2:4] == "5f"            # _ literal
        assert "85" not in result             # 0x85=ERROR must not appear

    def test_underscore_blocks_time(self):
        # x_TIME: the _TIME part — TIME (has WORDCQ) would normally be blocked by T after _
        # but the underscore check is separate: output ends with _, so TIME is blocked
        result = tok("x_TIME=0")
        assert "d1" not in result   # LHS TIME token must not appear
        assert "91" not in result   # RHS TIME token must not appear

    def test_no_underscore_allows_keyword(self):
        # Without underscore prefix, RUN tokenizes normally
        result = tok("RUN")
        assert result == "f9"   # 0xf9 = RUN


# ── Inline line number encoding ───────────────────────────────────────────────

class TestLineNumEncoding:
    """encode_linenum/decode_linenum correctness."""

    def test_known_value_139(self):
        # From CLAUDE.md: line 139 (0x008B) encodes as 0x74 0x4B 0x40
        from bastok import encode_linenum, decode_linenum
        assert encode_linenum(139) == bytes([0x74, 0x4B, 0x40])
        assert decode_linenum(0x74, 0x4B, 0x40) == 139

    def test_round_trip_all_valid(self):
        # All valid line numbers (0–65279) must round-trip through encode/decode
        from bastok import encode_linenum, decode_linenum
        failures = []
        for n in range(65280):
            b = encode_linenum(n)
            assert len(b) == 3
            if decode_linenum(b[0], b[1], b[2]) != n:
                failures.append(n)
        assert not failures, f"{len(failures)} line numbers failed round-trip"

    def test_encoded_bytes_in_safe_range(self):
        # All three bytes must be 0x40–0x7F (avoids token bytes and 0x0D)
        from bastok import encode_linenum
        for n in range(65280):
            b = encode_linenum(n)
            for byte in b:
                assert 0x40 <= byte <= 0x7F, \
                    f"Line {n}: byte {byte:#04x} outside safe range"

    def test_else_encodes_line_number(self):
        # ELSE (both inline 0x8B and line-start 0xCC) triggers line number encoding
        assert encode_linenum(200).hex() in tok("IF x THEN 100 ELSE 200")

    def test_line_number_not_encoded_in_expression(self):
        # GOTO 100+x% — the +x% means 100 is an expression, not a bare line number
        result = tok("GOTO 100+x%")
        assert "8d" not in result   # no inline line number marker
        assert "313030" in result   # "100" as ASCII digits


# ── Extended token prefixes ───────────────────────────────────────────────────

class TestExtendedTokenPrefixes:
    """Verify correct prefix byte for each extended token group."""

    def test_escstmt_prefix_c8(self):
        # All ESCSTMT tokens use prefix 0xC8: CASE, WHILE, SYS, CIRCLE, etc.
        assert tok("CASE x% OF").startswith("c88e")   # CASE = C8 8E
        assert tok("WHILE x%>0").startswith("c895")   # WHILE = C8 95
        assert tok('SYS "X"').startswith("c899")       # SYS = C8 99

    def test_esccom_prefix_c7(self):
        # ESCCOM tokens use prefix 0xC7: APPEND, AUTO, LIST, NEW, etc.
        assert tok("APPEND").startswith("c78e")        # APPEND = C7 8E
        assert tok("NEW").startswith("c797")           # NEW = C7 97

    def test_escfn_prefix_c6(self):
        # ESCFN tokens use prefix 0xC6: SUM and BEAT
        assert "c68e" in tok("x%=SUM(a%())")          # SUM = C6 8E
        assert "c68f" in tok("x%=BEAT")               # BEAT = C6 8F

    def test_extended_wordcq_new(self):
        # NEW has WORDCQ — NEWBURY stays ASCII
        assert tok("NEWBURY") == bytes("NEWBURY", "ascii").hex()

    def test_extended_wordcq_help(self):
        # HELP has WORDCQ — HELPFUL stays ASCII
        assert tok("HELPFUL") == bytes("HELPFUL", "ascii").hex()

    def test_extended_no_wordcq_case(self):
        # CASE has no WORDCQ — CASEWORK tokenizes CASE then emits WORK
        result = tok("CASEWORK")
        assert result.startswith("c88e")   # CASE token at start

    def test_extended_underscore_blocks(self):
        # _SYS: underscore in output blocks SYS from tokenizing
        result = tok("x_SYS")
        assert "c899" not in result   # SYS token must not appear

    def test_dual_install_decodes(self):
        # INSTALL appears at both C8 9A (legacy blunder) and C7 9F
        # Both must decode to INSTALL; tokenizer emits C8 9A (first in table)
        from bastok import ext_decode, tokenize_line
        assert ext_decode(0xC8, 0x9A) == "INSTALL"
        assert ext_decode(0xC7, 0x9F) == "INSTALL"
        assert tok("INSTALL").startswith("c89a")
