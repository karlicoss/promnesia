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
    const e = document.createElement('code')
    e.style.whiteSpace = 'pre-wrap'
    e.style.display = 'block'
    e.style.maxWidth = '120ch'
    const {
        original_url: original,
        normalised_url: normalised,
        dt_local    : dt,
        tags        : tags,
        context     : context,
        locator     : locator,
    } = v
    appendText(e, 'original: ')
    const l = createLink(original, original)
    l.title = `normalised: ${normalised}`
    e.appendChild(l) // meh
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

// TODO I guess, these snippets could be writable by people? and then they can customize tooltips to their liking
// returns extra elements to insert in DOM
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
    const wrapper = create0SpaceElement(eye)
    wrapper.classList.add('promnesia-visited-wrapper')

    // for debugging
    eye.dataset.promnesia_original   = v.original_url
    eye.dataset.promnesia_normalised = v.normalised_url
    //
    eye.classList.add('nonselectable')
    eye.textContent = '👁'
    eye.style.color = eyecolor
    eye.style.position = 'absolute'
    element.appendChild(wrapper)
    // todo 'interesting' visits would have either context or locator? dunno
    if (v === true) {
        // nothing else interesting we can do with such visit
        return []
    }

    eyecolor = v.context == null ? '#6666ff' : '#00ff00' // copy-pasted from 'generate' script..
    eye.style.color = eyecolor

    /*
     * So, toggler 'wraps around' the link
     * TODO not sure about that.. potentially might break DOM
     * yeah, touches it a bit, e.g. on HN..
     * another issue is that if it's parent zindex is lower, the popup will be below the body..
     * can see on the left stackoverflow sidebar...
     * also on github repositories, in the top bar where issues/PRs are
     * or in the file view
     * ugh. not sure what's the right way to deal with it. i.e. absolute position might break when scrolling
     * also generally cause grief if mispositioned
     */
    let toggler = document.createElement('span')
    toggler.classList.add('promnesia-visited-popup-toggler')
    toggler.title = 'click to pin'
    element.replaceWith(toggler)
    toggler.style.cursor = 'pointer'
    toggler.style.paddingTop    = '0.5em'
    toggler.style.paddingBottom = '0.5em'
    toggler.style.display = 'inline-block'
    toggler.appendChild(element)

    /* popup body */
    let content = document.createElement('div')
    content.style.border = 'solid 1px'
    content.style.background = 'lightyellow'
    content.style.padding = '1px'
    content.style.width = 'max-content'
    // eh. seems necessary, e.g. on youtube subscriptions list on the left??
    content.style.zIndex = 10000
    // TODO would be cool to reuse the same style used by the sidebar...
    let ev = formatVisit(v)
    for (const e of ev) {
        content.appendChild(e)
    }
    // TODO would be nice to add close button or something
    // NOTE: popup content can't be under 'a' itself, otherwise it all ends up linking to the original URL
    // it can't be under toggle as well, because then any popup click toggles
    // so it seems we need even extra container.. sigh
    let outer = document.createElement('span')
    outer.classList.add('promnesia-visited-wrapper')
    toggler.replaceWith(outer)
    outer.appendChild(toggler)
    let wrapper2 = create0SpaceElement(content)
    outer.appendChild(wrapper2)

    const movetotop = () => {
        // jeez. but kind of works.. (needs to be shared across all visits..)
        let lastz = window.lastz || 1
        wrapper2.style.zIndex = lastz
        window.lastz = lastz + 1
    }

    // let rect = toggler.getBoundingClientRect()
    // content.style.top  = `${(window.scrollY + rect.bottom)}px`
    // content.style.left = `${(window.scrollX + rect.left  )}px`
    content.style.position = 'absolute'
    content.style.left = '0px' // not sure?
    content.style.top  = '0px'
    // hmm, :hover pseudo class didn't work on that span for some reason...
    // https://stackoverflow.com/questions/12361244/css-hover-pseudo-class-not-working#comment17060438_12361291
    // logic as follows: when over toggler, show the popup
    const over = () => {
        content.style.display = 'block'
        toggler.style.background = 'lightyellow'
        eye    .style.color      = 'lightyellow'
        toggler.style.outline = '1px solid'

        movetotop()

        toggler.removeEventListener('mouseover', over)
        toggler.addEventListener   ('mouseout' , out )
    }
    // when out toggler, hide it
    const out = () => {
        content.style.display = 'none'
        toggler.style.background = eyecolor + '77' // transparency
        eye    .style.color      = eyecolor
        toggler.style.outline = ''

        toggler.removeEventListener('mouseout' , out )
        toggler.addEventListener   ('mouseover', over)
    }
    // and click to pin/unpin!
    const click = () => {
        const pinned = content.pinned || false
        if (pinned) {
            over() // let default behaviour take over
        } else {
            toggler.removeEventListener('mouseout' , out)
            toggler.removeEventListener('mouseover', over)
        }
        content.pinned = !pinned
    }
    toggler.addEventListener('click', click)
    content.addEventListener('click', movetotop)
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
