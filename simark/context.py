"""
Implementation of a simple LIFO stack that uses dictionaries to store state
information. Values may be inheritable from prior frames.
"""


class Stack:
    def __init__(self, **kwargs):
        self.frames = [kwargs]  # Root frame

    def reset(self):
        """Reset stack to initial state."""
        del self.frames[1:]

    @property
    def top(self):
        return self.frames[-1]

    def get(self, key, inherit=True, default=None):
        """Retrieve the value of an element. If inherit is False, retrieve a
        value from only the top-most frame, otherwise retrieve the most recent
        value, searching backwards through the stack."""
        if not inherit:
            top = self.frames[-1]
            return top[key] if key in top else default
        # Retrieve the most recent value
        return next((frame[key] for frame in reversed(self.frames) if key in frame), default)

    def set(self, key, value):
        """Set a value in the current frame."""
        # Replace references to mutable objects with copies
        self.top[key] = value if not isinstance(value, (dict, list, set)) else value.copy()

    def push(self, **kwargs):
        """Push a new frame with new values."""
        self.frames.append(kwargs)

    def pop(self):
        """Pop the most recent frame, ensuring at least one frame remains."""
        if len(self.frames) == 1:
            raise ValueError(f"Illegal pop of empty stack {repr(self.name)}")
        return self.frames.pop()


