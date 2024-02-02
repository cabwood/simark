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

    def __init__(self, context, level_change_func=None):
        self.context = context
        self.level_change_func = level_change_func
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
        new_level = self.level+1
        self.push(number=start_num, child_number=1, level=new_level)
        # Notify context of level change, so it can notify other counters
        if self.level_change_func:
            self.level_change_func(new_level)

    def exit(self):
        # Next child will be numbered consecutive to this one
        self.child_number = self.pop()['number'] + 1
        # Notify context of level change, so it can notify other counters
        if self.level_change_func:
            self.level_change_func(self.level)


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
        return len(self.counters)

    @property
    def number(self):
        return self.counters[-1]
    @number.setter
    def number(self, value):
        self.counters[-1] = value

    def get_text(self):
        if self.max_level == 1:
            return str(self.number)
        section_numbers = self.context.section_counter.numbers[0:self.level - 1]
        section_separator = self.context.section_counter.get_separator()
        section_text = section_separator.join(str(n) for n in section_numbers)
        return f'{section_text}{self.get_separator()}{self.number}'

    text = property(get_text)

    def section_level_changed(self, section_level):
        # Resize the counter list to match the current section level
        level = min(section_level + 1, self.max_level)
        while len(self.counters) < level:
            self.counters.append(1)
        while len(self.counters) > level:
            self.counters.pop()

    def reset(self):
        self.counters = [1]

    def enter(self):
        pass

    def exit(self):
        self.inc()

    def inc(self):
        self.number += 1


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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.section_counter = SectionCounter(self, level_change_func=self.section_level_changed)
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

    def get_var(self, name):
        var = self.vars.get(name)
        if var:
            return var.value
        return None

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

    def section_level_changed(self, level):
        # Notify other counters that a section was entered or exited
        self.table_counter.section_level_changed(level)
        self.figure_counter.section_level_changed(level)


class RenderMixin:

    html_class = None

    def render(self, context):
        context.reset_counters()
        self._setup(context)
        context.reset_counters()
        return self.render_self(context)

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

    def render_self(self, context):
        return self.render_children(context)

    def render_children(self, context):
        if self.children:
            return ''.join([child.render_self(context) for child in self.children])
        return ''

    def get_whitespace(self, context):
        indent = '' if self.compact else '  ' * self.depth
        newline = '' if self.compact else '\n'
        return indent, newline

    def get_class_attr(self, context, *classes):
        prefix = context.get_stack('main').get('html_class_prefix', '')
        if classes:
            return f' class="{" ".join([f"{prefix}{c}" for c in classes])}"'
        if self.html_class:
            return f' class="{prefix}{self.html_class}"'
        return ''


