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

with open('test_in.sm', 'r') as f:
    s = f.read()

parse_context = ParseContext(s, parsers=parsers)
document = DocumentParser().parse(parse_context)
document.walk(lambda element, level: print(f"{' '*4*level}{element}"))

render_context = RenderContext('html')
html_out = f'<div class="simark">\n{document.render(render_context)}\n</div>\n'

style_out = """
<style>
    .simark {
        font-family: Helvetica, sans-serif;
    }
    .simark_title {
        text-align: center;
    }
    .simark table {
        caption-side: bottom;
        border-collapse: collapse;
        border: thin solid black;
        margin: 0.2em 0.4em 0.2em 0.4em;
    }
    .simark tr {
        border-top: thin solid black;
    }
    .simark th, .simark td {
        padding: 0.2em 0.4em 0.2em 0.4em;
    }
    .simark table>caption, .simark figcaption {
        margin-top: 0.4em;
        font-style: italic;
        font-size: 0.85rem;
    }
    .simark figure {
        display: inline-table;
        margin: 0.2em 0.4em 0.2em 0.4em;
    }
    .simark figcaption {
        display: table-caption;
        caption-side: bottom;
        text-align: center;
    }
</style>

"""

with open('test_out.html', 'w') as f:
    f.write(style_out + html_out)

# print(html_out)

