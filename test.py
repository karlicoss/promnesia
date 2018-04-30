#!/usr/bin/env python3.6
from os.path import join
from tempfile import TemporaryDirectory

from wereyouhere.render import render


def test_takeout():
    test_takeout_dir = "testdata/takeout"
    import wereyouhere.generator.takeout as takeout_gen
    histories = takeout_gen.get_takeout_histories(test_takeout_dir)
    [hist] = histories
    assert len(hist) > 0 # kinda arbitrary?

    with TemporaryDirectory() as tdir:
        render([hist], join(tdir, 'res.json'))

def test_chrome():
    import wereyouhere.generator.chrome as chrome_gen
    import imp
    backup_db = imp.load_source('hdb', 'scripts/backup-chrome-history-db.py')

    with TemporaryDirectory() as tdir:
        backup_db.backup_to(tdir)

        [hist] = list(chrome_gen.iter_chrome_histories(tdir))
        assert len(hist) > 10 # kinda random sanity check

        render([hist], join(tdir, 'res.json'))


def test_plaintext_path_extractor():
    import wereyouhere.generator.custom as custom_gen
    from wereyouhere.generator.plaintext import extract_from_path

    hist = custom_gen.get_custom_history(
        extract_from_path('testdata/custom'),
        tag='test',
    )
    assert len(hist) == 4


def test_custom():
    import wereyouhere.generator.custom as custom_gen

    hist = custom_gen.get_custom_history(
        """grep -Eo -r --no-filename '(http|https)://\S+' testdata/custom""",
        tag='test',
    )
    assert len(hist) == 4 # TODO this will be changed later when we actually normalise
    with TemporaryDirectory() as tdir:
        render([hist], join(tdir, 'res.json'))

# TODO test config 
