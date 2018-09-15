function save_options() {
  var fpath = document.getElementById('fpath').value;
    chrome.storage.local.set({'history_json': fpath}, function() {
        console.log('Value is set to ' + fpath);
        chrome.runtime.sendMessage({
            'method':'refreshMap'
        }, function(/*response*/){
            console.log("reloaded the map");
        });
    });
}

function restore_options() {
    // Use default value color = 'red' and likesColor = true.
    chrome.storage.local.get({'history_json': ""}, function(items) {
        document.getElementById('fpath').value = items.history_json;
    });
}

document.addEventListener('DOMContentLoaded', restore_options);
document.getElementById('save').addEventListener('click', save_options);
