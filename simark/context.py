"""
Implementation of a simple LIFO stack that uses dictionaries to store state
information, and a context object that employs this stack to keep track of
its current state.
"""

class Stack:

    def __init__(self, name, **kwargs):
        self.name = name
        self.items = [kwargs]
        self.reset()

    def reset(self):
        # Keep only initial state
        self.items = self.items[:1]

    @property
    def top(self):
        return self.items[-1]

    def get(self, name, default=None):
        return self.top.get(name, default)

    def set(self, name, value):
        self.top[name] = value

    def push(self, **kwargs):
        # Top dictionary is a shallow copy of the dictionary underneath it,
        # updated with new or additional key/value pairs from kwargs.
        # Don't modify mutable members, like lists, since they are shared
        # by all stack entries, and they'll all be changed.
        item = self.top.copy()
        item.update(kwargs)
        self.items.append(item)

    def pop(self):
        # Can't pop bottom item
        if len(self.items) == 1:
            raise ValueError(f"Illegal pop of empty stack {repr(self.name)}")
        return self.items.pop()


class BaseContext:

    def __init__(self, **kwargs):
        self.stacks = {'main': Stack('main', **kwargs)}

    def get_stack(self, stack_name):
        stack = self.stacks.get(stack_name)
        if stack is None:
            stack = Stack(stack_name)
            self.stacks[stack_name] = stack
        return stack

    def push(self, stack_name, **kwargs):
        stack = self.get_stack(stack_name)
        stack.push(**kwargs)

    def pop(self, stack_name):
        stack = self.stacks[stack_name]
        return stack.pop()

