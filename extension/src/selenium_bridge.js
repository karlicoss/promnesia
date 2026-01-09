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

// Reverse bridge: allows reading extension state from webdriver
// Listens for a request event and stores the response in a DOM attribute
document.addEventListener('selenium-bridge-get-state', async () => {
    try {
        const state = await chrome.runtime.sendMessage('selenium-bridge-get-state')
        document.documentElement.dataset.seleniumBridgeState = JSON.stringify(state)
    } catch (error) {
        document.documentElement.dataset.seleniumBridgeState = JSON.stringify({error: error.message})
    }
})

// special variable to check against when we use selenium bridge
// otherwise it's possible that the script isn't injected yet, and then the event wouldn't get received
document.documentElement.dataset.seleniumBridgeInjected = true
