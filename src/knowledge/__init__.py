"""
Knowledge Graph Module

Implements GraphRAG with Neo4j for financial entity relationships.
"""

from .ontology import (
    Company,
    Sector,
    MacroEvent,
    Person,
    FinancialDoc,
)

__all__ = [
    "Company",
    "Sector",
    "MacroEvent",
    "Person",
    "FinancialDoc",
]
