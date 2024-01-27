class Stack:

    def __init__(self, name, **kwargs):
        self.name = name
        self._kwargs = kwargs
        self.reset()

    def reset(self, **kwargs):
        self.items = [self._kwargs]

    @property
    def top(self):
        return self.items[-1]

    def get(self, name, default=None):
        return self.top.get(name, default)

    def set(self, name, value):
        self.top[name] = value

    def push(self, **kwargs):
        item = self.top.copy()
        item.update(kwargs)
        self.items.append(item)

    def pop(self):
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

