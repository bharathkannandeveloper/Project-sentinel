"""
FIBO-Based Financial Ontology for Neo4j

Defines the node and relationship types for the Knowledge Graph,
aligned with the Financial Industry Business Ontology (FIBO).
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class RelationshipType(str, Enum):
    """Relationship types in the knowledge graph."""
    OPERATES_IN = "OPERATES_IN"        # Company -> Sector
    COMPETES_WITH = "COMPETES_WITH"    # Company <-> Company
    SUPPLIES_TO = "SUPPLIES_TO"        # Company -> Company
    MANAGED_BY = "MANAGED_BY"          # Company -> Person
    IMPACTS = "IMPACTS"                # MacroEvent -> Sector
    OCCURRED_IN = "OCCURRED_IN"        # MacroEvent -> Region
    MENTIONS = "MENTIONS"              # FinancialDoc -> Company
    DISCLOSES = "DISCLOSES"            # FinancialDoc -> Risk


class EventType(str, Enum):
    """Types of macroeconomic events."""
    WAR = "War"
    RATE_HIKE = "RateHike"
    RATE_CUT = "RateCut"
    TARIFF = "Tariff"
    PANDEMIC = "Pandemic"
    REGULATION = "Regulation"
    SUPPLY_SHOCK = "SupplyShock"
    NATURAL_DISASTER = "NaturalDisaster"


class Severity(str, Enum):
    """Event severity levels."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class PersonRole(str, Enum):
    """Executive roles."""
    CEO = "CEO"
    CFO = "CFO"
    CTO = "CTO"
    COO = "COO"
    CHAIRMAN = "Chairman"
    DIRECTOR = "Director"
    PROMOTER = "Promoter"


class DocumentType(str, Enum):
    """Financial document types."""
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    ANNUAL_REPORT = "AnnualReport"
    EARNINGS_CALL = "EarningsCall"
    NEWS_ARTICLE = "NewsArticle"


@dataclass
class BaseNode:
    """Base class for graph nodes."""
    _id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Neo4j."""
        d = {}
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
            if isinstance(value, Decimal):
                d[key] = float(value)
            elif isinstance(value, datetime):
                d[key] = value.isoformat()
            elif isinstance(value, Enum):
                d[key] = value.value
            else:
                d[key] = value
        return d
    
    @property
    def label(self) -> str:
        """Return the Neo4j node label."""
        return self.__class__.__name__


@dataclass
class Company(BaseNode):
    """
    Company node representing a legal business entity.
    
    FIBO: fibo-be-le-lp:LegalPerson
    """
    ticker: str = ""
    cik: str | None = None
    name: str = ""
    description: str = ""
    
    # Financial metrics
    market_cap: Decimal = Decimal("0")
    pe_ratio: Decimal | None = None
    debt_to_equity: Decimal | None = None
    
    # Pattaasu metrics
    is_pattaasu_compliant: bool = False
    pattaasu_score: Decimal = Decimal("0")
    
    # Metadata
    sector: str = ""
    industry: str = ""
    country: str = "US"
    exchange: str = ""


@dataclass
class Sector(BaseNode):
    """
    Sector node for industry classification.
    """
    name: str = ""
    sic_code: str | None = None
    
    # Aggregated metrics
    avg_pe: Decimal | None = None
    avg_de: Decimal | None = None
    growth_rate: Decimal | None = None
    company_count: int = 0


@dataclass
class MacroEvent(BaseNode):
    """
    Macroeconomic event that impacts markets.
    """
    event_type: EventType = EventType.REGULATION
    title: str = ""
    description: str = ""
    event_date: datetime | None = None
    severity: Severity = Severity.MEDIUM
    
    # Geographic scope
    region: str = ""
    is_global: bool = False
    
    # Impact assessment
    expected_duration_days: int | None = None
    affected_sectors: list[str] = field(default_factory=list)


@dataclass
class Person(BaseNode):
    """
    Person node for executives and key individuals.
    """
    name: str = ""
    role: PersonRole = PersonRole.DIRECTOR
    
    # Career history encoded as structured data
    current_company: str | None = None
    track_record: str = ""
    
    # Metrics
    tenure_years: float | None = None
    compensation: Decimal | None = None


@dataclass
class FinancialDoc(BaseNode):
    """
    Financial document node for SEC filings and reports.
    """
    doc_type: DocumentType = DocumentType.FORM_10K
    title: str = ""
    url: str = ""
    
    # Filing info
    filing_date: datetime | None = None
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    
    # Content metadata
    page_count: int | None = None
    has_risk_factors: bool = False
    has_mda: bool = False  # Management Discussion & Analysis
    
    # Associated company
    company_ticker: str = ""
    company_cik: str | None = None


# =============================================================================
# Neo4j SCHEMA CONSTRAINTS
# =============================================================================

NEO4J_CONSTRAINTS = """
// Unique constraints
CREATE CONSTRAINT company_ticker IF NOT EXISTS FOR (c:Company) REQUIRE c.ticker IS UNIQUE;
CREATE CONSTRAINT company_cik IF NOT EXISTS FOR (c:Company) REQUIRE c.cik IS UNIQUE;
CREATE CONSTRAINT sector_name IF NOT EXISTS FOR (s:Sector) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT doc_url IF NOT EXISTS FOR (d:FinancialDoc) REQUIRE d.url IS UNIQUE;

// Indexes for common queries
CREATE INDEX company_pattaasu IF NOT EXISTS FOR (c:Company) ON (c.is_pattaasu_compliant);
CREATE INDEX company_sector IF NOT EXISTS FOR (c:Company) ON (c.sector);
CREATE INDEX event_type IF NOT EXISTS FOR (e:MacroEvent) ON (e.event_type);
CREATE INDEX event_severity IF NOT EXISTS FOR (e:MacroEvent) ON (e.severity);
CREATE INDEX doc_type IF NOT EXISTS FOR (d:FinancialDoc) ON (d.doc_type);
"""

NEO4J_EXAMPLE_QUERIES = """
// Find all Pattaasu-compliant companies in a sector
MATCH (c:Company {is_pattaasu_compliant: true})-[:OPERATES_IN]->(s:Sector {name: $sector})
RETURN c ORDER BY c.pattaasu_score DESC

// Find supply chain risk from macro event
MATCH (e:MacroEvent {event_type: 'SupplyShock'})-[:IMPACTS]->(s:Sector)<-[:OPERATES_IN]-(c:Company)
RETURN c.ticker, c.name, s.name, e.title

// Find companies with common suppliers (contagion risk)
MATCH (c1:Company)-[:SUPPLIES_TO]->(supplier:Company)<-[:SUPPLIES_TO]-(c2:Company)
WHERE c1 <> c2
RETURN c1.ticker, c2.ticker, supplier.ticker, COUNT(*) as common_suppliers

// Find management track record
MATCH (p:Person)-[:MANAGED_BY]-(c:Company)
RETURN p.name, p.role, COLLECT(c.ticker) as companies

// Find recent filings mentioning risks
MATCH (d:FinancialDoc {has_risk_factors: true})-[:MENTIONS]->(c:Company)
WHERE d.filing_date > date() - duration('P30D')
RETURN c.ticker, d.title, d.filing_date
"""
