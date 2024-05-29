import browser from "webextension-polyfill"
import type {Scripting} from "webextension-polyfill"

import {assert} from './common'


export async function executeScript<R>(injection: Scripting.ScriptInjection): Promise<R> {
    /**
     * In firefox, executeScript sets error property, whereas in chrome it just throws
     * (see https://issues.chromium.org/issues/40205757)
     * For consistency, this wrapper throws in all cases instead
     */
    const results = await browser.scripting.executeScript(injection)
    assert(results.length == 1)
    const [{result, error}] = results
    if (error != null) {
        if (error instanceof Error) {
            throw error
        } else {
            throw new Error(`Error during executeScript: ${error}`)
        }
    }
    return result
}
