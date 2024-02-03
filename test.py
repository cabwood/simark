#!/usr/bin/env python

from simark.parse import ParseContext, Parser, All, Any, Exact

class P(Parser):

    def __init__(self, text):
        super().__init__(text)

    @classmethod
    def parse1(cls, context, text):
        return Exact.parse(context, text)


context = ParseContext('abc')

chunk = All.parse(context, Exact('a'), Exact('b'))

chunk.walk(lambda element, level: print(f"{' '*2*level}{element}"))
