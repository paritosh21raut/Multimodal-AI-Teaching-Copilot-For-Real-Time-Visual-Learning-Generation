"""Simulation templates (F-014). Order = detection priority: a more specific scenario first ("a block on an inclined
plane" is the incline, not the block on a horizontal surface). S3: the process templates (discrete steps) after the
motion templates."""
from copilot.simulation.templates import (
    block_on_surface, bohr_atom, dc_circuit, heart, incline, neutralisation, orbit, pendulum, photosynthesis,
    gas_piston, pn_junction, projectile, refraction, rlc_ac, rlc_transient, routing, tcp, thin_lens, unit_circle, water_cycle, wave,
)

ALL = (incline.TEMPLATE, block_on_surface.TEMPLATE, pendulum.TEMPLATE, projectile.TEMPLATE,
       rlc_transient.TEMPLATE, rlc_ac.TEMPLATE,  # S4: before the DC circuit ("an RLC circuit with a battery")
       pn_junction.TEMPLATE,  # S4: before the DC circuit ("a diode connected to a battery")
       dc_circuit.TEMPLATE, wave.TEMPLATE, orbit.TEMPLATE,
       unit_circle.TEMPLATE,
       water_cycle.TEMPLATE, heart.TEMPLATE, photosynthesis.TEMPLATE, bohr_atom.TEMPLATE,
       neutralisation.TEMPLATE,
       routing.TEMPLATE, tcp.TEMPLATE,  # S4: networks (routing: steps from the values; TCP: an event schedule)
       thin_lens.TEMPLATE, refraction.TEMPLATE,  # S4: optics (a lens before refraction: "light refracts in a lens")
       gas_piston.TEMPLATE)  # S4: an ideal gas
