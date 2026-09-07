"""
Relation Normalization

Normalizes extracted relations to controlled vocabulary.
Ensures no arbitrary relation labels enter canonical graph.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
import re

from .semantic_models import RelationType


class RelationNormalizer:
    """Normalizes relation types to controlled vocabulary"""
    
    # Mapping of common verbs to canonical relation types
    VERB_TO_RELATION = {
        "is": RelationType.IS_A,
        "are": RelationType.IS_A,
        "was": RelationType.IS_A,
        "were": RelationType.IS_A,
        "means": RelationType.DEFINED_AS,
        "defined": RelationType.DEFINED_AS,
        "refers": RelationType.DEFINED_AS,
        "provides": RelationType.PROVIDES,
        "offers": RelationType.PROVIDES,
        "delivers": RelationType.PROVIDES,
        "enables": RelationType.ENABLES,
        "allows": RelationType.ENABLES,
        "uses": RelationType.USES,
        "using": RelationType.USES,
        "utilizes": RelationType.USES,
        "requires": RelationType.REQUIRES,
        "needs": RelationType.REQUIRES,
        "depends": RelationType.DEPENDS_ON,
        "causes": RelationType.CAUSES,
        "results": RelationType.RESULTS_IN,
        "leads": RelationType.RESULTS_IN,
        "contains": RelationType.HAS_PART,
        "includes": RelationType.HAS_PART,
        "consists": RelationType.HAS_PART,
        "has": RelationType.HAS_ATTRIBUTE,
        "have": RelationType.HAS_ATTRIBUTE,
        "connects": RelationType.CONNECTS_TO,
        "measures": RelationType.MEASURED_BY,
        "precedes": RelationType.PRECEDES,
        "follows": RelationType.FOLLOWS,
        "contrasts": RelationType.CONTRASTS_WITH,
    }
    
    # Valid relation types (controlled vocabulary)
    VALID_RELATIONS = set(RelationType)
    
    def normalize(self, relation_type: RelationType) -> Optional[RelationType]:
        """
        Normalize relation type to controlled vocabulary.
        
        Returns None if relation is not in controlled vocabulary.
        """
        if relation_type in self.VALID_RELATIONS:
            return relation_type
        
        return None
    
    def normalize_from_verb(self, verb: str) -> Optional[RelationType]:
        """
        Convert a verb to canonical relation type.
        
        Returns None if verb doesn't map to a known relation.
        """
        verb_lower = verb.lower()
        
        # Check exact match
        if verb_lower in self.VERB_TO_RELATION:
            return self.VERB_TO_RELATION[verb_lower]
        
        # Check for word stems
        for key, relation in self.VERB_TO_RELATION.items():
            if verb_lower.startswith(key) or key.startswith(verb_lower):
                return relation
        
        return None
    
    def validate_relation(self, relation_type: RelationType) -> bool:
        """Check if relation type is valid"""
        return relation_type in self.VALID_RELATIONS
    
    def get_all_valid_relations(self) -> list:
        """Get list of all valid relation types"""
        return list(self.VALID_RELATIONS)