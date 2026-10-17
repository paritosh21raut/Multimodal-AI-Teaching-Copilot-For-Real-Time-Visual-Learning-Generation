"""Concept Simulation (F-014, V2): parametric simulation templates inside slides. Contract: docs/contracts/simulation-spec.md.

    base       the contract's shared models (SimBase, Playback, labels, derived values) and number formatting
    templates  one module per template: params, solver, lexicon, elements (+ web/sims/<id>.js renders it)
    registry   the template list, the SimulationSpec union, build / re-solve / switch
    values     spoken quantities -> template slots ("5 kg", "thirty degrees", "mu equals 0.2")
    detector   transcript lines -> RepresentationIntent (spoken cue, template setup, values); 0 tokens
    policy     the engine's decision for an intent (show / switch / update / ignore)
"""
