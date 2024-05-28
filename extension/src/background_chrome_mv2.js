// hack to support ES moudle background page in chrome with manifest v2
// see https://stackoverflow.com/a/71081597/706389
(async() => {
    await import ('./background.js');
})()
