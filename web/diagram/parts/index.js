// The part library's art, keyed by kind (config/diagram_parts.json). A kind with no art draws the unknown part.
import { mech } from "./mech.js";
import { lab, absolute } from "./lab.js";
import { matter } from "./matter.js";
import { shape } from "./shape.js";
import { field, circuit } from "./field.js";
import { motion } from "./motion.js";

export const PARTS = { ...mech, ...lab, ...matter, ...shape, ...field, ...circuit, ...motion };
export const ABSOLUTE = absolute;   // drawn in slide coordinates (a liquid follows its container's inside)
