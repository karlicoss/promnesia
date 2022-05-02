// see background.js::initBackground for explanation
chrome.runtime.sendMessage({method: "INJECT_BACKGROUND_CALLBACKS"})


// hacke to hook into the exception.. https://stackoverflow.com/a/38554438/706389
// hmm. sadly there are no arguments, so need to use different
//
document.addEventListener('selenium-bridge-activate', () => {
    chrome.runtime.sendMessage('selenium-bridge-activate')
})
