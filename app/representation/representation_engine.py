"""
Representation Engine

Decides how to visually represent educational content based on:
- Content type (definition, comparison, process, etc.)
- Semantic relations (IS_A, COMPARES, CAUSES, etc.)
- Number of concepts (single vs multiple)
- Presence of examples, comparisons, processes
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from datetime import datetime
import threading

from .representation_models import (
    VisualRepresentation,
    ContentType,
    RepresentationDecision,
)

from app.semantic.semantic_models import (
    SemanticFrame,
    Proposition,
    Relation,
    InstructionalAct,
    InstructionalActType,
    RelationType,
    ConceptRef,
)


class RepresentationEngine:
    """
    Determines the best visual representation for educational content.
    
    Decision rules:
    - IS_A + DEFINITION → definition layout (no visual)
    - COMPARISON signals → comparison_table
    - PROCESS/SEQUENCE → flowchart
    - CAUSES/ENABLES → cause_effect diagram
    - PART_OF/HAS_PART → hierarchy/diagram
    - Multiple examples → example_grid
    - Relations between concepts → concept_map
    - Numeric data → chart
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # Confidence thresholds
        self.min_confidence = 0.5
    
    def decide(
        self,
        frame: SemanticFrame,
        topic: str = "",
    ) -> RepresentationDecision:
        """
        Decide the best visual representation.
        
        Args:
            frame: SemanticFrame with concepts, propositions, relations
            topic: Current topic name
            
        Returns:
            RepresentationDecision
        """
        with self._lock:
            
            # Count signal types
            signals = self._analyze_signals(frame)
            
            # Determine content type
            content_type = self._determine_content_type(signals, frame)
            
            # Determine visual type
            visual_type, confidence, reason, spec = self._determine_visual(
                content_type,
                signals,
                frame,
            )
            
            return RepresentationDecision(
                visual_type=visual_type,
                content_type=content_type,
                confidence=confidence,
                reason=reason,
                visual_spec=spec,
            )
    
    def _analyze_signals(self, frame: SemanticFrame) -> Dict[str, Any]:
        """Analyze signals in the frame"""
        signals = {
            "definition_count": 0,
            "example_count": 0,
            "comparison_count": 0,
            "process_count": 0,
            "cause_effect_count": 0,
            "hierarchy_count": 0,
            "concept_count": len(frame.concepts),
            "proposition_count": len(frame.propositions),
            "relation_count": len(frame.relations),
            "has_numeric_data": False,
        }
        
        # Count instructional acts
        for act in frame.instructional_acts:
            if act.act_type == InstructionalActType.DEFINITION:
                signals["definition_count"] += 1
            elif act.act_type == InstructionalActType.EXAMPLE:
                signals["example_count"] += 1
            elif act.act_type in [InstructionalActType.COMPARISON, InstructionalActType.CONTRAST]:
                signals["comparison_count"] += 1
            elif act.act_type in [InstructionalActType.PROCESS, InstructionalActType.MECHANISM]:
                signals["process_count"] += 1
        
        # Analyze relations
        for relation in frame.relations:
            if relation.relation_type in [RelationType.CAUSES, RelationType.RESULTS_IN]:
                signals["cause_effect_count"] += 1
            elif relation.relation_type in [RelationType.PART_OF, RelationType.HAS_PART]:
                signals["hierarchy_count"] += 1
            elif relation.relation_type in [RelationType.CONTRASTS_WITH, RelationType.SIMILAR_TO]:
                signals["comparison_count"] += 1
        
        # Check for numeric data
        for prop in frame.propositions:
            if prop.quantities:
                signals["has_numeric_data"] = True
                break
        
        return signals
    
    def _determine_content_type(
        self,
        signals: Dict[str, Any],
        frame: SemanticFrame,
    ) -> ContentType:
        """Determine the content type"""
        
        if signals["definition_count"] > 0 and signals["concept_count"] <= 2:
            return ContentType.DEFINITION
        
        if signals["comparison_count"] > 0:
            return ContentType.COMPARISON
        
        if signals["process_count"] > 0:
            return ContentType.PROCESS
        
        if signals["cause_effect_count"] > 0:
            return ContentType.CAUSE_EFFECT
        
        if signals["hierarchy_count"] > 0:
            return ContentType.CLASSIFICATION
        
        if signals["example_count"] > 0:
            return ContentType.EXAMPLES
        
        if signals["has_numeric_data"]:
            return ContentType.DATA
        
        if signals["relation_count"] >= 3:
            return ContentType.RELATIONSHIPS
        
        if signals["proposition_count"] > 0:
            return ContentType.EXPLANATION
        
        return ContentType.MIXED
    
    def _determine_visual(
        self,
        content_type: ContentType,
        signals: Dict[str, Any],
        frame: SemanticFrame,
    ) -> tuple:
        """Determine the best visual representation"""
        
        # Definition → no visual (text is best)
        if content_type == ContentType.DEFINITION:
            return (
                VisualRepresentation.NONE,
                0.85,
                "Definitions are best presented as text",
                {},
            )
        
        # Comparison → comparison_table
        if content_type == ContentType.COMPARISON:
            spec = self._build_comparison_spec(frame)
            return (
                VisualRepresentation.COMPARISON_TABLE,
                0.80,
                "Comparison content is best shown as a table",
                spec,
            )
        
        # Process → flowchart
        if content_type == ContentType.PROCESS:
            spec = self._build_process_spec(frame)
            return (
                VisualRepresentation.FLOWCHART,
                0.80,
                "Process content is best shown as a flowchart",
                spec,
            )
        
        # Cause-Effect → diagram
        if content_type == ContentType.CAUSE_EFFECT:
            spec = self._build_cause_effect_spec(frame)
            return (
                VisualRepresentation.DIAGRAM,
                0.75,
                "Cause-effect relationships are best shown as a diagram",
                spec,
            )
        
        # Classification → hierarchy
        if content_type == ContentType.CLASSIFICATION:
            spec = self._build_hierarchy_spec(frame)
            return (
                VisualRepresentation.HIERARCHY,
                0.75,
                "Classification is best shown as a hierarchy",
                spec,
            )
        
        # Examples → example_grid
        if content_type == ContentType.EXAMPLES:
            spec = self._build_examples_spec(frame)
            return (
                VisualRepresentation.EXAMPLE_GRID,
                0.70,
                "Multiple examples are best shown as a grid",
                spec,
            )
        
        # Data → chart
        if content_type == ContentType.DATA:
            spec = self._build_chart_spec(frame)
            return (
                VisualRepresentation.CHART,
                0.70,
                "Numeric data is best shown as a chart",
                spec,
            )
        
        # Relationships → concept_map
        if content_type == ContentType.RELATIONSHIPS:
            spec = self._build_concept_map_spec(frame)
            return (
                VisualRepresentation.CONCEPT_MAP,
                0.70,
                "Related concepts are best shown as a concept map",
                spec,
            )
        
        # Default → no visual
        return (
            VisualRepresentation.NONE,
            0.60,
            "Text explanation is sufficient",
            {},
        )
    
    def _build_comparison_spec(self, frame: SemanticFrame) -> Dict:
        """Build comparison table spec"""
        concepts = [c.canonical_name for c in frame.concepts[:4]]
        
        # Extract comparison points
        comparison_relations = [
            r for r in frame.relations
            if r.relation_type in [RelationType.CONTRASTS_WITH, RelationType.SIMILAR_TO]
        ]
        
        rows = []
        for relation in comparison_relations[:5]:
            if relation.source and relation.target:
                rows.append({
                    "label": relation.relation_type.value,
                    "values": [
                        relation.source.canonical_name,
                        relation.target.canonical_name,
                    ],
                })
        
        return {
            "columns": concepts[:2] if len(concepts) >= 2 else ["A", "B"],
            "rows": rows,
        }
    
    def _build_process_spec(self, frame: SemanticFrame) -> Dict:
        """Build process flowchart spec"""
        # Extract process steps from propositions
        steps = []
        for prop in frame.propositions:
            if prop.subject and prop.object:
                steps.append(prop.subject.canonical_name)
                steps.append(prop.object.canonical_name)
        
        # Deduplicate preserving order
        unique_steps = []
        for step in steps:
            if step not in unique_steps:
                unique_steps.append(step)
        
        return {
            "nodes": unique_steps[:6],
            "edges": [],
        }
    
    def _build_cause_effect_spec(self, frame: SemanticFrame) -> Dict:
        """Build cause-effect diagram spec"""
        causes = []
        effects = []
        
        for relation in frame.relations:
            if relation.relation_type == RelationType.CAUSES:
                if relation.source and relation.target:
                    causes.append(relation.source.canonical_name)
                    effects.append(relation.target.canonical_name)
        
        return {
            "center": causes[0] if causes else "Cause",
            "components": effects[:5],
            "relationships": list(zip(causes[:5], effects[:5])),
        }
    
    def _build_hierarchy_spec(self, frame: SemanticFrame) -> Dict:
        """Build hierarchy spec"""
        # Find root concept (no parent relation)
        root = frame.concepts[0].canonical_name if frame.concepts else "Root"
        
        levels = []
        current_level = []
        
        for relation in frame.relations:
            if relation.relation_type in [RelationType.PART_OF, RelationType.HAS_PART]:
                if relation.source and relation.target:
                    current_level.append(relation.target.canonical_name)
        
        if current_level:
            levels.append({
                "name": root,
                "children": current_level[:5],
            })
        
        return {
            "root": root,
            "levels": levels,
        }
    
    def _build_examples_spec(self, frame: SemanticFrame) -> Dict:
        """Build examples grid spec"""
        examples = []
        
        for act in frame.instructional_acts:
            if act.act_type == InstructionalActType.EXAMPLE:
                for ref in act.concept_refs[:6]:
                    examples.append(ref.canonical_name)
        
        return {
            "examples": examples,
        }
    
    def _build_chart_spec(self, frame: SemanticFrame) -> Dict:
        """Build chart spec"""
        labels = []
        values = []
        
        for prop in frame.propositions:
            if prop.quantities:
                if prop.subject:
                    labels.append(prop.subject.canonical_name)
                for key, value in prop.quantities.items():
                    values.append(value)
        
        return {
            "chart_type": "bar",
            "x": labels[:6],
            "y": values[:6],
        }
    
    def _build_concept_map_spec(self, frame: SemanticFrame) -> Dict:
        """Build concept map spec"""
        concepts = [c.canonical_name for c in frame.concepts[:6]]
        
        center = concepts[0] if concepts else "Concept"
        
        return {
            "center": center,
            "concepts": concepts[1:],
        }