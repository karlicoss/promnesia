/* NOTE: this file is kept intact by webpack, for the sake of highlighting and linting  */

// 'API': take
// - link_element: list of <a> DOM elements on the page
// - visited: Map<Url, ?Visit>
// then you can walk through this and decorate as you please
// ideally you just can override/monkey patch showMark and hideMark and rely on showMarks/hideMarks to do the correct thing?

/*
 * NOTE at the moment it's pretty messy, and I often have very little idea what's happening...
 * would be very grateful if someone better at web helped with this
 *
 * ideally perhaps best to use some existing library for this that can handle in a generic manner?
 * could be useful for many applications..
 */

function shouldForceTop() {
    // some websites are really full of dynamic shit and it's impossible to display popups without messing with the document root..
    const host = new URL(window.location).hostname
    for (const d of [
        'youtube.',
    ]) {
        // meh, need to integrate with normaliser somehow..
        if (host.includes(d)) {
            return true
        }
    }
    return false
}


function createLink(href, title) {
    const a = document.createElement('a')
    a.title = title
    a.href  = href
    a.style.color = 'blue' // sometimes parent overrides it?
    a.appendChild(document.createTextNode(title))
    return a
}

function appendText(e, text) {
    e.appendChild(document.createTextNode(text))
}

// TODO make sure it's easy to toggle 'show visited' for a specific page

// maybe use something else instead of eye? so it's not spammy
function formatVisit(v) {
    // TODO disable link decoration?
    const e = document.createElement('code')
    e.style.whiteSpace = 'pre-wrap' // keep whitespace intact
    e.style.display = 'block'
    // meh .. otherwise disturbs parent elements
    e.style.margin  = '0px'
    e.style.padding = '0px'
    e.style.border  = '0px'

    // TODO max-width/color should def be css
    e.style.backgroundColor = 'lightyellow' // ugh.. might inherit page css otherwise?
    const {
        original_url: original,
        normalised_url: normalised,
        dt_local    : dt,
        tags        : tags,
        context     : context,
        locator     : locator,
    } = v
    appendText(e, 'url     : ') // todo I guess original would be the same as element link?
    const l = createLink(original, original)
    l.title = `normalised: ${normalised}`
    e.appendChild(l) // meh
    appendText(e, '\n' + l.title) // TODO do not commit
    appendText(e, `\ndt      : ${new Date(dt).toLocaleString()}`) // meh
    appendText(e, `\ntags    : ${tags.join(' ')}`)
    if (context != null) {
        appendText(e, '\n' + context)
    }
    const els = [e]
    const {href: href, title: title} = locator || {}
    if (href != null) {
        els.push(createLink(href, title))
    }
    return els
}

function create0SpaceElement(el) {
    // hack to 'attach' it to the element without occupying DOM space
    // https://stackoverflow.com/a/6040258/706389
    const w = document.createElement('span')
    w.style.width   = '0px'
    w.style.height  = '0px'
    w.style.position = 'relative'
    w.appendChild(el)
    return w
}


function getExtContainer() {
    const id = 'promnesia-marks-container-id'
    let cont = document.getElementById(id)
    if (cont == null) {
        cont = document.createElement('div') // todo class?
        cont.id = id
        document.body.appendChild(cont)
    }
    return cont
}


function moveToTop(el) {
    const rect = el.getBoundingClientRect()
    const atop  = window.scrollY + rect.top
    const aleft = window.scrollX + rect.left
    const parent = el.parentElement

    el.remove()
    const cont = getExtContainer()
    cont.appendChild(el)

    const new_vals = {
        position: 'absolute',
        top     : `calc(${atop }px + ${el.style.paddingTop  || '0px'})`,
        left    : `calc(${aleft}px + ${el.style.paddingLeft || '0px'})`,
        zIndex  :  9999, // ugh. necessary on youtube, otherwise links seep through??
    }
    const orig_vals = Object.fromEntries(Object.keys(new_vals).map(k => [k, el.style.getPropertyValue(k)]))
    Object.assign(el.style, new_vals)

    return () => { // reverse operation
        el.remove()
        // FIXME restore orig position in parent?
        parent.appendChild(el)
        Object.assign(el.style, orig_vals)
    }
}

/* NOTE: deliberately not used const because script is injected several times.. */
var Cls = {
    VISITED: 'promnesia-visited-link'   ,
    WRAPPER: 'promnesia-visited-wrapper',
}

// TODO I guess, these snippets could be writable by people? and then they can customize tooltips to their liking
/*
 * So, there are a few requirements from the marks we're trying to achieve here
 * - popups should be togglable (otherwise too spammy if shown by default)
 * - should show some visual hints that the popup is present at all (but shouldn't be too spammy)
 * - shouldn't change links placement in DOM -- that breaks many websites (and kind of annoying)
 * - shouldn't overlay any existing dom elements unless popup was clicked
 * - shouldn't break text selection
 * Returns extra elements to insert in DOM: (i.e. if they don't belong to any particular existing dom element)
 */
/*
 * Current implementation
 *
 * <a href... (element)> => <span (outer)><a href ... (element)>  <toggler eye ... > <popup> </span>
 */
function showMark(element) {
    const url = element.href
    // 'visited' passed in backgroud.js
    // eslint-disable-next-line no-undef
    const v = visited.get(url)
    if (!v) {
        return // no visits or was excluded (add some data attribute maybe?)
    }

    element.classList.add(Cls.VISITED)
    const erect = element.getBoundingClientRect()

    let eyecolor = '#550000' // 'boring'

    const eye = document.createElement('span')
    // for debugging
    eye.dataset.promnesia_original   = v.original_url
    eye.dataset.promnesia_normalised = v.normalised_url
    //
    eye.classList.add('nonselectable')
    eye.textContent = '👁'
    eye.style.color = eyecolor
    eye.style.position = 'relative'
    eye.style.bottom = '1em'

    // todo 'interesting' visits would have either context or locator? dunno
    eyecolor = v.context == null ? '#6666ff' : '#00ff00' // copy-pasted from 'generate' script..
    eye.style.color = eyecolor

    // outer decorates link along with its associated stuff added by promnesia
    const outer = document.createElement('span')
    outer.classList.add(Cls.WRAPPER)
    outer.style.display = 'inline'
    // ugh. putting it on the outer wrapper is glitchy, e.g. outline stretches when the popup appears and stays when disappears
    element.orig_outline = element.style.outline // keep to restore later
    element.style.outline = '0.5em solid '

    function getDisplayType(element) {
        const cStyle = element.currentStyle || window.getComputedStyle(element, "")
        return cStyle.display
    }

    const old_display = getDisplayType(element)
    // TODO shit. seems necessary but doesn't work in discord? fucking hell... something to do with flex?
    // maybe it's only relevant to navbars etc..
    const fix_display = old_display == 'block' ? 'inline-block' : old_display
    element.orig_display  = old_display
    element.style.display = fix_display

    // TODO hmmm... maybe check if the position is absolute on the element or some of its parents?
    // and display absolute here as well then?

    element.replaceWith(outer)
    outer.appendChild(element)

    /* toggler shows/hides popup
     * TODO: issue that if it's parent zindex is lower, the popup will be below the body..
     * can see on the left stackoverflow sidebar... or in Element web app
     * also on github repositories, in the top bar where issues/PRs are
     * or in the file view
     * ugh. not sure what's the right way to deal with it. i.e. absolute position might break when scrolling
     * TODO (put in comments which websites since I can't reproduce anymore..)
     * also generally cause grief if mispositioned
     * maybe.. have some 'force' button or something?
     */
    const toggler = document.createElement('span')
    toggler.classList.add('nonselectable')
    toggler.title = 'click to pin/unpin the popup'
    toggler.style.cursor     = 'crosshair' // TODO maybe custom cursor?
    toggler.style.display = 'inline-block'
    toggler.style.whiteSpace = 'pre' // otherwsie not displayed (since empty)
    /* the three rightmost characters cause the toggle to show.
     * the rest is left intect so it's possible to click on the URL
     */
    const width = `${Math.floor(erect.width / 4)}px`
    toggler.style.paddingLeft =       width // meh..
    toggler.style.marginLeft  = '-' + width
    toggler.style.width = '0px'
    toggler.textContent = ' ' // otherwise not displayed at all
    outer.appendChild(toggler)

    toggler.appendChild(eye)

    /* popup body */
    // TODO ugh. this messes up with selection
    // i.e. when we select over parent, it also selects all highligh stuff
    // not sure what to do.. maybe make nonselectable and only allow selection on the click on the popup?
    const popup = document.createElement('span')
    popup.style.outline = 'solid 1px'
    popup.style.background = 'lightyellow'
    // popup.style.padding = '1px'
    popup.style.width = 'max-content' // otherwise too narrow
    popup.style.maxWidth = '120ch'
    popup.style.position = 'relative' // necessary for  zIndex to work
    // TODO would be cool to reuse the same style used by the sidebar...
    const close = document.createElement('span')
    close.classList.add('nonselectable')
    close.style.float = 'right'
    close.style.color = 'red'
    close.style.cursor = 'pointer'
    close.style.fontWeight = 'bold'
    close.title = 'close popup'
    close.textContent = "×"
    popup.appendChild(close)
    let ev = formatVisit(v)
    for (const e of ev) {
        popup.appendChild(e)
    }

    // need a wrapper to make sure showing popup doesn't impact the link DOM
    const popup_w = create0SpaceElement(popup)
    outer.appendChild(popup_w)
    // ugh. absolute positions still might not work (e.g. on discord)
    // to make absolute always work need to attach to the document so it's guaranteed a stacking context...
    // but then might be mispositioned.. sigh
    popup_w.style.position = 'absolute'

    const bumpZindex = () => {
        // jeez. but kind of works.. (needs to be shared across all visits..)
        let lastz = window.lastz || 1
        popup .style.zIndex = lastz
        window.lastz = lastz + 1
    }
    let undoMove = null
    const over = () => {
        popup  .style.display = 'block'
        // ugh. why does this work?? inline seems necessary so it doesn't disturb the content...
        popup_w.style.display = 'inline-grid'
        toggler.style.background   = '#ff000099' // meh not sure if I need it?
        element.style.outlineColor = eyecolor

        // make sure it's on the very top...
        // otherwise on some naughty sites like youtube it's impossible to click without clicking on the video
        undoMove = moveToTop(toggler)

        toggler.removeEventListener('mouseover', over)
        toggler.addEventListener   ('mouseout' , out )

        // TODO kinda annoying that popup might go over the links?
        // maybe duplicate link display in the popup? not sure..
        // ught. naming kind clashes...
        bumpZindex() // not sure why it is here??

        if (shouldForceTop()) {
            forcePopupOnTop()
        }
    }
    // when out toggler, hide it
    const out = () => {
        popup  .style.display = 'none'
        popup_w.style.display = 'none'
        toggler.style.background   = eyecolor + '22' // transparency
        element.style.outlineColor = eyecolor + '22'

        if (undoMove != null) {
            undoMove()
        }

        toggler.removeEventListener('mouseout' , out )
        toggler.addEventListener   ('mouseover', over)
    }

    // and click to pin/unpin!
    const toggle = (e) => {
        e.stopPropagation()
        const pinned = popup.pinned || false
        if (pinned) {
            out() // let default behaviour take over
        } else {
            toggler.removeEventListener('mouseout' , out)
            toggler.removeEventListener('mouseover', over)
        }
        popup.pinned = !pinned
    }
    const forcePopupOnTop = () => {
        // ugh. last resort measure... for the most stubborn websites
        moveToTop(popup_w)
        // TODO restore it back on another double click?
    }
    // FIXME clicking on popup link closes all popups?? for now just open in new tab?
    toggler.addEventListener('click', toggle)
    close  .addEventListener('click', toggle)
    popup  .addEventListener('click', bumpZindex)
    popup.title = `
- single click to move popup up,
- double click to force popup on top of other elements
  may cause glitches, please report such sites here https://github.com/karlicoss/promnesia/issues/168
`.trim()
    popup.addEventListener('dblclick', forcePopupOnTop)
    out()
    return []
}

/*
 * Ideally should be an inverse for showMark
 */
function hideMark(element) {
    if (!element.classList.contains(Cls.VISITED)) {
        return
    }
    element.classList.remove(Cls.VISITED)
    // need to deal with the toggler & wrappers
    const outer = element.parentElement
    if (outer.classList.contains(Cls.WRAPPER)) {
        outer.replaceWith(element)
        // do we need anything else?? presumably it would be orphaned in DOM?
    }
    element.style.outline = element.orig_outline
    element.style.display = element.orig_display
}

function _doMarks(show /* boolean */) {
    const cont = getExtContainer()

    if (!show) {
        cont.remove()
    }

    // 'link_elements' passed in background.js
    // eslint-disable-next-line no-undef
    const elements = link_elements
    const ONE_GROUP = 20
    for (let i = 0; i < elements.length; i += ONE_GROUP) {
        const group = elements.slice(i, i + ONE_GROUP)
        // not necessary, but bet to process asynchronously to avoid performance issues
        setTimeout(() => {
            for (const link of group) {
                let elems = null
                try { // best to be defensive here..
                    const fn = show ? showMark : hideMark
                    elems = fn(link)
                } catch (e) {
                    console.error(e)
                }

                if (elems != null) {
                    // only relevant to 'show' mode??
                    for (const e of elems) {
                        // NOTE: attaching to the link element itself (or its parent) seems like a bad idea
                        // .e.g see on https://old.reddit.com/r/archlinux/comments/juianf/is_there_a_software_that_runs_a_command_at_a_time/
                        // the invisible menu appears when eyes are on
                        cont.appendChild(e)
                    }
                }
            }
        })
    }
}


// called from background.js
// eslint-disable-next-line no-unused-vars
function showMarks() {
    _doMarks(true)
}

// called from background.js
// eslint-disable-next-line no-unused-vars
function hideMarks() {
    _doMarks(false)
}

/*
 * I guess the most important thing is that as little layout disturbed when the user isn't showing popups, as possible
 *
 * TESTING:
 * would be nice to have something automatic...
 * check on
 * - wikipedia
 * - discord
 *   ugh. too much dynamic shit in discord to make it work reliably...
 * - stackoverflow
 * - twitter
 * - github
 * - reddit (todo shift the content...)
     TODO fuck. on reddit annotations are hiding below the items
     I think this is just too common problem..
 * - hackernews
 * - lobsters (todo seems to change DOM a bit)
 *   ugh. might be because of actual <li> items?
 * - slack
 * - https://www.w3schools.com/jsref/met_document_addeventlistener.asp
 * - youtube
 * eh. I guess need to add a warning that some websites might get shifter
 * link to an issue to collect them + suggest to blocklist..
 * TODO or maybe bind to the sidebar?
 */
