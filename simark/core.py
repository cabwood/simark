import re
import html
from .parse import NoMatch, Parser, Any, Many, Opt, Regex, Literal, Element, TextChunk
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

def group_chunks(chunks, member_func, group_func):
    """
    Test membership of each chunk in chunks with member_func(item).
    Replace consecutive member chunks with the object returned returned by
    group_func(members).
    """
    grouped = []
    members = []
    for chunk in chunks:
        if member_func(chunk):
            members.append(chunk)
        else:
            if members:
                grouped.append(group_func(members))
            members = []
            grouped.append(chunk)
    if members:
        grouped.append(group_func(members))
    return grouped

def promote_children(chunks, member_func):
    """
    Replace each instance of a chunk in chunks, for which member_func(chunk)
    returns true, with that chunk's own children, effectively promoting
    those children by one place in the hierarchy.
    """
    merged = []
    for chunk in chunks:
        if member_func(chunk):
            merged.extend(chunk.children)
        else:
            merged.append(chunk)
    return merged

def concatenate_text(context, chunks):
    """
    Combine contents of consecutive Text onjects into a single Text object
    """

    def cat(texts):
        text = ''.join(t.text for t in texts)
        return Text(context.src, texts[0].start_pos, texts[-1].end_pos, text=text)

    return group_chunks(chunks, lambda c: isinstance(c, BaseText), cat)


class BaseElement(RenderMixin, Element):

    inline = False

    def is_whitespace(self):
        return all(child.is_whitespace() for child in self.children)

    def parse3(self, context):

        def make_group(inlines):
            # Concatenate consecutive Text chunks, and bundle all chunks into
            # a group container of specified class
            inlines = concatenate_text(context, inlines)
            return group_class(context.src, inlines[0].start_pos, inlines[-1].end_pos, children=inlines)
          
        def keep(child):
            if not isinstance(child, group_class):
                return True
            children = child.children
            if not children:
                return False
            if len(children) == 1 and isinstance(children[0], Text) and children[0].is_whitespace():
                return False
            return True

        group_class = context.get_state('main', 'inline_group_class', InlineGroup)
        children = self.children
        # Children of Unknown elements become my own children
        children = promote_children(children, lambda c: isinstance(c, Unknown))
        # Children of inline groups become my own children
        children = promote_children(children, lambda c: isinstance(c, group_class))
        # Group and concatenate consecutive inline elements
        children = group_chunks(children, lambda c: c.inline, make_group)
        # Discard empty groups
        self.children = [child for child in children if keep(child)]


class Block(Parser):

    @classmethod
    def parse1(cls, context):
        parsers = context.get_state('main', 'block_parsers', [])
        chunk = Any.parse(context, *parsers)
        chunk.inline = False
        return chunk


class Inline(Parser):

    @classmethod
    def parse1(cls, context):
        parsers = context.get_state('main', 'inline_parsers', [])
        chunk = Any.parse(context, *parsers)
        chunk.inline = True
        return chunk


class InlineGroup(BaseElement):
    pass


class BaseText(BaseElement):

    inline = True

    re_whitespace = re.compile('\s*$')

    def __init__(self, src, start_pos, end_pos, text):
        super().__init__(src, start_pos, end_pos)
        self.text = text

    def is_whitespace(self):
        return self.re_whitespace.match(self.text)

    def render_self(self, context):
        class_attr = self.get_class_attr(context)
        html_out = html.escape(self.text)
        return f'<span{class_attr}>{html_out}</span>' if class_attr else html_out

    def __str__(self):
        return f"{self.__class__.__name__}[{self.start_pos}:{self.end_pos}] {repr(self.text)}"


class Text(BaseText):

    pattern = re.compile(rf"(\\\\|\\`|\\{esc_element_open}|\\{esc_element_close}|[^`{esc_element_open}{esc_element_close}])+")

    @classmethod
    def parse1(cls, context):
        match = Regex.parse(context, cls.pattern).match
        return Text(context.src, match.start(0), match.end(0), unescape(match[0],
            ESC_BACKSLASH,
            ESC_BACKTICK,
            ESC_ELEMENT_OPEN,
            ESC_ELEMENT_CLOSE,
        ))


class Verbatim(Parser):

    parser = Regex(re.compile(r"(`+)(.+?)\1", re.DOTALL))
                          # Non-greedy ^

    @classmethod
    def parse1(cls, context):
        match = cls.parser.parse(context).match
        return Text(context.src, match.start(2), match.end(2), match[2])


class Unknown(BaseElement):

    open_parser = Literal(ELEMENT_OPEN)
    close_parser = Opt(Literal(ELEMENT_CLOSE))

    @classmethod
    def parse1(cls, context):
        start_pos = context.pos
        cls.open_parser.parse(context)
        children = Parts.parse(context).children
        cls.close_parser.parse(context)
        return Unknown(context.src, start_pos=start_pos, end_pos=context.pos, children=children)


class Parts(Parser):

    parser = \
        Many(
            Any(
                Verbatim,
                Block,
                Inline,
                Unknown,
                Text,
            )
        )

    @classmethod
    def parse1(cls, context):
        return cls.parser.parse(context)


class DoubleQuotedParser(Parser):
    
    pattern = re.compile(r'\s*"((?:\\\\|\\"|[^"])*)"')

    @classmethod
    def parse1(cls, context):
        match = Regex.parse(context, cls.pattern).match
        return TextChunk(context.src, match.start(1), match.end(1), unescape(match[1],
            ESC_BACKSLASH,
            ESC_DOUBLE_QUOTE
        ))


class SingleQuotedParser(Parser):
    
    pattern = re.compile(r"\s*'((?:\\\\|\\'|[^'])*)'")

    @classmethod
    def parse1(cls, context):
        match = Regex.parse(context, cls.pattern).match
        return TextChunk(context.src, match.start(1), match.end(1), unescape(match[1],
            ESC_BACKSLASH,
            ESC_SINGLE_QUOTE
        ))


class UnquotedParser(Parser):
    
    pattern = re.compile(rf"""\s*((?:\\"|\\'\\{esc_element_close}|\\{esc_element_split}|[^\s{esc_element_close}{esc_element_split}])*)\s*""")

    @classmethod
    def parse1(cls, context):
        match = Regex.parse(context, cls.pattern).match
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
        DoubleQuotedParser,
        SingleQuotedParser,
        UnquotedParser,
    )

    @classmethod
    def parse1(cls, context):
        start_pos = context.pos
        try:
            name = cls.name_parser.parse(context).match[1].lower()
        except NoMatch:
            name = None
        value = cls.value_parser.parse(context).text
        return Argument(context.src, start_pos, context.pos, name, value)


class Argument(Element):

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

class Arguments(Element):

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
        return {name: values[-1] for name, values in self.by_name.items()}


class ArgumentsParser(Parser):

    parser = Many(ArgumentParser)

    @classmethod
    def parse1(cls, context):
        arg_chunks = cls.parser.parse(context).children
        return Arguments(arg_chunks)


class Element(BaseElement):

    names = None
    name_case_sensitive = False
    allow_children = True

    open_parser = Literal(ELEMENT_OPEN)
    name_parser = Regex(r'\s*([A-Za-z0-9_]+)')
    split_parser = Regex(rf'\s*{esc_element_split}')
    close_parser = Regex(rf'\s*({esc_element_close}|$)')
    arguments_parser = ArgumentsParser
    child_parser = Parts

    def __init__(self, src, start_pos, end_pos, children=None, name=None, arguments=None):
        super().__init__(src, start_pos, end_pos, children)
        self.name = name
        self.arguments = arguments

    @classmethod
    def parse1(cls, context):
        start_pos = context.pos
        cls.open_parser.parse(context)
        arguments = {}
        name = cls.parse_name(context, arguments)
        arguments['name'] = name
        arguments = cls.parse_arguments(context, arguments) or arguments
        try:
           cls.split_parser.parse(context)
        except NoMatch:
            children = []
        else:
            children = cls.parse_children(context, arguments)
        arguments['children'] = children
        cls.close_parser.parse(context)
        return cls.make_element(context.src, start_pos, context.pos, **arguments)

    @classmethod
    def parse_name(cls, context, arguments):
        name = cls.name_parser.parse(context).match[1]
        if not hasattr(cls, '_names'):
            cls._names = cls.get_names()
        n = name if cls.name_case_sensitive else name.lower()
        if not n in cls._names:
            raise NoMatch
        return name

    @classmethod
    def parse_arguments(cls, context, arguments):
        arguments.update(cls.arguments_parser.parse(context).get_as_dict())
        return arguments

    @classmethod
    def parse_children(cls, context, arguments):
        children = cls.get_child_parser(context).parse(context).children
        if children and not cls.allow_children:
            raise NoMatch
        return children

    @classmethod
    def get_child_parser(cls, context):
        return cls.child_parser

    @classmethod
    def get_names(cls):
        if cls.name_case_sensitive:
            names = [name for name in cls.names]
        else:
            names = [name.lower() for name in cls.names]
        return names

    @classmethod
    def make_element(cls, src, start_pos, end_pos, **arguments):
        return cls(src, start_pos, end_pos, **arguments)

    def __str__(self):
        return f"{self.__class__.__name__}[{self.start_pos}:{self.end_pos}]"


class Document(BaseElement):

    @classmethod
    def parse1(cls, context):
        parts = Parts.parse(context)
        return Document(context.src, parts.start_pos, parts.end_pos, parts.children)


