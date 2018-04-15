#!/usr/bin/env python3.6

def test_takeout():
    test_takeout_dir = "testdata/takeout"
    import wereyouhere.generator.takeout as takeout_gen
    histories = takeout_gen.get_takeout_histories(test_takeout_dir)
    [hist] = histories
    pass

def test_chrome():
    from tempfile import TemporaryDirectory
    import wereyouhere.generator.chrome as chrome_gen
    import imp

    with TemporaryDirectory() as tdir:
        backup_db = imp.load_source('hdb', 'scripts/backup-chrome-history-db.py')
        backup_db.backup_to(tdir)

        [hist] = list(chrome_gen.iter_chrome_histories(tdir))
        assert len(hist) > 10 # kinda random sanity check
