import { runPage } from '../render.js';
import { requireSession } from '../session.js';

runPage(() => requireSession());
