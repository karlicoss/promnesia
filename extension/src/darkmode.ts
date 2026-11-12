import browser from "webextension-polyfill"

const COLOR_SCHEME_KEY = 'color_scheme'

export async function applyStoredColorScheme(body: Element): Promise<void> {
    const stored = await browser.storage.local.get(COLOR_SCHEME_KEY)
    const scheme = stored[COLOR_SCHEME_KEY] as string | undefined
    if (scheme === 'dark') {
        body.classList.add('promnesia-dark')
    } else if (scheme === 'light') {
        body.classList.add('promnesia-light')
    }
}

function isDark(body: Element, win: Window): boolean {
    return body.classList.contains('promnesia-dark') || (
        !body.classList.contains('promnesia-light') &&
        win.matchMedia('(prefers-color-scheme: dark)').matches
    )
}

export function setupDarkModeButton(button: HTMLButtonElement, body: Element, win: Window): void {
    const update = (): void => {
        button.textContent = isDark(body, win) ? '☀️' : '🌙'
        button.title = isDark(body, win) ? 'Switch to light mode' : 'Switch to dark mode'
    }

    update()

    button.addEventListener('click', () => {
        if (isDark(body, win)) {
            body.classList.remove('promnesia-dark')
            body.classList.add('promnesia-light')
            browser.storage.local.set({[COLOR_SCHEME_KEY]: 'light'})
        } else {
            body.classList.remove('promnesia-light')
            body.classList.add('promnesia-dark')
            browser.storage.local.set({[COLOR_SCHEME_KEY]: 'dark'})
        }
        update()
    })
}
