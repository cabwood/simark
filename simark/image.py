import re
import html
from .parse import NoMatch
from .core import Element, ElementParser


image_sizes = {
    'auto': None,
    'tiny': 60,
    'small': 120,
    'medium': 240,
    'large': 480,
    'huge': 960,
}


class Image(Element):

    def __init__(self, src, start_pos, end_pos, children, name=None, arguments=None, \
                 url=None, size_mode=None, size_value=None, show_numbers=None, show_caption=None, inline=None):
        super().__init__(src, start_pos, end_pos, children, name, arguments)
        self.url = url
        self.size_mode = size_mode
        self.size_value = size_value
        self.show_numbers = show_numbers
        self.show_caption = show_caption
        self.inline = inline

    def before_child_setup(self, context):
        context.begin_figure()

    def after_child_setup(self, context):
        context.end_figure()

    def setup(self, context):
        self.numbers = context.figure_numbers

    def render_self(self, context):
        src_attr = f' src="{self.url}"'
        if self.size_mode == 'name':
            width = image_sizes[self.size_value]
            width_style = f' style="width: {width}px;"' if width else ''
        else:
            if self.size_mode == 'abs':
                width_style = f' style="width: {self.size_value}px;"'
            else:
                # Relative sizing
                width_style = f' style="width: {self.size_value}vw;"'
        caption_html = ''
        if self.show_caption:
            caption_html = self.render_children(context)
            if self.show_numbers:
                caption_html = f'Fig. {html.escape(self.numbers)}. {caption_html}'
            caption_html = caption_html.strip()
            if caption_html:
                caption_html = f'<figcaption{width_style}>{caption_html}</figcaption>'
        img_html = f'<img{src_attr}{width_style}>'
        indent, newline = self.get_whitespace()
        return f'{indent}<figure>{img_html}{caption_html}</figure>{newline}'


class ImageParser(ElementParser):

    names = ['image']
    element_class = Image
    re_size_name = re.compile(f'\s*({"|".join(image_sizes.keys())})\s*$')
    re_size_abs = re.compile(r'\s*(\d+)\s*(?:px)?$')
    re_size_rel = re.compile(r'\s*(\d+)\s*\%$')

    def check_arguments(self, context, arguments, extra):
        url = arguments.get('url', 0)
        if not url:
            raise NoMatch
        extra['url'] = url
        size = arguments.get('size', default='')
        match = self.re_size_name.match(size)
        if match:
            extra['size_mode'] = 'name'
            extra['size_value'] = match[1]
        else:
            match = self.re_size_abs.match(size)
            if match:
                extra['size_mode'] = 'abs'
                extra['size_value'] = match[1]
            else:
                match = self.re_size_rel.match(size)
                if match:
                    extra['size_mode'] = 'rel'
                    extra['size_value'] = match[1]
                else:
                    extra['size_mode'] = 'name'
                    extra['size_value'] = 'auto'
        extra['show_numbers'] = arguments.get_bool('numbers', default=True)
        extra['show_caption'] = arguments.get_bool('caption', default=True)
        extra['inline'] = arguments.get_bool('inline', default=False)
        return arguments

