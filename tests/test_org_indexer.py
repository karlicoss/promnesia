from contextlib import contextmanager
from pathlib import Path

from promnesia.indexers.org import extract_from_file

@contextmanager
def tmp_org(tmp_path: Path, text: str):
    path = tmp_path / 'file.org'
    path.write_text(text)
    yield path


DATA = """
* TODO [#C] figure out
:PROPERTIES:
:CREATED:  [2018-08-06 Mon 22:52]
:END:

most important

* [2019-05-10 Fri 17:20] [[https://reddit.com/r/bodyweightfitness/comments/bl7nyy/how_i_learned_to_handstand_about_5_minutes_ago/][How I learned to handstand about 5 minutes ago, after trying for around a year. A surprising method you maybe haven't tried.]] /r/bodyweightfitness

 This whole time I've been trying to keep myself up, when you're really supposed to be preventing the fall.  This exercise gets you to use the strongest muscles in this exercise (shoulders) to prevent your torso falling down. Whereas I think previously I, and a lot of people, would be trying to balance the body mostly with the hands, and the position of the legs, if that makes sense.

 Anyway, hope it helps someone.

* TODO [#C] [2019-10-16 Wed 08:28] xxx /r/cpp
 I've enjoyed [Chandler Carruth's _There Are No Zero-cost Abstractions_](
 https://www.youtube.com/watch?v=rHIkrotSwcc) very much.

    """


def test_org_extractor(tmp_path):
    with tmp_org(tmp_path, DATA) as of:
        items = list(extract_from_file(of))
        assert len(items) == 2

        cpp = items[1]
        assert cpp.url == 'https://www.youtube.com/watch?v=rHIkrotSwcc'


XXX = """
#+FILETAGS: topology

simulations/visualisations of fundamental group

https://en.wikipedia.org/wiki/Computational_topology

http://graphics.stanford.edu/courses/cs468-09-fall/
hmm wonder if that does it. they mention triangulation.

https://en.wikipedia.org/wiki/Triangulation_(topology)
https://en.wikipedia.org/wiki/Digital_manifold
""".strip()


def test_heading(tmp_path):
    with tmp_org(tmp_path, XXX) as of:
        items = list(extract_from_file(of))
        assert {i.url for i in items} == {
            'https://en.wikipedia.org/wiki/Computational_topology',
            'http://graphics.stanford.edu/courses/cs468-09-fall/',
            'https://en.wikipedia.org/wiki/Triangulation_(topology)',
            'https://en.wikipedia.org/wiki/Digital_manifold',
        }
