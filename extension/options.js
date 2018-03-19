function save_options() {
  var fpath = document.getElementById('fpath').value;
    chrome.storage.local.set({'history_json': fpath}, function() {
        console.log('Value is set to ' + fpath);
    });
}
document.getElementById('save').addEventListener('click', save_options);
