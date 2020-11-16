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
    // for debugging
    eye.dataset.promnesia_original   = v.original_url
    eye.dataset.promnesia_normalised = v.normalised_url
    //
    eye.classList.add('nonselectable')
    eye.textContent = '👁'
    eye.style.color = eyecolor
    eye.style.position = 'absolute'
    {
        let rect = element.getBoundingClientRect()
        eye.style.top  = `calc(${(window.scrollY + rect.top  )}px - 0.8em)`
        eye.style.left =      `${(window.scrollX + rect.right)}px`
    }

    // todo 'interesting' visits would have either context or locator? dunno
    if (v === true) {
        // nothing else interesting we can do with such visit
        return [eye]
    }

    eyecolor = v.context == null ? '#6666ff' : '#00ff00' // copy-pasted from 'generate' script..
    eye.style.color = eyecolor

    let toggler = document.createElement('span')
    toggler.classList.add('promnesia-visited-popup-toggler')
    toggler.title = 'click to pin'
    element.replaceWith(toggler)
    toggler.style.cursor = 'pointer'
    toggler.style.paddingTop    = '0.5em'
    toggler.style.paddingBottom = '0.5em'
    toggler.appendChild(element)

    let popup = document.createElement('div')
    let content = document.createElement('div')
    content.style.border = 'solid 1px'
    content.style.background = 'lightyellow'
    content.style.padding = '1px'
    // eh. seems necessary, e.g. on youtube subscriptions list on the left??
    content.style.zIndex = 10000
    popup.appendChild(content)
    // TODO max width??
    // TODO use an actual style or something?
    let ev = formatVisit(v)
    for (const e of ev) {
        content.appendChild(e)
    }

    // TODO would be cool to reuse the same style used by the sidebar...
    let rect = toggler.getBoundingClientRect()
    content.style.top  = `${(window.scrollY + rect.bottom)}px`
    content.style.left = `${(window.scrollX + rect.left  )}px`
    content.style.position = 'absolute'
    // hmm, :hover pseudo class didn't work on that span for some reason...
    // https://stackoverflow.com/questions/12361244/css-hover-pseudo-class-not-working#comment17060438_12361291
    // logic as follows: when over toggler, show the popup
    const over = () => {
        content.style.display = 'block'
        toggler.style.background = 'lightyellow'
        eye    .style.color      = 'lightyellow'
        toggler.style.outline = '1px solid'

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
    out()
    element.appendChild(popup)
    return [eye, popup]
}

/*
 * Ideally should be an inverse for showMark
 */
function hideMark(element) {
    if (!element.classList.contains('promnesia-visited-link')) {
        return
    }
    // NOTE: eyes and popup will be handled by hideMarks, they are attached to the special container
    // only need to deal with the toggler
    const toggler = element.parentElement
    if (!toggler.classList.contains('promnesia-visited-popup-toggler')) {
        console.warning("Expected %o to be the toggler for %o, but couln't find it", toggler, element)
        return
    }
    toggler.replaceWith(element)
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
