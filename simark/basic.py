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

    def render_plain(self, context):
        if self.children:
            open_out = self.src[self.start_pos:self.children[0].start_pos]
            close_out = self.src[self.children[-1].end_pos:self.end_pos]
            return f'{open_out}{self.render_children_plain(context)}{close_out}'
        else:
            return self.raw

    def render_html(self, context):
        if self.children:
            open_out = html.escape(self.src[self.start_pos:self.children[0].start_pos])
            close_out = html.escape(self.src[self.children[-1].end_pos:self.end_pos])
            return f'{open_out}{self.render_children_html(context)}{close_out}'
        else:
            return html.escape(self.raw)


class UnknownParser(ElementParser):

    element_class = Unknown

    def check_name(self, context, name, extra):
        # Allow any name
        return name


#=============================================================================


class Reference(Element):

    inline = True

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, var_name=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.var_name = var_name

    def setup(self, context):
        self.var_value = str(context.get_var(self.var_name))

    def render_plain(self, context):
        return self.var_value

    def render_html(self, context):
        html_out = html.escape(self.var_value)
        class_attr = self.get_class_attr(context)
        return f'<span{class_attr}>{html_out}</span>' if class_attr else html_out


class ReferenceParser(ElementParser):

    names = ['ref']
    allow_children = False
    element_class = Reference

    def check_arguments(self, context, arguments, extra):
        var_name = arguments.get('var', 0)
        if not var_name:
            raise NoMatch
        extra['var_name'] = var_name
        return arguments


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

    def render_plain(self, context):
        return ''

    def render_html(self, context):
        return ''


class DefineParser(ElementParser):

    names = ['def']
    element_class = Define

    def check_arguments(self, context, arguments, extra):
        var_name = arguments.get('var', 0)
        if not var_name:
            raise NoMatch
        extra['var_name'] = var_name
        return arguments

    def check_children(self, context, children, extra):
        for child in children:
            if not isinstance(child, (Text, Reference)):
                raise NoMatch
        return children


#=============================================================================


class Increment(Element):

    inline = True

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, var_name=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.var_name = var_name

    def setup(self, context):
        context.inc_var(self.var_name)

    def render_plain(self, context):
        return ''

    def render_html(self, context):
        return ''


class IncrementParser(ElementParser):

    names = ['inc']
    element_class = Increment
    allow_children = False

    def check_arguments(self, context, arguments, extra):
        var_name = arguments.get('var', 0)
        if not var_name:
            raise NoMatch
        extra['var_name'] = var_name
        return arguments


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

    def before_setup(self, context):
        context.begin_section(start_num=self.start_num)

    def after_setup(self, context):
        context.end_section()

    def render_html(self, context):
        tab = self.get_indent()
        html_out = self.render_children_html(context)
        class_attr = self.get_class_attr(context)
        return f'{tab}<section{class_attr}>\n{html_out}\n{tab}</section>\n'


class SectionParser(ElementParser):

    names = ['section', 's']
    element_class = Section

    def check_arguments(self, context, arguments, extra):
        extra['start_num'] = arguments.get_int('start')
        return arguments



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

    def render_plain(self, context):
        return self.numbers + self.render_children_plain(context)

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
        tab = self.get_indent()
        return f'{tab}<h{level}{class_attr}>{html_out}</h{level}>\n'


class HeadingParser(ElementParser):

    names = ['h']
    element_class = Heading

    def check_arguments(self, context, arguments, extra):
        extra['level'] = arguments.get_int('level', 0)
        extra['show_numbers'] = arguments.get_bool('numbers', default=True)
        return arguments


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

    def before_setup(self, context):
        context.begin_list(self.style, start_num=self.start_num)

    def after_setup(self, context):
        context.end_list()

    def render_plain(self, context):
        return self.render_children_plain(context)

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        style_attr = f' style="{list_styles.get(self.style, list_styles["."])}"'
        start_attr = '' if self.start_num == 1 else f' start="{self.start_num}"'
        name_out = 'ol' if self.style in '1aAiI' else 'ul'
        html_out = self.render_children_html(context)
        tab = self.get_indent()
        return f'{tab}<{name_out}{class_attr}{style_attr}{start_attr}>\n{html_out}\n{tab}</{name_out}>'


class ListParser(ElementParser):

    names = ['list', 'l']
    element_class = List

    def check_arguments(self, context, arguments, extra):
        style = arguments.get('style', pos=0)
        if not style in list_styles:
            style = '.'
        extra['style'] = style
        extra['start_num'] = arguments.get_int('start', pos=None, default=1, invalid=1)
        return arguments


#=============================================================================


class ListItem(Element):

    paragraphs = True

    def before_setup(self, context):
        context.inc_list()

    def setup(self, context):
        self.numbers = context.list_numbers

    def render_plain(self, context):
        text_out = self.render_children_plain(context)
        return f'{self.numbers} {text_out}'

    def render_html(self, context):
        tab = self.get_indent()
        class_attr = self.get_class_attr(context)
        html_out = self.render_children_html(context)
        return f'{tab}<li{class_attr}>\n{html_out}\n{tab}</li>\n'


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

    def check_arguments(self, context, arguments, extra):
        url = arguments.get('url', 0)
        if not url:
            raise NoMatch
        extra['url'] = url
        return arguments


#=============================================================================


class LineBreak(Element):

    inline = True

    def render_html(self, context):
        return '<br>'


class LineBreakParser(ElementParser):

    names = ['br']
    element_class = LineBreak


#=============================================================================


class ParagraphBreak(Element):

    pass


class ParagraphBreakParser(ElementParser):

    names = ['p']
    element_class = ParagraphBreak
    allow_children = False


#=============================================================================


class Entity(Element):

    inline = True

    def render_plain(self, context):
        return plain_entities[self.name[1:]]

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
        tab = self.get_indent()
        return f'{tab}<pre{class_attr}>{html_out}</pre>'


class CodeParser(ElementParser):

    names = ['code']
    element_class = Code

    def get_child_parser(self, context):
        # All elements must descend from Text
        return Many(
            Any(
                VerbatimParser(),
                TextParser(),
                NonCloseCharParser(),
            )
        )

    def check_children(self, context, children, extra):
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
        tab = self.get_indent()
        content_html = self.render_children_html(context)
        float_style = float_styles[self.align]
        clear_style = ' clear: both;' if self.clear else ''
        return f'{tab}<div style="{float_style}{clear_style}">\n{content_html}\n{tab}</div>\n'


class FloatParser(ElementParser):

    names = ['float']
    element_class = Float

    def check_arguments(self, context, arguments, extra):
        align = arguments.get('align', 0, default='l')
        if not align in float_styles:
            raise NoMatch
        extra['align'] = align
        extra['clear'] = arguments.get_bool('clear')


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
        tab = self.get_indent()
        return f'{tab}<div{class_attr}{style_attr}>\n{html_out}\n{tab}</div>\n'


class BlockParser(ElementParser):

    names = ['block']
    element_class = Block

    def check_arguments(self, context, arguments, extra):
        align = arguments.get('align', 0)
        if not align in block_align_styles:
            raise NoMatch
        extra['align'] = align


