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


re_whitespace = re.compile(r'\s+')


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
        html_out = html.escape(re.sub(re_whitespace, ' ', self.text))
        return f'<span{class_attr}>{html_out}</span>' if class_attr else html_out

    def __str__(self):
        return f"{self.__class__.__name__}[{self.start_pos}:{self.end_pos}] {repr(self.text)}"


class TextParser(Parser):

    parser = Regex(rf"(\\\\|\\`|\\{esc_element_open}|\\{esc_element_close}|[^`{esc_element_open}{esc_element_close}])+")

    def parse1(self, context):
        match = self.parser.parse(context).match
        return Text(context.src, match.start(0), match.end(0), unescape(match[0],
            ESC_BACKSLASH,
            ESC_BACKTICK,
            ESC_ELEMENT_OPEN,
            ESC_ELEMENT_CLOSE,
        ))


class Paragraph(BaseElement):

    def before_child_setup(self, context):
        # Render children compact
        context.compact = True

    def render_html(self, context):
        indent, newline = self.get_whitespace()
        return f'{indent}<p>{self.render_children_html(context)}</p>{newline}'


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

    parser = Regex(rf"\\\\|\\`|\\{esc_element_open}|\\{esc_element_close}|[^{esc_element_close}]")

    def parse1(self, context):
        match = self.parser.parse(context).match
        return Text(context.src, match.start(0), match.end(0), unescape(match[0],
            ESC_BACKSLASH,
            ESC_BACKTICK,
            ESC_ELEMENT_OPEN,
            ESC_ELEMENT_CLOSE,
        ))


class DoubleQuotedParser(Parser):
    
    parser = Regex(r'\s*"((?:\\\\|\\"|[^"])*)"')

    def parse1(self, context):
        match = self.parser.parse(context).match
        return TextChunk(context.src, match.start(1), match.end(1), unescape(match[1],
            ESC_BACKSLASH,
            ESC_DOUBLE_QUOTE
        ))


class SingleQuotedParser(Parser):
    
    parser = Regex(r"\s*'((?:\\\\|\\'|[^'])*)'")

    def parse1(self, context):
        match = self.parser.parse(context).match
        return TextChunk(context.src, match.start(1), match.end(1), unescape(match[1],
            ESC_BACKSLASH,
            ESC_SINGLE_QUOTE
        ))


class UnquotedParser(Parser):
    
    parser = Regex(rf"""\s*((?:\\"|\\'\\{esc_element_close}|\\{esc_element_split}|[^\s{esc_element_close}{esc_element_split}])*)\s*""")

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

    name_parser = Regex(rf"\s*([A-Za-z0-9_]+)\s*=")
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

class Arguments:

    # This class doesn't need to descend from Chunk, because arguments won't
    # be rendered (even though they affect rendered output), and do not need
    # to be children of their parent element.

    def __init__(self, arg_chunks=None):
        self.by_name = {}
        self.by_pos = []
        if arg_chunks:
            for arg_chunk in arg_chunks:
                self.append(arg_chunk.name, arg_chunk.value)

    def update(self, arguments):
        # Update named arguments with values from another Arguments object
        self.by_name.update(arguments.by_name)

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

    def get_as_dict(self):
        return {name: values[-1] if values else None for name, values in self.by_name}

    def __str__(self):
        args = [str(value) for value in self.by_pos]
        args.extend([f'{name}={value}' for name, value in self.by_name.items()])
        return f'({", ".join(args)})'


class ArgumentsParser(Parser):

    parser = Many(ArgumentParser())

    def parse1(self, context):
        start_pos = context.pos
        arg_chunks = self.parser.parse(context).children
        return Arguments(arg_chunks)


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
        texts = []
        for child in children:
            if isinstance(child, Text):
                if start_pos is None:
                    start_pos = child.start_pos
                    texts = []
                texts.append(child.text.strip())
                end_pos = child.end_pos
            else:
                if texts:
                    new_children.append(Text(context.src, start_pos, end_pos, ' '.join(texts)))
                start_pos = None
                texts = []
                new_children.append(child)
        if texts:
            new_children.append(Text(context.src, start_pos, end_pos, ' '.join(texts)))
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

    def __init__(self, src, start_pos, end_pos, children=None, name=None, arguments=None):
        super().__init__(src, start_pos, end_pos, children)
        self.name = name
        self.arguments = arguments

    def __str__(self):
        return f"{self.__class__.__name__}[{self.start_pos}:{self.end_pos}]{self.arguments}"


class ElementParser(PartsParser):

    names = None
    name_case_sensitive = False
    element_class = 'Element'
    allow_children = True

    open_parser = Exact(ELEMENT_OPEN)
    name_parser = Regex(r'\s*([A-Za-z0-9_]+)')
    split_parser = Regex(rf'\s*{esc_element_split}')
    close_parser = Regex(rf'\s*({esc_element_close}|$)')
    arguments_parser = ArgumentsParser()

    def parse1(self, context):
        start_pos = context.pos
        self.open_parser.parse(context)
        arguments = {}
        name = self.parse_name(context, arguments)
        arguments['name'] = name
        arguments = self.parse_arguments(context, arguments) or arguments
        try:
           self.split_parser.parse(context)
        except NoMatch:
            children = []
        else:
            children = self.parse_children(context, arguments)
        arguments['children'] = children
        self.close_parser.parse(context)
        return self.make_element(context.src, start_pos, context.pos, **arguments)

    def parse_name(self, context, arguments):
        name = self.name_parser.parse(context).match[1]
        if not hasattr(self, '_names'):
            self._names = self.get_names()
        n = name if self.name_case_sensitive else name.lower()
        if not n in self._names:
            raise NoMatch
        return name

    def parse_arguments(self, context, arguments):
        args_dict = self.arguments_parser.parse(context).get_as_dict()
        arguments.update(self.arguments_parser.parse(context).get_as_dict())
        return arguments

    def parse_children(self, context, arguments):
        children = self.get_child_parser(context).parse(context).children
        if children and not self.allow_children:
            raise NoMatch
        return children

    def get_child_parser(self, context):
        if not hasattr(self, '_child_parser'):
            self._child_parser = Many(
                Any(
                    VerbatimParser(),
                    *context.state.get('parsers', []),
                    TextParser(),
                    NonCloseCharParser(),
                )
            )
        return self._child_parser

    def get_names(self):
        if self.name_case_sensitive:
            names = [name for name in self.names]
        else:
            names = [name.lower() for name in self.names]
        return names

    def make_element(self, src, start_pos, end_pos, **arguments):
        return self.element_class(src, start_pos, end_pos, **arguments)


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
                *context.state.get('parsers', []),
                TextParser(),
                AnyCharParser(),
            )
        )


