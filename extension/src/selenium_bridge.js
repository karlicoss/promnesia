// hack to hook into the extension... https://stackoverflow.com/a/38554438/706389
// only used during tests

for (const x of [
    'selenium-bridge-_execute_action',
    'selenium-bridge-_execute_browser_action',
    'selenium-bridge-mark_visited',
    'selenium-bridge-search',
]) {
    document.addEventListener(x, () => {
        browser.runtime.sendMessage(x)
    })
}


// 'reverse bridge': allows reading extension state from webdriver
document.addEventListener('selenium-bridge-get-state', async (event) => {
    // clear previous state
    delete document.documentElement.dataset.seleniumBridgeState
    // we use a timestamp to make sure we don't read some stale response
    const timestamp_ms = event.detail.timestamp_ms
    let state
    try {
        state = await browser.runtime.sendMessage('selenium-bridge-get-state')
    } catch (error) {
        console.error(error)
        state = {error: error}
    }
    state.timestamp_ms = timestamp_ms
    document.documentElement.dataset.seleniumBridgeState = JSON.stringify(state)
})

// special variable to check against when we use selenium bridge
// otherwise it's possible that the script isn't injected yet, and then the event wouldn't get received
document.documentElement.dataset.seleniumBridgeInjected = true
