import html
from itertools import permutations
from .parse import NoMatch, Many, Any, Regex
from .core import ElementParser, Element, TextParser, Text, VerbatimParser
from .entities import plain_entities, html_entities


#=============================================================================


class GetVar(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, var_name=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.var_name = var_name

    def evaluate(self, context):
        return context.get_var(self.var_name)

    def setup_enter(self, context):
        self.var_value = self.evaluate(context)

    def render_self(self, context):
        if self.var_value is None:
            # Another pass, another chance to evaluate
            self.var_value = self.evaluate(context) or ''
        html_out = html.escape(str(self.var_value))
        class_attr = self.get_class_attr(context)
        return f'<span{class_attr}>{html_out}</span>' if class_attr else html_out


class GetVarParser(ElementParser):

    names = ['get']
    allow_children = False
    element_class = GetVar

    @classmethod
    def parse_arguments(cls, context, arguments):
        args = cls.arguments_parser.parse(context)
        var_name = args.get('var', 0)
        if not var_name:
            raise NoMatch
        arguments['var_name'] = var_name


#=============================================================================


class SetVar(Element):

    def __init__(self, src, start_pos, end_pos, children=None, name=None, arguments=None, var_name=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.var_name = var_name

    def setup_enter(self, context):
        # Content should be only Text or GetVar. Value is concatenation of
        # plain text content
        value = ''
        for child in self.children:
            if isinstance(child, Text):
                value += child.text
            elif isinstance(child,GetVar):
                value += str(child.evaluate(context))
        context.set_var(self.var_name, value)

    def render_self(self, context):
        return ''


class SetVarParser(ElementParser):

    names = ['set']
    element_class = SetVar
    child_parser = Many(
        Any(
            TextParser(),
            GetVarParser(),
        )
    )

    @classmethod
    def parse_arguments(cls, context, arguments):
        args = cls.arguments_parser.parse(context)
        var_name = args.get('var', 0)
        if not var_name:
            raise NoMatch
        arguments['var_name'] = var_name

    @classmethod
    def parse_children(cls, context, arguments):
        return cls.child_parser.parse(context).children


#=============================================================================


class IncVar(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, var_name=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.var_name = var_name

    def setup_enter(self, context):
        context.inc_var(self.var_name)

    def render_self(self, context):
        return ''


class IncVarParser(ElementParser):

    names = ['inc']
    element_class = IncVar
    allow_children = False

    @classmethod
    def parse_arguments(cls, context, arguments):
        args = cls.arguments_parser.parse(context)
        var_name = args.get('var', 0)
        if not var_name:
            raise NoMatch
        arguments['var_name'] = var_name


#=============================================================================


class Paragraph(Element):

    def render_self(self, context):
        html_out = self.render_children(context)
        class_attr = self.get_class_attr(context)
        indent, newline = self.get_whitespace(context)
        return f'{indent}<p{class_attr}>{html_out}</p>{newline}'


class ParagraphParser(ElementParser):

    names = ['p']
    element_class = Paragraph


#=============================================================================


def permutate(items):
    perms = []
    for r in range(1, len(items)+1):
        for p in permutations(items, r):
            perms.append(''.join(p))
    return perms


class Format(Element):

    def render_self(self, context):
        html_out = self.render_children(context)
        for c in self.name:
            html_out = f'<{c}>{html_out}</{c}>'
        class_attr = self.get_class_attr(context)
        return f'<span{class_attr}>{html_out}</span>' if class_attr else html_out


class FormatParser(ElementParser):

    names = permutate('ibu')
    element_class = Format


#=============================================================================


class Section(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, start_num=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.start_num = start_num

    def setup_enter(self, context):
        context.section_counter.enter(start_num=self.start_num)

    def setup_exit(self, context):
        context.section_counter.exit()

    def render_self(self, context):
        html_out = self.render_children(context)
        class_attr = self.get_class_attr(context)
        indent, newline = self.get_whitespace(context)
        return f'{indent}<section{class_attr}>{newline}{html_out}{newline}{indent}</section>{newline}'


class SectionParser(ElementParser):

    names = ['section', 's']
    element_class = Section

    @classmethod
    def parse_arguments(cls, context, arguments):
        args = cls.arguments_parser.parse(context)
        arguments['start_num'] = args.get_int('start')



#=============================================================================


class Heading(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, level=None, show_numbers=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.level = level
        self.show_numbers = show_numbers

    def setup_enter(self, context):
        if self.level is None:
            self.level = context.section_counter.level
        if self.level == 0:
            # No numbering at top level
            self.numbers = ''
        else:
            show_nums = self.show_numbers
            self.numbers = context.section_counter.text + ' ' if show_nums else ''

    def render_self(self, context):
        # Clamp level to between 1 and 6, corresponding to available HTML <h?> options
        html_out = html.escape(self.numbers) + self.render_children(context)
        html_classes = []
        if self.html_class:
            html_classes.append(self.html_class)
        if self.level == 0:
            # Apply a class so CSS can find and center this
            html_classes.append('title')
        class_attr = self.get_class_attr(context, *html_classes)
        level = max(min(6, self.level), 1)
        indent, newline = self.get_whitespace(context)
        return f'{indent}<h{level}{class_attr}>{html_out}</h{level}>{newline}'


class HeadingParser(ElementParser):

    names = ['h']
    element_class = Heading

    @classmethod
    def parse_arguments(cls, context, arguments):
        args = cls.arguments_parser.parse(context)
        arguments['level'] = args.get_int('level', 0)
        arguments['show_numbers'] = args.get_bool('numbers', default=True)


#=============================================================================


class ListItem(Element):

    def setup_enter(self, context):
        self.numbers = context.list_counter.text

    def setup_exit(self, context):
        context.list_counter.inc()

    def render_self(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children(context)
        indent, newline = self.get_whitespace(context)
        return f'{indent}<li{class_attr}>{html_out}</li>{newline}'


class ListItemParser(ElementParser):

    names = ['item']
    element_class = ListItem


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
        self.style = style if style in list_styles else '.'
        self.start_num = start_num

    def setup_enter(self, context):
        context.list_counter.enter(self.style, start_num=self.start_num)

    def setup_exit(self, context):
        context.list_counter.exit()

    def render_self(self, context):
        class_attr = self.get_class_attr(context)
        style_attr = f' style="{list_styles[self.style]}"'
        start_attr = '' if self.start_num == 1 else f' start="{self.start_num}"'
        tag = 'ol' if self.style in '1aAiI' else 'ul'
        html_out = self.render_children(context)
        indent, newline = self.get_whitespace(context)
        return f'{indent}<{tag}{class_attr}{style_attr}{start_attr}>{newline}{html_out}{newline}{indent}</{tag}>{newline}'


class ListParser(ElementParser):

    names = ['list']
    element_class = List
    child_parser = Many(
        Any(
            ListItemParser(),
            Regex(r'\s*'),
        )
    )

    @classmethod
    def parse_arguments(cls, context, arguments):
        args = cls.arguments_parser.parse(context)
        arguments['style'] = args.get('style')
        arguments['start_num'] = args.get_int('start', pos=None, default=1, invalid=1)

    @classmethod
    def parse_children(cls, context, arguments):
        children = cls.child_parser.parse(context).children
        return [child for child in children if isinstance(child, ListItem)]


#=============================================================================


class Link(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, url=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.url = url

    def render_self(self, context):
        html_out = self.render_children(context) or html.escape(self.url)
        class_attr = self.get_class_attr(context)
        return f'<a{class_attr} href="{self.url}">{html_out}</a>'


class LinkParser(ElementParser):

    names = ['link']
    element_class = Link

    @classmethod
    def parse_arguments(cls, context, arguments):
        args = cls.arguments_parser.parse(context)
        url = args.get('url', 0)
        if not url:
            raise NoMatch
        arguments['url'] = url


#=============================================================================


class LineBreak(Element):

    def render_self(self, context):
        return f'<br>'


class LineBreakParser(ElementParser):

    names = ['l']
    element_class = LineBreak


#=============================================================================


class Entity(Element):

    def render_self(self, context):
        return html_entities[self.name[1:]]


class EntityParser(ElementParser):

    names = [f'_{s}' for s in plain_entities.keys()]
    name_case_sensitive = True
    element_class = Entity


#=============================================================================


class Code(Element):

    def render_self(self, context):
        class_attr = self.get_class_attr(context)
        html_out = self.render_children(context)
        indent, newline = self.get_whitespace(context)
        return f'{indent}<pre{class_attr}>{html_out}</pre>{newline}'


class CodeParser(ElementParser):

    names = ['code']
    element_class = Code
    parser = Many(
                Any(
                    VerbatimParser(),
                    TextParser(),
                )
            )

    @classmethod
    def parse_children(cls, context, arguments):
        children = cls.parser.parse(context).children
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

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, align=None, clear=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.align = align
        self.clear = clear

    def render_self(self, context):
        content_html = self.render_children(context)
        float_style = float_styles[self.align]
        clear_style = ' clear: both;' if self.clear else ''
        indent, newline = self.get_whitespace(context)
        return f'{indent}<div style="{float_style}{clear_style}">{newline}{content_html}{newline}{indent}</div>{newline}'


class FloatParser(ElementParser):

    names = ['float']
    element_class = Float

    @classmethod
    def parse_arguments(cls, context, arguments):
        args = cls.arguments_parser.parse(context)
        align = args.get('align', 0, default='l')
        if not align in float_styles:
            raise NoMatch
        arguments['align'] = align
        arguments['clear'] = arguments.get_bool('clear')


#=============================================================================


align_styles = {
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


class Align(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, align=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.align = align

    def render_self(self, context):
        class_attr = self.get_class_attr(context)
        style_attr = f' style="{align_styles[self.align]}"' if self.align else ''
        html_out = self.render_children(context)
        indent, newline = self.get_whitespace(context)
        return f'{indent}<div{class_attr}{style_attr}>{newline}{html_out}{newline}{indent}</div>{newline}'


class AlignParser(ElementParser):

    names = ['block']
    element_class = Align

    @classmethod
    def parse_arguments(cls, context, arguments):
        args = cls.arguments_parser.parse(context)
        align = args.get('align', 0)
        if not align in align_styles:
            raise NoMatch
        arguments['align'] = align


