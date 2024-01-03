

class NoMatch(Exception):
    """
    Raised by Parser.parse1() or parse2() to indicate that the element at the
    current position does not match with the parser's expected content.
    """


#=============================================================================
# Context
#=============================================================================


class ParseContext:

    def __init__(self, src, pos=0, parsers=None):
        self.src = src
        self.pos = pos
        self.parsers = parsers or []
        self.stack = []

    @property
    def end_pos(self):
        return len(self.src)

    @property
    def eof(self):
        return self.pos >= self.end_pos

    def push(self):
        self.stack.append(self.get_state())

    def pop(self, restore=False):
        state = self.stack.pop()
        if restore:
            self.set_state(state)

    def get_state(self):
        return {'pos': self.pos}

    def set_state(self, state):
        self.pos = state['pos']


#=============================================================================
# Parsed objects
#=============================================================================


class Chunk:
    """
    Elements found and returned by Parser.do_parse(), are descendants of Chunk.
    """

    def __init__(self, src, start_pos, end_pos, children=None):
        self.src = src
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.children = children
        self.depth = 0

    @property
    def raw(self):
        return self.src[self.start_pos:self.end_pos]
    
    def walk(self, func, level=0, skip=False):
        if not skip:
            func(self, level=level)
        if self.children:
            for child in self.children:
                child.walk(func, level=level+1)

    def __str__(self):
        return f"{self.__class__.__name__}[{self.start_pos}:{self.end_pos}]"


class TextChunk(Chunk):

    def __init__(self, src, start_pos, end_pos, text):
        super().__init__(src, start_pos, end_pos)
        self.text = text

    def __str__(self):
        return f"{self.__class__.__name__}[{self.start_pos}:{self.end_pos}] {repr(self.text)}"


class RegexChunk(Chunk):

    def __init__(self, src, start_pos, end_pos, match):
        super().__init__(src, start_pos, end_pos)
        self.match = match


class NullChunk(Chunk):

    def __init__(self, src, pos):
        super().__init__(src, pos, pos)


#=============================================================================
# Parsers
#=============================================================================


class Parser:

    def parse(self, context):
        context.push()
        try:
            chunk = self.parse1(context)
            chunk = self.parse2(context, chunk)
            context.pop(restore=False)
            return chunk
        except NoMatch:
            context.pop(restore=True)
            raise

    def parse1(self, context):
        raise NotImplementedError

    def parse2(self, context, chunk):
        """
        After the chunk has been successfully parsed and created, this is an
        opportunity for subsequent processing and validation, and even
        complete replacement of the chunk with some other object.
        """
        return chunk


class All(Parser):

    def __init__(self, *parsers):
        self.parsers = parsers

    def parse1(self, context):
        start_pos = context.pos
        children = [parser.parse(context) for parser in self.parsers]
        return Chunk(context.src, start_pos, context.pos, children=children)


class Any(Parser):

    def __init__(self, *parsers):
        self.parsers = parsers

    def parse1(self, context):
        for parser in self.parsers:
            try:
                return parser.parse(context)
            except NoMatch:
                pass
        raise NoMatch


class Opt(Parser):

    def __init__(self, parser):
        self.parser = parser

    def parse1(self, context):
        try:
            return self.parser.parse(context)
        except NoMatch:
            return NullChunk(context.src, context.pos)


class Many(Parser):

    def __init__(self, parser, min_count=0, max_count=None):
        self.parser = parser
        self.min_count = min_count
        self.max_count = max_count

    def parse1(self, context):
        start_pos = context.pos
        children = []
        count = 0
        last_pos = context.pos
        while True:
            if self.max_count and count >= self.max_count:
                break
            try:
                chunk = self.parser.parse(context)
            except NoMatch:
                break
            # Stop if the last chunk didn't advance current position
            # to avoid looping indefinitely
            if context.pos == last_pos:
                break
            children.append(chunk)
            count += 1
            last_pos = context.pos
        if count < self.min_count:
            raise NoMatch
        return Chunk(context, start_pos, context.pos, children=children)


class Regex(Parser):

    def __init__(self, regex):
        self.regex = regex

    def parse1(self, context, regex=None):
        start_pos = context.pos
        match = self.regex.match(context.src, pos=start_pos)
        if not match:
            raise NoMatch
        end_pos = match.end()
        context.pos = end_pos
        return RegexChunk(context, start_pos, end_pos, match)


class Exact(Parser):

    def __init__(self, text):
        self.text = text

    def parse1(self, context):
        start_pos = context.pos
        end_pos = start_pos + len(self.text)
        if context.src[start_pos:end_pos] != self.text:
            raise NoMatch
        context.pos = end_pos
        return TextChunk(context, start_pos, end_pos, self.text)


