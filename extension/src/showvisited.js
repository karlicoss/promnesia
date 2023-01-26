// hmm. for some reason esm version isn't properly working with CSS??
// but umd bundle does???
// import tippy from '../node_modules/tippy.js/dist/tippy.esm.js'
// import tippy from '../node_modules/tippy.js/dist/tippy-bundle.umd.js'
// OK, headless is better because it doesn't inject extra CSS
// also not causing issues with unsafe HTML assignment
import tippy from '../node_modules/tippy.js/headless/dist/tippy-headless.esm.js'

// 'API': take
// - link_element: list of <a> DOM elements on the page
// - visited: Map<Url, ?Visit>
// then you can walk through this and decorate as you please
// ideally you just can override/monkey patch showMark and hideMark and rely on showMarks/hideMarks to do the correct thing?


/* NOTE: deliberately not used const because script is injected several times.. */
// NOTE: ideally these class names should be kept as intact as possible to keep backwards compatibility with user CSS
var Cls = {
    VISITED    : 'promnesia-visited'        ,
    POPUP      : 'promnesia-visited-popup'  ,
    POPUP_LINK : 'promnesia-visited-popup-link',
    TIPPY      : 'promnesia-tippy',
    EYE        : 'promnesia-eye',
}


function createLink(href, title) {
    const a = document.createElement('a')
    a.title = title
    a.href  = href
    a.style.color = 'blue' // sometimes parent overrides it?
    a.appendChild(document.createTextNode(title))
    return a
}


function formatVisit(v) {
    // still need outer container cause tippy.js takes in a single html element
    const e = document.createElement('span')
    e.classList.add(Cls.POPUP)

    const {
        original_url: original,
        normalised_url: normalised,
        dt_local    : dt,
        tags        : sources,
        context     : context,
        locator     : locator,
    } = v
    const l_el = document.createElement('span')
    l_el.style.display = 'block'
    l_el.textContent = 'canonical: '
    e.appendChild(l_el)

    const l = createLink(original, normalised)
    l.classList.add(Cls.POPUP_LINK)
    l.title = `original URL: ${original}`
    l_el.appendChild(l) // meh
    // appendText(e, '\n' + l.title) // for debug
    const e_srcs = document.createElement('span')
    e_srcs.style.display = 'block'
    e_srcs.textContent = 'sources : '
    for (const src of sources) {
        const e_src = document.createElement('span')
        e_src.classList.add('src')
        e_src.classList.add(src) // todo sanitize?
        e_src.textContent = src
        e_srcs.appendChild(e_src)
    }
    e.appendChild(e_srcs)
    if (context != null) {
        const e_ctx = document.createElement('span')
        e_ctx.classList.add('context')
        e_ctx.textContent = context
        e.appendChild(e_ctx)
    }
    const {href: href, title: title} = locator || {}
    if (href != null) {
        const llink = createLink(href, title)
        llink.classList.add(Cls.POPUP_LINK)
        e.appendChild(llink)
    }
    const e_at = document.createElement('span')
    e_at.classList.add('datetime')
    e_at.textContent = `${new Date(dt).toLocaleString()}`
    e.appendChild(e_at)
    return e
}



// see https://github.com/karlicoss/promnesia/issues/341#issuecomment-1404338206
// also possibly relevant issue (not merged in popper 2.0 which tippyjs is using though)
// https://github.com/floating-ui/floating-ui/issues/1918
function getGoodTippyParent(element) {
    // contain: layout in the ancestor might cause tooltip boundaries to clip
    // so we want to find the closest parent that doesn't have that as its ancestor
    // ugh I'm pretty sure it will break on some sites...
    // you can see that happening on google.com search page
    let cur = element
    let last = cur
    while (cur != null) {
        const contain = cur.style.contain
        if (contain.includes("layout")) {
            last = cur
        }
        cur = cur.parentElement
    }
    // todo assert last is not none?
    return last
}


// TODO I guess, these snippets could be writable by people? and then they can customize tooltips to their liking
/*
 * So, there are a few requirements from the marks we're trying to achieve here
 * - popups should be togglable (otherwise too spammy if shown by default)
 * - should show some visual hints that the popup is present at all (but shouldn't be too spammy)
 * - shouldn't change links placement in DOM -- that breaks many websites (and kind of annoying)
 * - shouldn't overlay any existing dom elements unless popup was clicked
 * - shouldn't break text selection
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

    const popup = formatVisit(v)
    // TODO try async import??
    try {
        const reference = getGoodTippyParent(element)
        const tip = tippy(reference, {
            render(instance) {
                const popper = document.createElement('div')
                popper.classList.add(Cls.TIPPY)
                const box = document.createElement('div')
                popper.appendChild(box)
                box.appendChild(instance.props.content)
                return {popper}
            },
            content: popup,
            maxWidth: "none",  /* default makes it wrap over */
            interactive: true,  // so it's not hiding on hover

            /* useful for debugging */
            // trigger: "manual",
            // showOnCreate: true,
            // hideOnClick: false,
        })

        // normally tippy sets it itself, but in this case we might attach tippy to one of parents
        // so this is to make sure it hides properly in hideMark
        element._tippy = tip
    } catch (e) {
        console.error('[promnesia]: error while adding tooltip to %o', element)
        console.error(e)
    }

    /* 'boring' link -- mere visit, e.g. from the browser history
    * 'interesting' -- have contexts or something like that
    */
    const boring = v.context == null

    // copy-pasted from 'generate' script.. maybe move to css?
    let baseColor = boring ? '#6666ff' : '#00ff00'
    let baseColorTr = baseColor + '22' // meh

    // eh, could use perhaps? css can match against it..
    // element.setAttribute('data-promnesia-src', src)

    const first = popup.querySelector('.src') // meh
    if (first != null) {
        const extras = Array.from(first.classList).filter(e => e != 'src')
        for (const src of extras) {
            const c = getComputedStyle(document.documentElement).getPropertyValue(`--promnesia-src-${src}-color`)
            if (c != '') {
                baseColor   = c
                baseColorTr = c // TODO not sure what's the right thing to do about this
                break // only use first
            }
        }
    }

    // we're using outline for marks. could also use boxShadow, but outlines extend beyond the element
    // could also use border-image?? but it takes up space :(
    // outline is set in sidebar.css/showvisited.css

    // NOTE hmm, displaying eye icon via :after doesn't seem to work well because it moves page content
    // and all tips I found to display without moving require setting actual element to position: relative... which we don't want to mess with
    // e.g. this https://stackoverflow.com/a/1191519/706389

    const style = element.style

    style.oldOutlineColor = style.outlineColor
    // !important is necessary, otherwise sometimes not working, e.g. google.com search results
    style.setProperty('outline-color',  baseColorTr, 'important')


    if (style.backgroundImage == '') {
        // otherwise do not add eye icon -- this may cause weird artifacts
        // TODO note sure if it's super reliable, e.g. it might have not backgroundImage but somthing else...

        element.classList.add(Cls.EYE)
        // TODO shit. doing this via background sometimes may not work because child element might have its own background???
        // https://developer.mozilla.org/en-US/docs/Web/HTML e.g. on this page
        // you can even see it here
        // even monospace doesn't help?
        // style='fill: color' on svg text doesn't help either
        // https://www.compart.com/en/unicode/U+1F441
        const eyeIcon = `url("data:image/svg+xml;utf8,
<svg xmlns='http://www.w3.org/2000/svg'
 fill='${baseColor.replace('#', '%23')}'
 width='10'
 height='10'>
<text font-size='10' x='0' y='10'>👁</text>
</svg>")`.replaceAll('\n', '')
        style.backgroundImage = eyeIcon
    }
}

/*
 * Ideally should be an inverse for showMark
 */
function hideMark(element) {
    if (!element.classList.contains(Cls.VISITED)) {
        return
    }
    element.classList.remove(Cls.VISITED)

    const style = element.style
    style.outlineColor = style.oldOutlineColor

    if (element.classList.contains(Cls.EYE)) {
        element.classList.remove(Cls.EYE)
        style.backgroundImage = ''
    }

    try {
        element._tippy.destroy()
    } catch (e) {
        console.error('[promnesia]: error while removing tooltip from %o', element)
        console.error(e)
    }
}


function _doMarks(show /* boolean */) {
    // 'link_elements' passed in background.js
    // eslint-disable-next-line no-undef
    const elements = link_elements
    const ONE_GROUP = 20
    for (let i = 0; i < elements.length; i += ONE_GROUP) {
        const group = elements.slice(i, i + ONE_GROUP)
        // not necessary, but bet to process asynchronously to avoid performance issues
        setTimeout(() => {
            for (const link of group) {
                const fn = show ? showMark : hideMark
                try { // best to be defensive here..
                    fn(link)
                } catch (e) {
                    console.error(e)
                }
            }
        })
    }
}


function showMarks() {
    _doMarks(true)
}

function hideMarks() {
    _doMarks(false)
}

// expose for background.js
window.showMarks = showMarks
window.hideMarks = hideMarks

/*
 * I guess the most important thing is that as little layout disturbed when the user isn't showing popups, as possible
 *
 * NOTE: TESTING:
 * see tests/test.html, it's meant to simulate weird complicated webpages to test the logic
 * would be nice to have something automatic...
 * if testing manually, check on
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
 * - superorganizers
 * eh. I guess need to add a warning that some websites might get shifter
 * link to an issue to collect them + suggest to blocklist..
 * TODO or maybe bind to the sidebar?
 */
