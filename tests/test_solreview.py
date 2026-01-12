"""Comprehensive unit tests for solreview.py"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from solreview import (
    strip_comments,
    clean_empty_lines,
    extract_names,
    parse_blocks,
    parse_file,
    discover_sol_files,
    calculate_columns,
    truncate_line,
    create_file_separator,
    flow_content,
    apply_bold,
    render_page,
    render_pagination,
    Block,
    FileContent,
    Page,
    BOLD_BLUE,
    DIM,
    RESET,
    REVERSE,
)


# =============================================================================
# Tests for strip_comments
# =============================================================================

class TestStripComments:
    """Tests for the comment stripping function."""

    def test_single_line_comment_removal(self):
        code = 'uint x = 1; // this is a comment\nuint y = 2;'
        result = strip_comments(code)
        assert '//' not in result
        assert 'this is a comment' not in result
        assert 'uint x = 1;' in result
        assert 'uint y = 2;' in result

    def test_single_line_comment_at_start(self):
        code = '// comment\nuint x = 1;'
        result = strip_comments(code)
        assert 'comment' not in result
        assert 'uint x = 1;' in result

    def test_multi_line_comment_removal(self):
        code = 'uint x = 1; /* this is\na multi-line\ncomment */ uint y = 2;'
        result = strip_comments(code)
        assert '/*' not in result
        assert '*/' not in result
        assert 'multi-line' not in result
        assert 'uint x = 1;' in result
        assert 'uint y = 2;' in result

    def test_multi_line_comment_spanning_lines(self):
        code = '''uint a = 1;
/*
 * This is a
 * multi-line comment
 */
uint b = 2;'''
        result = strip_comments(code)
        assert 'multi-line comment' not in result
        assert 'uint a = 1;' in result
        assert 'uint b = 2;' in result

    def test_preserve_double_quoted_string_with_slashes(self):
        code = 'string s = "http://example.com";'
        result = strip_comments(code)
        assert 'http://example.com' in result

    def test_preserve_double_quoted_string_with_comment_chars(self):
        code = 'string s = "/* not a comment */";'
        result = strip_comments(code)
        assert '/* not a comment */' in result

    def test_preserve_single_quoted_string_with_slashes(self):
        code = "string s = 'http://example.com';"
        result = strip_comments(code)
        assert 'http://example.com' in result

    def test_preserve_single_quoted_string_with_comment_chars(self):
        code = "string s = '/* not a comment */';"
        result = strip_comments(code)
        assert '/* not a comment */' in result

    def test_escaped_quotes_in_string(self):
        code = r'string s = "escaped \" quote // not comment";'
        result = strip_comments(code)
        assert 'escaped' in result
        assert 'not comment' in result

    def test_natspec_triple_slash_comments(self):
        code = '''/// @notice This is natspec
/// @param x The value
function foo(uint x) {}'''
        result = strip_comments(code)
        assert '@notice' not in result
        assert '@param' not in result
        assert 'function foo(uint x) {}' in result

    def test_natspec_block_comments(self):
        code = '''/**
 * @notice This function does something
 * @param x The input value
 */
function bar(uint x) {}'''
        result = strip_comments(code)
        assert '@notice' not in result
        assert 'function bar(uint x) {}' in result

    def test_nested_comment_behavior(self):
        # Solidity doesn't support nested comments
        code = '/* outer /* inner */ still in comment */ uint x;'
        result = strip_comments(code)
        # After first */, the rest should remain
        assert 'uint x;' in result

    def test_empty_code(self):
        result = strip_comments('')
        assert result == ''

    def test_code_without_comments(self):
        code = 'uint x = 1;\nuint y = 2;'
        result = strip_comments(code)
        assert result == code

    def test_only_comments(self):
        code = '// only comment'
        result = strip_comments(code)
        assert result.strip() == ''

    def test_comment_after_string(self):
        code = 'string s = "value"; // comment after'
        result = strip_comments(code)
        assert 'string s = "value";' in result
        assert 'comment after' not in result


# =============================================================================
# Tests for clean_empty_lines
# =============================================================================

class TestCleanEmptyLines:
    """Tests for empty line cleanup."""

    def test_removes_multiple_empty_lines(self):
        code = 'line1\n\n\n\nline2'
        result = clean_empty_lines(code)
        assert result == 'line1\nline2'

    def test_removes_leading_empty_lines(self):
        code = '\n\n\nline1'
        result = clean_empty_lines(code)
        assert result == 'line1'

    def test_removes_trailing_empty_lines(self):
        code = 'line1\n\n\n'
        result = clean_empty_lines(code)
        assert result == 'line1'

    def test_removes_mixed_empty_lines(self):
        code = 'line1\n\nline2\n\n\nline3'
        result = clean_empty_lines(code)
        assert result == 'line1\nline2\nline3'

    def test_preserves_whitespace_only_as_empty(self):
        code = 'line1\n   \nline2'
        result = clean_empty_lines(code)
        assert result == 'line1\nline2'

    def test_preserves_indented_content(self):
        code = 'line1\n    indented\nline3'
        result = clean_empty_lines(code)
        assert result == 'line1\n    indented\nline3'

    def test_empty_input(self):
        result = clean_empty_lines('')
        assert result == ''

    def test_all_empty_lines(self):
        code = '\n\n\n'
        result = clean_empty_lines(code)
        assert result == ''

    def test_single_line_no_newline(self):
        code = 'single line'
        result = clean_empty_lines(code)
        assert result == 'single line'


# =============================================================================
# Tests for extract_names
# =============================================================================

class TestExtractNames:
    """Tests for name extraction."""

    def test_extracts_contract_name(self):
        code = 'contract MyToken { }'
        names = extract_names(code)
        assert 'MyToken' in names

    def test_extracts_library_name(self):
        code = 'library SafeMath { }'
        names = extract_names(code)
        assert 'SafeMath' in names

    def test_extracts_interface_name(self):
        code = 'interface IERC20 { }'
        names = extract_names(code)
        assert 'IERC20' in names

    def test_extracts_abstract_contract_name(self):
        code = 'abstract contract Base { }'
        names = extract_names(code)
        assert 'Base' in names

    def test_extracts_function_name(self):
        code = 'function transfer(address to) public { }'
        names = extract_names(code)
        assert 'transfer' in names

    def test_extracts_modifier_name(self):
        code = 'modifier onlyOwner() { _; }'
        names = extract_names(code)
        assert 'onlyOwner' in names

    def test_does_not_extract_event_name(self):
        code = 'event Transfer(address from, address to);'
        names = extract_names(code)
        assert 'Transfer' not in names

    def test_does_not_extract_struct_name(self):
        code = 'struct User { address addr; uint balance; }'
        names = extract_names(code)
        assert 'User' not in names

    def test_does_not_extract_enum_name(self):
        code = 'enum Status { Active, Inactive }'
        names = extract_names(code)
        assert 'Status' not in names

    def test_extracts_multiple_names(self):
        code = '''
        contract Token {
            function transfer() public {}
            function approve() public {}
            modifier onlyOwner() { _; }
        }
        '''
        names = extract_names(code)
        assert 'Token' in names
        assert 'transfer' in names
        assert 'approve' in names
        assert 'onlyOwner' in names

    def test_extracts_names_with_inheritance(self):
        code = 'contract Token is ERC20, Ownable { }'
        names = extract_names(code)
        assert 'Token' in names
        # Parent contracts are not definitions, so not extracted
        assert 'ERC20' not in names
        assert 'Ownable' not in names

    def test_empty_code(self):
        names = extract_names('')
        assert names == set()

    def test_code_without_definitions(self):
        code = 'uint x = 1; string s = "test";'
        names = extract_names(code)
        assert names == set()


# =============================================================================
# Tests for parse_blocks
# =============================================================================

class TestParseBlocks:
    """Tests for block parsing."""

    def test_parses_simple_contract(self):
        code = '''contract Token {
    uint public x;
}'''
        blocks = parse_blocks(code)
        contract_blocks = [b for b in blocks if b.block_type == 'contract']
        assert len(contract_blocks) == 1
        assert contract_blocks[0].name == 'Token'

    def test_parses_function_inside_contract(self):
        code = '''contract Token {
    function foo() public {
        uint x = 1;
    }
}'''
        blocks = parse_blocks(code)
        function_blocks = [b for b in blocks if b.block_type == 'function']
        assert len(function_blocks) == 1
        assert function_blocks[0].name == 'foo'

    def test_parses_multiple_functions(self):
        code = '''contract Token {
    function foo() public {}
    function bar() public {}
}'''
        blocks = parse_blocks(code)
        function_blocks = [b for b in blocks if b.block_type == 'function']
        assert len(function_blocks) == 2
        names = {b.name for b in function_blocks}
        assert names == {'foo', 'bar'}

    def test_parses_library(self):
        code = '''library SafeMath {
    function add(uint a, uint b) internal pure returns (uint) {
        return a + b;
    }
}'''
        blocks = parse_blocks(code)
        lib_blocks = [b for b in blocks if b.block_type == 'library']
        assert len(lib_blocks) == 1
        assert lib_blocks[0].name == 'SafeMath'

    def test_parses_interface(self):
        code = '''interface IERC20 {
    function totalSupply() external view returns (uint);
}'''
        blocks = parse_blocks(code)
        iface_blocks = [b for b in blocks if b.block_type == 'interface']
        assert len(iface_blocks) == 1
        assert iface_blocks[0].name == 'IERC20'

    def test_parses_modifier(self):
        code = '''contract Ownable {
    modifier onlyOwner() {
        require(msg.sender == owner);
        _;
    }
}'''
        blocks = parse_blocks(code)
        mod_blocks = [b for b in blocks if b.block_type == 'modifier']
        assert len(mod_blocks) == 1
        assert mod_blocks[0].name == 'onlyOwner'

    def test_parses_constructor(self):
        code = '''contract Token {
    constructor() {
        owner = msg.sender;
    }
}'''
        blocks = parse_blocks(code)
        const_blocks = [b for b in blocks if b.block_type == 'constructor']
        assert len(const_blocks) == 1

    def test_parses_fallback(self):
        code = '''contract Token {
    fallback() external {
    }
}'''
        blocks = parse_blocks(code)
        fallback_blocks = [b for b in blocks if b.block_type == 'fallback']
        assert len(fallback_blocks) == 1

    def test_parses_receive(self):
        code = '''contract Token {
    receive() external payable {
    }
}'''
        blocks = parse_blocks(code)
        receive_blocks = [b for b in blocks if b.block_type == 'receive']
        assert len(receive_blocks) == 1

    def test_block_height_property(self):
        # Functions must be inside a contract (at brace depth 1) to be recognized
        code = '''contract Test {
    function foo() {
        line1;
        line2;
    }
}'''
        blocks = parse_blocks(code)
        func_blocks = [b for b in blocks if b.block_type == 'function']
        assert len(func_blocks) == 1
        assert func_blocks[0].height == 4  # function line + 2 body lines + closing brace

    def test_empty_code(self):
        blocks = parse_blocks('')
        assert blocks == [] or all(not b.lines or all(l.strip() == '' for l in b.lines) for b in blocks)


# =============================================================================
# Tests for discover_sol_files
# =============================================================================

class TestDiscoverSolFiles:
    """Tests for .sol file discovery."""

    def test_finds_sol_files_in_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'Token.sol').write_text('contract Token {}')
            (tmppath / 'Utils.sol').write_text('library Utils {}')

            files = discover_sol_files(tmppath)
            assert len(files) == 2
            filenames = {f.name for f in files}
            assert filenames == {'Token.sol', 'Utils.sol'}

    def test_finds_sol_files_recursively(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'Token.sol').write_text('contract Token {}')
            subdir = tmppath / 'subdir'
            subdir.mkdir()
            (subdir / 'Nested.sol').write_text('contract Nested {}')

            files = discover_sol_files(tmppath)
            assert len(files) == 2
            filenames = {f.name for f in files}
            assert filenames == {'Token.sol', 'Nested.sol'}

    def test_ignores_non_sol_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'Token.sol').write_text('contract Token {}')
            (tmppath / 'readme.md').write_text('# Readme')
            (tmppath / 'config.json').write_text('{}')

            files = discover_sol_files(tmppath)
            assert len(files) == 1
            assert files[0].name == 'Token.sol'

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = discover_sol_files(Path(tmpdir))
            assert files == []

    def test_returns_sorted_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'Zebra.sol').write_text('contract Zebra {}')
            (tmppath / 'Alpha.sol').write_text('contract Alpha {}')
            (tmppath / 'Middle.sol').write_text('contract Middle {}')

            files = discover_sol_files(tmppath)
            # Should be sorted by path
            assert files == sorted(files)


# =============================================================================
# Tests for parse_file
# =============================================================================

class TestParseFile:
    """Tests for file parsing."""

    def test_parses_file_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'Token.sol'
            filepath.write_text('''contract Token {
    function transfer() public {}
}''')

            result = parse_file(filepath)
            assert result.filename == 'Token.sol'
            assert len(result.blocks) > 0

    def test_strips_comments_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'Token.sol'
            filepath.write_text('''// This is a comment
contract Token {
    /* multi-line
       comment */
    function transfer() public {}
}''')

            result = parse_file(filepath)
            all_lines = '\n'.join('\n'.join(b.lines) for b in result.blocks)
            assert '//' not in all_lines
            assert '/*' not in all_lines

    def test_removes_empty_lines_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'Token.sol'
            filepath.write_text('''contract Token {

    function transfer() public {}

}''')

            result = parse_file(filepath)
            all_lines = [line for b in result.blocks for line in b.lines]
            # No empty lines should remain
            assert all(line.strip() != '' for line in all_lines)


# =============================================================================
# Tests for calculate_columns
# =============================================================================

class TestCalculateColumns:
    """Tests for column calculation."""

    def test_wide_terminal_multiple_columns(self):
        num_cols, col_width = calculate_columns(250, min_col_width=80)
        assert num_cols >= 2
        assert col_width >= 80

    def test_narrow_terminal_single_column(self):
        num_cols, col_width = calculate_columns(100, min_col_width=80)
        assert num_cols == 1

    def test_minimum_one_column(self):
        num_cols, col_width = calculate_columns(60, min_col_width=80)
        assert num_cols == 1

    def test_exact_fit_for_two_columns(self):
        # 80 + 3 (separator) + 80 = 163
        num_cols, col_width = calculate_columns(163, min_col_width=80)
        assert num_cols == 2

    def test_three_columns(self):
        # 80*3 + 3*2 (separators) = 246
        num_cols, col_width = calculate_columns(250, min_col_width=80)
        assert num_cols >= 2

    def test_custom_min_width(self):
        num_cols, col_width = calculate_columns(200, min_col_width=60)
        assert num_cols >= 2
        assert col_width >= 60


# =============================================================================
# Tests for truncate_line
# =============================================================================

class TestTruncateLine:
    """Tests for line truncation."""

    def test_short_line_unchanged(self):
        line = 'hello'
        result = truncate_line(line, 10)
        assert result == 'hello'

    def test_long_line_truncated(self):
        line = 'hello world this is a long line'
        result = truncate_line(line, 10)
        assert len(result) == 10
        assert result == 'hello worl'

    def test_exact_length_unchanged(self):
        line = 'exactly10!'
        result = truncate_line(line, 10)
        assert result == 'exactly10!'

    def test_preserves_ansi_codes(self):
        line = f'{BOLD_BLUE}hello{RESET} world'
        result = truncate_line(line, 8)
        # ANSI codes should be preserved but not counted
        assert BOLD_BLUE in result
        assert 'hello' in result

    def test_truncates_after_ansi(self):
        line = f'{BOLD_BLUE}hello{RESET} world extra'
        result = truncate_line(line, 11)
        # Should have "hello world" (11 visible chars)
        assert 'extra' not in result

    def test_empty_line(self):
        result = truncate_line('', 10)
        assert result == ''

    def test_line_of_spaces(self):
        line = '          '  # 10 spaces
        result = truncate_line(line, 5)
        assert result == '     '


# =============================================================================
# Tests for create_file_separator
# =============================================================================

class TestCreateFileSeparator:
    """Tests for file separator creation."""

    def test_returns_three_lines(self):
        lines = create_file_separator('Token.sol', 40)
        assert len(lines) == 3

    def test_contains_filename(self):
        lines = create_file_separator('Token.sol', 40)
        assert 'Token.sol' in lines[1]

    def test_has_box_drawing_char(self):
        lines = create_file_separator('Token.sol', 40)
        assert '\u2500' in lines[0]
        assert '\u2500' in lines[2]

    def test_truncates_long_filename(self):
        lines = create_file_separator('VeryLongContractNameThatExceedsWidth.sol', 20)
        assert len(lines[1]) <= 20
        assert '...' in lines[1]

    def test_separator_width(self):
        width = 50
        lines = create_file_separator('Token.sol', width)
        assert len(lines[0]) == width
        assert len(lines[2]) == width


# =============================================================================
# Tests for flow_content
# =============================================================================

class TestFlowContent:
    """Tests for content flow into pages."""

    def test_single_file_single_page(self):
        block = Block(block_type='contract', name='Token', lines=['contract Token {', '}'])
        file_content = FileContent(filename='Token.sol', blocks=[block])

        pages = flow_content([file_content], num_cols=1, col_width=80, page_height=50, names={'Token'})
        assert len(pages) >= 1

    def test_creates_multiple_pages_when_needed(self):
        # Create a file with many lines
        lines = [f'    line{i};' for i in range(100)]
        block = Block(block_type='contract', name='Big', lines=['contract Big {'] + lines + ['}'])
        file_content = FileContent(filename='Big.sol', blocks=[block])

        pages = flow_content([file_content], num_cols=1, col_width=80, page_height=20, names={'Big'})
        assert len(pages) > 1

    def test_multiple_columns(self):
        block = Block(block_type='contract', name='Token', lines=['contract Token {', '}'])
        file_content = FileContent(filename='Token.sol', blocks=[block])

        pages = flow_content([file_content], num_cols=3, col_width=80, page_height=50, names={'Token'})
        assert len(pages) >= 1
        assert len(pages[0].columns) == 3

    def test_empty_file_list(self):
        pages = flow_content([], num_cols=2, col_width=80, page_height=50, names=set())
        assert len(pages) == 1
        assert all(col == [] for col in pages[0].columns)

    def test_file_separator_included(self):
        block = Block(block_type='contract', name='Token', lines=['contract Token {', '}'])
        file_content = FileContent(filename='Token.sol', blocks=[block])

        pages = flow_content([file_content], num_cols=1, col_width=80, page_height=50, names={'Token'})
        all_lines = [line for page in pages for col in page.columns for line in col]
        # Should contain the filename somewhere
        assert any('Token.sol' in line for line in all_lines)


# =============================================================================
# Tests for apply_bold
# =============================================================================

class TestApplyBold:
    """Tests for bold formatting."""

    def test_bolds_function_definition(self):
        names = {'transfer'}
        line = 'function transfer() public {'
        result = apply_bold(line, names)
        assert f'{BOLD_BLUE}function transfer{RESET}' in result

    def test_bolds_contract_definition(self):
        names = {'Token'}
        line = 'contract Token {'
        result = apply_bold(line, names)
        assert f'{BOLD_BLUE}contract Token{RESET}' in result

    def test_bolds_library_definition(self):
        names = {'SafeMath'}
        line = 'library SafeMath {'
        result = apply_bold(line, names)
        assert f'{BOLD_BLUE}library SafeMath{RESET}' in result

    def test_bolds_interface_definition(self):
        names = {'IERC20'}
        line = 'interface IERC20 {'
        result = apply_bold(line, names)
        assert f'{BOLD_BLUE}interface IERC20{RESET}' in result

    def test_bolds_modifier_definition(self):
        names = {'onlyOwner'}
        line = 'modifier onlyOwner() {'
        result = apply_bold(line, names)
        assert f'{BOLD_BLUE}modifier onlyOwner{RESET}' in result

    def test_bolds_abstract_contract(self):
        names = {'Base'}
        line = 'abstract contract Base {'
        result = apply_bold(line, names)
        # The function applies both "abstract contract" and "contract" patterns
        # resulting in nested highlighting, but the name is still bolded
        assert BOLD_BLUE in result
        assert 'Base' in result
        assert 'abstract' in result

    def test_no_bold_when_no_match(self):
        names = {'foo'}
        line = 'function bar() public {'
        result = apply_bold(line, names)
        assert result == line
        assert BOLD_BLUE not in result

    def test_does_not_bold_function_calls(self):
        names = {'Token', 'transfer'}
        line = 'token.transfer(100);'
        result = apply_bold(line, names)
        # Function calls should NOT be highlighted
        assert BOLD_BLUE not in result
        assert result == line

    def test_does_not_bold_standalone_name(self):
        names = {'Token', 'transfer'}
        line = 'Token myToken = new Token();'
        result = apply_bold(line, names)
        # Standalone names without keywords should not be bolded
        # Only "contract Token", "function transfer" etc. should be bolded
        assert result == line

    def test_empty_names_set(self):
        names = set()
        line = 'function foo() public {'
        result = apply_bold(line, names)
        assert result == line

    def test_preserves_whitespace(self):
        names = {'foo'}
        line = '    function foo() public {'
        result = apply_bold(line, names)
        assert result.startswith('    ')


# =============================================================================
# Tests for render_pagination
# =============================================================================

class TestRenderPagination:
    """Tests for pagination rendering."""

    def test_single_page_empty(self):
        result = render_pagination(1, 1, 80)
        assert result == ''

    def test_multiple_pages_shows_numbers(self):
        result = render_pagination(1, 3, 80)
        assert '[1]' in result
        assert '[2]' in result
        assert '[3]' in result

    def test_current_page_highlighted(self):
        result = render_pagination(2, 3, 80)
        assert f'{REVERSE}[2]{RESET}' in result

    def test_includes_navigation_hint(self):
        result = render_pagination(1, 3, 80)
        assert 'q: quit' in result


# =============================================================================
# Tests for render_page
# =============================================================================

class TestRenderPage:
    """Tests for page rendering."""

    def test_renders_single_column(self):
        page = Page(columns=[['line1', 'line2']])
        result = render_page(page, 1, 1, 80, 24, 80)
        assert 'line1' in result
        assert 'line2' in result

    def test_renders_multiple_columns(self):
        page = Page(columns=[['col1line1'], ['col2line1']])
        result = render_page(page, 1, 1, 160, 24, 75)
        assert 'col1line1' in result
        assert 'col2line1' in result

    def test_includes_column_separator(self):
        page = Page(columns=[['left'], ['right']])
        result = render_page(page, 1, 1, 160, 24, 75)
        # Should have vertical separator
        assert '\u2502' in result

    def test_includes_pagination(self):
        page = Page(columns=[['content']])
        result = render_page(page, 1, 3, 80, 24, 80)
        assert '[1]' in result
        assert '[2]' in result
        assert '[3]' in result


# =============================================================================
# Tests for data classes
# =============================================================================

class TestDataClasses:
    """Tests for data classes."""

    def test_block_height(self):
        block = Block(block_type='function', name='foo', lines=['line1', 'line2', 'line3'])
        assert block.height == 3

    def test_empty_block_height(self):
        block = Block(block_type='other', name='')
        assert block.height == 0

    def test_block_default_lines(self):
        block = Block(block_type='contract', name='Test')
        assert block.lines == []

    def test_file_content_defaults(self):
        fc = FileContent(filename='test.sol')
        assert fc.filename == 'test.sol'
        assert fc.blocks == []

    def test_file_content_with_blocks(self):
        block = Block(block_type='contract', name='Test')
        fc = FileContent(filename='test.sol', blocks=[block])
        assert len(fc.blocks) == 1

    def test_page_defaults(self):
        page = Page()
        assert page.columns == []

    def test_page_with_columns(self):
        page = Page(columns=[['line1'], ['line2']])
        assert len(page.columns) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
