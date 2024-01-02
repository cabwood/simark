

class NoMatch(Exception):
    """
    Raised by Parser.do_parse() to indicate that the element at the current
    position does not meet the parser's requirements. Left uncaught, this
    results in the parse context being restored to its state prior to the
    call to Parser.do_parse()
    """


#=============================================================================
# Context
#=============================================================================


class ParseContext:

    def __init__(self, src, pos=0, parent=None, parsers=None):
        self.parent = parent
        self.src = src
        self.pos = pos
        self.parent = parent
        self.parsers = parsers or []

    def __enter__(self):
        return self.copy()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        return False

    @property
    def end_pos(self):
        return len(self.src)

    @property
    def eof(self):
        return self.pos >= self.end_pos

    def copy(self):
        return ParseContext(self.src, pos=self.pos, parent=self, parsers=self.parsers)

    def commit(self):
        self.parent.pos = self.pos


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
        with context as ctx:
            chunk = self.parse1(ctx)
            chunk = self.parse2(context, chunk)
            ctx.commit()
            return chunk

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
        children = []
        for parser in self.parsers:
            chunk = parser.parse(context)
            if not chunk:
                raise NoMatch
            children.append(chunk)
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


