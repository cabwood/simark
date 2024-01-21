import html
from .parse import Parser, NoMatch, Many, Any, Opt, Regex, Exact, Chunk
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


table_align_classes = {
    '<': ('at', 'al'),
    '-': ('am', 'ac'),
    '>': ('ab', 'ar'),
}

table_border_classes = {
    '0': ('bt0', 'bb0', 'bl0', 'br0'),
    '1': ('bt1', 'bb1', 'bl1', 'br1'),
    '2': ('bt2', 'bb2', 'bl2', 'br2'),
    '3': ('bt3', 'bb3', 'bl3', 'br3'),
}


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


class TableFormats:

    def __init__(self):
        self.row_align = _Formats()
        self.col_align = _Formats()
        self.row_borders = _Formats()
        self.col_borders = _Formats()


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


class _BaseElement(Element):
    """
    Ancenstor class for tables, table sections, rows and cells, handling
    common formatting features that they all share.
    """

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, col_align=None, row_align=None, col_borders=None, row_borders=None):
        super().__init__(src, start_pos, end_pos, children, name=name, arguments=arguments)
        self.row_align = ''.join(c if c in table_align_classes else '_' for c in row_align or '')
        self.col_align = ''.join(c if c in table_align_classes else '_' for c in col_align or '')
        self.row_borders = ''.join(c if c in table_border_classes else '_' for c in row_borders or '')
        self.col_borders = ''.join(c if c in table_border_classes else '_' for c in col_borders or '')
    
    def apply_formats(self, formats):
        for child in self.children:
            child.apply_formats(formats)


class _BaseElementParser(ElementParser):

    def check_arguments(self, context, arguments, extra):
        extra['col_align'] = arguments.get('col_align', default='')
        extra['row_align'] = arguments.get('row_align', default='')
        extra['col_borders'] = arguments.get('col_borders', default='')
        extra['row_borders'] = arguments.get('row_borders', default='')
        return arguments


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


class TableCell(_BaseElement):

    paragraphs = True
    html_tag = 'td'

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, \
            col_align=None, row_align=None, row_borders=None, col_borders=None, \
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

    def apply_formats(self, formats):
        formats.row_align.set_format(self.row_index, self.col_index, self.row_align[0:1])
        formats.col_align.set_format(self.row_index, self.col_index, self.col_align[0:1])
        formats.row_borders.set_format(self.row_index, self.col_index, self.row_borders[0:1])
        formats.row_borders.set_format(self.row_index + self.row_span, self.col_index, self.row_borders[1:2])
        formats.col_borders.set_format(self.row_index, self.col_index, self.col_borders[0:1])
        formats.col_borders.set_format(self.row_index, self.col_index + self.col_span, self.col_borders[1:2])
        self.formats = formats


class _CellShortParser(Parser):
    """
    Finds and returns a TableCell parsed from bar '|' delimited content.
    """

    lead_parser = Regex(r'(\|+)(~*)([_<>-]?)([_<>-]?)')

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
            col_span=col_span, row_span=row_span, col_align=col_align, row_align=row_align, short=True)

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

    def get_col_count(self):
        if not self.children:
            return 0
        last = self.children[-1]
        return last.col_index + last.col_span

    def apply_formats(self, formats):
        col_count = self.get_col_count()
        for col_index in range(col_count):
            char = self.row_align[0:1] or '_'
            if char != '_':
                formats.row_align.set_format(self.row_index, col_index, char)
            char = self.row_borders[0:1] or '_'
            if char != '_':
                formats.row_borders.set_format(self.row_index, col_index, char)
            char = self.row_borders[1:2] or '_'
            if char != '_':
                formats.row_borders.set_format(self.row_index, col_index + 1, char)
        col_align = self.col_align[0:col_count]
        for col_index, char in enumerate(col_align):
            if char != '_':
                formats.col_align.set_format(self.row_index, col_index, char)
        col_borders = self.col_align[0:col_count+1]
        for col_index, char in enumerate(col_borders):
            if char != '_':
                formats.col_borders.set_format(self.row_index, col_index, char)
        for cell in self.children:
            cell.apply_formats(formats)


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


class _ProxyCell:

    def __init__(self, cell):
        self.cell = cell

    @property
    def col_index(self):
        return self.cell.col_index

    @property
    def col_span(self):
        return self.cell.col_span


class TableSection(_BaseElement):
    """
    Functionality common to <thead>, <tbody> and <tfoot> elements
    """

    html_tag = None

    def render_html(self, context):
        if not self.children:
            return ''
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<{self.html_tag}{class_attr}>{newline}{html_out}{newline}{indent}</{self.html_tag}>{newline}'

    def get_col_count(self):
        col_count = 0
        for row in self.children:
            row_len = row.get_col_count()
            if  row_len > col_count:
                col_count = row_len
        return col_count

    def apply_formats(self, formats):
        row_count = len(self.children)
        col_count = self.get_col_count()
        row_align = self.row_align[0:row_count]
        row_borders = self.row_borders[0:row_count+1]
        for col_index in range(col_count):
            for row_index, char in enumerate(row_align):
                formats.row_align.set_format(row_index + self.row_index, col_index, char)
            for row_index, char in enumerate(row_borders):
                formats.row_borders.set_format(row_index + self.row_index, col_index, char)
        col_align = self.col_align[0:col_count]
        col_borders = self.col_borders[0:col_count+1]
        for row_index in range(self.row_index, self.row_index + row_count):
            for col_index, char in enumerate(col_align):
                formats.col_align.set_format(row_index, col_index, char)
            for col_index, char in enumerate(col_borders):
                formats.col_borders.set_format(row_index, col_index, char)
        for row in self.children:
            row.apply_formats(formats)


class TableSectionBreak(Chunk):
    pass


class TableSectionBreakParser(Parser):

    parser = Regex(r'-+[^\S\n]*(\n|$)')

    def parse1(self, context):
        start_pos = context.pos
        self.parser.parse(context)
        return TableSectionBreak(context.src, start_pos, context.pos)


class TableSectionParser(_BaseElementParser):

    child_parser = Many(
        Any(
            TableRowParser(),
            all_whitespace_parser,
        )
    )

    def parse_children(self, context):
        children = self.child_parser.parse(context).children
        return [child for child in children if isinstance(child, TableRow)]


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


class Table(_BaseElement):

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

    def get_col_count(self):
        col_count = 0
        for section in (self.head, self.body, self.foot):
            section_len = section.get_col_count()
            if  section_len > col_count:
                col_count = section_len
        return col_count

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

            # Find the length of the longest row. We'll try not to allow cells
            # to extend horizontally beyond this width.
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
                        if until_index >= 0:
                            # Cell preceeds an already occupied cell, so span
                            # is constrained
                            max_span = until_index - col_index
                            cell.col_span = min(max_span, max(1, cell.col_span))
                        # Requested span cannot exceed the maximum permitted
                        # here, nor can it be less than 1
                        cell.col_index = col_index
                        col_index += cell.col_span

        head_rows = [[cell for cell in row.children] for row in self.head.children]
        body_rows = [[cell for cell in row.children] for row in self.body.children]
        foot_rows = [[cell for cell in row.children] for row in self.foot.children]
        # Row spanning cannot occur across sections, so limit all cells'
        # row_span to the maximum possible for each individual section.
        self.head.row_index = 0
        self.body.row_index = len(self.head.children)
        self.foot.row_index = self.body.row_index + len(self.body.children)
        for index, row in enumerate(self.head.children):
            row.row_index = self.head.row_index + index
        for index, row in enumerate(self.body.children):
            row.row_index = self.body.row_index + index
        for index, row in enumerate(self.foot.children):
            row.row_index = self.foot.row_index + index
        apply_row_span(head_rows, self.head.row_index)
        apply_row_span(body_rows, self.body.row_index)
        apply_row_span(foot_rows, self.foot.row_index)
        # Processing from here on is the same for all rows, irrespective of
        # the section that contains them.
        rows = head_rows + body_rows + foot_rows
        apply_col_span(rows)

    def apply_formats(self, formats):
        rows = self.head.children + self.body.children + self.foot.children
        row_count = len(rows)
        col_count = self.get_col_count()
        for col_index in range(col_count):
            row_align = self.row_align[0:row_count]
            for row_index, char in enumerate(row_align):
                formats.row_align.set_format(row_index, col_index, char)
            row_borders = self.row_borders[0:row_count+1]
            for row_index, char in enumerate(row_borders):
                formats.row_borders.set_format(row_index, col_index, char)
        col_align = self.col_align[0:col_count]
        col_borders = self.col_borders[0:col_count+1]
        for row_index in range(row_count):
            for col_index, char in enumerate(col_align):
                formats.col_align.set_format(row_index, col_index, char)
            for col_index, char in enumerate(col_borders):
                formats.col_borders.set_format(row_index, col_index, char)
        self.head.apply_formats(formats)
        self.body.apply_formats(formats)
        self.foot.apply_formats(formats)


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
            TableHeadParser(),
            TableBodyParser(),
            TableFootParser(),
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
        # Every rendered table has <thead>, <tbody> and <tfoot> elements, and
        # perhaps a <caption>, but these may be missing from the source.
        # It's easiest and safest to just create new empty caption, head,
        # body and foot elements, and populate them with appropriate items
        # already parsed from the source.
        caption = TableCaption(context.src, context.pos, context.pos, [], show_numbers=chunk.show_numbers, visible=chunk.show_caption)
        head = TableHead(context.src, context.pos, context.pos, [])
        body = TableBody(context.src, context.pos, context.pos, [])
        foot = TableFoot(context.src, context.pos, context.pos, [])
        # Iterate parsed children, inserting them into the appropriate
        # caption, head, body or foot container as we go.
        section = 0
        for child in chunk.children:
            if isinstance(child, TableCaption):
                caption.children.extend(child.children)
                # Copy properties
                caption.show_numbers = child.show_numbers
                caption.visible = child.visible
            elif isinstance(child, TableSectionBreak):
                if section < 2:
                    section += 1
            elif isinstance(child, TableRow):
                # Orphan rows go into the current target section
                if section == 0:
                    head.children.append(child)
                elif section == 1:
                    body.children.append(child)
                else:
                    foot.children.append(child)
            elif isinstance(child, TableHead):
                head.children.extend(child.children)
                # Copy properties
                head.row_align = child.row_align
                head.col_align = child.col_align
                head.row_borders = child.row_borders
                head.col_borders = child.col_borders
                # Head was explititly defined. Send subsequent orphan rows
                # to the body.
                section = 1
            elif isinstance(child, TableBody):
                body.children.extend(child.children)
                # Copy properties
                body.row_align = child.row_align
                body.col_align = child.col_align
                body.row_borders = child.row_borders
                body.col_borders = child.col_borders
                # Body was explititly defined. Send subsequent orphan
                # rows to the foot.
                section = 2
            elif isinstance(child, TableFoot):
                foot.children.extend(child.children)
                # Copy properties
                foot.row_align = child.row_align
                foot.col_align = child.col_align
                foot.row_borders = child.row_borders
                foot.col_borders = child.col_borders
                # Foot was explititly defined. From now on, send orphan rows
                # to the foot.
                section = 2
        chunk.caption = caption
        chunk.head = head
        chunk.body = body
        chunk.foot = foot
        # Replace children, keeping only non-empty elements
        chunk.children = [c for c in (caption, head, body, foot) if c.children]
        chunk.apply_spans()
        formats = TableFormats()
        chunk.apply_formats(formats)
        return chunk
    
