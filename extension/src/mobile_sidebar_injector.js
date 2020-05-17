/* @flow */
import {getActiveTab, injectSidebar} from './background';


window.onload = async () => {
    // ok, on android it seem to retrieve the page we came from, as we want here
    const atab = await getActiveTab();
    await injectSidebar(atab);

    // VVV don't this this works unless window was created dynamically
    // window.close();
};
