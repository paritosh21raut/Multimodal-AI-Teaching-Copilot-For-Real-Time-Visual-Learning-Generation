"""Simulation templates (F-014). Order = detection priority: a more specific scenario first ("a block on an inclined
plane" is the incline, not the block on a horizontal surface). S3: the process templates (discrete steps) after the
motion templates."""
from copilot.simulation.templates import (
    block_on_surface, bohr_atom, dc_circuit, heart, incline, neutralisation, orbit, pendulum, photosynthesis,
    projectile, unit_circle, water_cycle, wave,
)

ALL = (incline.TEMPLATE, block_on_surface.TEMPLATE, pendulum.TEMPLATE, projectile.TEMPLATE,
       dc_circuit.TEMPLATE, wave.TEMPLATE, orbit.TEMPLATE,
       unit_circle.TEMPLATE,
       water_cycle.TEMPLATE, heart.TEMPLATE, photosynthesis.TEMPLATE, bohr_atom.TEMPLATE,
       neutralisation.TEMPLATE)
