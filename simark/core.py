import re
import html
from .parse import NoMatch, Parser, Any, Many, Regex, Exact, Chunk, TextChunk
from .render import RenderMixin

#=============================================================================
# Document elements and parsers
#=============================================================================

ELEMENT_OPEN = '{'
ELEMENT_CLOSE = '}'
ELEMENT_SPLIT = '|'

esc_element_open = re.escape(ELEMENT_OPEN)
esc_element_close = re.escape(ELEMENT_CLOSE)
esc_element_split = re.escape(ELEMENT_SPLIT)

ESC_BACKSLASH = (r"\\", "\\")
ESC_BACKTICK = (r"\`", "`")
ESC_SINGLE_QUOTE = (r"\'", "'")
ESC_DOUBLE_QUOTE = (r'\"', '"')
ESC_ELEMENT_OPEN = (rf"\{ELEMENT_OPEN}", ELEMENT_OPEN)
ESC_ELEMENT_CLOSE = (rf"\{ELEMENT_CLOSE}", ELEMENT_CLOSE)
ESC_ELEMENT_SPLIT = (rf"\{ELEMENT_SPLIT}", ELEMENT_SPLIT)


def unescape(s, *patterns):
    for esc, rep in patterns:
        s = s.replace(esc, rep)
    return s


class BaseElement(RenderMixin, Chunk):

    inline = False
    paragraphs = False


class Text(BaseElement):

    inline = True

    def __init__(self, src, start_pos, end_pos, text):
        super().__init__(src, start_pos, end_pos)
        self.text = text

    def render_plain(self, context):
        return self.text

    def render_html(self, context):
        class_attr = self.get_class_attr(context)
        html_out = html.escape(self.text)
        return f'<span{class_attr}>{html_out}</span>' if class_attr else html_out

    def __str__(self):
        return f"{self.__class__.__name__}[{self.start_pos}:{self.end_pos}] {repr(self.text)}"


class TextParser(Parser):

    parser = Regex(re.compile(rf"(\\\\|\\`|\\{esc_element_open}|\\{esc_element_close}|[^`{esc_element_open}{esc_element_close}])+"))

    def parse1(self, context):
        match = self.parser.parse(context).match
        return Text(context.src, match.start(0), match.end(0), unescape(match[0],
            ESC_BACKSLASH,
            ESC_BACKTICK,
            ESC_ELEMENT_OPEN,
            ESC_ELEMENT_CLOSE,
        ))


class Paragraph(BaseElement):

    def render_plain(self, context):
        return f'\n\n{self.render_children_plain(context)}'

    def render_html(self, context):
        return f'<p>{self.render_children_html(context)}</p>\n'


class VerbatimParser(Parser):

    parser = Regex(re.compile(r"(`+)(.+?)\1", re.DOTALL))
                          # Non-greedy ^

    def parse1(self, context):
        match = self.parser.parse(context).match
        return Text(context.src, match.start(2), match.end(2), match[2])


class AnyCharParser(Parser):

    parser = Regex(re.compile(rf"\\\\|\\'|\\{esc_element_open}|\\{esc_element_close}|.", re.DOTALL))

    def parse1(self, context):
        match = self.parser.parse(context).match
        return Text(context.src, match.start(0), match.end(0), unescape(match[0],
            ESC_BACKSLASH,
            ESC_BACKTICK,
            ESC_ELEMENT_OPEN,
            ESC_ELEMENT_CLOSE,
        ))


class NonCloseCharParser(Parser):

    parser = Regex(re.compile(rf"\\\\|\\`|\\{esc_element_open}|\\{esc_element_close}|[^{esc_element_close}]"))

    def parse1(self, context):
        match = self.parser.parse(context).match
        return Text(context.src, match.start(0), match.end(0), unescape(match[0],
            ESC_BACKSLASH,
            ESC_BACKTICK,
            ESC_ELEMENT_OPEN,
            ESC_ELEMENT_CLOSE,
        ))


class DoubleQuotedParser(Parser):
    
    parser = Regex(re.compile(r'\s*"((?:\\\\|\\"|[^"])*)"'))

    def parse1(self, context):
        match = self.parser.parse(context).match
        return TextChunk(context.src, match.start(1), match.end(1), unescape(match[1],
            ESC_BACKSLASH,
            ESC_DOUBLE_QUOTE
        ))


class SingleQuotedParser(Parser):
    
    parser = Regex(re.compile(r"\s*'((?:\\\\|\\'|[^'])*)'"))

    def parse1(self, context):
        match = self.parser.parse(context).match
        return TextChunk(context.src, match.start(1), match.end(1), unescape(match[1],
            ESC_BACKSLASH,
            ESC_SINGLE_QUOTE
        ))


class UnquotedParser(Parser):
    
    parser = Regex(re.compile(rf"""\s*((?:\\"|\\'\\{esc_element_close}|\\{esc_element_split}|[^\s{esc_element_close}{esc_element_split}])*)\s*"""))

    def parse1(self, context):
        match = self.parser.parse(context).match
        return TextChunk(context.src, match.start(1), match.end(1), unescape(match[1],
            ESC_BACKSLASH,
            ESC_SINGLE_QUOTE,
            ESC_DOUBLE_QUOTE,
            ESC_ELEMENT_CLOSE,
            ESC_ELEMENT_SPLIT,
        ))


class ArgumentParser(Parser):

    name_parser = Regex(re.compile(rf"\s*([A-Za-z0-9_]+)\s*="))
    value_parser = Any(
        DoubleQuotedParser(),
        SingleQuotedParser(),
        UnquotedParser(),
    )

    def parse1(self, context):
        start_pos = context.pos
        try:
            name = self.name_parser.parse(context).match[1].lower()
        except NoMatch:
            name = None
        value = self.value_parser.parse(context).text
        return Argument(context.src, start_pos, context.pos, name, value)


class Argument(Chunk):

    def __init__(self, src, start_pos, end_pos, name, value):
        super().__init__(src, start_pos, end_pos)
        self.name = name
        self.value = value


bool_arguments = {
    'true': True,
    'false': False,
    'on': True,
    'off': False,
    'yes': True,
    'no': False,
    '1': True,
    '0': False,
}

class Arguments(Chunk):

    def __init__(self, src, start_pos, end_pos, arg_chunks):
        super().__init__(src, start_pos, end_pos, children=arg_chunks)
        self.by_name = {}
        self.by_pos = []
        for arg_chunk in arg_chunks:
            self.append(arg_chunk.name, arg_chunk.value)

    def append(self, name, value):
        self.by_pos.append(value)
        l = self.by_name.get(name)
        if l is None:
            l = list()
            self.by_name[name] = l
        l.append(value)

    def _get(self, name, pos=None):
        l = self.by_name.get(name)
        if l:
            return l[-1]
        if pos is None or pos >= len(self.by_pos):
            return None
        return self.by_pos[pos]

    def get(self, name, pos=None, default=None):
        value = self._get(name, pos)
        if value is None:
            return default
        return value
    
    def get_int(self, name, pos=None, default=None, invalid=None):
        value = self._get(name, pos)
        if value is None:
            return default
        try:
            value = int(value)
        except ValueError:
            return invalid
        return value

    def get_bool(self, name, pos=None, default=None, invalid=None):
        value = self._get(name, pos)
        if value is None:
            return default
        return bool_arguments.get(value.lower(), invalid)


class ArgumentsParser(Parser):

    parser = Many(ArgumentParser())

    def parse1(self, context):
        start_pos = context.pos
        arguments = self.parser.parse(context).children
        return Arguments(context.src, start_pos, context.pos, arguments)


class PartsParser(Parser):

    def parse2(self, context, chunk):
        children = chunk.children
        children = self.concatenate_text(context, children)
        if chunk.paragraphs:
            children = self.build_paragraphs(context, children)
        chunk.children = children
        return chunk

    def concatenate_text(self, context, children):
        new_children = []
        start_pos = None
        text = ''
        for child in children:
            if isinstance(child, Text):
                if start_pos is None:
                    start_pos = child.start_pos
                    text = ''
                text += child.text
                end_pos = child.end_pos
            else:
                if text:
                    new_children.append(Text(context.src, start_pos, end_pos, text))
                start_pos = None
                text = ''
                new_children.append(child)
        if text:
            new_children.append(Text(context.src, start_pos, end_pos, text))
        return new_children

    def build_paragraphs(self, context, children):
        # Group consecutive, non-empty, inline elements as children of a single Paragraph
        new_children = []
        start_pos = None
        elements = []
        for child in children:
            if child.inline:
                if start_pos is None:
                    start_pos = child.start_pos
                    elements = []
                if not isinstance(child, Text) or child.text.strip():
                    elements.append(child)
                end_pos = child.end_pos
            else:
                if elements:
                    new_children.append(Paragraph(context.src, start_pos, end_pos, elements))
                start_pos = None
                elements = []
                new_children.append(child)
        if elements:
            new_children.append(Paragraph(context.src, start_pos, end_pos, elements))
        return new_children


class Element(BaseElement):

    inline = False

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None):
        super().__init__(src, start_pos, end_pos, children)
        self.name = name
        self.arguments = arguments

    def __str__(self):
        return f"{self.__class__.__name__}[{self.start_pos}:{self.end_pos}] name={repr(self.name)}, arguments={repr(self.arguments)}"


class ElementParser(PartsParser):

    names = None
    name_case_sensitive = False
    element_class = 'Element'
    allow_children = True

    open_parser = Exact(ELEMENT_OPEN)
    name_parser = Regex(re.compile(rf"\s*([A-Za-z0-9_]+)"))
    split_parser = Regex(re.compile(rf"\s*{esc_element_split}"))
    close_parser = Regex(re.compile(rf"\s*({esc_element_close}|$)"))
    arguments_parser = ArgumentsParser()

    def parse1(self, context):
        extra = {}
        start_pos = context.pos
        self.open_parser.parse(context)
        name = self.name_parser.parse(context).match[1]
        name = self.check_name(context, name, extra)
        extra['name'] = name
        arguments = self.arguments_parser.parse(context)
        arguments = self.check_arguments(context, arguments, extra)
        extra['arguments'] = arguments
        try:
           self.split_parser.parse(context)
        except NoMatch:
            children = []
        else:
            if not hasattr(self, '_child_parser'):
                self._child_parser = self.get_child_parser(context)
            children = self._child_parser.parse(context).children
        children = self.check_children(context, children, extra)
        self.close_parser.parse(context)
        return self.make_element(context.src, start_pos, context.pos, children, **extra)

    def get_child_parser(self, context):
        return Many(
            Any(
                VerbatimParser(),
                *context.parsers,
                TextParser(),
                NonCloseCharParser(),
            )
        )

    def get_names(self):
        if self.name_case_sensitive:
            names = [name for name in self.names]
        else:
            names = [name.lower() for name in self.names]
        return names

    def check_name(self, context, name, extra):
        if not hasattr(self, '_names'):
            self._names = self.get_names()
        n = name if self.name_case_sensitive else name.lower()
        if not n in self._names:
            raise NoMatch
        return name

    def check_arguments(self, context, arguments, extra):
        return arguments

    def check_children(self, context, children, extra):
        if children and not self.allow_children:
            raise NoMatch
        return children

    def make_element(self, src, start_pos, end_pos, children, **extra):
        return self.element_class(src, start_pos, end_pos, children, **extra)


class Document(BaseElement):

    paragraphs = True


class DocumentParser(PartsParser):

    def parse1(self, context):
        if not hasattr(self, '_child_parser'):
            self._child_parser = self.get_child_parser(context)
        chunk = self._child_parser.parse(context)
        return Document(context.src, chunk.start_pos, chunk.end_pos, chunk.children)

    def get_child_parser(self, context):
        return Many(
            Any(
                VerbatimParser(),
                *context.parsers,
                TextParser(),
                AnyCharParser(),
            )
        )


