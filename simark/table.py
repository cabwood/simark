import re
import html
from .parse import Parser, Many, Any, Regex
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


class TableSection(Element):
    """
    Functionality common to <thead>, <tbody> and <tfoot> elements
    """

    html_tag = None

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, h_align=None, v_align=None):
        super().__init__(src, start_pos, end_pos, children, name=name, arguments=arguments)
        self.h_align = h_align
        self.v_align = v_align

    def before_child_setup(self, context):
        if isinstance(self.parent, Table):
            if self.h_align is None:
                self.h_align = self.parent.h_align
            if self.v_align is None:
                self.v_align = self.parent.v_align

    def render_html(self, context):
        if not self.children:
            return ''
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<{self.html_tag}{class_attr}>{newline}{html_out}{newline}{indent}</{self.html_tag}>{newline}'


class TableSectionParser(ElementParser):

    empty_line_parser = Regex(re.compile(f'[^\S\n]*\n'))

    def get_child_parser(self, context):
        return Many(
            Any(
                TableRowParser(),
                self.empty_line_parser,
            )
        )

    def check_arguments(self, context, arguments, extra):
        extra['h_align'] = arguments.get('h_align')
        extra['v_align'] = arguments.get('v_align')
        return arguments

    def check_children(self, context, children, extra):
        # Discard anything that isn't a TableRow
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


class TableTextParser(Parser):
    """
    Like TextParser, except bar "|" and newline also terminate the text, and
    may be empty.
    """

    parser = Regex(re.compile(rf"(\\\\|\\`|\\\||\\{esc_element_open}|\\{esc_element_close}|[^|\n`{esc_element_open}{esc_element_close}])*"))

    def parse1(self, context):
        match = self.parser.parse(context).match
        return Text(context.src, match.start(0), match.end(0), unescape(match[0],
            ESC_BACKSLASH,
            ESC_BACKTICK,
            ESC_ELEMENT_OPEN,
            ESC_ELEMENT_CLOSE,
            ('\\|', '|'),
        ))


table_h_align_attrs = {
    '_': '',
    'l': 'text-align: left;',
    'm': 'text-align: center;',
    'c': 'text-align: center;',
    'r': 'text-align: right;',
}

table_v_align_attrs = {
    '_': '',
    't': 'vertical-align: top;',
    'm': 'vertical-align: middle;',
    'c': 'vertical-align: middle;',
    'b': 'vertical-align: bottom;',
}

class TableCell(Element):

    paragraphs = True

    html_tag = 'td'

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, h_align=None, v_align=None):
        super().__init__(src, start_pos, end_pos, children, name=name, arguments=arguments)
        self.h_align = h_align
        self.v_align = v_align

    def before_child_setup(self, context):
        # Render children compact
        context.compact = True
        if isinstance(self.parent, TableRow):
            row_h_align = self.parent.h_align or ''
            if self.h_align is None and self.column_index < len(row_h_align):
                self.h_align = row_h_align[self.column_index]
            row_v_align = self.parent.v_align or ''
            if self.v_align is None and self.column_index < len(row_v_align):
                self.v_align = row_v_align[self.column_index]

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        styles = [
            table_h_align_attrs.get(self.h_align),
            table_v_align_attrs.get(self.v_align),
        ]
        style_value = ' '.join([style for style in styles if style])
        style_attr = f' style="{style_value}"' if style_value else ''
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<{self.html_tag}{class_attr}{style_attr}>{html_out}</{self.html_tag}>{newline}'


class TableCellParser(ElementParser):

    bar_parser = Regex(re.compile(r'\|?'))

    def parse1(self, context):
        start_pos = context.pos
        if not hasattr(self, '_child_parser'):
            self._child_parser = self.get_child_parser(context)
        children = self._child_parser.parse(context).children
        self.bar_parser.parse(context)
        return TableCell(context.src, start_pos, context.pos, children)

    def get_child_parser(self, context):
        return Many(
            Any(
                VerbatimParser(),
                *context.parsers,
                TableTextParser(),
            ),
        )

    def check_arguments(self, context, arguments, extra):
        extra['h_align'] = arguments.get('h_align')
        extra['v_align'] = arguments.get('v_align')
        return arguments


class TableRow(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, h_align=None, v_align=None):
        super().__init__(src, start_pos, end_pos, children, name=name, arguments=arguments)
        self.h_align = h_align
        self.v_align = v_align

    def before_child_setup(self, context):
        # For undefined appearance arguments, use parent's settings
        if isinstance(self.parent, TableSection):
            if self.h_align is None:
                self.h_align = self.parent.h_align
            if self.v_align is None:
                self.v_align = self.parent.v_align

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<tr{class_attr}>{newline}{html_out}{newline}{indent}</tr>{newline}'


class TableRowParser(Parser):

    cells_parser = Many(TableCellParser(), min_count=1)
    eol_parser = Regex(re.compile(r'\s*\n?|$'))

    def parse1(self, context):
        start_pos = context.pos
        children = self.cells_parser.parse(context).children
        self.eol_parser.parse(context)
        # Assign a column number to each child
        for index, child in enumerate(children):
            child.column_index = index
        return TableRow(context.src, start_pos, context.pos, children)


class Table(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, \
            h_align=None, v_align=None, auto_head=None, auto_foot=None, show_caption=None, show_numbers=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.h_align = h_align or ''
        self.v_align = v_align or ''
        self.auto_head = True if auto_head is None else auto_head
        self.auto_foot = False if auto_foot is not None else auto_foot
        self.show_caption = True if show_caption is None else show_caption
        self.show_numbers = True if show_numbers is None else show_numbers

    def before_child_setup(self, context):
        if self.show_caption and self.show_numbers:
            context.begin_table()

    def after_child_setup(self, context):
        if self.show_caption and self.show_numbers:
            context.end_table()

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
                TableHeadParser(),
                TableBodyParser(),
                TableFootParser(),
                TableCaptionParser(),
                TableRowParser(),
                self.eol_parser,
            )
        )

    def check_arguments(self, context, arguments, extra):
        extra['h_align'] = arguments.get('h_align')
        extra['v_align'] = arguments.get('v_align')
        extra['auto_head'] = arguments.get_bool('autohead')
        extra['auto_foot'] = arguments.get_bool('autofoot')
        extra['show_caption'] = arguments.get_bool('caption')
        extra['show_numbers'] = arguments.get_bool('numbers')
        return arguments

    def check_children(self, context, children, extra):
        # Every rendered table has <thead>, <tbody> and <tfoot> elements, and
        # perhaps a <caption>, but these may be missing from the source.
        # Using autohead and autofoot arguments also complicates parsing.
        # It's easiest and safest to just create new caption, head, body and
        # foot elements, and to populate them with rows found in the source.
        show_caption = extra['show_caption']
        show_numbers = extra['show_numbers']
        caption = TableCaption(context.src, context.pos, context.pos, [], show_numbers=show_numbers, visible=show_caption)
        head = TableHead(context.src, context.pos, context.pos, [])
        body = TableBody(context.src, context.pos, context.pos, [])
        foot = TableFoot(context.src, context.pos, context.pos, [])
        # Iterate parsed children of the table, populating the appropriate
        # caption, head, body or foot containers with elements and arguments
        # that belong with them. Drop anything that doesn't belong at all.
        for child in children:
            if isinstance(child, TableRow):
                # Orphaned row should be part of the body
                body.children.append(child)
            elif isinstance(child, TableHead):
                # A table head section was defined. Move its children into head
                head.children.extend(child.children)
                # Apply section arguments to the head
                head.h_align = child.h_align
                head.v_align = child.v_align
            elif isinstance(child, TableBody):
                # A table body section was defined. Move its children into body
                body.children.extend(child.children)
                # Apply section arguments to the body
                body.h_align = child.h_align
                body.v_align = child.v_align
            elif isinstance(child, TableFoot):
                # A table foot section was defined. Move its children into foot
                foot.children.extend(child.children)
                # Apply section arguments to the foot
                foot.h_align = child.h_align
                foot.v_align = child.v_align
            elif isinstance(child, TableCaption):
                # A table caption was defined. Move its children into caption
                caption.children.extend(child.children)
        if (not head.children) and extra['auto_head'] and (len(body.children) > 1):
            head.children.append(body.children[0])
            del body.children[0]
        if (not foot.children) and extra['auto_foot'] and (len(body.children) > 1):
            foot.children.append(body.children[-1])
            del body.children[-1]
        # Keep only non-empty elements
        return [child for child in (caption, head, body, foot) if child.children]


