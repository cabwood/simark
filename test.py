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

parser = _RowShortParser()

src = """a | b | c """

context = ParseContext(src, parsers=parsers)

chunk = parser.parse(context)

chunk.walk(lambda element, level: print(f"{' '*4*level}{element}"))

