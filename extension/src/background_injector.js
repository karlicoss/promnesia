// see background.js::initBackground for explanation
chrome.runtime.sendMessage({method: "INJECT_BACKGROUND_CALLBACKS"})


// hack to hook into the extension... https://stackoverflow.com/a/38554438/706389
for (const x of [
    'selenium-bridge-activate',
    'selenium-bridge-mark-visited',
    'selenium-bridge-search',
]) {
    document.addEventListener(x, () => {
        chrome.runtime.sendMessage(x)
    })
}
