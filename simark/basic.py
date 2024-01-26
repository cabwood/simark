import re
import html
from itertools import permutations
from .parse import NoMatch, Many, Any
from .core import ElementParser, Element, TextParser, Text, VerbatimParser, NonCloseCharParser
from .entities import plain_entities, html_entities

class Unknown(Element):
    """
    Matches elements which are structurally valid, but fail other tests such
    as name or argument validity. Match failure might otherwise produce a
    Text object that would eat an element-opener, and upset element nesting.
    """

    def render_html(self, context):
        if self.children:
            open_out = html.escape(self.src[self.start_pos:self.children[0].start_pos])
            close_out = html.escape(self.src[self.children[-1].end_pos:self.end_pos])
            return f'{open_out}{self.render_children_html(context)}{close_out}'
        else:
            return html.escape(self.raw)

    def __str__(self):
        return f"{self.__class__.__name__}[{self.start_pos}:{self.end_pos}] (name={self.name})"


class UnknownParser(ElementParser):

    element_class = Unknown

    def parse_name(self, context, arguments):
        # Allow any name
        arguments['name'] = self.name_parser.parse(context).match[1]


#=============================================================================


class Reference(Element):

    inline = True

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, var_name=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.var_name = var_name

    def setup(self, context):
        self.var_value = str(context.get_var(self.var_name))

    def render_html(self, context):
        html_out = html.escape(self.var_value)
        class_attr = self.get_class_attr(context)
        return f'<span{class_attr}>{html_out}</span>' if class_attr else html_out


class ReferenceParser(ElementParser):

    names = ['ref']
    allow_children = False
    element_class = Reference

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        var_name = args.get('var', 0)
        if not var_name:
            raise NoMatch
        arguments['var_name'] = var_name


#=============================================================================


class Define(Element):

    inline = True

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, var_name=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.var_name = var_name

    def setup(self, context):
        # Ignore anything that isn't Text or Reference. Accumulate
        # plain text content, for variable value.
        value = ''
        for child in self.children:
            if isinstance(child, (Text, Reference)):
                value += child.render_plain(context)
        context.set_var(self.var_name, value)

    def render_html(self, context):
        return ''


class DefineParser(ElementParser):

    names = ['def']
    element_class = Define

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        var_name = args.get('var', 0)
        if not var_name:
            raise NoMatch
        arguments['var_name'] = var_name

    def parse_children(self, context, arguments):
        children = super().parse_children(context, arguments)
        arguments['children'] = [child for child in arguments['children'] if not isinstance(child, (Text, Reference))]
        return children


#=============================================================================


class Increment(Element):

    inline = True

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, var_name=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.var_name = var_name

    def setup(self, context):
        context.inc_var(self.var_name)

    def render_html(self, context):
        return ''


class IncrementParser(ElementParser):

    names = ['inc']
    element_class = Increment
    allow_children = False

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        var_name = args.get('var', 0)
        if not var_name:
            raise NoMatch
        arguments['var_name'] = var_name


#=============================================================================


def permutate(items):
    perms = []
    for r in range(1, len(items)+1):
        for p in permutations(items, r):
            perms.append(''.join(p))
    return perms


class Format(Element):

    inline = True

    def render_html(self, context):
        html_out = self.render_children_html(context)
        for c in self.name:
            html_out = f'<{c}>{html_out}</{c}>'
        class_attr = self.get_class_attr(context)
        return f'<span{class_attr}>{html_out}</span>' if class_attr else html_out


class FormatParser(ElementParser):

    names = permutate('ibu')
    element_class = Format


#=============================================================================


class Section(Element):

    paragraphs = True

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, start_num=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.start_num = start_num

    def before_child_setup(self, context):
        context.begin_section(start_num=self.start_num)

    def after_child_setup(self, context):
        context.end_section()

    def render_html(self, context):
        html_out = self.render_children_html(context)
        class_attr = self.get_class_attr(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<section{class_attr}>{newline}{html_out}{newline}{indent}</section>{newline}'


class SectionParser(ElementParser):

    names = ['section', 's']
    element_class = Section

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        arguments['start_num'] = args.get_int('start')



#=============================================================================


class Heading(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, level=None, show_numbers=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.level = level
        self.show_numbers = show_numbers

    def setup(self, context):
        if self.level is None:
            self.level = context.section_level
        # No numbering at top level
        if self.level == 0:
            self.numbers = ''
            return
        show_nums = self.show_numbers
        if show_nums is None:
            show_nums = context.show_heading_numbers
        self.numbers = context.section_numbers + '. ' if show_nums else ''

    def render_html(self, context):
        # Clamp level to between 1 and 6, corresponding to available HTML <h?> options
        html_out = html.escape(self.numbers) + self.render_children_html(context)
        html_classes = []
        if self.html_class:
            html_classes.append(self.html_class)
        if self.level == 0:
            # Apply a class so CSS can find and center this
            html_classes.append('title')
        class_attr = self.get_class_attr(context, *html_classes)
        level = max(min(6, self.level), 1)
        indent, newline = self.get_whitespace()
        return f'{indent}<h{level}{class_attr}>{html_out}</h{level}>{newline}'


class HeadingParser(ElementParser):

    names = ['h']
    element_class = Heading

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        arguments['level'] = args.get_int('level', 0)
        arguments['show_numbers'] = args.get_bool('numbers', default=True)


#=============================================================================


list_styles = {
    '1': 'list-style-type: decimal;',
    'a': 'list-style-type: lower-alpha;',
    'A': 'list-style-type: upper-alpha;',
    'i': 'list-style-type: lower-roman;',
    'I': 'list-style-type: upper-roman;',
    '.': 'list-style-type: disc;',
    'o': 'list-style-type: circle;',
}

class List(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, style=None, start_num=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.style = style
        self.start_num = start_num

    def before_child_setup(self, context):
        context.begin_list(self.style, start_num=self.start_num)

    def after_child_setup(self, context):
        context.end_list()

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        style_attr = f' style="{list_styles.get(self.style, list_styles["."])}"'
        start_attr = '' if self.start_num == 1 else f' start="{self.start_num}"'
        tag = 'ol' if self.style in '1aAiI' else 'ul'
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<{tag}{class_attr}{style_attr}{start_attr}>{newline}{html_out}{newline}{indent}</{tag}>{newline}'


class ListParser(ElementParser):

    names = ['list', 'l']
    element_class = List

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        arguments['style'] = list_styles.get(args.get('style', pos=0), '.')
        arguments['start_num'] = args.get_int('start', pos=None, default=1, invalid=1)


#=============================================================================


class ListItem(Element):

    paragraphs = True

    def before_child_setup(self, context):
        context.inc_list()

    def setup(self, context):
        self.numbers = context.list_numbers

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<li{class_attr}>{newline}{html_out}{newline}{indent}</li>{newline}'


class ListItemParser(ElementParser):

    names = ['listitem', 'li']
    element_class = ListItem


#=============================================================================


class Link(Element):

    inline = True

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, url=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.url = url

    def render_html(self, context):
        html_out = self.render_children_html(context) or html.escape(self.url)
        class_attr = self.get_class_attr(context)
        return f'<a{class_attr} href="{self.url}">{html_out}</a>'


class LinkParser(ElementParser):

    names = ['link']
    element_class = Link

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        url = args.get('url', 0)
        if not url:
            raise NoMatch
        arguments['url'] = url


#=============================================================================


class LineBreak(Element):

    inline = True

    def render_html(self, context):
        return f'<br>'


class LineBreakParser(ElementParser):

    names = ['l']
    element_class = LineBreak


#=============================================================================


class ParagraphBreak(Element):

    pass


class ParagraphBreakParser(ElementParser):

    names = ['p']
    element_class = ParagraphBreak

    from .core import Paragraph

    def parse1(self, context):
        # A {p} element without children is a paragraph break, which is used to
        # divide text into paragraphs. If the {p} element has children, though,
        # we should place them inside a regular Paragraph element.
        chunk = super().parse1(context)
        if chunk.children:
            return self.Paragraph(chunk.src, chunk.start_pos, chunk.end_pos, chunk.children)
        return chunk


#=============================================================================


class Entity(Element):

    inline = True

    def render_html(self, context):
        return html_entities[self.name[1:]]


class EntityParser(ElementParser):

    names = [f'_{s}' for s in plain_entities.keys()]
    name_case_sensitive = True
    element_class = Entity


#=============================================================================


class Code(Element):

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<pre{class_attr}>{html_out}</pre>{newline}'


class CodeParser(ElementParser):

    names = ['code']
    element_class = Code

    def parse_children(self, context, arguments):
        children = super().parse_children(context, arguments)
        # Remove leading and trailing empty lines
        if children:
            text = ''
            start_pos = children[0].start_pos
            end_pos = children[-1].end_pos
            for child in children:
                text += child.text
            lines = text.split('\n')
            while lines:
                if lines[0].strip():
                    break
                del lines[0]
            while lines:
                if lines[-1].strip():
                    break
                del lines[-1]
            return [Text(context.src, start_pos, end_pos, '\n'.join(lines))]
        return children

    def get_child_parser(self, context):
        # All elements must descend from Text
        return Many(
            Any(
                VerbatimParser(),
                TextParser(),
                NonCloseCharParser(),
            )
        )


#=============================================================================


float_styles = {
    'l': "float: left;",
    'left': "float: left;",
    'r': "float: right;",
    'right': "float: right;",
}


class Float(Element):

    paragraphs = True

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, align=None, clear=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.align = align
        self.clear = clear

    def render_html(self, context):
        content_html = self.render_children_html(context)
        float_style = float_styles[self.align]
        clear_style = ' clear: both;' if self.clear else ''
        indent, newline = self.get_whitespace()
        return f'{indent}<div style="{float_style}{clear_style}">{newline}{content_html}{newline}{indent}</div>{newline}'


class FloatParser(ElementParser):

    names = ['float']
    element_class = Float

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        align = args.get('align', 0, default='l')
        if not align in float_styles:
            raise NoMatch
        arguments['align'] = align
        arguments['clear'] = arguments.get_bool('clear')


#=============================================================================


block_align_styles = {
    None: '',
    'l': 'text-align: left;',
    'left': 'text-align: left;',
    'r': 'text-align: right;',
    'right': 'text-align: right;',
    'm': 'text-align: center;',
    'c': 'text-align: center;',
    'center': 'text-align: center;',
    'middle': 'text-align: center;',
}


class Block(Element):

    paragraphs = True

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, align=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.align = align

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        style_attr = f' style="{block_align_styles[self.align]}"' if self.align else ''
        html_out = self.render_children_html(context)
        indent, newline = self.get_whitespace()
        return f'{indent}<div{class_attr}{style_attr}>{newline}{html_out}{newline}{indent}</div>{newline}'


class BlockParser(ElementParser):

    names = ['block']
    element_class = Block

    def parse_arguments(self, context, arguments):
        args = self.arguments_parser.parse(context)
        align = args.get('align', 0)
        if not align in block_align_styles:
            raise NoMatch
        arguments['align'] = align


