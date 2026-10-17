"""The words that name a slot in speech (base.Slot.names, used by simulation.values.resolve), shared by templates.

They include the forms Whisper writes for them ("co-efficient", "coefficient of fiction", "fictional coefficient",
"mew"). A name alone sets nothing: it says which slot a value said without a unit belongs to ("the pushing force is
50"), which slot a later bare number belongs to ("make it 30"), and the target of "double the mass".
"""
from copilot.simulation.values import MU_NAMES

MASS = r"mass|masses|block'?s mass"
# the push / pull: "the pushing force", "applied force", "force applied", "the push", "effort"; a bare "force" is the
# push too, except after a result word (values._RESULT: "the friction force", "the net force")
FORCE = (r"push(?:ing)?\s+force|pull(?:ing)?\s+force|applied\s+force|force\s+applied|external\s+force|"
         r"the\s+push|the\s+pull|push|pull|effort|force")
MU = MU_NAMES
G = r"g|gravity|acceleration\s+due\s+to\s+gravity|value\s+of\s+g"
ANGLE = r"angle(?:\s+of\s+(?:inclination|the\s+(?:incline|slope|plane|ramp)))?|inclination(?:\s+angle)?|theta|θ"
