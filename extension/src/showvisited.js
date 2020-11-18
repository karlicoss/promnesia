/* NOTE: this file is kept intact by webpack, for the sake of highlighting and linting  */

// 'API': take
// - link_element: list of <a> DOM elements on the page
// - visited: Map<Url, ?Visit>
// then you can walk through this and decorate as you please
// ideally you just can override/monkey patch showMark and hideMark and rely on showMarks/hideMarks to do the correct thing?


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
    e.style.whiteSpace = 'pre-wrap'
    e.style.display = 'block'
    // TODO max-width/color should def be css
    e.style.maxWidth = '120ch'
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

// TODO crap.. still shifts some elements on lobsters?

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
function showMark(element) {
    const url = element.href
    // 'visited' passed in backgroud.js
    // eslint-disable-next-line no-undef
    const v = visited.get(url)
    if (!v) {
        return // no visits or was excluded (add some data attribute maybe?)
    }

    element.classList.add('promnesia-visited-link')

    let eyecolor = '#550000' // 'boring'

    const eye = document.createElement('span')
    // meh, but works
    const eye_w = create0SpaceElement(eye)
    eye_w.classList.add('promnesia-visited-wrapper')

    // for debugging
    eye.dataset.promnesia_original   = v.original_url
    eye.dataset.promnesia_normalised = v.normalised_url
    //
    eye.classList.add('nonselectable')
    eye.textContent = '👁'
    eye.style.color = eyecolor
    eye.style.position = 'absolute'
    eye.style.bottom = '1em'

    // todo 'interesting' visits would have either context or locator? dunno
    eyecolor = v.context == null ? '#6666ff' : '#00ff00' // copy-pasted from 'generate' script..
    eye.style.color = eyecolor

    // outer decorates link along with its associated stuff added by promnesia
    const outer = document.createElement('span')
    outer.style.display = 'inline-flex'
    outer.style.flexDirection = 'column'
    // ugh. putting it on the outer wrapper is glitchy, e.g. outline stretches when the popup appears
    element.style.outline = '0.5em solid '

    element.replaceWith(outer)
    outer.appendChild(element)

    /* toggler shows/hides popup
     * TODO: issue that if it's parent zindex is lower, the popup will be below the body..
     * can see on the left stackoverflow sidebar... or in Element web app
     * also on github repositories, in the top bar where issues/PRs are
     * or in the file view
     * ugh. not sure what's the right way to deal with it. i.e. absolute position might break when scrolling
     * also generally cause grief if mispositioned
     * maybe.. have some 'force' button or something?
     */
    const toggler = document.createElement('span')
    toggler.classList.add('nonselectable')
    toggler.title = 'click to pin/unpin the popup'
    toggler.style.cursor     = 'crosshair' // TODO maybe custom cursor?
    // toggler.style.background = '#ff000077' // TODO debug
    toggler.style.position = 'absolute' // otherwise displays as a second col
    toggler.style.whiteSpace = 'pre' // otherwsie not displayed (since empty)
    /* the three rightmost characters cause the toggle to show.
     * the rest is left intect so it's possible to click on the URL
     */
    toggler.style.paddingLeft =  `${Math.floor(element.clientWidth / 4)}px` // meh..
    toggler.textContent = ' ' // otherwise not displayed
    toggler.style.alignSelf = 'end'
    outer.appendChild(toggler)

    eye_w.style.alignSelf = 'end'
    outer.appendChild(eye_w)

    /* popup body */
    // TODO ugh. this messes up with selection
    // i.e. when we select over parent, it also selects all highligh stuff
    // not sure what to do.. maybe make nonselectable and only allow selection on the click on the popup?
    const popup = document.createElement('span')
    popup.style.outline = 'solid 1px'
    popup.style.background = 'lightyellow'
    popup.style.padding = '1px'
    popup.style.width = 'max-content' // otherwise too narrow
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
    popup_w.style.alignSelf = 'start'
    outer.appendChild(popup_w)

    const movetotop = () => {
        // jeez. but kind of works.. (needs to be shared across all visits..)
        let lastz = window.lastz || 1
        popup .style.zIndex = lastz
        window.lastz = lastz + 1
    }
    const over = () => {
        popup.style.display = 'block'
        element.style.outlineColor = eyecolor
        toggler.style.background = '#ff000099' // meh not sure if I need it?

        // TODO kinda annoying that popup might go over the links?
        // maybe duplicate link display in the popup? not sure..
        movetotop()

        toggler.removeEventListener('mouseover', over)
        toggler.addEventListener   ('mouseout' , out )
    }
    // when out toggler, hide it
    const out = () => {
        popup.style.display = 'none'
        element.style.outlineColor = eyecolor + '22' // transparency
        toggler.style.background = '' // meh

        toggler.removeEventListener('mouseout' , out )
        toggler.addEventListener   ('mouseover', over)
    }

    // and click to pin/unpin!
    const toggle = () => {
        const pinned = popup.pinned || false
        if (pinned) {
            out() // let default behaviour take over
        } else {
            toggler.removeEventListener('mouseout' , out)
            toggler.removeEventListener('mouseover', over)
        }
        popup.pinned = !pinned
    }
    toggler.addEventListener('click', toggle)
    close  .addEventListener('click', toggle)
    popup.addEventListener('click', movetotop)
    out()
    return []
}

/*
 * Ideally should be an inverse for showMark
 */
function hideMark(element) {
    const VISITED = 'promnesia-visited-link'
    const WRAPPER = 'promnesia-visited-wrapper'
    if (!element.classList.contains(VISITED)) {
        return
    }
    element.classList.remove(VISITED)
    // need to deal with the toggler & wrappers
    // TODO this is only gonna be the case if it was indeed wrapped?
    const outer = element.parentElement.parentElement
    if (outer.classList.contains(WRAPPER)) {
        outer.replaceWith(element)
        // do we need anything else?? presumably it would be orphaned in DOM?
    }
    // ok, now we also have an eye inside the link
    // todo use different class?
    // TODO maybe also keep it in the outer container?? dunno
    for (const el of element.getElementsByClassName(WRAPPER)) {
        el.remove()
    }
}

function _doMarks(show /* boolean */) {
    let cont = document.getElementById('promnesia-marks-container-id')
    if (cont == null) {
        cont = document.createElement('div') // todo class?
        cont.id = 'promnesia-marks-container-id'
        document.body.appendChild(cont)
    }

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
