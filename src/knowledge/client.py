"""
Neo4j Graph Client

Async client for Neo4j Knowledge Graph operations.
Implements CRUD operations for financial entities.
"""
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger("sentinel.knowledge.client")


class Neo4jClient:
    """
    Async Neo4j client for Knowledge Graph operations.
    
    Handles connection management and provides methods for
    creating, querying, and managing graph entities.
    """
    
    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        """
        Initialize the Neo4j client.
        
        Args:
            uri: Neo4j bolt URI (default from settings)
            user: Username (default from settings)
            password: Password (default from settings)
        """
        self.uri = uri or getattr(settings, 'NEO4J_URI', 'bolt://localhost:7687')
        self.user = user or getattr(settings, 'NEO4J_USER', 'neo4j')
        self.password = password or getattr(settings, 'NEO4J_PASSWORD', '')
        
        self._driver = None
    
    async def connect(self) -> bool:
        """
        Establish connection to Neo4j.
        
        Returns:
            True if connection successful
        """
        try:
            from neo4j import AsyncGraphDatabase
            
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
            
            # Test connection
            async with self._driver.session() as session:
                result = await session.run("RETURN 1 as test")
                await result.consume()
            
            logger.info(f"Connected to Neo4j at {self.uri}")
            return True
            
        except ImportError:
            logger.error("neo4j package not installed: pip install neo4j")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False
    
    async def close(self) -> None:
        """Close the connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._driver is not None
    
    async def execute(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result records as dictionaries
        """
        if not self._driver:
            await self.connect()
        
        async with self._driver.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records
    
    # ==========================================================================
    # COMPANY OPERATIONS
    # ==========================================================================
    
    async def create_company(
        self,
        ticker: str,
        name: str,
        **properties: Any,
    ) -> dict[str, Any] | None:
        """
        Create or update a Company node.
        
        Args:
            ticker: Stock ticker symbol
            name: Company name
            **properties: Additional properties
            
        Returns:
            Created/updated node properties
        """
        query = """
        MERGE (c:Company {ticker: $ticker})
        SET c.name = $name,
            c.updated_at = datetime()
        SET c += $properties
        RETURN c
        """
        
        # Filter out None values
        props = {k: v for k, v in properties.items() if v is not None}
        
        results = await self.execute(query, {
            "ticker": ticker,
            "name": name,
            "properties": props,
        })
        
        if results:
            return dict(results[0]["c"])
        return None
    
    async def get_company(self, ticker: str) -> dict[str, Any] | None:
        """Get a Company node by ticker."""
        query = """
        MATCH (c:Company {ticker: $ticker})
        RETURN c
        """
        
        results = await self.execute(query, {"ticker": ticker})
        if results:
            return dict(results[0]["c"])
        return None
    
    async def get_pattaasu_companies(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get all Pattaasu-compliant companies.
        
        Returns:
            List of compliant companies sorted by score
        """
        query = """
        MATCH (c:Company {is_pattaasu_compliant: true})
        RETURN c
        ORDER BY c.pattaasu_score DESC
        LIMIT $limit
        """
        
        results = await self.execute(query, {"limit": limit})
        return [dict(r["c"]) for r in results]
    
    # ==========================================================================
    # SECTOR OPERATIONS
    # ==========================================================================
    
    async def create_sector(
        self,
        name: str,
        **properties: Any,
    ) -> dict[str, Any] | None:
        """Create or update a Sector node."""
        query = """
        MERGE (s:Sector {name: $name})
        SET s.updated_at = datetime()
        SET s += $properties
        RETURN s
        """
        
        props = {k: v for k, v in properties.items() if v is not None}
        
        results = await self.execute(query, {
            "name": name,
            "properties": props,
        })
        
        if results:
            return dict(results[0]["s"])
        return None
    
    async def link_company_to_sector(
        self,
        ticker: str,
        sector_name: str,
    ) -> bool:
        """Create OPERATES_IN relationship between Company and Sector."""
        query = """
        MATCH (c:Company {ticker: $ticker})
        MERGE (s:Sector {name: $sector})
        MERGE (c)-[:OPERATES_IN]->(s)
        RETURN c, s
        """
        
        results = await self.execute(query, {
            "ticker": ticker,
            "sector": sector_name,
        })
        
        return len(results) > 0
    
    # ==========================================================================
    # MACRO EVENT OPERATIONS
    # ==========================================================================
    
    async def create_macro_event(
        self,
        event_type: str,
        title: str,
        **properties: Any,
    ) -> dict[str, Any] | None:
        """Create a MacroEvent node."""
        query = """
        CREATE (e:MacroEvent {
            event_type: $event_type,
            title: $title,
            created_at: datetime()
        })
        SET e += $properties
        RETURN e
        """
        
        props = {k: v for k, v in properties.items() if v is not None}
        
        results = await self.execute(query, {
            "event_type": event_type,
            "title": title,
            "properties": props,
        })
        
        if results:
            return dict(results[0]["e"])
        return None
    
    async def link_event_to_sector(
        self,
        event_title: str,
        sector_name: str,
        impact_severity: str = "Medium",
    ) -> bool:
        """Create IMPACTS relationship between MacroEvent and Sector."""
        query = """
        MATCH (e:MacroEvent {title: $event_title})
        MATCH (s:Sector {name: $sector})
        MERGE (e)-[r:IMPACTS]->(s)
        SET r.severity = $severity
        RETURN e, s
        """
        
        results = await self.execute(query, {
            "event_title": event_title,
            "sector": sector_name,
            "severity": impact_severity,
        })
        
        return len(results) > 0
    
    # ==========================================================================
    # RELATIONSHIP QUERIES
    # ==========================================================================
    
    async def find_supply_chain_risk(
        self,
        ticker: str,
        depth: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Find companies in supply chain with risk exposure.
        
        Args:
            ticker: Starting company ticker
            depth: How many hops in supply chain
            
        Returns:
            List of related companies with relationship info
        """
        query = """
        MATCH path = (c:Company {ticker: $ticker})-[:SUPPLIES_TO*1..%d]-(related:Company)
        RETURN related.ticker as ticker,
               related.name as name,
               length(path) as distance
        ORDER BY distance
        """ % depth
        
        return await self.execute(query, {"ticker": ticker})
    
    async def find_sector_exposure(
        self,
        sector_name: str,
    ) -> dict[str, Any]:
        """
        Get exposure analysis for a sector.
        
        Returns:
            Sector metrics including company count, risks, etc.
        """
        query = """
        MATCH (s:Sector {name: $sector})<-[:OPERATES_IN]-(c:Company)
        OPTIONAL MATCH (e:MacroEvent)-[:IMPACTS]->(s)
        WITH s, 
             count(DISTINCT c) as company_count,
             avg(c.debt_to_equity) as avg_de,
             collect(DISTINCT e.title) as active_events
        RETURN s.name as sector,
               company_count,
               avg_de,
               active_events
        """
        
        results = await self.execute(query, {"sector": sector_name})
        return results[0] if results else {}
    
    # ==========================================================================
    # SCHEMA MANAGEMENT
    # ==========================================================================
    
    async def create_constraints(self) -> None:
        """Create database constraints and indexes."""
        constraints = [
            "CREATE CONSTRAINT company_ticker IF NOT EXISTS FOR (c:Company) REQUIRE c.ticker IS UNIQUE",
            "CREATE CONSTRAINT sector_name IF NOT EXISTS FOR (s:Sector) REQUIRE s.name IS UNIQUE",
            "CREATE INDEX company_pattaasu IF NOT EXISTS FOR (c:Company) ON (c.is_pattaasu_compliant)",
        ]
        
        for constraint in constraints:
            try:
                await self.execute(constraint)
            except Exception as e:
                logger.warning(f"Constraint creation warning: {e}")
    
    async def get_stats(self) -> dict[str, int]:
        """Get node count statistics."""
        query = """
        MATCH (n)
        WITH labels(n) as labels
        UNWIND labels as label
        RETURN label, count(*) as count
        ORDER BY count DESC
        """
        
        results = await self.execute(query)
        return {r["label"]: r["count"] for r in results}
    
    # Context manager support
    async def __aenter__(self) -> "Neo4jClient":
        await self.connect()
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        await self.close()


# Singleton-ish access
_client: Neo4jClient | None = None


async def get_neo4j_client() -> Neo4jClient:
    """Get or create the Neo4j client."""
    global _client
    if _client is None:
        _client = Neo4jClient()
        await _client.connect()
    return _client
