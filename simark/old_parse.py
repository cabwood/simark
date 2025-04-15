import re
from typing import Any
from .context import BaseContext


class NoMatch(Exception):
    """
    Raised during parsing to indicate that the element at the current position
    does not match with expected content.
    """


#=============================================================================
# Context
#=============================================================================


class ParseContext(BaseContext):

    def __init__(self, src, pos=0, **kwargs):
        super().__init__(**kwargs)
        self.src = src
        self.pos = pos

    @property
    def end_pos(self):
        return len(self.src)

    @property
    def eof(self):
        return self.pos >= self.end_pos


#=============================================================================
# Parsers
#=============================================================================


class Parser:

    def __init__(self, *args, **kwargs):
        # Method parse() starts life as a class method, that invokes parse1()
        # with its own args and kwargs. Monkey-patch parse() so it becomes an
        # an instance method that instead calls parse1 with arguments provided
        # here, during initialiasation. Record arguments to be passed later on
        # to parse1.
        self.parse = self.parse_inst
        self.args = args
        self.kwargs = kwargs

    @classmethod
    def parse(cls, context, *args, **kwargs):
        return cls._parse(context, *args, **kwargs)

    def parse_inst(self, context):
        return self._parse(context, *self.args, **self.kwargs)

    @classmethod
    def _parse(cls, context, *args, **kwargs):
        pos = context.pos
        try:
            chunk = cls.parse1(context, *args, **kwargs)
            chunk = cls.parse2(context, chunk)
            chunk.parse3(context)
            return chunk
        except NoMatch:
            context.pos = pos
            raise

    @classmethod
    def parse1(cls, context, *args, **kwargs):
        raise NotImplementedError

    @classmethod
    def parse2(cls, context, chunk):
        """
        After the chunk has been successfully parsed and created, this is an
        opportunity for subsequent processing and validation, and even
        complete replacement of the chunk with some other object.
        """
        return chunk


class Leave(Parser):
    """
    Parse the chunk but don't consume it
    """

    def __init__(self, parser):
        super().__init__(parser)

    @classmethod
    def parse1(cls, context, parser):
        pos = context.pos
        chunk = parser.parse(context)
        context.pos = pos
        return chunk


class All(Parser):

    def __init__(self, *parsers):
        super().__init__(*parsers)

    @classmethod
    def parse1(self, context, *parsers):
        start_pos = context.pos
        children = [parser.parse(context) for parser in parsers]
        return Chunk(context.src, start_pos, context.pos, children=children)


class Any(Parser):

    def __init__(self, *parsers):
        super().__init__(*parsers)

    @classmethod
    def parse1(self, context, *parsers):
        for parser in parsers:
            try:
                return parser.parse(context)
            except NoMatch:
                pass
        raise NoMatch


class Opt(Parser):

    def __init__(self, parser):
        super().__init__(parser)

    @classmethod
    def parse1(self, context, parser):
        try:
            return parser.parse(context)
        except NoMatch:
            return NullChunk(context.src, context.pos)


class Many(Parser):

    def __init__(self, parser, min_count=0, max_count=None):
        super().__init__(parser, min_count=min_count, max_count=max_count)

    @classmethod
    def parse1(self, context, parser, min_count=0, max_count=None):
        start_pos = context.pos
        chunks = []
        count = 0
        last_pos = context.pos
        while True:
            if max_count and count >= max_count:
                break
            try:
                chunk = parser.parse(context)
            except NoMatch:
                break
            # Stop if the last chunk didn't advance current position
            # to avoid looping indefinitely
            if context.pos == last_pos:
                break
            chunks.append(chunk)
            count += 1
            last_pos = context.pos
        if count < min_count:
            raise NoMatch
        return Chunk(context.src, start_pos, context.pos, children=chunks)


class Regex(Parser):

    def __init__(self, pattern):
        super().__init__(pattern if isinstance(pattern, re.Pattern) else re.compile(pattern, re.MULTILINE))

    @classmethod
    def parse1(self, context, pattern):
        start_pos = context.pos
        match = pattern.match(context.src, pos=start_pos)
        if not match:
            raise NoMatch
        end_pos = match.end()
        context.pos = end_pos
        return RegexChunk(context.src, start_pos, end_pos, match)


class Exact(Parser):

    def __init__(self, text):
        super().__init__(text)

    @classmethod
    def parse1(self, context, text):
        start_pos = context.pos
        end_pos = start_pos + len(text)
        if context.src[start_pos:end_pos] != text:
            raise NoMatch
        context.pos = end_pos
        return TextChunk(context.src, start_pos, end_pos, text)


#=============================================================================
# Parsed objects
#=============================================================================


class Chunk(Parser):
    """
    Elements found and returned by a parser object or function are descendants
    of Chunk.
    """

    def __init__(self, src, start_pos, end_pos, children=None):
        super().__init__()
        self.src = src
        self.start_pos = start_pos
        self.end_pos = end_pos
        self._children = children
        self.depth = 0

    def parse3(self, context):
        """
        The last opportunity for the chunk to validate and organise itself prior
        to rendering, or whatever comes next.
        """
        pass

    @property
    def raw(self):
        return self.src[self.start_pos:self.end_pos]
    
    def walk(self, func, level=0, skip=False):
        if not skip:
            func(self, level=level)
        if self.children:
            for child in self.children:
                child.walk(func, level=level+1)

    def get_children(self):
        if self._children is None:
            self._children = []
        return self._children

    def set_children(self, children):
        self._children = children

    @property
    def children(self):
        return self.get_children()
    @children.setter
    def children(self, children):
        self.set_children(children)

    @property
    def __str_prefix__(self):
        return f'{self.__class__.__name__}[{self.start_pos}:{self.end_pos}]'

    def __str__(self):
        return self.__str_prefix__


class TextChunk(Chunk):

    def __init__(self, src, start_pos, end_pos, text):
        super().__init__(src, start_pos, end_pos)
        self.text = text

    def __str__(self):
        return f"{self.__str_prefix__} {repr(self.text)}"


class RegexChunk(Chunk):

    def __init__(self, src, start_pos, end_pos, match):
        super().__init__(src, start_pos, end_pos)
        self.match = match

    def __str__(self):
        return f"{self.__str_prefix__} {repr(self.match[0])}"


class NullChunk(Chunk):

    def __init__(self, src, pos):
        super().__init__(src, pos, pos)


