#!/usr/bin/env python

from simark import \
    VerbatimParser, \
    DocumentParser, \
    ParseContext, \
    RenderContext, \
    Paragraph, ParagraphParser, \
    FormatParser, \
    LineBreakParser, \
    HeadingParser, \
    SectionParser, \
    ListParser, \
    LinkParser, \
    GetVarParser, \
    SetVarParser, \
    IncVarParser, \
    EntityParser, \
    CodeParser, \
    ImageParser, \
    FloatParser, \
    AlignParser, \
    TableParser

block_parsers = [
    ParagraphParser(),
    HeadingParser(),
    SectionParser(),
    ListParser(),
    CodeParser(),
    FloatParser(),
    AlignParser(),
    TableParser(),
]

inline_parsers = [
    VerbatimParser(),
    FormatParser(),
    LineBreakParser(),
    LinkParser(),
    GetVarParser(),
    SetVarParser(),
    IncVarParser(),
    EntityParser(),
    ImageParser(),
]

with open('test_in.sm', 'r') as f:
    s = f.read()

parse_context = ParseContext(s,
    inline_parsers=inline_parsers,
    block_parsers=block_parsers,
    inline_group_class = Paragraph
)
document = DocumentParser().parse(parse_context)
document.walk(lambda element, level: print(f"{' '*2*level}{element}"))


render_context = RenderContext(
    html_class_prefix='sml_',
)
html_out = f'<div class="simark">\n{document.render(render_context)}\n</div>\n'

css = '<link rel="stylesheet" href="test.css">\n'

with open('test_out.html', 'w') as f:
    f.write(css + html_out)

# print(html_out)

