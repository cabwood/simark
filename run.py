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

with open('test_sml.sml', 'r') as f:
    s = f.read()

parse_context = ParseContext(s, parsers=parsers)
document = DocumentParser().parse(parse_context)
document.walk(lambda element, level: print(f"{' '*4*level}{element}"))

render_context = RenderContext('html')
html_out = f'<div class="sml">{document.render(render_context)}</div>'

style_out = """
<style>
    .sml {
        font-family: Helvetica, sans-serif;
    }
    .sml_title {
        text-align: center;
    }
    .sml table {
        caption-side: bottom;
        border-collapse: collapse;
        border: thin solid black;
        margin: 0.2em 0.4em 0.2em 0.4em;
    }
    .sml tr {
        border-top: thin solid black;
    }
    .sml th, .sml td {
        padding: 0.2em 0.4em 0.2em 0.4em;
    }
    .sml table>caption, .sml figcaption {
        margin-top: 0.4em;
        font-style: italic;
        font-size: 0.85rem;
    }
    .sml figure {
        display: inline-table;
        margin: 0.2em 0.4em 0.2em 0.4em;
    }
    .sml figcaption {
        display: table-caption;
        caption-side: bottom;
        text-align: center;
    }
</style>
"""

with open('test_sml.html', 'w') as f:
    f.write(style_out + html_out)

# print(html_out)

