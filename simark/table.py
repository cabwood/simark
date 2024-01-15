import re
import html
from .parse import Parser, NoMatch, All, Many, Any, Regex, Exact, Chunk
from .core import ElementParser, Element, Text, VerbatimParser, Arguments, \
    unescape, esc_element_open, esc_element_close, \
    ESC_BACKSLASH, ESC_BACKTICK, ESC_ELEMENT_OPEN, ESC_ELEMENT_CLOSE


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


class TableCaptionParser(ElementParser):

    names = ['caption']
    element_class = TableCaption

    def check_arguments(self, context, arguments, extra):
        extra['show_numbers'] = arguments.get_bool('numbers')
        return arguments


border_flags = '_0123456789'
h_align_flags = '_lcmr'
v_align_flags = '_tcmb'

class BaseTableElement(Element):
    """
    Ancenstor class for tables, table sections, rows and cells, handling
    common formatting features that they all share.
    """

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, col_align=None, row_align=None, col_borders=None, row_borders=None):
        super().__init__(src, start_pos, end_pos, children, name=name, arguments=arguments)
        self.col_align = '' if col_align is None else col_align
        self.row_align = '' if row_align is None else row_align
        self.col_borders = '' if col_borders is None else col_borders
        self.row_borders = '' if row_borders is None else row_borders
    

class BaseTableElementParser(ElementParser):

    def check_arguments(self, context, arguments, extra):
        extra['col_align'] = arguments.get('col_align')
        extra['row_align'] = arguments.get('row_align')
        extra['col_borders'] = arguments.get('col_borders')
        extra['row_borders'] = arguments.get('row_borders')
        return arguments


class TableSection(BaseTableElement):
    """
    Functionality common to <thead>, <tbody> and <tfoot> elements
    """

    html_tag = None

    def before_child_setup(self, context):
        if isinstance(self.parent, Table):
            if self.col_align is None:
                self.col_align = self.parent.col_align
            if self.row_align is None:
                self.row_align = self.parent.row_align

    def render_html(self, context):
        if not self.children:
            return ''
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<{self.html_tag}{class_attr}>{newline}{html_out}{newline}{indent}</{self.html_tag}>{newline}'


class TableSectionParser(BaseTableElementParser):

    empty_line_parser = Regex(re.compile(f'[^\S\n]*\n'))

    def get_child_parser(self, context):
        return Many(
            Any(
                TableRowParser(),
                self.empty_line_parser,
            )
        )


class TableSectionBreak(Chunk):
    pass


class TableSectionBreakParser(Parser):

    parser = Regex(re.compile(f'\s*-+\s*\n'))

    def parse1(self, context):
        start_pos = context.pos
        match = self.parser.parse(context).match
        return TableSectionBreak(context.src, start_pos, context.pos)


class TableHead(TableSection):

    html_tag = 'thead'

    def setup(self, context):
        for row in self.children:
            for cell in row.children:
                cell.html_tag = 'th'


class TableHeadParser(TableSectionParser):

    names = ['head']
    element_class = TableHead


class TableBody(TableSection):

    html_tag = 'tbody'


class TableBodyParser(TableSectionParser):

    names = ['body']
    element_class = TableBody


class TableFoot(TableSection):

    html_tag = 'tfoot'


class TableFootParser(TableSectionParser):

    names = ['foot']
    element_class = TableFoot


class TableTextParser(Parser):
    """
    Like TextParser, except bar '|' terminates the text. If allow_newline
    is False, '\\n' will also terminate the text.
    """

    forbid_newline_parser = Regex(re.compile(rf"(\\\\|\\`|\\\||\\{esc_element_open}|\\{esc_element_close}|[^|\n`{esc_element_open}{esc_element_close}])+"))
    allow_newline_parser = Regex(re.compile(rf"(\\\\|\\`|\\\||\\{esc_element_open}|\\{esc_element_close}|[^|`{esc_element_open}{esc_element_close}])+"))

    def __init__(self, allow_newline=False):
        super().__init__()
        self.allow_newline = allow_newline

    def parse1(self, context):
        if self.allow_newline:
            match = self.allow_newline_parser.parse(context).match
        else:
            match = self.forbid_newline_parser.parse(context).match
        return Text(context.src, match.start(0), match.end(0), unescape(match[0],
            ESC_BACKSLASH,
            ESC_BACKTICK,
            ESC_ELEMENT_OPEN,
            ESC_ELEMENT_CLOSE,
            ('\\|', '|'),
        ))


table_col_align_attrs = {
    '_': '',
    'l': 'text-align: left;',
    'm': 'text-align: center;',
    'c': 'text-align: center;',
    'r': 'text-align: right;',
}

table_row_align_attrs = {
    '_': '',
    't': 'vertical-align: top;',
    'm': 'vertical-align: middle;',
    'c': 'vertical-align: middle;',
    'b': 'vertical-align: bottom;',
}


class TableCell(BaseTableElement):

    paragraphs = True

    html_tag = 'td'

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, \
            col_align=None, row_align=None, row_borders=None, col_borders=None, \
            col_span=None, row_span=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments, \
            row_align=row_align, col_align=col_align, row_borders=row_borders, col_borders=col_borders)
        self.col_span = 1 if col_span is None else col_span
        self.row_span = 1 if row_span is None else row_span

    def before_child_setup(self, context):
        # Render children compact
        context.compact = True

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        styles = [
            # table_col_align_attrs.get(self.col_align),
            # table_row_align_attrs.get(self.row_align),
        ]
        style_value = ' '.join([style for style in styles if style])
        style_attr = f' style="{style_value}"' if style_value else ''
        row_span_attr = f' rowspan="{self.row_span}"' if self.row_span > 1 else ''
        col_span_attr = f' colspan="{self.col_span}"' if self.col_span > 1 else ''
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<{self.html_tag}{class_attr}{style_attr}{row_span_attr}{col_span_attr}>{html_out}</{self.html_tag}>{newline}'


class TableCellShortParser(Parser):
    """
    Cell content can be expressed bar '|' delimited, or wrapped in a {cell}
    construct. This parser finds and returns a TableCell parsed from bar '|'
    delimited content.
    """

    allow_newline_lead_parser = Regex(r'\s*(\|+)(~*)([<>-]?)')
    forbid_newline_lead_parser = Regex(r'[^\S\n]*(\|+)(~*)([<>-]?)')
    
    def __init__(self, allow_newline=False):
        super().__init__()
        self.allow_newline = allow_newline

    def parse1(self, context):
        if not hasattr(self, '_child_parser'):
            self._child_parser = self.get_child_parser(context)
        start_pos = context.pos
        try:
            # Absence of opening '|' is acceptable
            if self.allow_newline:
                lead = self.allow_newline_lead_parser.parse(context)
            else:
                lead = self.forbid_newline_lead_parser.parse(context)
        except NoMatch:
            lead = None
            col_span = 1
            row_span = 1
            col_align = '_'
        else:
            col_span = len(lead.match[1])
            row_span = len(lead.match[2]) + 1
            col_align = lead.match[3] if lead.match[3] else '_'
        children = self._child_parser.parse(context).children
        return TableCell(context.src, start_pos, context.pos, children, col_span=col_span, row_span=row_span, col_align=col_align)

    def get_child_parser(self, context):
        return Many(
            Any(
                VerbatimParser(),
                *context.parsers,
                TableTextParser(allow_newline=self.allow_newline),
            ),
        )


class TableCellElementParser(BaseTableElementParser):
    """
    Cell content can be expressed bar "|" delimited, or wrapped in a {cell}
    construct. This parser finds and returns a TableCell parsed from a {cell}
    construct.
    """

    names = ['cell']
    element_class = TableCell

    lead_parser = Regex(re.compile(r'\s*\|?\s*'))

    def parse1(self, context):
        # The element maybe preceeded by whitespace and/or a '|'
        self.lead_parser.parse(context)
        # Now look for the {cell}
        return super().parse1(context)

    def check_arguments(self, context, arguments, extra):
        arguments = super().check_arguments(context, arguments, extra)
        extra['col_span'] = arguments.get_int('col_span')
        extra['row_span'] = arguments.get_int('row_span')
        return arguments


class TableCellParser(Parser):

    def __init__(self, allow_newline=False):
        super().__init__()
        self.allow_newline = allow_newline

    def parse1(self, context):
        if not hasattr(self, '_child_parser'):
            self._child_parser = self.get_child_parser()
        return self._child_parser.parse(context)

    def get_child_parser(self):
        return Any(
            TableCellElementParser(),
            TableCellShortParser(allow_newline=self.allow_newline),
        )


class TableRow(BaseTableElement):

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<tr{class_attr}>{newline}{html_out}{newline}{indent}</tr>{newline}'


class TableRowShortParser(Parser):
    """
    Rows can be expressed shorthand, as bar-separated content, or as a
    {row} element. This parser finds and returns a TableRow expressed
    in shorthand.
    """

    # Shorthand rows are terminated by a newline, so do not permit newlines
    # in the parsed cells
    cells_parser = Many(TableCellParser(allow_newline=False), min_count=1)
    eol_parser = Regex(r'[^\S\n]*(\n|$)')

    def parse1(self, context):
        start_pos = context.pos
        cells = self.cells_parser.parse(context).children
        self.eol_parser.parse(context)
        return TableRow(context.src, start_pos, context.pos, cells)


class TableRowElementParser(BaseTableElementParser):
    """
    Rows can be expressed shorthand, as bar-separated content, or as a
    {row} element. This parser finds and returns a TableRow expressed
    as a {row} construct.
    """

    names = ['row']
    element_class = TableRow

    def get_child_parser(self, context):
        # Cells wrapped in a {row} are not terminated by newline, so permit
        # newlines in the parsed data
        return Many(TableCellParser(allow_newline=True), min_count=1)


class TableRowParser(Parser):

    parser = Any(
        TableRowElementParser(),
        TableRowShortParser(),
    )

    def parse1(self, context):
        return self.parser.parse(context)


class _ProxyCell:

    def __init__(self, cell):
        self.cell = cell

    @property
    def col_index(self):
        return self.cell.col_index

    @property
    def col_span(self):
        return self.cell.col_span


class Table(BaseTableElement):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, \
            col_align=None, row_align=None, row_borders=None, col_borders=None, \
            show_caption=None, show_numbers=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments, \
            row_align=row_align, col_align=col_align, row_borders=row_borders, col_borders=col_borders)
        self.show_caption = True if show_caption is None else show_caption
        self.show_numbers = True if show_numbers is None else show_numbers

    def before_child_setup(self, context):
        if self.show_caption and self.show_numbers:
            context.begin_table()

    def after_child_setup(self, context):
        if self.show_caption and self.show_numbers:
            context.end_table()

    def apply_spans(self):

        def apply_row_span(rows, first_row_index):
            # Check that there are enough rows to accomodate a cell's requested
            # vertical extension, and correct row_span if there are not.
            row_count = len(rows)
            for row_index, row in enumerate(rows):
                for cell in row:
                    cell.row_index = row_index + first_row_index
                    if cell.row_span > 1:
                        if row_index + cell.row_span > row_count:
                            cell.row_span = row_count - row_index
            # Extend cells with row_span > 1 downwards, by appending proxies
            # to represent them in subsequent rows.
            for row_index, row in enumerate(rows):
                for cell in row:
                    # Ignore proxies appended during prior iterations
                    if not isinstance(cell, _ProxyCell):
                        if cell.row_span > 1:
                            for index in range(row_index + 1, row_index + cell.row_span):
                                rows[index].append(_ProxyCell(cell))

        def apply_col_span(rows):

            def get_available(occupied, index):
                for start_index, end_index in occupied:
                    if index < start_index:
                        return index, start_index
                    if index < end_index:
                        index = end_index
                return index, -1

            # Find the length of the longest row. We won't allow cells to extend
            # horizontally beyond this number of columns.
            col_count = 0
            for row in rows:
                l = len(row)
                if l > col_count:
                    col_count = l
            for row in rows:
                # Build array of tuples representing position ranges that
                # are already occupied by rows extended from above. These
                # positions are not available for occupation by other cells
                occupied = [(cell.col_index, cell.col_index + cell.col_span)
                    for cell in row if isinstance(cell, _ProxyCell)]
                # Position each movable cell at the first available column,
                # and limit its span to the maximum possible
                col_index = 0
                for cell in row:
                    if isinstance(cell, TableCell):
                        col_index, until_index = get_available(occupied, col_index)
                        if until_index < 0:
                            # Cell comes after any occupied cells, and span
                            # is not constrained
                            max_span = col_count - col_index - 1
                        else:
                            # Cell preceeds an already occupied cell, so span
                            # is constrained
                            max_span = until_index - col_index
                        # Requested span cannot exceed the maximum permitted
                        # here, nor can it be less than 1
                        col_span = min(max_span, max(1, cell.col_span))
                        cell.col_index = col_index
                        cell.col_span = col_span
                        col_index += col_span

        head_rows = [[cell for cell in row.children] for row in self.head.children]
        body_rows = [[cell for cell in row.children] for row in self.body.children]
        foot_rows = [[cell for cell in row.children] for row in self.foot.children]
        # Row spanning cannot occur across sections, so limit all cells'
        # row_span to the maximum possible for each individual section.
        apply_row_span(head_rows, 0)
        apply_row_span(body_rows, len(head_rows))
        apply_row_span(foot_rows, len(head_rows) + len(body_rows))
        # Processing from here on is the same for all rows, irrespective of
        # the section that contains them.
        rows = head_rows + body_rows + foot_rows
        apply_col_span(rows)

    def apply_formats(self):
        pass

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<table{class_attr}>{newline}{html_out}{newline}{indent}</table>{newline}'


class TableParser(ElementParser):

    names = ['table']
    element_class = Table

    eol_parser = Regex(re.compile(r'\s*\n?|$'))

    def get_child_parser(self, context):
        return Many(
            Any(
                TableCaptionParser(),
                TableSectionBreakParser(),
                TableHeadParser(),
                TableBodyParser(),
                TableFootParser(),
                TableRowParser(),
                self.eol_parser,
            )
        )

    def check_arguments(self, context, arguments, extra):
        extra['col_align'] = arguments.get('col_align')
        extra['row_align'] = arguments.get('row_align')
        extra['col_borders'] = arguments.get('col_borders')
        extra['row_borders'] = arguments.get('row_borders')
        extra['show_caption'] = arguments.get_bool('caption')
        extra['show_numbers'] = arguments.get_bool('numbers')
        return arguments

    def parse2(self, context, chunk):
        # Every rendered table has <thead>, <tbody> and <tfoot> elements, and
        # perhaps a <caption>, but these may be missing from the source.
        # Using autohead and autofoot arguments also complicates parsing.
        # It's easiest and safest to just create new empty caption, head,
        # body and foot elements, and populate them with appropriate items
        # already parsed from the source.
        caption_parts = []
        head_rows = []
        body_rows = []
        foot_rows = []
        # Iterate parsed children, inserting them into the appropriate
        # caption, head, body or foot container as we go.
        section = 0
        for child in chunk.children:
            if isinstance(child, TableCaption):
                caption_parts.extend(child.children)
            elif isinstance(child, TableSectionBreak):
                if section < 2:
                    section += 1
            elif isinstance(child, TableRow):
                # Orphaned rows go into the current target section
                if section == 0:
                    head_rows.append(child)
                elif section == 1:
                    body_rows.append(child)
                else:
                    foot_rows.append(child)
            elif isinstance(child, TableHead):
                head_rows.extend(child.children)
            elif isinstance(child, TableBody):
                body_rows.extend(child.children)
            elif isinstance(child, TableFoot):
                foot_rows.extend(child.children)
        chunk.caption = TableCaption(context.src, context.pos, context.pos, caption_parts, show_numbers=chunk.show_numbers, visible=chunk.show_caption)
        chunk.head = TableHead(context.src, context.pos, context.pos, head_rows)
        chunk.body = TableBody(context.src, context.pos, context.pos, body_rows)
        chunk.foot = TableFoot(context.src, context.pos, context.pos, foot_rows)
        # Replace children, keeping only non-empty elements
        chunk.children = [c for c in (chunk.caption, chunk.head, chunk.body, chunk.foot) if c.children]
        chunk.apply_spans()
        chunk.apply_formats()
        return chunk
    
