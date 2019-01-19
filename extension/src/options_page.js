import {setUrlsFile, getUrlsFile} from './options';

function saveOptions() {
    const fpath = document.getElementById('fpath').value;
    setUrlsFile(fpath, () => {
        console.log('Value is set to ' + fpath);
        // TODO abstract it away
        // TODO here, we will set endpoint instead
    });
}

function restoreOptions() {
    // Use default value color = 'red' and likesColor = true.
    getUrlsFile(fname => {
        document.getElementById('fpath').value = fname;
    });
}

document.addEventListener('DOMContentLoaded', restoreOptions);
document.getElementById('save').addEventListener('click', saveOptions);
