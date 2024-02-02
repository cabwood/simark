#!/usr/bin/env python
import re
from simark.parse import ParseContext, Parser, Many, parse_regex, parse_many
from simark.core import Text, BaseElement, BaseElementParser

context = ParseContext('   ')

class CharParser(Parser):

    char_pattern = re.compile(r'.')

    def parse1(self, context):
        chunk = parse_regex(context, self.char_pattern)
        return Text(context.src, chunk.start_pos, chunk.end_pos, text=chunk.match[0])

class TestElement(BaseElement):
    pass

class TestParser(BaseElementParser):

    parser = Many(CharParser(), min_count=1)

    def parse1(self, context):
        children = self.parser.parse(context).children
        return TestElement(context.src, children[0].start_pos, children[-1].end_pos, children=children)


chunk = TestParser().parse(context)

chunk.walk(lambda chunk, level: print(f"{' '*2*level}{chunk}"))

print(chunk.is_whitespace())