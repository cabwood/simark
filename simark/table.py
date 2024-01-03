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

    def load_arguments(self, arguments):
        # No arguments implemented yet
        pass

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
        self.h_align = '' if h_align is None else h_align
        self.v_align = '' if v_align is None else v_align

    def before_child_setup(self, context):
        pass

    def set_child_alignment(self, h_align, v_align):
        pass

    def load_arguments(self, arguments):
        """
        Adopt relevant arguments from those provided, to permit overdiding
        of inherited behaviour.
        """
        h_align = arguments.get('h_align')
        if h_align is not None:
            self.h_align = h_align
        v_align = arguments.get('v_align')
        if v_align is not None:
            self.v_align = v_align

    def render_html(self, context):
        if not self.children:
            return ''
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<{self.html_tag}{class_attr}>{newline}{html_out}{newline}{indent}</{self.html_tag}>{newline}'


class TableRowGroupParser(ElementParser):

    empty_line_parser = Regex(re.compile(f'[^\S\n]*\n'))

    def get_child_parser(self, context):
        return Many(
            Any(
                TableRowParser(),
                self.empty_line_parser,
            )
        )

    def check_children(self, context, children, extra):
        # Discard anything that isn't a TableRow
        return [child for child in children if isinstance(child, TableRow)]


class TableHead(TableSection):

    html_tag = 'thead'

    def setup(self, context):
        for row in self.children:
            for cell in row.children:
                cell.html_tag = 'th'


class TableHeadParser(TableRowGroupParser):

    names = ['head']
    element_class = TableHead


class TableBody(TableSection):

    html_tag = 'tbody'


class TableBodyParser(TableRowGroupParser):

    names = ['body']
    element_class = TableBody


class TableFoot(TableSection):

    html_tag = 'tfoot'


class TableFootParser(TableRowGroupParser):

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
    'l': ' align="left"',
    'm': ' align="middle"',
    'r': ' align="right"',
}

table_v_align_attrs = {
    't': ' vertical-align="top"',
    'm': ' vertical-align="middle"',
    'b': ' vertical-align="bottom"',
}

class TableCell(Element):

    paragraphs = True

    html_tag = 'td'
    h_align = 'm'
    v_align = 'm'

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, h_align=None, v_align=None):
        super().__init__(src, start_pos, end_pos, children, name=name, arguments=arguments)
        self.h_align = 'm' if h_align is None else h_align
        self.v_align = 'm' if v_align is None else v_align

    def before_child_setup(self, context):
        # Render children compact
        context.compact = True

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        align_attr = table_h_align_attrs.get(self.h_align, table_h_align_attrs['m'])
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<{self.html_tag}{class_attr}{align_attr}>{html_out}</{self.html_tag}>{newline}'


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
        # foot elements, and to populate them with arguments and rows found
        # in the source, one by one.
        h_align = extra['h_align']
        v_align = extra['v_align']
        show_caption = extra['show_caption']
        show_numbers = extra['show_numbers']
        caption = TableCaption(context.src, context.pos, context.pos, [], show_numbers=show_numbers, visible=show_caption)
        head = TableHead(context.src, context.pos, context.pos, [], h_align=h_align, v_align=v_align)
        body = TableBody(context.src, context.pos, context.pos, [], h_align=h_align, v_align=v_align)
        foot = TableFoot(context.src, context.pos, context.pos, [], h_align=h_align, v_align=v_align)
        # Iterate parsed children of the table, populating the appropriate
        # caption, head, body or foot containers with elements and arguments
        # that belong with them. Drop anything that doesn't belong at all.
        for child in children:
            if isinstance(child, TableRow):
                # Orphaned row should be part of the body
                body.children.append(child)
            elif isinstance(child, TableHead):
                # A table head section was defined. Move its children and any
                # arguments into the new head element
                head.load_arguments(child.arguments)
                head.children.extend(child.children)
            elif isinstance(child, TableBody):
                # A table body section was defined. Move its children and any
                # arguments into the new body element
                body.load_arguments(child.arguments)
                body.children.extend(child.children)
            elif isinstance(child, TableFoot):
                # A table foot section was defined. Move its children and any
                # arguments into the new foot element
                foot.load_arguments(child.arguments)
                foot.children.extend(child.children)
            elif isinstance(child, TableCaption):
                # A table caption was defined. Move its children and any
                # arguments into the new caption element
                caption.load_arguments(child.arguments)
                caption.children.extend(child.children)
        if (not head.children) and extra['auto_head'] and (len(body.children) > 1):
            head.children.append(body.children[0])
            del body.children[0]
        if (not foot.children) and extra['auto_foot'] and (len(body.children) > 1):
            foot.children.append(body.children[-1])
            del body.children[-1]
        # Keep only non-empty elements
        return [child for child in (caption, head, body, foot) if child.children]


