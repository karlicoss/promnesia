import sys
from datetime import UTC, datetime
from types import ModuleType, SimpleNamespace

import pytest

from ...common import Loc, Visit
from ...sources import fbmessenger


def test_fbmessenger_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    thread = SimpleNamespace(id='123', name='Example chat')
    dt = datetime(2026, 1, 1, tzinfo=UTC)
    text = 'See https://example.com/article'
    error = RuntimeError('unreadable message')
    messages = [
        error,
        SimpleNamespace(text=None),
        SimpleNamespace(text='No links here'),
        SimpleNamespace(text=text, thread=thread, dt=dt),
    ]

    namespace = ModuleType('my.fbmessenger')
    monkeypatch.setattr(namespace, '__path__', [], raising=False)
    module = ModuleType('my.fbmessenger.all')
    monkeypatch.setattr(module, 'messages', lambda: iter(messages), raising=False)
    monkeypatch.setitem(sys.modules, namespace.__name__, namespace)
    monkeypatch.setitem(sys.modules, module.__name__, module)

    assert list(fbmessenger.index()) == [
        error,
        Visit(
            url='https://example.com/article',
            dt=dt,
            context=text,
            locator=Loc(title='chat with Example chat', href='https://www.messenger.com/t/123'),
        ),
    ]
