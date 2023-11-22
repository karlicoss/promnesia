from ..common import extract_urls


def test_extract_simple() -> None:
    lines = """
 I've enjoyed [Chandler Carruth's _There Are No Zero-cost Abstractions_](
 https://www.youtube.com/watch?v=rHIkrotSwcc) very much.
""".strip()
    assert set(extract_urls(lines)) == {'https://www.youtube.com/watch?v=rHIkrotSwcc'}


def test_extract_2() -> None:
    text = '''‍♂️ Чтобы снизить вероятность ошибиться, важно знать про когнитивные искажения.
    Если для вас это новое словосочетание, начните с книжки
    "Гарри Поттер и Методы рационального мышления" - http://hpmor.ru/, если вы знакомы с понятием - читайте цепочки на сайтах
    lesswrong.ru и lesswrong.com, книжку Даниэля Канемана "Thinking, fast and slow" и канал Пион https://t.me/ontologics
    '''
    assert set(extract_urls(text)) == {'http://hpmor.ru/', 'lesswrong.ru', 'lesswrong.com', 'https://t.me/ontologics'}


def test_extract_md() -> None:
    lines = '''
Hey, I recently implemented a new extension for that [addons.mozilla.org](https://addons.mozilla.org/en-US/firefox/addon/org-grasp-for-org-capture/), [github](https://github.com/karlicoss/grasp), perhaps it could be useful for you!
    '''
    assert set(extract_urls(lines)) == {
        'addons.mozilla.org',
        'https://addons.mozilla.org/en-US/firefox/addon/org-grasp-for-org-capture/',
        'https://github.com/karlicoss/grasp',
    }


# just random links to test multiline/whitespace behaviour
def test_extract_3() -> None:
    lines = '''
python.org/one.html ?? https://python.org/two.html some extra text

    whatever.org
    '''
    assert set(extract_urls(lines, syntax='org')) == {
        'python.org/one.html',
        'https://python.org/two.html',
        'whatever.org',
    }
