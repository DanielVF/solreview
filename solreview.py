#!/usr/bin/env python3
"""
Solidity Code Review Tool

A terminal-based tool for dense, multi-column display of Solidity (.sol) files.
"""

import argparse
import re
import shutil
import sys
import termios
import tty
from dataclasses import dataclass, field
from pathlib import Path


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Block:
    """A code block that shouldn't be split across columns."""
    block_type: str  # 'function', 'contract', 'library', 'interface', 'other'
    name: str  # Name for bolding (empty string if none)
    lines: list[str] = field(default_factory=list)

    @property
    def height(self) -> int:
        return len(self.lines)


@dataclass
class FileContent:
    """Parsed content of a single .sol file."""
    filename: str
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Page:
    """A single page of the display."""
    columns: list[list[str]] = field(default_factory=list)


# =============================================================================
# ANSI Codes
# =============================================================================

BOLD_BLUE = '\033[1;34m'  # Bold + Blue
DIM = '\033[2m'           # Dim/faded
RESET = '\033[0m'
REVERSE = '\033[7m'
CLEAR_SCREEN = '\033[2J\033[H'
ANSI_PATTERN = re.compile(r'\033\[[0-9;]*m')

# Keywords for Solidity definitions (order matters: 'abstract contract' before 'contract')
DEFINITION_KEYWORDS = ['abstract contract', 'contract', 'library', 'interface', 'function', 'modifier', 'constructor']


def visible_length(text: str) -> int:
    """Return the visible length of text, excluding ANSI escape codes."""
    return len(ANSI_PATTERN.sub('', text))


# =============================================================================
# Solidity Parser
# =============================================================================

def strip_comments(code: str) -> str:
    """Remove all comments from Solidity code while preserving string literals."""
    result = []
    i = 0
    n = len(code)

    while i < n:
        # Check for string literals (preserve them)
        if code[i] in ('"', "'"):
            quote_char = code[i]
            result.append(code[i])
            i += 1
            while i < n and code[i] != quote_char:
                if code[i] == '\\' and i + 1 < n:
                    result.append(code[i:i+2])
                    i += 2
                else:
                    result.append(code[i])
                    i += 1
            if i < n:
                result.append(code[i])
                i += 1
        # Check for single-line comment
        elif code[i:i+2] == '//':
            # Skip until end of line
            while i < n and code[i] != '\n':
                i += 1
        # Check for multi-line comment
        elif code[i:i+2] == '/*':
            i += 2
            while i < n and code[i:i+2] != '*/':
                i += 1
            i += 2  # Skip */
        else:
            result.append(code[i])
            i += 1

    return ''.join(result)


def clean_empty_lines(code: str) -> str:
    """Remove all empty lines for vertical compactness."""
    lines = code.split('\n')
    result = [line for line in lines if line.strip() != '']
    return '\n'.join(result)


def extract_names(code: str) -> set[str]:
    """Extract function, contract, library, and interface names for bolding."""
    names = set()
    for keyword in DEFINITION_KEYWORDS:
        pattern = r'\b' + keyword.replace(' ', r'\s+') + r'\s+(\w+)'
        for match in re.finditer(pattern, code):
            names.add(match.group(1))
    return names


def parse_blocks(code: str) -> list[Block]:
    """Parse code into blocks that shouldn't be split."""
    lines = code.split('\n')
    blocks = []
    current_block = Block(block_type='other', name='')
    brace_depth = 0
    in_block = False
    block_start_depth = 0

    # Patterns for block starts
    contract_pattern = re.compile(r'\b(abstract\s+)?(contract|library|interface)\s+(\w+)')
    function_pattern = re.compile(r'\b(function|modifier|constructor|fallback|receive)\s*(\w*)')

    for line in lines:
        stripped = line.strip()

        # Count braces (simple approach - doesn't handle strings perfectly but good enough)
        open_braces = line.count('{')
        close_braces = line.count('}')

        # Check for new block start at depth 0 or 1
        if brace_depth <= 1:
            contract_match = contract_pattern.search(line)
            func_match = function_pattern.search(line)

            if contract_match and brace_depth == 0:
                # Save previous block if it has content
                if current_block.lines:
                    blocks.append(current_block)

                name = contract_match.group(3)
                block_type = contract_match.group(2)
                current_block = Block(block_type=block_type, name=name)
                in_block = True
                block_start_depth = brace_depth

            elif func_match and brace_depth == 1 and func_match.group(1) in ('function', 'modifier', 'constructor', 'fallback', 'receive'):
                # Save previous block
                if current_block.lines:
                    blocks.append(current_block)

                name = func_match.group(2) or func_match.group(1)  # Use keyword if no name
                current_block = Block(block_type=func_match.group(1), name=name)
                in_block = True
                block_start_depth = brace_depth

        current_block.lines.append(line)
        brace_depth += open_braces - close_braces

        # Check if block ended
        if in_block and brace_depth <= block_start_depth and (open_braces > 0 or close_braces > 0):
            if current_block.lines:
                blocks.append(current_block)
            current_block = Block(block_type='other', name='')
            in_block = False

    # Don't forget the last block
    if current_block.lines:
        blocks.append(current_block)

    return blocks


def parse_file(filepath: Path) -> FileContent:
    """Parse a single .sol file into blocks."""
    code = filepath.read_text(encoding='utf-8', errors='replace')
    code = strip_comments(code)
    code = clean_empty_lines(code)
    blocks = parse_blocks(code)

    return FileContent(filename=filepath.name, blocks=blocks)


# =============================================================================
# Layout Engine
# =============================================================================

def calculate_columns(terminal_width: int, min_col_width: int = 80) -> tuple[int, int]:
    """Calculate number of columns and their width."""
    # Reserve 3 chars between columns for separator
    separator_width = 3

    # Try to fit as many columns as possible
    num_cols = max(1, (terminal_width + separator_width) // (min_col_width + separator_width))

    # Calculate actual column width
    col_width = (terminal_width - (num_cols - 1) * separator_width) // num_cols

    return num_cols, col_width


def truncate_line(line: str, width: int) -> str:
    """Truncate a line to fit within width, accounting for ANSI codes."""
    # Simple truncation - count visible characters
    visible_len = 0
    result = []
    i = 0

    while i < len(line):
        if line[i] == '\033':
            # ANSI escape sequence - include it but don't count
            j = i
            while j < len(line) and line[j] != 'm':
                j += 1
            result.append(line[i:j+1])
            i = j + 1
        else:
            if visible_len < width:
                result.append(line[i])
                visible_len += 1
            i += 1

    return ''.join(result)


def create_file_separator(filename: str, width: int) -> list[str]:
    """Create a visual separator for a new file."""
    separator = '\u2500' * width  # Unicode box drawing horizontal line
    name_line = f"  {filename}"
    if len(name_line) > width:
        name_line = name_line[:width-3] + '...'

    return [separator, name_line, separator]


def flow_content(files: list[FileContent], num_cols: int, col_width: int, page_height: int, names: set[str]) -> list[Page]:
    """Flow all content into pages with columns."""
    pages = []
    current_col = 0
    col_heights = [0] * num_cols

    def new_page() -> Page:
        """Create a new page and reset column heights."""
        nonlocal col_heights
        col_heights = [0] * num_cols
        return Page(columns=[[] for _ in range(num_cols)])

    current_page = new_page()

    def space_available(col: int, needed: int) -> bool:
        """Check if there's space in current column."""
        return col_heights[col] + needed <= page_height

    def add_formatted_line(line: str) -> None:
        """Format and add a line to the current column."""
        formatted = apply_bold(line, names)
        formatted = truncate_line(formatted, col_width)
        current_page.columns[current_col].append(formatted)
        col_heights[current_col] += 1

    def find_column_for_block(block_height: int) -> int:
        """Find a column that can fit the block, or start new page."""
        nonlocal current_page, current_col

        # First check current column
        if space_available(current_col, block_height):
            return current_col

        # Try subsequent columns
        for col in range(current_col + 1, num_cols):
            if space_available(col, block_height):
                return col

        # Need new page
        pages.append(current_page)
        current_page = new_page()
        return 0

    for file_content in files:
        # Add file separator
        separator_lines = create_file_separator(file_content.filename, col_width)
        sep_height = len(separator_lines)

        # Find column for separator
        target_col = find_column_for_block(sep_height)
        current_col = target_col

        # Add separator
        for line in separator_lines:
            current_page.columns[current_col].append(line)
            col_heights[current_col] += 1

        # Add each block
        for block in file_content.blocks:
            block_height = block.height

            # Handle oversized blocks (taller than page)
            if block_height > page_height:
                # Split the block at line boundaries
                remaining_lines = block.lines[:]
                while remaining_lines:
                    available = page_height - col_heights[current_col]
                    if available <= 0:
                        current_col += 1
                        if current_col >= num_cols:
                            pages.append(current_page)
                            current_page = new_page()
                            current_col = 0
                        available = page_height

                    chunk = remaining_lines[:available]
                    remaining_lines = remaining_lines[available:]

                    for line in chunk:
                        add_formatted_line(line)
            else:
                # Normal block - find column where it fits
                target_col = find_column_for_block(block_height)
                current_col = target_col

                for line in block.lines:
                    add_formatted_line(line)

    # Don't forget the last page
    if any(col for col in current_page.columns):
        pages.append(current_page)

    return pages if pages else [Page(columns=[[] for _ in range(num_cols)])]


# =============================================================================
# Terminal Renderer
# =============================================================================

def apply_bold(line: str, names: set[str]) -> str:
    """Apply bold formatting to definitions (keyword + name) only."""
    if not names:
        return line
    for keyword in DEFINITION_KEYWORDS:
        for name in names:
            pattern = r'\b(' + re.escape(keyword) + r')(\s+)(' + re.escape(name) + r')\b'
            line = re.sub(pattern, f'{BOLD_BLUE}\\1\\2\\3{RESET}', line)
    return line


def render_page(page: Page, current_page: int, total_pages: int,
                terminal_width: int, terminal_height: int, col_width: int) -> str:
    """Render a single page to a string."""
    output = []
    num_cols = len(page.columns)
    separator = f' {DIM}\u2502{RESET} '  # Unicode vertical bar (dimmed)

    # Calculate the maximum height of all columns
    max_height = max(len(col) for col in page.columns) if page.columns else 0

    # Reserve lines for pagination
    content_height = terminal_height - 2  # 1 for pagination, 1 for blank line

    # Pad columns to equal height
    padded_columns = []
    for col in page.columns:
        padded = col[:content_height]  # Truncate if needed
        padded.extend([''] * (content_height - len(padded)))  # Pad with empty lines
        padded_columns.append(padded)

    # Render each line
    for row_idx in range(content_height):
        row_parts = []
        for col_idx, col in enumerate(padded_columns):
            line = col[row_idx] if row_idx < len(col) else ''
            # Pad line to column width (accounting for ANSI codes)
            padding = ' ' * max(0, col_width - visible_length(line))
            row_parts.append(line + padding)

        output.append(separator.join(row_parts))

    # Add blank line before pagination
    output.append('')

    # Add pagination
    pagination = render_pagination(current_page, total_pages, terminal_width)
    output.append(pagination)

    return '\n'.join(output)


def render_pagination(current: int, total: int, width: int) -> str:
    """Render the pagination bar."""
    if total <= 1:
        return ''

    parts = []
    for i in range(1, total + 1):
        if i == current:
            parts.append(f'{REVERSE}[{i}]{RESET}')
        else:
            parts.append(f'[{i}]')

    pagination = ' '.join(parts)

    # Add navigation hint
    hint = '  (1-9: jump to page, q: quit)'
    full_line = pagination + hint

    # Center it
    padding = ' ' * max(0, (width - visible_length(full_line)) // 2)

    return padding + full_line


# =============================================================================
# Keyboard Input
# =============================================================================

def getch() -> str:
    """Get a single character from stdin without echo."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


# =============================================================================
# Main Application
# =============================================================================

def discover_sol_files(folder: Path) -> list[Path]:
    """Recursively find all .sol files in a folder, sorted by path."""
    return sorted(p for p in folder.rglob('*.sol') if p.is_file())


def run_viewer(folder: Path) -> None:
    """Main viewer loop."""
    # Discover files
    sol_files = discover_sol_files(folder)

    if not sol_files:
        print(f"No .sol files found in {folder}")
        return

    # Parse all files
    print(f"Loading {len(sol_files)} Solidity files...", end='', flush=True)
    files = [parse_file(f) for f in sol_files]
    print(" done.")

    # Collect all names for bolding
    all_code = '\n'.join(
        line for f in files for block in f.blocks for line in block.lines
    )
    names = extract_names(all_code)

    # Main loop
    current_page = 1

    while True:
        # Get terminal size (might change on resize)
        term_size = shutil.get_terminal_size()
        terminal_width = term_size.columns
        terminal_height = term_size.lines

        # Calculate layout
        num_cols, col_width = calculate_columns(terminal_width)
        page_height = terminal_height - 3  # Reserve for pagination

        # Generate pages
        pages = flow_content(files, num_cols, col_width, page_height, names)
        total_pages = len(pages)

        # Clamp current page
        current_page = max(1, min(current_page, total_pages))

        # Render
        page = pages[current_page - 1]
        output = render_page(page, current_page, total_pages,
                           terminal_width, terminal_height, col_width)

        # Display
        print(CLEAR_SCREEN + output, end='', flush=True)

        # Get input
        ch = getch()

        if ch == 'q' or ch == 'Q' or ch == '\x03':  # q or Ctrl+C
            print(CLEAR_SCREEN, end='')
            break
        elif ch.isdigit() and ch != '0':
            page_num = int(ch)
            if 1 <= page_num <= total_pages:
                current_page = page_num
        elif ch == 'n' or ch == ' ':  # Next page
            if current_page < total_pages:
                current_page += 1
        elif ch == 'p' or ch == 'b':  # Previous page
            if current_page > 1:
                current_page -= 1


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Dense multi-column Solidity code viewer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Navigation:
  1-9     Jump to page number
  n/Space Next page
  p/b     Previous page
  q       Quit
'''
    )
    parser.add_argument(
        'folder',
        type=Path,
        help='Folder containing .sol files (searched recursively)'
    )

    args = parser.parse_args()

    if not args.folder.exists():
        print(f"Error: Folder '{args.folder}' does not exist")
        sys.exit(1)

    if not args.folder.is_dir():
        print(f"Error: '{args.folder}' is not a directory")
        sys.exit(1)

    try:
        run_viewer(args.folder)
    except KeyboardInterrupt:
        print(CLEAR_SCREEN, end='')


if __name__ == '__main__':
    main()
