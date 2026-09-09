"""Debug integration issue"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.presentation.integration import PresentationIntelligence
from app.presentation.slide_decision.slide_decision_engine import SlideDecisionEngine
from app.semantic.semantic_models import (
    SemanticFrame, Concept, ConceptRef, Proposition, 
    InstructionalAct, InstructionalActType, RelationType,
)

# Create test frame
frame = SemanticFrame(chunk_id="test")
frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
frame.propositions.append(Proposition(
    subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
    predicate=RelationType.PROVIDES,
    object=ConceptRef(concept_id="o1", canonical_name="reliability"),
    confidence=0.85,
    evidence_ids=["e1"],
))
frame.instructional_acts.append(InstructionalAct(
    act_type=InstructionalActType.DEFINITION,
    concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
))

pi = PresentationIntelligence()

print("=" * 60)
print("FIRST CALL")
print("=" * 60)
result1 = pi.process(
    frame=frame,
    topic_changed=True,
    current_topic="TCP",
    important_concepts=["TCP"],
)
print(f"Result 1 action: {result1['action'] if result1 else 'None'}")
print(f"Processed chunks: {pi._processed_chunks}")

print("\n" + "=" * 60)
print("SECOND CALL")
print("=" * 60)
result2 = pi.process(
    frame=frame,
    topic_changed=False,
    current_topic="TCP",
    important_concepts=["TCP"],
)
print(f"Result 2 action: {result2['action'] if result2 else 'None'}")
print(f"Processed chunks: {pi._processed_chunks}")

# Check what novelty would be
print("\n" + "=" * 60)
print("NOVELTY CHECK")
print("=" * 60)
novelty = pi._calculate_novelty(frame, ["TCP"])
print(f"Novelty for ['TCP']: {novelty}")
print(f"Processed chunks after: {pi._processed_chunks}")