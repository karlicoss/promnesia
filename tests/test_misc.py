from pathlib import Path
from promnesia.common import extract_urls

def test_extract():
    lines = """
 I've enjoyed [Chandler Carruth's _There Are No Zero-cost Abstractions_](
 https://www.youtube.com/watch?v=rHIkrotSwcc) very much.
""".strip()
    assert set(extract_urls(lines)) == {'https://www.youtube.com/watch?v=rHIkrotSwcc'}


def test_extract_2():
   text = '''‍♂️ Чтобы снизить вероятность ошибиться, важно знать про когнитивные искажения.
   Если для вас это новое словосочетание, начните с книжки
   "Гарри Поттер и Методы рационального мышления" - http://hpmor.ru/, если вы знакомы с понятием - читайте цепочки на сайтах
   lesswrong.ru и lesswrong.com, книжку Даниэля Канемана "Thinking, fast and slow" и канал Пион https://t.me/ontologics
   '''
   assert set(extract_urls(text)) == {'http://hpmor.ru/', 'lesswrong.ru', 'lesswrong.com', 'https://t.me/ontologics'}

def test_extract_md():
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


from promnesia.common import PathIsh, _is_windows as windows
from promnesia.sources.auto import by_path


def handled(p: PathIsh) -> bool:
    idx, m = by_path(Path(p))
    return idx is not None
    # ideally these won't hit libmagic path (would try to open the file and cause FileNotFoundError)


def test_filetypes() -> None:
    # test media
    for ext in 'avi mp4 mp3 webm'.split() + ([] if windows else 'mkv'.split()):
        assert handled('file.' + ext)

    # images
    for ext in 'gif jpg png jpeg'.split():
        assert handled('file.' + ext)

    # TODO more granual checks that these are ignored?
    # binaries
    for ext in 'o sqlite'.split() + ([] if windows else 'class jar'.split()):
        assert handled('file.' + ext)

    # these might have potentially some links
    for ext in [
            'svg',
            'pdf', 'epub', 'ps',
            'doc', 'ppt', 'xsl',
            # seriously, windows doesn't know about docx???
            *([] if windows else 'docx pptx xlsx'.split()),
            *([] if windows else 'ods odt rtf'.split()),
    ] + ([] if windows else 'djvu'.split()): 
        assert handled('file.' + ext)

    # source code
    for ext in 'rs tex el js sh hs pl h py hpp c go css'.split() + ([] if windows else 'java cpp'.split()):
        assert handled('file.' + ext)

    assert handled('x.html')
