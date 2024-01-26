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
    '1': ('ab', 'al'),
    '2': ('ab', 'ac'),
    '3': ('ab', 'ar'),
    '4': ('am', 'al'),
    '5': ('am', 'ac'),
    '6': ('am', 'ar'),
    '7': ('at', 'al'),
    '8': ('at', 'ac'),
    '9': ('at', 'ar'),
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
        self.align = _Formats()


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

    def __init__(self, src, start_pos, end_pos, show_numbers=None, visible=None, **arguments):
        super().__init__(src, start_pos, end_pos, **arguments)
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
            return TableCaption(context.src, start_pos, context.pos, children=children)
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

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        arguments['show_numbers'] = args.get_bool('numbers')


class TableCaptionParser(Parser):

    content_parser = Any(
        _CaptionElementParser(),
        _CaptionShortParser(),
    )

    def parse1(self, context):
        return self.content_parser.parse(context)


class _BaseElement(Element):
    """
    Ancenstor class for tables, rowsets, rows and cells, handling common
    formatting features that they all share.
    """

    default_row_borders = ''
    default_col_borders = ''
    default_align = ''

    def __init__(self, src, start_pos, end_pos, row_borders=None, col_borders=None, align=None, **arguments):
        super().__init__(src, start_pos, end_pos, **arguments)
        self.row_borders = self.default_row_borders if row_borders is None else row_borders
        self.col_borders = self.default_col_borders if col_borders is None else col_borders
        self.align = self.default_align if align is None else align

    def get_bounds_rect(self):
        raise NotImplementedError

    def apply_formats(self, formats):
        self.formats = formats
        row_offset, col_offset, row_count, col_count = self.get_bounds_rect()
        row_borders = fix_borders(expand_format_str(self.row_borders, row_count+1))
        col_borders = fix_borders(expand_format_str(self.col_borders, col_count+1))
        align = fix_aligns(expand_format_str(self.align, col_count))
        for row_index in range(row_count + 1):
            for col_index in range(col_count):
                formats.row_borders.set_format(row_offset + row_index, col_offset + col_index, row_borders[row_index])
        for col_index in range(col_count + 1):
            for row_index in range(row_count):
                formats.col_borders.set_format(row_offset + row_index, col_offset + col_index, col_borders[col_index])
        for row_index in range(row_count):
            for col_index in range(col_count):
                formats.align.set_format(row_offset + row_index, col_offset + col_index, align[col_index])
        self.apply_child_formats(formats)

    def apply_child_formats(self, formats):
        pass


class TableCell(_BaseElement):

    paragraphs = True
    html_tag = 'td'

    def __init__(self, src, start_pos, end_pos, row_borders=None, col_borders=None, align=None, \
            col_span=None, row_span=None, short=False, **arguments):
        super().__init__(src, start_pos, end_pos, row_borders=row_borders, col_borders=col_borders, align=align, **arguments)
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
        format = self.formats.align.get_format(self.row_index, self.col_index)
        if format:
            classes.extend(table_align_classes[format])
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

    lead_parser = Regex(r'(\|+)(~*)([1-9]?)')

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
            align = '_'
        else:
            # Leader present, set cell properties according to leader content
            col_span = len(lead.match[1])
            row_span = max(1, len(lead.match[2]))
            align = lead.match[3] if lead.match[3] else '_'
        parse_whitespace(context)
        children = self.get_child_parser(context).parse(context).children
        return TableCell(context.src, start_pos, context.pos, children=children, \
            align=align, col_span=col_span, row_span=row_span, short=True)

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


class _CellElementParser(ElementParser):
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

    def parse_children(self, context, arguments):
        # Contents of a {cell} construct may always contain newlines
        context.push(allow_newline=True)
        try:
            return super().parse_children(context, arguments)
        finally:
            context.pop()

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        arguments['row_borders'] = args.get('row_borders')
        arguments['col_borders'] = args.get('col_borders')
        arguments['align'] = args.get('align')
        arguments['col_span'] = args.get_int('col_span')
        arguments['row_span'] = args.get_int('row_span')


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
            return TableRow(context.src, start_pos, context.pos, children=cells)
        finally:
            context.pop()


class _RowElementParser(ElementParser):
    """
    Finds and returns a TableRow expressed as a {row} construct.
    """

    names = ['row']
    element_class = TableRow

    cells_parser = _CellsParser()

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        arguments['row_borders'] = args.get('row_borders')
        arguments['col_borders'] = args.get('col_borders')
        arguments['align'] = args.get('align')

    def parse_children(self, context, arguments):
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


class TableRowSet(_BaseElement):

    names = ['rowset']

    def render_html(self, context):
        return self.render_children_html(context)

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


class TableRowSetParser(ElementParser):

    names = ['rowset']
    element_class = TableRowSet

    child_parser = Many(
        Any(
            TableRowParser(),
            all_whitespace_parser,
        )
    )

    def get_child_parser(self, context):
        return self.child_parser

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        arguments['row_borders'] = args.get('row_borders')
        arguments['col_borders'] = args.get('col_borders')
        arguments['align'] = args.get('align')

    def parse_children(self, context, arguments):
        children = super().parse_children(context, arguments)
        return [child for child in children if isinstance(child, TableRow)]


class TableRowSetBreak(Chunk):

    default_row_borders = ''
    default_col_borders = ''
    default_align = ''

    def __init__(self, src, start_pos, end_pos, row_borders='', col_borders='', align='', **arguments):
        super().__init__(src, start_pos, end_pos, **arguments)
        self.row_borders = self.default_row_borders if row_borders is None else row_borders
        self.col_borders = self.default_col_borders if col_borders is None else col_borders
        self.align = self.default_align if align is None else align


class TableRowSetBreakParser(Parser):

    all_parser = Regex(r'\|?-+([^\s\|-]*)[^\S\n-]*-*[^\S\n]*\|?[^\S\n]*(\n|$)')

    def parse1(self, context):
        start_pos = context.pos
        lead = self.all_parser.parse(context).match[1]
        args = lead.split(',')
        args += [''] * (3 - len(args))
        return TableRowSetBreak(context.src, start_pos, context.pos,
            row_borders=args[0],
            col_borders=args[1],
            align=args[2],
        )


class _Section(Element):

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<{self.html_tag}{class_attr}>{newline}{html_out}{newline}{indent}</{self.html_tag}>{newline}'


class TableHead(_Section):

    html_tag = 'thead'


class TableBody(_Section):

    html_tag = 'tbody'


class TableFoot(_Section):

    html_tag = 'tfoot'


class Table(_BaseElement):

    default_row_borders = '1*1'
    default_col_borders = '1*1'

    def __init__(self, src, start_pos, end_pos, show_caption=None, show_numbers=None, row_borders=None, col_borders=None, align=None, head=None, foot=None, **arguments):
        super().__init__(src, start_pos, end_pos, row_borders=row_borders, col_borders=col_borders, align=align, **arguments)
        self.show_caption = True if show_caption is None else show_caption
        self.show_numbers = True if show_numbers is None else show_numbers
        self.head_count = 0 if head is None else head
        self.foot_count = 0 if foot is None else foot

    def before_child_setup(self, context):
        if self.show_caption and self.show_numbers:
            context.begin_table()

    def after_child_setup(self, context):
        if self.show_caption and self.show_numbers:
            context.end_table()

    def get_bounds_rect(self):
        col_count = 0
        row_count = 0
        for rowset in self.rowsets:
            _, _, h, w = rowset.get_bounds_rect()
            row_count += h
            if w > col_count:
                col_count = w
        return 0, 0, row_count, col_count

    def apply_spans(self):

        def apply_row_span(rowset):
            row_count = len(rowset.children)
            supplements = [[] for n in range(row_count)]
            for row_index, row in enumerate(rowset.children):
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

        def apply_col_span(rowset, supplements):

            def get_available(occupied, index):
                for start_index, end_index in occupied:
                    if index < start_index:
                        return index, start_index
                    if index < end_index:
                        index = end_index
                return index, -1

            # Build an array of cells to be manipulated without modifiying the
            # underlying hierarchy.
            rows = [row.children for row in rowset.children]
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
        for rowset in self.rowsets:
            rowset.row_index = row_index
            for row in rowset.children:
                row.row_index = row_index
                col_index = 0
                for cell in row.children:
                    cell.row_index = row_index
                    cell.col_index = col_index
                    col_index += cell.col_span
                row_index += 1
            supplements = apply_row_span(rowset)
            apply_col_span(rowset, supplements)

    def apply_child_formats(self, formats):
        for rowset in self.rowsets:
            rowset.apply_formats(formats)

    def apply_structure(self):
        children = []
        if self.caption:
            children.append(self.caption)
        # Make a copy of rowsets list that can be modified without affecting
        # the original
        rowsets = [s for s in self.rowsets]
        head_rowsets = []
        count = self.head_count
        while count > 0 and rowsets:
            head_rowsets.append(rowsets[0])
            del rowsets[0]
            count -= 1
        foot_rowsets = []
        count = self.foot_count
        while count > 0 and rowsets:
            foot_rowsets.insert(0, rowsets[-1])
            del rowsets[-1]
            count -= 1
        if head_rowsets:
            first = head_rowsets[0]
            last = head_rowsets[-1]
            children.append(TableHead(first.src, first.start_pos, last.end_pos, children=head_rowsets))
        if rowsets:
            first = rowsets[0]
            last = rowsets[-1]
            children.append(TableBody(first.src, first.start_pos, last.end_pos, children=rowsets))
        if foot_rowsets:
            first = foot_rowsets[0]
            last = foot_rowsets[-1]
            children.append(TableFoot(first.src, first.start_pos, last.end_pos, children=foot_rowsets))
        self.children = children

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
            TableRowSetParser(),
            TableRowSetBreakParser(),
            TableCaptionParser(),
            TableRowParser(),
            all_whitespace_parser,
        )
    )

    def get_child_parser(self, context):
        return self.child_parser

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        arguments['row_borders'] = args.get('row_borders')
        arguments['col_borders'] = args.get('col_borders')
        arguments['align'] = args.get('align')
        arguments['show_caption'] = args.get_bool('caption')
        arguments['show_numbers'] = args.get_bool('numbers')
        arguments['head'] = args.get_int('head')
        arguments['foot'] = args.get_int('foot')

    def parse2(self, context, chunk):
        captions = []
        rowsets = [TableRowSet(context.src, 0, 0, children=[])]
        for child in chunk.children:
            if isinstance(child, TableCaption):
                captions.append(child)
            elif isinstance(child, TableRowSetBreak):
                # If current rowset is empty, then discard it
                if not rowsets[-1].children:
                    del rowsets[-1]
                rowsets.append(TableRowSet(context.src, child.start_pos, 0, children=[],
                    row_borders=child.row_borders,
                    col_borders=child.col_borders,
                    align=child.align,
                ))
            elif isinstance(child, TableRowSet):
                # If current rowset is empty, then discard it
                if not rowsets[-1].children:
                    del rowsets[-1]
                rowsets.append(child)
                # Start a new rowset
                rowsets.append(TableRowSet(context.src, context.pos, 0, children=[]))
            elif isinstance(child, TableRow):
                rowsets[-1].children.append(child)
        # If current rowset is empty, then discard it
        if rowsets and not rowsets[-1].children:
            del rowsets[-1]
        # If all rowsets are empty, table is invalid
        if sum(len(s.children) for s in rowsets) == 0:
            raise NoMatch
        # Concatenate captions if necessary
        if len(captions) > 1:
            children = []
            for caption in captions:
                children.extend(caption.children)
            captions[-1].children = children
        chunk.caption = None if not captions else captions[-1]
        chunk.rowsets = rowsets
        chunk.apply_spans()
        chunk.apply_formats(TableFormats())
        chunk.apply_structure()
        return chunk
    
