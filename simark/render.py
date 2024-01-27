from string import ascii_uppercase
from roman import toRoman
from .context import Stack, BaseContext


HTML_CLASS_PREFIX = 'sml_'


def num_to_alpha_upper(num):
    if num < 1:
        return '?'
    l = len(ascii_uppercase)
    n = num
    s = ''
    while n > 0:
        r = (n-1) % l
        s = ascii_uppercase[r] + s
        n = (n-r) // l
    return s

def num_to_alpha_lower(num):
    return num_to_alpha_upper(num).lower()

def num_to_roman_upper(num):
    if num < 1:
        return '?'
    return toRoman(num)

def num_to_roman_lower(num):
    return toRoman(num).lower()

list_style_funcs = {
    '1': lambda num: str(num),
    'a': num_to_alpha_lower,
    'A': num_to_alpha_upper,
    'i': num_to_roman_lower,
    'I': num_to_roman_upper,
    '.': lambda num: str(num),
    'o': lambda num: str(num),
}


class ContextVar:

    def get_value(self):
        raise NotImplementedError

    def set_value(self, value):
        raise NotImplementedError

    @property
    def value(self):
        return self.get_value()
    @value.setter
    def value(self, value):
        self.set_value(value)

    def inc_value(self):
        raise NotImplementedError


class DocVar(ContextVar):

    def __init__(self, value=''):
        self._value = value

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = value

    def inc_value(self):
        try:
            value = int(self.get_value())
        except ValueError:
            return
        self.set_value(value+1)


class EnvVar(ContextVar):

    def __init__(self, get_func, set_func, inc_func):
        self.get_func = get_func
        self.set_func = set_func
        self.inc_func = inc_func

    def get_value(self):
        return self.get_func()

    def set_value(self, value):
        if self.set_func:
            self.set_func(value)

    def inc_value(self):
        if self.inc_func:
            self.inc_func()


class SectionCounter(Stack):

    default_separator = '.'

    def __init__(self, context):
        self.context = context
        super().__init__('section', level=0, child_number=1)

    def get_separator(self):
        return self.context.get_stack('main').get('section_separator') or self.default_separator

    @property
    def level(self):
        return self.get('level')

    @property
    def number(self):
        return self.get('number')

    def get_text(self):
        return self.get_separator().join(str(n) for n in self.numbers)

    text = property(get_text)

    @property
    def child_number(self):
        return self.get('child_number')
    @child_number.setter
    def child_number(self, value):
        self.set('child_number', value)

    @property
    def numbers(self):
        # Top level has no number, so don't include it
        return [item['number'] for item in self.items[1:]]

    def enter(self, start_num=None):
        if start_num is None:
            start_num = self.child_number
        self.push(number=start_num, child_number=1, level=self.level+1)

    def exit(self):
        # Next child will be numbered consecutive to this one
        self.child_number = self.pop()['number'] + 1


class CompoundCounter:

    default_separator = '-'
    max_level = 2

    def __init__(self, context):
        self.context = context
        self.reset()

    def get_separator(self):
        return self.default_separator

    @property
    def level(self):
        # Level is determined by current section level, and capped by max_level
        return min(self.context.section_counter.level + 1, self.max_level)

    @property
    def numbers(self):
        section_numbers = self.context.section_counter.numbers[0:self.level - 1]
        return section_numbers + [self.counters[-1]]

    def get_text(self):
        return self.get_separator().join(str(n) for n in self.numbers)

    text = property(get_text)

    def resize_counters(self):
        # Resize the counter list to match the current section level
        level = self.level
        while len(self.counters) < level:
            self.counters.append(1)
        if len(self.counters) > level:
            self.counters = self.counters[0:level]

    def reset(self):
        self.counters = [1]

    def enter(self):
        self.resize_counters()

    def exit(self):
        self.counters[-1] += 1

    def inc(self):
        self.resize_counters()
        self.counters[-1] += 1


class TableCounter(CompoundCounter):

    def get_separator(self):
        return self.context.get_stack('main').get('table_separator') or self.default_separator


class FigureCounter(CompoundCounter):

    def get_separator(self):
        return self.context.get_stack('main').get('figure_separator') or self.default_separator


class ListCounter(Stack):

    default_separator = '.'

    def __init__(self, context):
        self.context = context
        super().__init__('list', level=0)

    def get_separator(self):
        return self.context.get_stack('main').get('list_separator') or self.default_separator

    @property
    def level(self):
        return self.get('level')

    @property
    def number(self):
        return self.get('number')
    @number.setter
    def number(self, value):
        self.set('number', value)

    def get_text(self):
        items = zip([list_style_funcs[style] for style in self.styles], self.numbers)
        return self.get_separator().join(f(n) for f, n in items)

    text = property(get_text)

    @property
    def numbers(self):
        # Top level has no number, so don't include it
        return [item['number'] for item in self.items[1:]]

    @property
    def style(self):
        return self.get('style')

    @property
    def styles(self):
        # Top level has no style, so don't include it
        return [item['style'] for item in self.items[1:]]

    def enter(self, style, start_num=None):
        if start_num is None:
            start_num = 1
        self.push(number=start_num, style=style, level=self.level+1)

    def exit(self):
        # Next child will be numbered consecutive to this one
        self.child_number = self.pop()['number'] + 1

    def inc(self):
        self.number += 1


class RenderContext(BaseContext):

    show_heading_numbers = True
    show_table_numbers = True
    show_figure_numbers = True

    def __init__(self, format, html_class_prefix=HTML_CLASS_PREFIX, **kwargs):
        super().__init__(**kwargs)
        self.format = format
        self.html_class_prefix = html_class_prefix
        self.section_counter = SectionCounter(self)
        self.table_counter = TableCounter(self)
        self.figure_counter = FigureCounter(self)
        self.list_counter = ListCounter(self)
        self.vars = {
            'section': EnvVar(self.section_counter.get_text, None, None),
            'table': EnvVar(self.table_counter.get_text, None, self.table_counter.inc),
            'figure': EnvVar(self.figure_counter.get_text, None, self.table_counter.inc),
            'list': EnvVar(self.list_counter.get_text, None, self.list_counter.inc),
        }

    def reset_counters(self):
        self.section_counter.reset()
        self.table_counter.reset()
        self.figure_counter.reset()
        self.list_counter.reset()

    def get_var(self, name, default=''):
        var = self.vars.get(name)
        return var.value if var else default

    def set_var(self, name, value):
        var = self.vars.get(name)
        if var:
            var.value = value
        else:
            self.vars[name] = DocVar(value)

    def inc_var(self, name):
        var = self.vars.get(name)
        if var:
            var.inc_value()


class RenderMixin:

    html_class = None

    def render(self, context):
        context.reset_counters()
        self._setup(context)
        context.reset_counters()
        return self._render(context)

    def _setup(self, context):
        stack = context.get_stack('main')
        self.parent = stack.get('parent', default=None)
        self.depth = stack.get('depth', default=0)
        self.compact = stack.get('compact', default=None)
        self.setup_enter(context)
        try:
            stack.push(parent=self, depth=self.depth+1)
            try:
                for child in self.children:
                    child._setup(context)
            finally:
                stack.pop()
        finally:
            self.setup_exit(context)

    def setup_enter(self, context):
        """Called prior to setting up children"""
        pass

    def setup_exit(self, context):
        """Called after children have been setup"""
        pass

    def _render(self, context):
        if context.format == 'plain':
            return self.render_plain(context)
        elif context.format == 'html':
            return self.render_html(context)
        raise ValueError(f'Invalid format {context.format}')

    def render_plain(self, context):
        return self.render_children_plain(context)

    def render_children_plain(self, context):
        if self.children:
            return ''.join([child.render_plain(context) for child in self.children])
        return ''

    def render_html(self, context):
        return self.render_children_html(context)

    def render_children_html(self, context):
        if self.children:
            return ''.join([child.render_html(context) for child in self.children])
        return ''

    def get_whitespace(self, context):
        indent = '' if self.compact else '  ' * self.depth
        newline = '' if self.compact else '\n'
        return indent, newline

    def get_class_attr(self, context, *classes):
        prefix = context.html_class_prefix or ""
        if classes:
            return f' class="{" ".join([f"{prefix}{c}" for c in classes])}"'
        if self.html_class:
            return f' class="{prefix}{self.html_class}"'
        return ''


