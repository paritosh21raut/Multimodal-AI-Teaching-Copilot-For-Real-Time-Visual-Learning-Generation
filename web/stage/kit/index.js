// The kit registry: draw functions keyed by catalog id (config/stage_catalog.json); a browser test checks both ways.
import { BACKDROPS } from './backdrops.js';
import { PROPS } from './props.js';
import { SPECIES } from '../animals.js';

export { BACKDROPS, PROPS, SPECIES };
export const kitIds = () => ({ props: Object.keys(PROPS), backdrops: Object.keys(BACKDROPS), species: Object.keys(SPECIES) });
