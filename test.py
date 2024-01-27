#!/usr/bin/env python

from simark.parse import *
from simark.table import *

from simark import \
    DocumentParser, \
    ParseContext, \
    RenderContext, \
    UnknownParser, \
    FormatParser, \
    LineBreakParser, \
    ParagraphBreakParser, \
    HeadingParser, \
    SectionParser, \
    ListParser, \
    LinkParser, \
    ReferenceParser, \
    DefineParser, \
    IncrementParser, \
    EntityParser, \
    CodeParser, \
    ImageParser, \
    FloatParser, \
    BlockParser, \
    TableParser

parsers = [
    FormatParser(),
    LineBreakParser(),
    ParagraphBreakParser(),
    HeadingParser(),
    SectionParser(),
    ListParser(),
    LinkParser(),
    ReferenceParser(),
    DefineParser(),
    IncrementParser(),
    EntityParser(),
    CodeParser(),
    ImageParser(),
    FloatParser(),
    BlockParser(),
    TableParser(),
    UnknownParser(),
]

# parser = _RowShortParser()

# src = """a | b | c """

# context = ParseContext(src, parsers=parsers)

# chunk = parser.parse(context)

# chunk.walk(lambda element, level: print(f"{' '*4*level}{element}"))

from simark.render import SectionCounter
s = SectionCounter(None)
print(s.numbers)
s.enter(start_num=5)
print(s.numbers)
s.enter() ; print(s.numbers) ; s.exit()
print(s.numbers)
s.enter() ; print(s.numbers) ; print(s.text) ; s.exit()
s.enter() ; print(s.numbers) ; s.exit()
s.enter() ; print(s.numbers) ; s.exit()
print(s.numbers)
s.exit()
print(s.numbers)
s.enter() ; print(s.numbers)
s.enter() ; print(s.numbers) ; s.exit()
s.enter() ; print(s.numbers) ; s.exit()
s.exit()
print(s.numbers)
