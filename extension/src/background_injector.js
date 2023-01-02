// see background.js::initBackground for explanation
chrome.runtime.sendMessage({method: "INJECT_BACKGROUND_CALLBACKS"})


// hack to hook into the extension... https://stackoverflow.com/a/38554438/706389
document.addEventListener('selenium-bridge-activate', () => {
    chrome.runtime.sendMessage('selenium-bridge-activate')
})
document.addEventListener('selenium-bridge-mark-visited', () => {
    chrome.runtime.sendMessage('selenium-bridge-mark-visited')
})
