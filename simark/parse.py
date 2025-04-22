from __future__ import annotations
from typing import Callable, Any
import re
import functools
from collections import UserDict

class Context:

    def __init__(self, src, builtins: dict[str, tuple[Entity, dict[str, Entity] | None]] | None = None) -> None:
        self.src: str = src
        self.pos: int = 0
        self.expected: str = None
        self.last_phrase_pos: bool = None
        self.local_bindings: list[dict[str, Binding]] = [{}]
        self.global_bindings: list[dict[str, Binding]] = [{}]
        self.global_depth: int = 1
        if builtins:
            root_globals = self.global_bindings[0]
            for name, (value, defaults) in builtins.items():
                binding = Binding(name, value, defaults, is_local=False)
                root_globals[name.lower()] = binding 

    def seek(self, pos):
        self.pos = max(0, min(pos, len(self.src)))

    def eof(self):
        return self.pos >= len(self.src)

    def eol(self):
        return self.eof() or self.src[self.pos] == '\n'

    def push_local_bindings(self, bindings: dict[str, Binding] | None = None):
        frame = {}
        if bindings:
            frame.update(bindings)
        self.local_bindings.append(frame)

    def pop_local_bindings(self):
        if len(self.local_bindings) == 1:
            raise RuntimeError("Cannot pop root bindings")
        self.local_bindings.pop()

    def push_global_bindings(self):
        # Global bindings is a pseudo-stack, that can only have one or two
        # frames. If there are aleady two frames, then don't push another.
        if self.global_depth < 2:
            self.global_bindings.append({})
        # Pseudo stack depth must track pushes and pops as if they always
        # occurred, regardless of actual stack depth.
        self.global_depth += 1

    def pop_global_bindings(self):
        if self.global_depth == 1:
            raise RuntimeError("Cannot pop root bindings")
        if self.global_depth == 2:
            self.global_bindings.pop()
        self.global_depth -= 1

    def get(self, name: str, default=None) -> Binding | None:
        key = name.lower()
        for frame in reversed(self.local_bindings):
            if key in frame:
                return frame[key]
        for frame in reversed(self.global_bindings):
            if key in frame:
                return frame[key]
        return default

    def set_local(self, binding: Binding):
        self.local_bindings[-1][binding.name.lower()] = binding

    def set_global(self, binding: Binding):
        self.global_bindings[-1][binding.name.lower()] = binding

    def add_builtin(self, name: str, value: Entity, defaults: dict[str, Entity] | None = None):
        binding = Binding(name, value, defaults, is_local=False)
        self.set_global(binding)


def rollback_no_match(matcher):
    @functools.wraps(matcher)
    def wrapper(context: Context, *args, **kwargs):
        start_pos = context.pos
        saved_last_phrase_pos = context.last_phrase_pos
        saved_expected = context.expected
        result = matcher(context, *args, **kwargs)
        if result is None:
            context.pos = start_pos
            context.last_phrase_pos = saved_last_phrase_pos
        # Always restored expected element
        context.expected = saved_expected
        return result
    return wrapper


class Match:

    def __init__(self, context: Context, start_pos: int, end_pos: int, **kwargs) -> None:
        self.context = context
        self.start_pos = start_pos
        self.end_pos = end_pos
        for k, v in kwargs:
            setattr(self, k, v)

    def __str__(self):
        return self.context.src[self.start_pos:self.end_pos]

    def __repr__(self):
        return f"{self.__class__.__name__} {str(self)!r}"


def peek(context: Context, matcher, *args, **kwargs):
    saved_pos = context.pos
    saved_last_phrase_pos = context.last_phrase_pos
    saved_expected = context.expected
    try:
        return matcher(context, *args, **kwargs)
    finally:
        context.pos = saved_pos
        context.last_phrase_pos = saved_last_phrase_pos
        context.expected = saved_expected

def match_advance(context: Context, count=1):
    start_pos = context.pos
    end_pos = start_pos + count
    if end_pos > len(context.src):
        return None
    context.pos = end_pos
    return Match(context, start_pos, end_pos)

ws_regex = re.compile(r"[^\S\n]+")
ws_nl_regex = re.compile(r"\s+")

def match_whitespace(context: Context, newlines=False):
    start_pos = context.pos
    pattern = ws_nl_regex if newlines else ws_regex
    re_match = pattern.match(context.src, pos=start_pos)
    if not re_match:
        return None
    end_pos = re_match.end()
    context.pos = end_pos
    return Match(context, start_pos, end_pos)

def match_literal(context: Context, literal: str, case_sensitive: bool=True):
    start_pos = context.pos
    end_pos = start_pos + len(literal)
    source = context.src[start_pos:end_pos]
    equal = source == literal if case_sensitive else source.lower() == literal.lower()
    if equal:
        context.pos = end_pos
        return Match(context, start_pos, end_pos)
    return None


class RegexMatch(Match):

    def __init__(self, context: Context, start_pos: int, end_pos: int, re_match: re.Match) -> None:
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
        context.pos = end_pos
        return RegexMatch(context, start_pos, end_pos, re_match=re_match)
    return None


identifier_regex = re.compile(r"[a-zA-Z_][a-zA-Z0-9_.]*")

def read_identifier(context):
    match = match_regex(context, identifier_regex)
    if not match:
        return None
    return str(match)


@rollback_no_match
def read_until(context: Context, reader: Callable,
                term: str, *args: Any, **kwargs: Any) -> list[Any] | None:
    """Accumulates elements returned by repeated calls to function `reader`,
    until that reader fails to return an element. Requires terminator `term`
    to be present after the elements.

    Args:
        context: The parsing context object.
        reader: A callable that returns a parsed element (or None if no
            element could be read at the current position). Any additional
            *args and **kwargs are passed to this reader.
        term: A literal string that *must* be present following the sequence
            of retrieved elements.
        *args: Additional positional arguments passed to `reader`.
        **kwargs: Additional keyword arguments passed to `reader`.

    Returns:
        A list containing the elements successfully read by `reader` (which
        may be empty), or None if the terminator `term` was not present.
    """
    # Prevent other readers from consuming our terminator
    context.expected = term
    contents = []
    while True:
        last_pos = context.pos
        content = reader(context, *args, **kwargs)
        if content is None:
            break
        contents.append(content)
        if context.pos == last_pos:
            # No position advance, break to avoid infinite looping
            break
    if match_literal(context, term):
        return contents
    return None


@rollback_no_match
def read_many(context: Context, reader: Callable, *args, **kwargs):
    """Accumulates elements returned by repeated calls to function `reader`,
    until that reader returns None.

    Args:
        context: The parsing context object.
        reader: A callable that returns a parsed element (or None if no
            element could be read at the current position). Any additional
            *args and **kwargs are passed to this reader.
        *args: Additional positional arguments passed to `reader`.
        **kwargs: Additional keyword arguments passed to `reader`.

    Returns:
        A list containing the elements successfully read by `reader` (which
        may be empty).
    """
    contents = []
    while True:
        last_pos = context.pos
        content = reader(context, *args, **kwargs)
        if content is None:
            break
        contents.append(content)
        if context.pos == last_pos:
            # No position advance, break to avoid infinite looping
            break
    return contents


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

    def call(self, context: Context):
        raise NotImplementedError()


class Null(Entity):

    def call(self, context):
        return self


class Group(Entity):

    def __init__(self, children: list[Entity]) -> None:
        self.children = children

    def walk(self, func, level=0, skip=False):
        super().walk(func, level=level, skip=skip)
        if self.children:
            for child in self.children:
                child.walk(func, level=level+1)

    def call(self, context: Context):
        return self.__class__([child.call(context) for child in self.children])


class Text(Entity):

    def __init__(self, text) -> None:
        self.text = text

    def __repr__(self):
        return f"{self.__class__.__name__}({self.text!r})"

    regex = re.compile(r"[^~\\`\^\{\}\[\]\|\n]+")

    @staticmethod
    def read(context: Context):
        match = match_regex(context, Text.regex)
        if match:
            return Text(str(match[0]))
        return None

    def call(self, context: Context):
        return self


class Escape(Text):

    regex = re.compile(r"\\([\\\[\]{}|`\^])")

    @staticmethod
    def read(context: Context):
        match = match_regex(context, Escape.regex)
        if match:
            return Escape(str(match[1]))
        return None


class Nbsp(Text):

    def __init__(self) -> None:
        super().__init__('\u00A0')

    regex = re.compile(r"[^\S\n]*\\_[^\S\n]*")

    @staticmethod
    def read(context: Context):
        match = match_regex(context, Nbsp.regex)
        if match:
            return Nbsp()
        return None


class VerbatimMatch(Match):

    def __init__(self, context: Context, start_pos: int, end_pos: int, content_match, delim_match) -> None:
        super().__init__(context, start_pos, end_pos)
        self.content_match = content_match
        self.delim_match = delim_match


class Verbatim(Text):

    def __init__(self, text, delim) -> None:
        super().__init__(text)
        self.delim = delim

    @staticmethod
    def read(context: Context):
        match = Verbatim.match(context)
        if match:
            return Verbatim(str(match.content_match), str(match.delim_match))
        return None

    delim_regex = re.compile(r"`+")
    content_regex = re.compile(r"[^`]+")

    @staticmethod
    def match(context: Context):
        start_pos = context.pos
        delim_match = match_regex(context, Verbatim.delim_regex)
        if not delim_match:
            return None
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
            # so should be consumed as content. Coincidentally this uses the
            # same regex as the one that extracted delim_str above, but this
            # next operation serves a very different purpose.
            match_regex(context, Verbatim.delim_regex)
        context.pos = start_pos
        return None


class Error(Entity):

    def __init__(self, message: str, content: Entity | None=None) -> None:
        super().__init__()
        self.message = message
        self.content = content

    def __repr__(self):
        return f"{self.__class__.__name__}({self.message!r})"

    def walk(self, func, level=0, skip=False):
        super().walk(func, level=level, skip=skip)
        if self.content is not None:
            self.content.walk(func, level=level+1)

    def call(self, context: Context):
        return self


class Nest(Group):

    @staticmethod
    @rollback_no_match
    def read(context: Context):
        if not match_literal(context, '{'):
            return None
        blocks = read_until(context, Block.read, '}')
        if blocks is None:
            return None
        return Nest(blocks)


class Block(Group):

    sep_regex = re.compile(r"([^\S\n]*(\n|\Z))*")

    @staticmethod
    @rollback_no_match
    def read(context: Context):
        match_regex(context, Block.sep_regex)
        lines = read_many(context, Line.read)
        if len(lines) == 0:
            return None
        # Consume whitespace, ready for the next Block.read
        match_regex(context, Block.sep_regex)
        return Block(lines)


class Line(Group):

    term_regex = re.compile(r"\n")

    @staticmethod
    @rollback_no_match
    def read(context: Context):
        start_pos = context.pos
        phrases = read_many(context, Phrase.read)
        # An empty line is technically a single empty phrase, so we require
        # the line to have substance to be considered non-empty.
        if context.pos == start_pos:
            # There was no position advancement, line was not substantial.
            return None
        # Consume line terminator, ready for the next Line.read
        match_regex(context, Line.term_regex)
        return Line(phrases)


class Phrase(Group):

    sep_regex = re.compile(r"\|")

    @staticmethod
    @rollback_no_match
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
        units = read_many(context, Unit.read)
        # Consume phrase separator, ready for the next Phrase.read
        if not match_regex(context, Phrase.sep_regex):
            # No separator, this is the last phrase in the line
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
                return None
            match_content(context, closer)
            if not match_literal(context, closer):
                context.pos = start_pos
                return None
            return Match(context, start_pos, context.pos)

        def match_non_term(context: Context, term_pattern: re.Pattern):
            start_pos = context.pos
            re_match = term_pattern.search(context.src, pos=start_pos)
            end_pos = re_match.start() if re_match else len(context.src)
            if end_pos == start_pos:
                return None
            context.pos = end_pos
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
                    match_advance(context)
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
                match_advance(context)
            return Match(context, start_pos, context.pos)

        return match_content(context, terminator)


class Binding:
    """Represents an association between some namespace entity and any default
    bindings it shall apply when invoked.
    """

    def __init__(self, name: str, value: Entity, defaults: list[Binding] | None, is_local) -> None:
        super().__init__()
        self.name = name.lower()
        self.value = value
        self.defaults = defaults
        self.is_local = is_local

    def __repr__(self):
         return f"{self.__class__.__name__}({self.name}={self.value!r})"

    def walk(self, func, level=0, skip=False):
        if not skip:
            func(self, level=level)
        if self.defaults:
            for binding in self.defaults:
                binding.walk(func, level=level+1)

    equal_regex = re.compile(r"[^\S\n]*=[^\S\n]*")

    @staticmethod
    @rollback_no_match
    def read(context: Context, allow_defaults: bool, is_local: bool) -> Binding:
        match_whitespace(context, newlines=True)
        # Retrieve the binding name
        name = read_identifier(context)
        if name is None:
            return None
        defaults = None
        if allow_defaults:
            # Retrieve optional default values
            match_whitespace(context)
            # Changes to global bindings during evaluation of a default's
            # value should not persist, but should be visible to entities
            # in the value expression. Push a tempoary global frame to be
            # popped once default evaluations are complete.
            context.push_global_bindings()
            try:
                defaults = read_bindings_between(context, '[', ']', allow_defaults=False, is_local=True)
            finally:
                context.pop_global_bindings()
        # Require '=', with optional whitespace either side
        if not match_regex(context, Binding.equal_regex):
            return None
        # Any bindings, global or local, established during evaluation of the
        # right-hand-side expression must be visible to entities within that
        # expression, but must not persist thereafter.
        context.push_global_bindings()
        context.push_local_bindings()
        try:
            # Retrieve right-hand-side expression, a sequence of units
            units = read_many(context, Unit.read)
        finally:
            context.pop_global_bindings()
            context.pop_local_bindings()
        # Munge the expression terms down to a single entity
        count = len(units)
        if count == 0:
            # Empty expression
            value = Null()
        elif count == 1:
            # A single expression term can be used as-is
            value = units[0]
        else:
            # Multiple expression terms must be grouped
            value = Group(units)
        binding = Binding(name, value, defaults, is_local)
        return binding

    def apply(self, context: Context):
        if self.is_local:
            context.set_local(self)
        else:
            context.set_global(self)


binding_sep_regex = re.compile(r"\s*\|\s*|[^\S\n]*\n\s*")

@rollback_no_match
def read_bindings_between(context: Context, opener: str, closer: str, allow_defaults: bool, is_local: bool) -> list[Binding]:

    def read_binding_with_sep(context: Context, allow_defaults: bool):
        binding = Binding.read(context, allow_defaults, is_local)
        # Always immediately apply bindings as they are encountered
        if binding is not None:
            binding.apply(context)
            match_regex(context, binding_sep_regex)
        return binding

    if not match_literal(context, opener):
        return None
    bindings = read_until(context, read_binding_with_sep, closer, allow_defaults)
    return bindings


class _Bindings(Entity):

    def __init__(self, bindings: list[Binding]):
        self.bindings = bindings

    def walk(self, func, level=0, skip=False):
        super().walk(func, level=level, skip=skip)
        if self.bindings:
            for binding in self.bindings:
                binding.walk(func, level=level+1)

    def call(self, context):
        for binding in self.bindings:
            binding.apply(context)


class LocalBindings(_Bindings):

    @staticmethod
    def read(context):
        bindings = read_bindings_between(context, '[', ']', allow_defaults=True, is_local=True)
        if bindings is None:
            return None
        return LocalBindings(bindings)


class GlobalBindings(_Bindings):

    @staticmethod
    def read(context):
        bindings = read_bindings_between(context, '[[', ']]', allow_defaults=True, is_local=False)
        if bindings is None:
            return None
        return GlobalBindings(bindings)


class Ref(Entity):

    def __init__(self, name: str, arguments: list[Binding] | None) -> None:
        self.name = name
        self.arguments = arguments

    def __repr__(self):
        if self.arguments:
            return f"Ref({self.name}[{self.arguments!r}])"
        return f"{self.__class__.__name__}({self.name})"

    @staticmethod
    @rollback_no_match
    def read(context: Context, with_prefix: bool=True) -> Ref:
        if with_prefix:
            if not match_literal(context, '~'):
                return None
        name = read_identifier(context)
        if name is None:
            return None
        match_whitespace(context)
        arguments = read_bindings_between(context, '[', ']', allow_defaults=False, is_local=True)
        match_whitespace(context)
        return Ref(name, arguments)
    
    def call(self, context: Context):
        target_binding = context.get(self.name)
        if not target_binding:
            return Error("Not found", Raw(self.name))
        # Prepare bindings for the calling scope
        call_bindings: dict[str, Binding] = {}
        # Add default bindings first
        if target_binding.defaults:
            for default in target_binding.defaults:
                call_bindings[default.name.lower()] = default
        # Evaluate call-time arguments in the *current* context and add them,
        # potentially overwriting defaults.
        if self.arguments:
            for argument in self.arguments:
                # Crucial to avoid recursion: evaluate the argument's value
                # before creating the binding for the new scope
                arg_value = argument.value.call(context)
                call_bindings[argument.name.lower()] = Binding(argument.name, arg_value, None, True)
        # Push new local scope with defaults and evaluated arguments
        context.push_local_bindings(call_bindings)
        try:
            result = target_binding.value.call(context)
        finally:
            context.pop_local_bindings()

        return result


class Call(Entity):

    def __init__(self, name: str, arguments: list[Binding] | None, result: Entity) -> None:
        self.name = name
        self.arguments = arguments
        self.result = result

    def __repr__(self):
        if self.arguments:
            return f"Call({self.name}[{self.arguments!r}])"
        return f"{self.__class__.__name__}({self.name})"

    def walk(self, func, level=0, skip=False):
        super().walk(func, level=level, skip=skip)
        self.result.walk(func, level=level+1)

    @staticmethod
    @rollback_no_match
    def read(context: Context):
        if not match_literal(context, '\\'):
            return None
        ref = Ref.read(context, False)
        if not ref:
            return None
        result = ref.call(context)
        return Call(ref.name, ref.arguments, result)

    def call(self, context: Context):
        return self.result


class Annotation(Entity):

    def __init__(self, name: str, value: Entity):
        self.name = name
        self.value = value

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name}={self.value!r})"

    equal_regex = re.compile(r"[^\S\n]*=[^\S\n]*")
    value_regex = re.compile(r"[^~\\`\^\{\}\[\]\|\s]+")

    @staticmethod
    @rollback_no_match
    def read(context: Context):
        if not match_literal(context, '^'):
            return None
        name = read_identifier(context)
        if name is None:
            return None
        if not match_regex(context, Annotation.equal_regex):
            return Annotation(name, Null())
        verbatim = Verbatim.read(context)
        if verbatim:
            return Annotation(name, Text(verbatim.text))
        text_match = match_regex(context, Annotation.value_regex)
        if text_match:
            return Annotation(name, Text(str(text_match)))
        return Annotation(name, Text(""))
        

class Unit(Entity):

    term_regex = re.compile(r"\||\n")
    open_regex = re.compile(r"\{|\[")

    def read_other(context: Context):
        if peek(context, match_regex, Unit.term_regex):
            return None
        if context.expected is not None:
            if peek(context, match_literal, context.expected):
                return None
        match = match_regex(context, Unit.open_regex)
        if match:
            return Error("Unmatched", Raw(str(match)))
        match = match_advance(context)
        if match:
            return Error("Unexpected", Raw(str(match)))
        return None

    readers = [
        Text.read,
        Escape.read,
        Nbsp.read,
        Verbatim.read,
        Ref.read,
        Call.read,
        Nest.read,
        GlobalBindings.read,
        LocalBindings.read,
        Annotation.read,
        read_other,
    ]

    @staticmethod
    def read(context: Context):
        for reader in Unit.readers:
            unit = reader(context)
            if unit:
                return unit


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


def print_entity(entity, level):
    print(f"{level * '  '}{entity!r}")


class PhraseMacro(Entity):

    def call(self, context: Context):
        phrase = Phrase.read(context)
        if phrase is None:
            return Null()
        return phrase
        

def test1():
    from table import Cell

    src = """^rowspan=2^irrelevant=hello^colspan=1 cell 1 | cell 2 | cell 3"""

    builtins = {
        "phrase": (PhraseMacro(), None),
    }

    ctx = Context(src, builtins)
    doc = Cell.read(ctx)
    if doc is None:
        print("No match")
    else:
        doc.walk(print_entity)
    print(f"Remaining: {ctx.src[ctx.pos:]!r}")

if __name__ == "__main__":
    test1()

