#!/usr/bin/env python3
import tempfile
from pathlib import Path

import pytest # type: ignore
from pytest import mark # type: ignore
skip = mark.skip


def assert_has_in_context(thing: str, hist):
    for v in hist.visits:
        if thing in v.context:
            return
    raise AssertionError(f"haven't found {thing} in context")

def history(*args, **kwargs):
    from wereyouhere.generator.smart import previsits_to_history
    return previsits_to_history(*args, **kwargs)[0] # TODO meh

def test_hypothesis():
    from config import Extractors
    ex = Extractors.HYPOTHESIS
    hist = history(ex)
    assert len(hist) > 100
    assert_has_in_context('blindfolded people can use sound to distinguish', hist)


def test_org():
    from config import Extractors
    from private import notes_extractor
    with tempfile.TemporaryDirectory() as tdir:
        td = Path(tdir)
        (td / 'test.org').write_text("""
* [2016-05-14 Sat 15:33] [[https://www.reddit.com/r/androidapps/comments/4i36z9/how_you_use_your_android_to_the_maximum/d2uq24i][sc4s2cg comments on How you use your android to the maximum?]] :android:

* something
      https://link.com

* [2019-05-14 Tue 20:26] [[https://www.instapaper.com/read/1193274157][ip]]   [[https://blog.andymatuschak.org/post/169043084412/successful-habits-through-smoothly-ratcheting][Successful habits through smoothly ratcheting targets]]


* fewf

 * [2019-05-03 Fri 08:29] apparently [[https://en.wikipedia.org/wiki/Resilio_Sync][Resilio Sync]] exists, but it's proprietary, nothing else I know of or resulting from quick googling
 * [2019-06-13 Thu 19:45] [[https://en.wikipedia.org/wiki/InterPlanetary_File_System][IPFS]] looks close, but appparently not user friendly yet


        """)
        results = list(notes_extractor(td, tag='gerg'))
        assert len(results) == 6
        assert results[0].url == 'https://www.reddit.com/r/androidapps/comments/4i36z9/how_you_use_your_android_to_the_maximum/d2uq24i'
        assert results[1].url == 'https://link.com'
        assert results[-2].url == 'https://en.wikipedia.org/wiki/Resilio_Sync'
        # TODO shit def need org specific url extractor (and then extract from everything remaining)
        # assert results[-1].url == 'https://en.wikipedia.org/wiki/InterPlanetary_File_System'



if __name__ == '__main__':
    pytest.main(__file__)
