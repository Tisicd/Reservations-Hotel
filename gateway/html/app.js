import { boot } from './js/screens.js';
import { initRouter } from './js/router.js';
import { initDemo } from './js/demo.js';
import { initAuth } from './js/auth.js';

boot();
initAuth();
initRouter();
initDemo();
