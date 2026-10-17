"""Simulation templates (F-014). Order = detection priority: a more specific scenario first ("a block on an inclined
plane" is the incline, not the block on a horizontal surface)."""
from copilot.simulation.templates import block_on_surface, dc_circuit, incline, orbit, pendulum, projectile, unit_circle, wave

ALL = (incline.TEMPLATE, block_on_surface.TEMPLATE, pendulum.TEMPLATE, projectile.TEMPLATE,
       dc_circuit.TEMPLATE, wave.TEMPLATE, orbit.TEMPLATE,
       unit_circle.TEMPLATE)
