#!/usr/bin/env python3.6

def test_takeout():
    test_takeout_dir = "testdata/takeout"
    import wereyouhere.generator.takeout as takeout_gen
    histories = takeout_gen.get_takeout_histories(test_takeout_dir)
    [hist] = histories
    pass
