import re
import functools
from typing import List


class Context:

    def __init__(self, src, root_symbols=None):
        self.src = src
        self.pos = 0
        self.expected = None
        self.last_phrase_pos = None
        self.symbols = []
        self.push_symbols(root_symbols)

    def seek(self, pos):
        self.pos = max(0, min(pos, len(self.src)))

    def eof(self):
        return self.pos >= len(self.src)

    def eol(self):
        return self.eof() or self.src[self.pos] == '\n'

    def push_symbols(self, symbols=None):
        self.symbols.append(dict() if symbols is None else symbols)

    def pop_symbols(self):
        self.symbols.pop()

    def get_symbol(self, key: str, inherit=True, default=None):
        lower_key = key.lower()
        if inherit:
            for frame in reversed(self.symbols):
                if lower_key in frame:
                    return frame[lower_key]
            return default
        else:
            frame = self.symbols[-1]
            if lower_key in frame:
                return frame[lower_key]
            return default
        
    def get_int_symbol(self, key: str, inherit=True, default=None):
        try:
            value = self.get_symbol(key, inherit=inherit)
            return default if value is None else int(str(value))
        except (ValueError, TypeError):
            return default

    def set_symbol(self, key: str, value):
        self.symbols[-1][key.lower()] = value


class Match:

    def __init__(self, context: Context, start_pos: int, end_pos: int, **kwargs):
        self.context = context
        self.start_pos = start_pos
        self.end_pos = end_pos
        for k, v in kwargs:
            setattr(self, k, v)

    def __str__(self):
        return self.context.src[self.start_pos:self.end_pos]

    def __repr__(self):
        return f"{self.__class__.__name__} {str(self)!r}"

    def __bool__(self):
        return self.start_pos > self.end_pos


class NoMatch(Match):

    def __init__(self, context: Context, **kwargs):
        super().__init__(context, context.pos, context.pos, **kwargs)

    def __bool__(self):
        return False


def peek(context: Context, matcher, *args, **kwargs):
    start_pos = context.pos
    try:
        return matcher(context, *args, **kwargs)
    finally:
        context.pos = start_pos

def advance(context: Context, count=1):
    start_pos = context.pos
    end_pos = start_pos + count
    if end_pos > len(context.src):
        return NoMatch(context)
    context.seek(end_pos)
    return Match(context, start_pos, end_pos)

ws_regex = re.compile(r"[^\S\n]*")
ws_nl_regex = re.compile(r"\s*")

def match_ws(context: Context, newlines=False):
    start_pos = context.pos
    pattern = ws_nl_regex if newlines else ws_regex
    re_match = pattern.match(context.src, pos=start_pos)
    end_pos = re_match.end()
    context.seek(end_pos)
    return Match(context, start_pos, end_pos)

def match_literal(context: Context, literal: str, case_sensitive: bool=True):
    start_pos = context.pos
    end_pos = start_pos + len(literal)
    source = context.src[start_pos:end_pos]
    equal = source == literal if case_sensitive else source.lower() == literal.lower()
    if equal:
        context.pos = end_pos
        return Match(context, start_pos, end_pos)
    return NoMatch(context)


class RegexMatch(Match):

    def __init__(self, context: Context, start_pos: int, end_pos: int, re_match: re.Match):
        super().__init__(context, start_pos, end_pos)
        self.re_match = re_match

    def __bool__(self):
        return self.re_match is not None

    def __getitem__(self, key):
        start_pos, end_pos = self.re_match.span(key)
        return Match(self.context, start_pos, end_pos)


def match_regex(context: Context, pattern: re.Pattern):
    start_pos = context.pos
    re_match = pattern.match(context.src, pos=start_pos)
    if re_match:
        end_pos = re_match.end()
        context.seek(end_pos)
        return RegexMatch(context, start_pos, end_pos, re_match=re_match)
    return NoMatch(context)


#=============================================================================
# Core entities
#=============================================================================

class Entity:

    def __repr__(self):
        return self.__class__.__name__

    def walk(self, func, level=0, skip=False):
        if not skip:
            func(self, level=level)

    @staticmethod
    def read(context: Context):
        raise NotImplementedError()

    def call(self):
        return self


class Group(Entity):

    def __init__(self, children: list[Entity]):
        self.children = children

    # def append(self, entity):
    #     self.children.append(entity)

    def walk(self, func, level=0, skip=False):
        super().walk(func, level=level, skip=skip)
        if self.children:
            for child in self.children:
                child.walk(func, level=level+1)

    def call(self, context: Context):
        return ''.join([child.call(context) for child in self.children])


class Text(Entity):

    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return f"{self.__class__.__name__}({self.text!r})"

    regex = re.compile(r"[^~\\`\{\}\[\]\|\n]+")

    @staticmethod
    def read(context: Context):
        match = match_regex(context, Text.regex)
        if match:
            return Text(str(match[0]))
        return None

    def call(self, context: Context):
        return self.text


class Escape(Text):

    regex = re.compile(r"\\([\\\[\]{}|`])")

    @staticmethod
    def read(context: Context):
        match = match_regex(context, Escape.regex)
        if match:
            return Escape(str(match[1]))
        return None


class Nbsp(Text):

    def __init__(self):
        super().__init__('\u00A0')

    regex = re.compile(r"[^\S\n]*\\_[^\S\n]*")

    @staticmethod
    def read(context: Context):
        match = match_regex(context, Nbsp.regex)
        if match:
            return Nbsp()
        return None


class VerbatimMatch(Match):

    def __init__(self, context: Context, start_pos: int, end_pos: int, content, delim):
        super().__init__(context, start_pos, end_pos)
        self.content = content
        self.delim = delim


class Verbatim(Text):

    def __init__(self, text, delim):
        super().__init__(text)
        self.delim = delim

    @staticmethod
    def read(context: Context):
        match = Verbatim.match(context)
        if match:
            return Verbatim(str(match.content), str(match.delim))
        return None

    delim_regex = re.compile(r"`+")
    content_regex = re.compile(r"[^`]+")

    @staticmethod
    def match(context: Context):
        start_pos = context.pos
        delim_match = match_regex(context, Verbatim.delim_regex)
        if not delim_match:
            return NoMatch(context)
        delim_str = str(delim_match)
        content_pos = context.pos
        while not context.eof():
            match_regex(context, Verbatim.content_regex)
            close_pos = context.pos
            if match_literal(context, delim_str):
                # Closing delimiter was consumed, end of verbatim
                return VerbatimMatch(context, start_pos, context.pos,
                        Match(context, content_pos, close_pos),
                        Match(context, start_pos, content_pos))
            # Subsequent '`' characters are not part of a closing delimiter,
            # so should be consumed as content
            match_regex(context, Verbatim.delim_regex)
        context.seek(start_pos)
        return NoMatch(context)


class Error(Entity):

    def __init__(self, pos, message, content=None):
        self.pos = pos
        self.message = message
        self.content = content

    def __repr__(self):
        return f"{self.__class__.__name__}({self.message!r})"

    def walk(self, func, level=0, skip=False):
        super().walk(func, level=level, skip=skip)
        if self.content is not None:
            self.content.walk(func, level=level+1)


class Nest(Group):

    @staticmethod
    def read(context: Context):
        start_pos = context.pos
        if not match_literal(context, '{'):
            return None
        saved_expected = context.expected
        try:
            # Prevent other readers from consuming our closing '}'
            context.expected = '}'
            saved_last_phrase_pos = context.last_phrase_pos
            blocks = []
            while True:
                block = Block.read(context)
                if block is None:
                    break
                blocks.append(block)
            if match_literal(context, '}'):
                return Nest(blocks)
            # No closing brace found, so this is not a valid nest
            # Restore context state
            context.pos = start_pos
            context.last_phrase_pos = saved_last_phrase_pos
            return None
        finally:
            # Always restore expected
            context.expected = saved_expected


class Block(Group):

    sep_regex = re.compile(r"([^\S\n]*(\n|\Z))*")

    @staticmethod
    def read(context: Context):
        start_pos = context.pos
        match_regex(context, Block.sep_regex)
        lines = []
        while True:
            line = Line.read(context)
            if line is None:
                break
            lines.append(line)
        if len(lines) == 0:
            context.pos = start_pos
            return None
        match_regex(context, Block.sep_regex)
        return Block(lines)


class Line(Group):

    term_regex = re.compile(r"\n")

    @staticmethod
    def read(context: Context):
        start_pos = context.pos
        phrases = []
        while True:
            phrase = Phrase.read(context)
            if phrase is None:
                break
            phrases.append(phrase)
        # Even an empty line will contain an empty phrase, but we require the
        # line to have substance to be considered truly non-empty. If there
        # no position advancement, then the line is empty.
        if context.pos == start_pos:
            # No advancement, line is empty
            return None
        match_regex(context, Line.term_regex)
        return Line(phrases)


class Phrase(Group):

    sep_regex = re.compile(r"\|")

    def read(context: Context):
        # Empty phrases are permitted, but if an empty phrase is read without
        # a subsequent '|' separator, there would be no position advancement,
        # leading to infinite looping. In such a case it is assumed that this
        # was the last phrase, and its position is recorded in context as
        # last_phrase_pos. If position has not advanced since then, there's
        # no phrase to read.
        if context.pos == context.last_phrase_pos:
            # This phrase was already consumed
            return None
        units = []
        while not context.eof():
            unit = Unit.read(context)
            if unit is None:
                break
            units.append(unit)
        if not match_regex(context, Phrase.sep_regex):
            # No separator, this is the last phrase
            context.last_phrase_pos = context.pos
        return Phrase(units)


class Raw(Text):
        
    special_chars = '`\\[{]}'

    @staticmethod
    def read_until(context, terminator):
        match = Raw.match_until(context, terminator)
        return Raw(context.src[match.start_pos:match.end_pos])

    @staticmethod
    def match_until(context: Context, terminator):

        # Memoize regex compilation for frequently used terminators
        @functools.cache
        def make_term_pattern(terminator):
            if terminator:
                return re.compile(f"[{re.escape(Raw.special_chars)}]|{re.escape(terminator)}")
            return re.compile(f"[{re.escape(Raw.special_chars)}]")

        def match_bracketed(context: Context, opener: str, closer: str):
            start_pos = context.pos
            if not match_literal(context, opener):
                return NoMatch(context)
            match_content(context, closer)
            if not match_literal(context, closer):
                context.seek(start_pos)
                return NoMatch(context)
            return Match(context, start_pos, context.pos)

        def match_non_term(context: Context, term_pattern: re.Pattern):
            start_pos = context.pos
            re_match = term_pattern.search(context.src, pos=start_pos)
            end_pos = re_match.start() if re_match else len(context.src)
            if end_pos == start_pos:
                return NoMatch(context)
            context.seek(end_pos)
            return Match(context, start_pos, end_pos)

        def match_content(context: Context, terminator):
            start_pos = context.pos
            term_pattern = make_term_pattern(terminator)
            while not context.eof():
                if terminator and peek(context, match_literal, terminator):
                    # The terminator has been found, stop here.
                    break
                # Try to consume escape '\' with the next character
                if match_literal(context, '\\'):
                    advance(context)
                    continue
                # Try to consume a verbatim block
                if Verbatim.match(context):
                    continue
                # Try to consume a nested [...] segment. Inside this segment
                # the supplied terminator can be ignored.
                if match_bracketed(context, '[', ']'):
                    continue
                # Try to consume a nested [...] segment. Inside this segment
                # the supplied terminator can be ignored.
                if match_bracketed(context, '{', '}'):
                    continue
                # Consume regular text, halting at anything special
                if match_non_term(context, term_pattern):
                    continue
                # If no text consumed, we must be at a special char not yet
                # handled, such as ']' or '}'. Consume a single character to
                # make progress.
                advance(context)
            return Match(context, start_pos, context.pos)

        return match_content(context, terminator)


class Macro(Entity):

    def __init__(self, name, args=None):
        self. name = name
        self.args = {} if args is None else args

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name!r})"

    ident_regex = re.compile(r"[a-zA-Z_][a-zA-Z0-9_.]*")
    arg_assign_regex = re.compile(r"[^\S\n]*=")
    arg_sep_regex = re.compile(r"\s*\|")

    @staticmethod
    def read(context):

        def read_name(context: Context):
            match = match_regex(context, Macro.ident_regex)
            if match:
                return str(match)
            return None

        def read_expr(context: Context):
            units = []
            while True:
                unit = Unit.read(context)
                if not unit:
                    break
                units.append(unit)
            count = len(units)
            # Empty expr is fine
            if count == 0:
                return Text("")
            if count == 1:
                return units[0]
            return Group(units)

        def read_one_arg(context: Context):
            start_pos = context.pos
            name = read_name(context)
            if name is None:
                return None
            if not match_regex(context, Macro.arg_assign_regex):
                context.pos = start_pos
                return None
            expr = read_expr(context)
            if not expr:
                context.pos = start_pos
                return None
            return (name, expr)

        def read_many_args(context: Context):
            args = []
            while True:
                arg = read_one_arg(context)
                if not arg:
                    break
                args.append(arg)
                match_regex(context, Macro.arg_sep_regex)
            return args

        def read_args(context: Context):
            match_ws(context)
            if not match_literal(context, '['):
                # Missing argument block means no arguments, not an error
                return {}
            match_ws(context)
            saved_expected = context.expected
            try:
                context.expected = ']'
                args = read_many_args(context)
                match_ws(context)
                if match_literal(context, ']'):
                    return {name: expr for name, expr in args}
                return None
            finally:
                context.expected = saved_expected

        start_pos = context.pos
        exec = match_literal(context, '\\')
        if not exec:
            if not match_literal(context, '~'):
                return None
        name = read_name(context)
        if name is None:
            context.pos = start_pos
            return None
        args = read_args(context)
        if args is None:
            context.pos = start_pos
            return None
        macro = Macro(name, args)
        if exec:
            return macro.call(context)
        return macro

    def call(self, context: Context):
        target = context.get_symbol(self.name)
        if target is None:
            return Error(context.pos, f"{self.name} not found")
        context.push_symbols(self.args)
        try:
            return target.call(context)
        finally:
            context.pop_symbols()


class Unit(Entity):

    def read_unexpected(context: Context):
        # Phrase separator is always expected
        if peek(context, match_literal, '|'):
            return None
        if context.expected is not None:
            if peek(context, match_literal, context.expected):
                return None
        match = advance(context)
        if match:
            return Error(context.pos, "Unexpected", Text(str(match)))
        return None

    readers = [
        Text.read,
        Escape.read,
        Nbsp.read,
        Verbatim.read,
        Macro.read,
        Nest.read,
        read_unexpected,
    ]

    @staticmethod
    def read(context: Context):
        for reader in Unit.readers:
            unit = reader(context)
            if unit:
                return unit


class Param(Macro):

    def call(self, context):
        return Macro(self.name, self.args)


class Document(Group):

    @staticmethod
    def read(context: Context):
        blocks = []
        while True:
            block = Block.read(context)
            if block is None:
                break
            blocks.append(block)
        return Document(blocks)

#=============================================================================


class Bold(Entity):

    def call(self, context: Context):
        value = context.get_symbol("content", default=Text(""))
        return Text(f"<b>{value.call(context)}</b>")

class Italic(Entity):

    def call(self, context: Context):
        value = context.get_symbol("content", default=Text(""))
        return Text(f"<i>{value.call(context)}</i>")


def print_entity(entity, level):
    print(f"{level * '  '}{repr(entity)}")


def test1():
    src = """~c[content=yes|x=1]"""
    src = """{B}"""
    sym = {"b": Bold(), "i": Italic()}
    ctx = Context(src, root_symbols=sym)
    doc = Nest.read(ctx)
    if doc is None:
        print("No match")
    else:
        doc.walk(print_entity)
    print(f"Remaining: {ctx.src[ctx.pos:]!r}")

if __name__ == "__main__":
    test1()

