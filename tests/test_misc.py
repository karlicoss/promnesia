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
