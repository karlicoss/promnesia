from pathlib import Path
from promnesia.common import traverse
from unittest.mock import Mock, patch
from common import DATA


testDataPath = Path(DATA) / 'traverse'

# Patch shutil.which so it always returns false (when trying to which fdfind, etc)
# so that it falls back to find
@patch('promnesia.common.shutil.which', return_value=False)
def test_traverse_ignore_find(patched):
    '''
    traverse() with `find` but ignore some stuff
    '''
    # act
    paths = set(traverse(testDataPath, ignore=['ignoreme.txt', 'ignoreme2']))

    # assert
    assert paths == {testDataPath / 'imhere2/real.txt', testDataPath / 'imhere.txt'}

def test_traverse_ignore_fdfind():
    '''
    traverse() with `fdfind` but ignore some stuff
    '''
    # act
    paths = set(traverse(testDataPath, ignore=['ignoreme.txt', 'ignoreme2']))

    # assert
    assert paths == {testDataPath / 'imhere.txt', testDataPath / 'imhere2/real.txt'}

# TODO: It would be nice to test the implementation directly without having to do this
# weird patching in the future
@patch('promnesia.common._is_windows', new_callable=lambda: True)
def test_traverse_ignore_windows(patched):
    '''
    traverse() with python when _is_windows is true but ignore some stuff
    '''
    # act
    paths = set(traverse(testDataPath, ignore=['ignoreme.txt', 'ignoreme2']))

    # assert
    assert paths == {testDataPath / 'imhere.txt', testDataPath / 'imhere2/real.txt'}
