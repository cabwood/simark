#!/usr/bin/env python

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
    GetVarParser, \
    SetVarParser, \
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
    GetVarParser(),
    SetVarParser(),
    IncrementParser(),
    EntityParser(),
    CodeParser(),
    ImageParser(),
    FloatParser(),
    BlockParser(),
    TableParser(),
    UnknownParser(),
]

with open('test_in.sm', 'r') as f:
    s = f.read()

parse_context = ParseContext(s, parsers=parsers)
document = DocumentParser().parse(parse_context)
# document.walk(lambda element, level: print(f"{' '*4*level}{element}"))


render_context = RenderContext('html')
html_out = f'<div class="simark">\n{document.render(render_context)}\n</div>\n'

css = '<link rel="stylesheet" href="test.css">\n'

with open('test_out.html', 'w') as f:
    f.write(css + html_out)

# print(html_out)

