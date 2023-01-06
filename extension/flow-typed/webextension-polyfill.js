/* @flow */

/*
 * Based on https://github.com/Shraymonks/flow-interfaces-chrome
 * not sure if browser polyfill has flow types??
 * https://github.com/mozilla/webextension-polyfill/issues/421
 */


type browser$StorageArea = {
  get: (keys: string | Array<string> | Object | null) => Promise<Object>,
  set: (items: Object) => Promise<void>,
}


type browser$storage = {
  local: browser$StorageArea,
  managed: browser$StorageArea,
  sync: browser$StorageArea,
}


type result = boolean
type granted = boolean


type browser$permissions = {
  contains: (permissions: chrome$Permissions) => Promise<result>,
  request : (permissions: chrome$Permissions) => Promise<granted>,
}


type browser$tabs = {
  get(tabId: number): Promise<chrome$Tab>,
  query(queryInfo: {
    active?: boolean,
    audible?: boolean,
    currentWindow?: boolean,
    highlighted?: boolean,
    index?: number,
    lastFocusedWindow?: boolean,
    muted?: boolean,
    pinned?: boolean,
    status?: chrome$TabStatus,
    title?: string,
    url?: string | Array<string>,
    windowId?: number,
    windowType?: chrome$WindowType
  }): Promise<Array<chrome$Tab>>,
  executeScript: (
    ((
      tabId?: number,
      details: {
        allFrames?: boolean,
        code?: string,
        file?: string,
        frameId?: number,
        matchAboutBlank?: boolean,
        runAt?: chrome$RunAt
      },
    ) => Promise<void>) &
    ((
      details: {
        allFrames?: boolean,
        code?: string,
        file?: string,
        frameId?: number,
        matchAboutBlank?: boolean,
        runAt?: chrome$RunAt
      },
    ) => Promise<void>)
  ),
  insertCSS: (
    ((
      tabId: number,
      details: {
        allFrames?: boolean,
        code?: string,
        file?: string,
        frameId?: number,
        matchAboutBlank?: boolean,
        runAt?: chrome$RunAt
      },
    ) => Promise<void>) &
    ((
      details: {
        allFrames?: boolean,
        code?: string,
        file?: string,
        frameId?: number,
        matchAboutBlank?: boolean,
        runAt?: chrome$RunAt
      },
    ) => Promise<void>)
  ),
}


type ExecuteResult = {
  result: any,
}


type browser$scripting = {
  executeScript: ({
    target: {tabId?: number},
    func: () => void,
  }) => Promise<Array<ExecuteResult>>,
}


declare var browser: {
  storage: browser$storage,
  permissions: browser$permissions,
  tabs: browser$tabs,
  scripting: browser$scripting,
}


declare module "webextension-polyfill" {
  declare var storage: browser$storage;
  declare var permissions: browser$permissions;
  declare var tabs: browser$tabs;
  declare var scripting: browser$scripting;
}
