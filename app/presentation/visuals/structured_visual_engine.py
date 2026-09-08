"""
Structured Visual Engine

Creates visual specifications for native PPT rendering.
Handles: flowchart, comparison table, hierarchy, timeline, concept map.

The engine produces STRUCTURED DATA (not rendered shapes).
The renderer consumes these specs to draw actual PPT shapes.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
import threading

from app.presentation.models.presentation_models import (
    RepresentationType,
    SlidePlan,
    ContentBlock,
    ContentBlockType,
)


class StructuredVisualEngine:
    """
    Creates structured visual specs for different representation types.
    
    Each visual type has a specific data contract:
    - Flowchart: nodes + edges
    - Comparison: columns + rows
    - Hierarchy: root + levels
    - Timeline: events
    - Concept Map: center + related concepts
    """
    
    def __init__(self):
        self._lock = threading.RLock()
    
    def build_visual_spec(
        self,
        plan: SlidePlan,
    ) -> Optional[Dict[str, Any]]:
        """
        Build visual spec from slide plan.
        
        Args:
            plan: SlidePlan with representation and content blocks
            
        Returns:
            Visual spec dict or None if no visual needed
        """
        with self._lock:
            if not plan.representation:
                return None
            
            rep_type = plan.representation.representation_type
            
            builders = {
                RepresentationType.FLOWCHART: self._build_flowchart,
                RepresentationType.COMPARISON: self._build_comparison,
                RepresentationType.CONTRAST: self._build_contrast,
                RepresentationType.HIERARCHY: self._build_hierarchy,
                RepresentationType.TIMELINE: self._build_timeline,
                RepresentationType.CONCEPT_MAP: self._build_concept_map,
                RepresentationType.CAUSAL_CHAIN: self._build_causal_chain,
                RepresentationType.PROCESS: self._build_process,
                RepresentationType.EXAMPLE_GRID: self._build_example_grid,
                RepresentationType.SYSTEM_DIAGRAM: self._build_system_diagram,
                RepresentationType.ARCHITECTURE_DIAGRAM: self._build_architecture,
            }
            
            builder = builders.get(rep_type)
            if builder:
                return builder(plan)
            
            return None
    
    def _extract_relations(self, plan: SlidePlan) -> List[Dict[str, str]]:
        """Extract relations from content blocks"""
        relations = []
        
        for block in plan.content_blocks:
            if block.block_type == ContentBlockType.EXPLANATION:
                # Try to parse "A RELATION B" pattern
                parts = block.text.split()
                if len(parts) >= 3:
                    relations.append({
                        "source": parts[0],
                        "relation": parts[1],
                        "target": parts[2],
                    })
        
        return relations
    
    def _build_flowchart(self, plan: SlidePlan) -> Dict[str, Any]:
        """Build flowchart spec"""
        nodes = []
        edges = []
        
        # Extract process steps from content blocks
        for block in plan.content_blocks:
            if block.block_type in [ContentBlockType.EXPLANATION, ContentBlockType.PROCESS_STEP]:
                text = block.text.strip()
                if text and text not in nodes:
                    nodes.append(text)
        
        # If no process steps, use semantic units
        if not nodes:
            nodes = [block.text for block in plan.content_blocks if block.text]
        
        # Build edges (sequential)
        for i in range(len(nodes) - 1):
            edges.append([nodes[i], nodes[i + 1]])
        
        return {
            "type": "flowchart",
            "nodes": nodes[:6],
            "edges": edges[:5],
        }
    
    def _build_comparison(self, plan: SlidePlan) -> Dict[str, Any]:
        """Build comparison table spec"""
        # Extract comparison relations
        relations = self._extract_relations(plan)
        
        # Determine columns (unique sources + targets)
        sources = []
        targets = []
        
        for rel in relations:
            if rel["source"] not in sources:
                sources.append(rel["source"])
            if rel["target"] not in targets:
                targets.append(rel["target"])
        
        columns = sources[:2] if len(sources) >= 2 else ["A", "B"]
        
        # Build rows from relations
        rows = []
        for rel in relations[:5]:
            rows.append({
                "label": rel["relation"],
                "values": [rel["source"], rel["target"]],
            })
        
        return {
            "type": "comparison_table",
            "columns": columns,
            "rows": rows,
        }
    
    def _build_contrast(self, plan: SlidePlan) -> Dict[str, Any]:
        """Build contrast (two-column) spec"""
        relations = self._extract_relations(plan)
        
        left_items = []
        right_items = []
        
        for rel in relations:
            if rel["relation"].lower() in ["contrasts", "unlike", "whereas"]:
                left_items.append(rel["source"])
                right_items.append(rel["target"])
        
        return {
            "type": "contrast",
            "left_title": left_items[0] if left_items else "Concept A",
            "right_title": right_items[0] if right_items else "Concept B",
            "left_items": left_items[1:] if left_items else [],
            "right_items": right_items[1:] if right_items else [],
        }
    
    def _build_hierarchy(self, plan: SlidePlan) -> Dict[str, Any]:
        """Build hierarchy spec"""
        relations = self._extract_relations(plan)
        
        # Find root (source that is never a target)
        sources = {r["source"] for r in relations}
        targets = {r["target"] for r in relations}
        
        roots = sources - targets
        root = list(roots)[0] if roots else "Root"
        
        # Build levels
        levels = []
        children_by_parent = {}
        
        for rel in relations:
            parent = rel["source"]
            child = rel["target"]
            if parent not in children_by_parent:
                children_by_parent[parent] = []
            children_by_parent[parent].append(child)
        
        # First level children of root
        if root in children_by_parent:
            levels.append({
                "name": root,
                "children": children_by_parent[root][:5],
            })
            
            # Second level
            for child in children_by_parent[root][:3]:
                if child in children_by_parent:
                    levels.append({
                        "name": child,
                        "children": children_by_parent[child][:3],
                    })
        
        return {
            "type": "hierarchy",
            "root": root,
            "levels": levels,
        }
    
    def _build_timeline(self, plan: SlidePlan) -> Dict[str, Any]:
        """Build timeline spec"""
        events = []
        
        for block in plan.content_blocks:
            if block.text and block.block_type in [ContentBlockType.PROCESS_STEP, ContentBlockType.EXPLANATION]:
                events.append(block.text)
        
        return {
            "type": "timeline",
            "events": events[:6],
        }
    
    def _build_concept_map(self, plan: SlidePlan) -> Dict[str, Any]:
        """Build concept map spec"""
        relations = self._extract_relations(plan)
        
        concepts = []
        for rel in relations:
            if rel["source"] not in concepts:
                concepts.append(rel["source"])
            if rel["target"] not in concepts:
                concepts.append(rel["target"])
        
        center = concepts[0] if concepts else "Concept"
        
        return {
            "type": "concept_map",
            "center": center,
            "concepts": concepts[1:6],
            "relations": relations[:5],
        }
    
    def _build_causal_chain(self, plan: SlidePlan) -> Dict[str, Any]:
        """Build causal chain spec"""
        relations = self._extract_relations(plan)
        
        chain = []
        for rel in relations:
            if rel["relation"].lower() in ["causes", "results_in", "leads_to"]:
                chain.append(rel["source"])
                chain.append(rel["target"])
        
        # Deduplicate preserving order
        unique_chain = []
        for item in chain:
            if item not in unique_chain:
                unique_chain.append(item)
        
        return {
            "type": "causal_chain",
            "chain": unique_chain[:6],
        }
    
    def _build_process(self, plan: SlidePlan) -> Dict[str, Any]:
        """Build process spec (similar to flowchart)"""
        return self._build_flowchart(plan)
    
    def _build_example_grid(self, plan: SlidePlan) -> Dict[str, Any]:
        """Build example grid spec"""
        examples = []
        
        for block in plan.content_blocks:
            if block.block_type == ContentBlockType.EXAMPLE:
                examples.append(block.text)
        
        return {
            "type": "example_grid",
            "examples": examples[:6],
        }
    
    def _build_system_diagram(self, plan: SlidePlan) -> Dict[str, Any]:
        """Build system diagram spec"""
        relations = self._extract_relations(plan)
        
        components = []
        for rel in relations:
            if rel["source"] not in components:
                components.append(rel["source"])
            if rel["target"] not in components:
                components.append(rel["target"])
        
        center = plan.focal_message.split()[0] if plan.focal_message else "System"
        
        return {
            "type": "system_diagram",
            "center": center,
            "components": components[:6],
            "relationships": [(r["source"], r["target"]) for r in relations[:5]],
        }
    
    def _build_architecture(self, plan: SlidePlan) -> Dict[str, Any]:
        """Build architecture diagram spec"""
        return self._build_system_diagram(plan)