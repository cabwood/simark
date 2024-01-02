import re
import html
from .parse import Parser, Many, Any, Regex
from .core import ElementParser, Element, Text, VerbatimParser, \
    unescape, esc_element_open, esc_element_close, \
    ESC_BACKSLASH, ESC_BACKTICK, ESC_ELEMENT_OPEN, ESC_ELEMENT_CLOSE


class TableCaption(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, show_numbers=False):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.show_numbers = show_numbers

    def setup(self, context):
        self.numbers = context.table_numbers

    def render_html(self, context):
        html_out = self.render_children_html(context)
        if self.show_numbers:
            html_out = f'Table {html.escape(self.numbers)}. {html_out}'
        html_out = html_out.strip()
        if html_out:
            tab = self.get_indent()
            html_out = f'{tab}<caption>{html_out}</caption>\n'
        return html_out


class TableCaptionParser(ElementParser):

    names = ['caption']
    element_class = TableCaption


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


class TableHead(Element):

    def setup(self, context):
        # Convert table head cells to <th> tags
        for row in self.children:
            for cell in row.children:
                cell.is_header = True

    def render_html(self, context):
        if not self.children:
            return ''
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        tab = self.get_indent()
        return f'{tab}<thead{class_attr}>\n{html_out}\n{tab}</thead>\n'

class TableHeadParser(TableRowGroupParser):

    names = ['head']
    element_class = TableHead


class TableBody(Element):

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        tab = self.get_indent()
        return f'{tab}<tbody{class_attr}>\n{html_out}\n{tab}</tbody>\n'


class TableBodyParser(TableRowGroupParser):

    names = ['body']
    element_class = TableBody


class TableFoot(Element):

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        tab = self.get_indent()
        return f'{tab}<tfoot{class_attr}>\n{html_out}\n{tab}</tfoot>\n'


class TableFootParser(TableRowGroupParser):

    names = ['foot']
    element_class = TableFoot


class TableTextParser(Parser):
    """
    Like as TextParser, except bar "|" and newline also terminate the text,
    and may be empty.
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


table_align_attrs = {
    'l': ' align="left"',
    'm': ' align="middle"',
    'r': ' align="right"',
}

class TableCell(Element):

    paragraphs = True

    align_horz = 'm'
    is_header = False

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        align_attr = table_align_attrs.get(self.align_horz, table_align_attrs['m'])
        save_compact = context.compact
        context.compact = True
        html_out = self.render_children_html(context)
        context.compact = save_compact
        tag = 'th' if self.is_header else 'td'
        tab = self.get_indent()
        return f'{tab}<{tag}{class_attr}{align_attr}>{html_out}</{tag}>\n'


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


class TableRow(Element):

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        tab = self.get_indent()
        return f'{tab}<tr{class_attr}>\n{html_out}\n{tab}</tr>\n'


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
            caption=None, head=None, body=None, foot=None, align=None, show_caption=None, \
            show_numbers=None, auto_head=None, auto_foot=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.caption = caption
        self.head = head
        self.body = body
        self.foot = foot
        self.align = align
        self.show_numbers = show_numbers
        self.show_caption = show_caption
        self.auto_head = auto_head
        self.auto_foot = auto_foot

    def before_setup(self, context):
        context.begin_table()

    def setup(self, context):
        self.numbers = context.table_numbers

    def after_setup(self, context):
        context.end_table()

    def render_html(self, context):

        def set_alignment(rows, alignments):
            count = len(alignments)
            for row in rows:
                for index, cell in enumerate(row.children):
                    if index >= count:
                        break
                    cell.align_horz = alignments[index]

        class_attr = self.get_class_attr(context)
        caption_html = self.caption.render_html(context) if self.show_caption else ''
        set_alignment(self.body.children, self.align)
        set_alignment(self.foot.children, self.align)
        head_html = self.head.render_html(context) if self.head.children else ''
        body_html = self.body.render_html(context) if self.body.children else ''
        foot_html = self.foot.render_html(context) if self.foot.children else ''
        tab = self.get_indent()
        return f'{tab}<table{class_attr}>\n{caption_html}{head_html}{body_html}{foot_html}{tab}</table>\n'


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
        extra['align'] = arguments.get('align', 0)
        extra['show_numbers'] = arguments.get_bool('numbers', default=True)
        extra['show_caption'] = arguments.get_bool('caption', default=True)
        extra['auto_head'] = arguments.get_bool('autohead', default=True)
        extra['auto_foot'] = arguments.get_bool('autofoot', default=False)
        return arguments

    def check_children(self, context, children, extra):
        caption_parts = []
        head_rows = []
        body_rows = []
        foot_rows = []
        for child in children:
            if isinstance(child, TableRow):
                body_rows.append(child)
            elif isinstance(child, TableBody):
                body_rows.extend(child.children)
            elif isinstance(child, TableHead):
                head_rows.extend(child.children)
            elif isinstance(child, TableFoot):
                foot_rows.extend(child.children)
            elif isinstance(child, TableCaption):
                caption_parts.extend(child.children)
        if (not head_rows) and extra['auto_head'] and (len(body_rows) > 1):
            head_rows.append(body_rows[0])
            del body_rows[0]
        if (not foot_rows) and extra['auto_foot'] and (len(body_rows) > 1):
            foot_rows.append(body_rows[-1])
            del body_rows[-1]
        caption = TableCaption(context.src, context.pos, context.pos, caption_parts, \
                               show_numbers=extra['show_numbers']) if caption_parts else None
        head = TableHead(context.src, context.pos, context.pos, head_rows) if head_rows else None
        body = TableBody(context.src, context.pos, context.pos, body_rows) if body_rows else None
        foot = TableFoot(context.src, context.pos, context.pos, foot_rows) if foot_rows else None
        extra.update({'caption': caption, 'head': head, 'body': body, 'foot': foot})
        children = [child for child in [caption, head, body, foot] if child]
        return children


