from string import ascii_uppercase
from roman import toRoman

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


class RenderContext:

    show_heading_numbers = True
    show_table_numbers = True
    show_figure_numbers = True

    def __init__(self, format, compact=False, html_class_prefix=HTML_CLASS_PREFIX):
        self.format = format
        self.compact = compact
        self.html_class_prefix = html_class_prefix
        self.stack = []
        self.vars = {
            'section': EnvVar(self.get_section_numbers, None, self.inc_section),
            'list': EnvVar(self.get_list_numbers, None, self.inc_list),
            'table': EnvVar(self.get_table_numbers, None, self.inc_table),
            'figure': EnvVar(self.get_figure_numbers, None, self.inc_figure),
        }
        self.reset_counters()
        self.chunk_parent = None
        self.chunk_depth = 0

    def push(self):
        self.stack.append(self.get_state())

    def pop(self, restore=True):
        state = self.stack.pop()
        if restore:
            self.set_state(state)

    def get_state(self):
        return {
            'compact': self.compact,
            'chunk_parent': self.chunk_parent,
            'chunk_depth': self.chunk_depth,
        }

    def set_state(self, state):
        self.compact = state['compact']
        self.chunk_parent = state['chunk_parent']
        self.chunk_depth = state['chunk_depth']

    def reset_counters(self):
        self.reset_section()
        self.reset_list()
        self.reset_table()
        self.reset_figure()

    #=========================================================================

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

    #=========================================================================

    def reset_section(self):
        self.section_counts = [0]

    def begin_section(self, start_num=None):
        # Set the value of the current counter, then push a new one.
        if start_num is not None:
            self.section_counts[-1] = start_num
        else:
            self.inc_section()
        self.section_counts.append(0)
        # Table and figure counters reset with each new level 1 section
        level = self.get_section_level()
        if level == 1:
            self.table_counts[1] = 0
            self.figure_counts[1] = 0

    def end_section(self):
        # Don't delete root counter
        if len(self.section_counts) > 1:
            del self.section_counts[-1]

    def inc_section(self):
        self.section_counts[-1] += 1

    def get_section_level(self):
        return len(self.section_counts) - 1

    def get_section_numbers(self):
        # Don't show last counter, which is for children of the current section.
        return '.'.join(str(count) for count in self.section_counts[0:-1])

    @property
    def section_level(self):
        return self.get_section_level()

    @property
    def section_numbers(self):
        return self.get_section_numbers()

    #=========================================================================

    def reset_list(self):
        self.list_counts = []
        self.list_styles = []

    def begin_list(self, style, start_num=1):
        self.list_counts.append(start_num)
        self.list_styles.append(style)
        
    def end_list(self):
        if self.list_counts:
            del self.list_counts[-1]
            del self.list_styles[-1]

    def inc_list(self):
        if self.list_counts:
            self.list_counts[-1] += 1

    def get_list_numbers(self):
        return '.'.join(list_style_funcs[style](count) for count, style in zip(self.list_counts, self.list_styles))

    @property
    def list_numbers(self):
        return self.get_list_numbers()

    #=========================================================================

    def reset_table(self):
        self.table_counts = [0, 0]

    def begin_table(self, start_num=None):
        if start_num is not None:
            level = self.get_section_level()
            if level > 1:
                level = 1
            self.table_counts[level] = start_num
        else:
            self.inc_table()

    def end_table(self):
        pass

    def inc_table(self):
        level = self.get_section_level()
        if level > 1:
            level = 1
        self.table_counts[level] += 1

    def get_table_numbers(self):
        if self.section_level == 0:
            return str(self.table_counts[0])
        return f'{self.section_counts[0]}.{self.table_counts[1]}'

    @property
    def table_numbers(self):
        return self.get_table_numbers()
    
    #=========================================================================

    def reset_figure(self):
        self.figure_counts = [0, 0]

    def begin_figure(self, start_num=None):
        if start_num is not None:
            level = self.get_section_level()
            if level > 1:
                level = 1
            self.figure_counts[level] = start_num
        else:
            self.inc_figure()

    def end_figure(self):
        pass

    def inc_figure(self):
        level = self.get_section_level()
        if level > 1:
            level = 1
        self.figure_counts[level] += 1

    def get_figure_numbers(self):
        if self.section_level == 0:
            return str(self.figure_counts[0])
        return f'{self.section_counts[0]}.{self.figure_counts[1]}'

    @property
    def figure_numbers(self):
        return self.get_figure_numbers()


class RenderMixin:

    html_class = None

    def render(self, context):
        context.reset_counters()
        self._setup(context)
        context.reset_counters()
        return self._render(context)

    def _setup(self, context):
        self.parent = context.chunk_parent
        self.depth = context.chunk_depth
        self.compact = context.compact
        context.push()
        try:
            self.before_child_setup(context)
            if self.children:
                context.chunk_parent = self
                context.chunk_depth += 1
                for child in self.children:
                    child._setup(context)
            self.after_child_setup(context)
            self.setup(context)
        finally:
            context.pop()

    def before_child_setup(self, context):
        pass

    def after_child_setup(self, context):
        pass

    def setup(self, context):
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

    def get_whitespace(self):
        indent = '' if self.compact else ' ' * 2 * self.depth
        newline = '' if self.compact else '\n'
        return indent, newline 

    def get_class_attr(self, context, *classes):
        prefix = context.html_class_prefix or ""
        if classes:
            return f' class="{" ".join([f"{prefix}{c}" for c in classes])}"'
        if self.html_class:
            return f' class="{prefix}{self.html_class}"'
        return ''


