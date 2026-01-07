// hack to hook into the extension... https://stackoverflow.com/a/38554438/706389
// only used during tests

for (const x of [
    'selenium-bridge-_execute_action',
    'selenium-bridge-_execute_browser_action',
    'selenium-bridge-mark_visited',
    'selenium-bridge-search',
]) {
    document.addEventListener(x, () => {
        chrome.runtime.sendMessage(x)
    })
}

// special variable to check against when we use selenium bridge
// otherwise it's possible that the script isn't injected yet, and then the event wouldn't get received
document.documentElement.dataset.seleniumBridgeInjected = true
