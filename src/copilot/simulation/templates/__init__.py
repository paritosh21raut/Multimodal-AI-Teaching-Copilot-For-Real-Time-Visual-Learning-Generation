"""Simulation templates (F-014). Order = detection priority: a more specific scenario first ("a block on an inclined
plane" is the incline, not the block on a horizontal surface)."""
from copilot.simulation.templates import block_on_surface, incline

ALL = (incline.TEMPLATE, block_on_surface.TEMPLATE)
