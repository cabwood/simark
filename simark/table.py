import re
import html
from .parse import Parser, NoMatch, Many, Any, All, Opt, Regex, Exact, Chunk
from .core import ElementParser, Element, Text, VerbatimParser, \
    unescape, esc_element_open, esc_element_close, \
    ESC_BACKSLASH, ESC_BACKTICK, ESC_ELEMENT_OPEN, ESC_ELEMENT_CLOSE


all_whitespace_parser = Regex(r'\s*')
no_nl_whitespace_parser = Regex(r'[^\S\n]*')

def parse_whitespace(context):
    allow_newline = context.state.get('allow_newline', True)
    if allow_newline:
        return all_whitespace_parser.parse(context)
    return no_nl_whitespace_parser.parse(context)


table_border_classes = {
    '0': ('bt0', 'bb0', 'bl0', 'br0'),
    '1': ('bt1', 'bb1', 'bl1', 'br1'),
    '2': ('bt2', 'bb2', 'bl2', 'br2'),
    '3': ('bt3', 'bb3', 'bl3', 'br3'),
}

table_align_classes = {
    '<': ('at', 'al'),
    '=': ('am', 'ac'),
    '>': ('ab', 'ar'),
}

def expand_format_str(s, count):
    out = ['_'] * count
    last = '_'
    in_index = 0
    out_index = 0
    while in_index < len(s):
        this = s[in_index]
        if this == '*':
            # Repeat last char until end
            while out_index < count:
                out[out_index] = last
                out_index += 1
            in_index += 1
            break
        if out_index < count:
            out[out_index] = this
        out_index += 1
        in_index += 1
        last = this
    out_index = max(0, count - (len(s) - in_index))
    while out_index < count:
        out[out_index] = s[in_index]
        out_index += 1
        in_index += 1
    return ''.join(out)

def fix_borders(s):
    return ''.join(c if c in table_border_classes else '_' for c in s)

def fix_aligns(s):
    return ''.join(c if c in table_align_classes else '_' for c in s)


class _Formats:

    def __init__(self):
        self.formats = []

    def get_format(self, row_index, col_index):
        if row_index >= len(self.formats):
            return ''
        row = self.formats[row_index]
        if col_index >= len(row):
            return ''
        return row[col_index]

    def set_format(self, row_index, col_index, format):
        if format and format != '_':
            if row_index >= len(self.formats):
                for n in range(row_index - len(self.formats) + 1):
                    self.formats.append([])
            row = self.formats[row_index]
            if col_index >= len(row):
                for n in range(col_index - len(row) + 1):
                    row.append('')
            row[col_index] = format

    def __str__(self):
        return '\n'.join(' '.join(col for col in row) for row in self.formats)


class TableFormats:

    def __init__(self):
        self.row_borders = _Formats()
        self.col_borders = _Formats()
        self.row_align = _Formats()
        self.col_align = _Formats()


class TableTextParser(Parser):
    """
    Like TextParser, except bar '|' and possibly newline terminates the text.
    """

    all_parser = Regex(rf"(\\\\|\\`|\\\||\\{esc_element_open}|\\{esc_element_close}|[^|`{esc_element_open}{esc_element_close}])+")
    no_nl_parser = Regex(rf"(\\\\|\\`|\\\||\\{esc_element_open}|\\{esc_element_close}|[^\n|`{esc_element_open}{esc_element_close}])+")

    def parse1(self, context):
        if context.state.get('allow_newline'):
            match = self.all_parser.parse(context).match
        else:
            match = self.no_nl_parser.parse(context).match
        return Text(context.src, match.start(0), match.end(0), unescape(match[0],
            ESC_BACKSLASH,
            ESC_BACKTICK,
            ESC_ELEMENT_OPEN,
            ESC_ELEMENT_CLOSE,
            ('\\|', '|'),
        ))


class TableCaption(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, show_numbers=None, visible=None):
        super().__init__(src, start_pos, end_pos, children, name=name, arguments=arguments)
        self.show_numbers = True if show_numbers is None else show_numbers
        self.visible = True if visible is None else visible

    def setup(self, context):
        self.numbers = context.table_numbers

    def render_html(self, context):
        if not self.visible:
            return ''
        html_out = self.render_children_html(context)
        if self.show_numbers:
            html_out = f'Table {html.escape(self.numbers)}. {html_out}'
        html_out = html_out.strip()
        if html_out:
            indent, newline = self.get_whitespace()
            html_out = f'{indent}<caption>{html_out}</caption>{newline}'
        return html_out


class _CaptionShortParser(Parser):

    start_parser = Regex(r'[^\s\|]', consume=False)

    def parse1(self, context):
        self.start_parser.parse(context)
        context.push(allow_newline=False)
        try:
            start_pos = context.pos
            children = self.get_child_parser(context).parse(context).children
            return TableCaption(context.src, start_pos, context.pos, children)
        finally:
            context.pop()

    def get_child_parser(self, context):
        if not hasattr(self, '_child_parser'):
            self._child_parser = Many(
                Any(
                    VerbatimParser(),
                    *context.state.get('parsers', []),
                    TableTextParser(),
                ),
            )
        return self._child_parser


class _CaptionElementParser(ElementParser):

    names = ['caption']
    element_class = TableCaption

    def check_arguments(self, context, arguments, extra):
        extra['show_numbers'] = arguments.get_bool('numbers')
        return arguments


class TableCaptionParser(Parser):

    content_parser = Any(
        _CaptionElementParser(),
        _CaptionShortParser(),
    )

    def parse1(self, context):
        return self.content_parser.parse(context)



class _BaseElement(Element):
    """
    Ancenstor class for tables, sections, rows and cells, handling common
    formatting features that they all share.
    """

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, row_borders=None, col_borders=None, row_align=None, col_align=None):
        super().__init__(src, start_pos, end_pos, children, name=name, arguments=arguments)
        self.row_borders = row_borders or ''
        self.col_borders = col_borders or ''
        self.row_align = row_align or ''
        self.col_align = col_align or ''

    def get_bounds_rect(self):
        raise NotImplementedError

    def apply_formats(self, formats):
        self.formats = formats
        row_offset, col_offset, row_count, col_count = self.get_bounds_rect()
        row_borders = fix_borders(expand_format_str(self.row_borders, row_count+1))
        col_borders = fix_borders(expand_format_str(self.col_borders, col_count+1))
        row_align = fix_aligns(expand_format_str(self.row_align, row_count))
        col_align = fix_aligns(expand_format_str(self.col_align, col_count))
        for row_index in range(row_count + 1):
            for col_index in range(col_count):
                formats.row_borders.set_format(row_offset + row_index, col_offset + col_index, row_borders[row_index])
        for col_index in range(col_count + 1):
            for row_index in range(row_count):
                formats.col_borders.set_format(row_offset + row_index, col_offset + col_index, col_borders[col_index])
        for row_index in range(row_count):
            for col_index in range(col_count):
                formats.row_align.set_format(row_offset + row_index, col_offset + col_index, row_align[row_index])
        for col_index in range(col_count):
            for row_index in range(row_count):
                formats.col_align.set_format(row_offset + row_index, col_offset + col_index, col_align[col_index])
        self.apply_child_formats(formats)

    def apply_child_formats(self, formats):
        pass



class _BaseElementParser(ElementParser):

    def check_arguments(self, context, arguments, extra):
        extra['row_borders'] = arguments.get('row_borders', default='')
        extra['col_borders'] = arguments.get('col_borders', default='')
        extra['row_align'] = arguments.get('row_align', default='')
        extra['col_align'] = arguments.get('col_align', default='')
        return arguments


class TableCell(_BaseElement):

    paragraphs = True
    html_tag = 'td'

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, \
            row_borders=None, col_borders=None, col_align=None, row_align=None, \
            col_span=None, row_span=None, short=False):
        super().__init__(src, start_pos, end_pos, children, name, arguments, \
            row_align=row_align, col_align=col_align, row_borders=row_borders, col_borders=col_borders)
        self.col_span = 1 if col_span is None else col_span
        self.row_span = 1 if row_span is None else row_span
        self.short = short

    def before_child_setup(self, context):
        # Render children compact
        context.compact = True

    def render_html(self, context):
        classes = []
        format = self.formats.row_borders.get_format(self.row_index, self.col_index)
        if format:
            classes.append(table_border_classes[format][0])
        format = self.formats.row_borders.get_format(self.row_index + self.row_span, self.col_index)
        if format:
            classes.append(table_border_classes[format][1])
        format = self.formats.col_borders.get_format(self.row_index, self.col_index)
        if format:
            classes.append(table_border_classes[format][2])
        format = self.formats.col_borders.get_format(self.row_index, self.col_index + self.col_span)
        if format:
            classes.append(table_border_classes[format][3])
        format = self.formats.row_align.get_format(self.row_index, self.col_index)
        if format:
            classes.append(table_align_classes[format][0])
        format = self.formats.col_align.get_format(self.row_index, self.col_index)
        if format:
            classes.append(table_align_classes[format][1])
        class_attr = self.get_class_attr(context, *classes)
        row_span_attr = f' rowspan="{self.row_span}"' if self.row_span > 1 else ''
        col_span_attr = f' colspan="{self.col_span}"' if self.col_span > 1 else ''
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<{self.html_tag}{class_attr}{row_span_attr}{col_span_attr}>{html_out}</{self.html_tag}>{newline}'

    def get_bounds_rect(self):
        return self.row_index, self.col_index, self.row_span, self.col_span


class _CellShortParser(Parser):
    """
    Finds and returns a TableCell parsed from bar '|' delimited content.
    """

    lead_parser = Regex(r'(\|+)(~*)([_<>=]?)([_<>=]?)')

    def parse1(self, context):
        start_pos = context.pos
        parse_whitespace(context)
        try:
            lead = self.lead_parser.parse(context)
        except NoMatch:
            # Leader was absent or not found, so set default cell properties
            lead = None
            col_span = 1
            row_span = 1
            col_align = '_'
            row_align = '_'
        else:
            # Leader present, set cell properties according to leader content
            col_span = len(lead.match[1])
            row_span = max(1, len(lead.match[2]))
            col_align = lead.match[3] if lead.match[3] else '_'
            row_align = lead.match[4] if lead.match[4] else '_'
        parse_whitespace(context)
        children = self.get_child_parser(context).parse(context).children
        return TableCell(context.src, start_pos, context.pos, children, \
            row_align=row_align, col_align=col_align, col_span=col_span, row_span=row_span, short=True)

    def get_child_parser(self, context):
        if not hasattr(self, '_child_parser'):
            self._child_parser = Many(
                Any(
                    VerbatimParser(),
                    *context.state.get('parsers', []),
                    TableTextParser(),
                ),
            )
        return self._child_parser


class _CellElementParser(_BaseElementParser):
    """
    Finds and returns a TableCell parsed from a {cell} construct.
    """

    names = ['cell']
    element_class = TableCell

    lead_parser = Regex(r'\|?[^\S\n]*')

    def parse1(self, context):
        parse_whitespace(context)
        # Look for an optional bar prefix prior to the {cell} proper
        self.lead_parser.parse(context)
        return super().parse1(context)

    def parse_children(self, context):
        # Contents of a {cell} construct may always contain newlines
        context.push(allow_newline=True)
        try:
            return super().parse_children(context)
        finally:
            context.pop()

    def check_arguments(self, context, arguments, extra):
        arguments = super().check_arguments(context, arguments, extra)
        extra['col_span'] = arguments.get_int('col_span')
        extra['row_span'] = arguments.get_int('row_span')
        return arguments


class TableCellParser(Parser):

    content_parser = Any(
        _CellElementParser(),
        _CellShortParser(),
    )

    def parse1(self, context):
        return self.content_parser.parse(context)


class TableRow(_BaseElement):

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<tr{class_attr}>{newline}{html_out}{newline}{indent}</tr>{newline}'

    def get_bounds_rect(self):
        last = self.children[-1]
        return self.row_index, 0, 1, last.col_index + last.col_span

    def apply_child_formats(self, formats):
        for child in self.children:
            child.apply_formats(formats)


class _CellsParser(Parser):

    cells_parser = Many(TableCellParser(), min_count=1)

    def parse1(self, context):
        chunk = self.cells_parser.parse(context)
        # Drop the last cell if it's an empty shorthand one. For aesthetic
        # reasons, a shorthand row can be terminated with '|' without creating
        # a cell, but if the cell is explicity defined using {cell}, then
        # we can assume that the trailing cell is intentional.
        last = chunk.children[-1]
        if last.short and not last.children:
            del chunk.children[-1]
        return chunk


class _RowShortParser(Parser):
    """
    Finds and returns a TableRow expressed in bar-delimited form.
    """

    start_parser = Regex(r'\S', consume=False)
    cells_parser = _CellsParser()

    def parse1(self, context):
        self.start_parser.parse(context)
        # Shorthand rows are terminated by a newline, so do not permit
        # newlines in the parsed cells
        context.push(allow_newline=False)
        try:
            start_pos = context.pos
            cells = self.cells_parser.parse(context).children
            return TableRow(context.src, start_pos, context.pos, cells)
        finally:
            context.pop()


class _RowElementParser(_BaseElementParser):
    """
    Finds and returns a TableRow expressed as a {row} construct.
    """

    names = ['row']
    element_class = TableRow

    cells_parser = _CellsParser()

    def parse_children(self, context):
        # {row} elements can contain newline characters in their child cells,
        # since they are not terminated by newline.
        context.push(allow_newline=True)
        try:
            return self.cells_parser.parse(context).children
        finally:
            context.pop()


class TableRowParser(Parser):

    row_parser = Any(
        _RowElementParser(),
        _RowShortParser(),
    )

    def parse1(self, context):
        return self.row_parser.parse(context)


class TableSection(_BaseElement):

    html_tag = None

    def render_html(self, context):
        if not self.children:
            return ''
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<{self.html_tag}{class_attr}>{newline}{html_out}{newline}{indent}</{self.html_tag}>{newline}'

    def get_bounds_rect(self):
        col_count = 0
        row_count = 0
        for row in self.children:
            _, _, h, w = row.get_bounds_rect()
            row_count += h
            if w > col_count:
                col_count = w
        return self.row_index, 0, row_count, col_count

    def apply_child_formats(self, formats):
        for child in self.children:
            child.apply_formats(formats)


class TableSectionBreak(Chunk):

    def __init__(self, src, start_pos, end_pos, row_borders='', col_borders='', row_align='', col_align=''):
        super().__init__(src, start_pos, end_pos)
        self.row_borders = row_borders
        self.col_borders = col_borders
        self.row_align = row_align
        self.col_align = col_align


class TableSectionBreakParser(Parser):

    all_parser = Regex(r'\|?-+([^\s\|-]*)[^\S\n-]*-*[^\S\n]*\|?[^\S\n]*(\n|$)')

    def parse1(self, context):
        start_pos = context.pos
        lead = self.all_parser.parse(context).match[1]
        args = lead.split(',')
        args += [''] * (4 - len(args))
        return TableSectionBreak(context.src, start_pos, context.pos,
            row_borders=args[0],
            col_borders=args[1],
            row_align=args[2],
            col_align=args[3],
        )


class Table(_BaseElement):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, \
            show_caption=None, show_numbers=None, row_borders=None, col_borders=None, \
            row_align=None, col_align=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments, \
            row_borders=row_borders, col_borders=col_borders, row_align=row_align, col_align=col_align)
        self.show_caption = True if show_caption is None else show_caption
        self.show_numbers = True if show_numbers is None else show_numbers

    def before_child_setup(self, context):
        if self.show_caption and self.show_numbers:
            context.begin_table()

    def after_child_setup(self, context):
        if self.show_caption and self.show_numbers:
            context.end_table()

    def get_bounds_rect(self):
        col_count = 0
        row_count = 0
        for section in self.sections:
            _, _, h, w = section.get_bounds_rect()
            row_count += h
            if w > col_count:
                col_count = w
        return 0, 0, row_count, col_count

    def apply_spans(self):

        def apply_row_span(section):
            row_count = len(section.children)
            supplements = [[] for n in range(row_count)]
            for row_index, row in enumerate(section.children):
                for cell in row.children:
                    # Check that there are enough rows to accomodate a cell's
                    # requested vertical extension, and correct row_span if
                    # there are not.
                    if cell.row_span > 1:
                        if row_index + cell.row_span > row_count:
                            cell.row_span = row_count - row_index
                    if cell.row_span > 1:
                        for sup_index in range(row_index + 1, row_index + cell.row_span):
                            supplements[sup_index].append(cell)
            return supplements

        def apply_col_span(section, supplements):

            def get_available(occupied, index):
                for start_index, end_index in occupied:
                    if index < start_index:
                        return index, start_index
                    if index < end_index:
                        index = end_index
                return index, -1

            # Build an array of cells to be manipulated without modifiying the
            # underlying hierarchy.
            rows = [row.children for row in section.children]
            # Find the length of the longest row. We'll try not to allow cells
            # to extend horizontally beyond this width.
            col_count = 0
            for row in rows:
                l = len(row)
                if l > col_count:
                    col_count = l
            for row_index, row in enumerate(rows):
                # Build array of tuples representing position ranges that
                # are already occupied by rows extended from above. These
                # positions are not available for occupation by other cells
                occupied = [(cell.col_index, cell.col_index + cell.col_span) for cell in supplements[row_index]]
                # Position each movable cell at the first available column,
                # and limit its span to the maximum possible
                col_index = 0
                for cell in row:
                    col_index, until_index = get_available(occupied, col_index)
                    if until_index >= 0:
                        # Cell preceeds an already occupied cell, so span
                        # is constrained
                        max_span = until_index - col_index
                        cell.col_span = min(max_span, max(1, cell.col_span))
                    if cell.col_span > col_count:
                        cell.col_span = col_count
                    cell.col_index = col_index
                    col_index += cell.col_span

        row_index = 0
        for section in self.sections:
            section.row_index = row_index
            for row in section.children:
                row.row_index = row_index
                col_index = 0
                for cell in row.children:
                    cell.row_index = row_index
                    cell.col_index = col_index
                    col_index += cell.col_span
                row_index += 1
            supplements = apply_row_span(section)
            apply_col_span(section, supplements)

    def apply_child_formats(self, formats):
        for section in self.sections:
            section.apply_formats(formats)

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<table{class_attr}>{newline}{html_out}{newline}{indent}</table>{newline}'


class TableParser(ElementParser):

    names = ['table']
    element_class = Table

    child_parser = Many(
        Any(
            TableCaptionParser(),
            TableSectionBreakParser(),
            TableRowParser(),
            all_whitespace_parser,
        )
    )

    def get_child_parser(self, context):
        return self.child_parser

    def check_arguments(self, context, arguments, extra):
        extra['col_align'] = arguments.get('col_align')
        extra['row_align'] = arguments.get('row_align')
        extra['col_borders'] = arguments.get('col_borders')
        extra['row_borders'] = arguments.get('row_borders')
        extra['show_caption'] = arguments.get_bool('caption')
        extra['show_numbers'] = arguments.get_bool('numbers')
        return arguments

    def parse2(self, context, chunk):
        captions = []
        sections = [TableSection(context.src, 0, 0, [])]
        for child in chunk.children:
            if isinstance(child, TableCaption):
                captions.append(child)
            elif isinstance(child, TableSectionBreak):
                # If current section is empty, then discard it
                if not sections[-1].children:
                    del sections[-1]
                sections.append(TableSection(context.src, child.start_pos, 0, [],
                    row_align=child.row_align,
                    col_align=child.col_align,
                    row_borders=child.row_borders,
                    col_borders=child.col_borders,
                ))
            elif isinstance(child, TableSection):
                # If current section is empty, then discard it
                if not sections[-1].children:
                    del sections[-1]
                sections.append(child)
            elif isinstance(child, TableRow):
                sections[-1].children.append(child)
        # If current section is empty, then discard it
        if sections and not sections[-1].children:
            del sections[-1]
        # If all sections are empty, table is invalid
        if sum(len(s.children) for s in sections) == 0:
            raise NoMatch
        # Concatenate captions if necessary
        if len(captions) > 1:
            children = []
            for caption in captions:
                children.extend(caption.children)
            captions[-1].children = children
        chunk.caption = None if not captions else captions[-1]
        chunk.sections = sections
        chunk.children = captions[-1:] + sections
        chunk.apply_spans()
        chunk.apply_formats(TableFormats())
        return chunk
    
