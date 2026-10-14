from contextvars import ContextVar
denied_tools=ContextVar('denied_tools',default=frozenset())
def is_denied(name):
    return name.replace('_','/',1)+'.py' in denied_tools.get()
