"""
Graph Builder

Populates the Knowledge Graph with financial entities extracted from data.
Integrates with LLM for entity extraction and relationship inference.
"""
import logging
from decimal import Decimal
from typing import Any

from .client import Neo4jClient, get_neo4j_client
from .ontology import Company, Sector, MacroEvent

logger = logging.getLogger("sentinel.knowledge.builder")


class GraphBuilder:
    """
    Builds and populates the Knowledge Graph.
    
    Transforms financial data into graph nodes and relationships.
    Uses LLM for entity extraction when available.
    """
    
    def __init__(
        self,
        client: Neo4jClient | None = None,
        llm_manager: Any | None = None,
    ) -> None:
        """
        Initialize the graph builder.
        
        Args:
            client: Neo4j client (creates one if not provided)
            llm_manager: Optional LLM manager for entity extraction
        """
        self._client = client
        self.llm_manager = llm_manager
    
    async def _get_client(self) -> Neo4jClient:
        """Get Neo4j client."""
        if self._client is None:
            self._client = await get_neo4j_client()
        return self._client
    
    async def initialize_schema(self) -> None:
        """Create constraints and indexes."""
        client = await self._get_client()
        await client.create_constraints()
        logger.info("Graph schema initialized")
    
    async def ingest_company(
        self,
        ticker: str,
        financial_data: dict[str, Any],
        profile: dict[str, Any] | None = None,
    ) -> Company | None:
        """
        Ingest a company and its relationships into the graph.
        
        Args:
            ticker: Stock ticker symbol
            financial_data: Financial metrics from fetchers
            profile: Optional company profile
            
        Returns:
            Created Company node
        """
        client = await self._get_client()
        
        # Calculate Pattaasu compliance
        is_compliant = self._check_pattaasu_compliance(financial_data)
        pattaasu_score = self._calculate_pattaasu_score(financial_data)
        
        # Create company node
        company_data = await client.create_company(
            ticker=ticker,
            name=financial_data.get("company_name", ticker),
            sector=profile.get("sector", "") if profile else financial_data.get("sector", ""),
            industry=profile.get("industry", "") if profile else financial_data.get("industry", ""),
            debt_to_equity=float(financial_data.get("debt_to_equity", 0) or 0),
            pe_ratio=float(financial_data.get("pe_ratio", 0) or 0) if financial_data.get("pe_ratio") else None,
            is_pattaasu_compliant=is_compliant,
            pattaasu_score=float(pattaasu_score),
        )
        
        if not company_data:
            return None
        
        # Link to sector if available
        sector = profile.get("sector") if profile else financial_data.get("sector")
        if sector:
            await client.create_sector(name=sector)
            await client.link_company_to_sector(ticker, sector)
        
        return Company(
            ticker=ticker,
            name=company_data.get("name", ""),
            sector=sector or "",
            is_pattaasu_compliant=is_compliant,
            pattaasu_score=Decimal(str(pattaasu_score)),
        )
    
    async def ingest_macro_event(
        self,
        event_type: str,
        title: str,
        description: str = "",
        affected_sectors: list[str] | None = None,
        severity: str = "Medium",
    ) -> MacroEvent | None:
        """
        Ingest a macroeconomic event and link to affected sectors.
        
        Args:
            event_type: Type of event (War, RateHike, Tariff, etc.)
            title: Event title
            description: Event description
            affected_sectors: List of affected sector names
            severity: Event severity level
            
        Returns:
            Created MacroEvent node
        """
        client = await self._get_client()
        
        # Create event node
        event_data = await client.create_macro_event(
            event_type=event_type,
            title=title,
            description=description,
            severity=severity,
        )
        
        if not event_data:
            return None
        
        # Link to affected sectors
        if affected_sectors:
            for sector_name in affected_sectors:
                await client.create_sector(name=sector_name)
                await client.link_event_to_sector(title, sector_name, severity)
        
        from .ontology import EventType, Severity
        
        return MacroEvent(
            event_type=EventType(event_type),
            title=title,
            description=description,
            severity=Severity(severity),
            affected_sectors=affected_sectors or [],
        )
    
    async def extract_entities_from_text(
        self,
        text: str,
        context: str = "financial",
    ) -> list[dict[str, Any]]:
        """
        Use LLM to extract entities from text.
        
        Args:
            text: Text to extract entities from (e.g., 10-K MD&A)
            context: Type of text for extraction
            
        Returns:
            List of extracted entities with types
        """
        if not self.llm_manager:
            logger.warning("No LLM manager available for entity extraction")
            return []
        
        prompt = f"""Extract financial entities from the following text.

Context: {context}
Text: {text[:5000]}  # Limit to avoid token overflow

Output as JSON array with format:
[
  {{"type": "Company|Person|Event|Risk", "name": "...", "attributes": {{...}}}}
]

Only output the JSON array, nothing else."""

        try:
            response = await self.llm_manager.complete(
                prompt=prompt,
                temperature=0.1,
                max_tokens=2000,
            )
            
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            return []
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []
    
    def _check_pattaasu_compliance(self, data: dict[str, Any]) -> bool:
        """Check if company meets Pattaasu criteria."""
        try:
            de = Decimal(str(data.get("debt_to_equity", 99) or 99))
            pledging = Decimal(str(data.get("promoter_pledging_pct", 100) or 0))
            fcf1 = Decimal(str(data.get("free_cash_flow_year1", 0) or 0))
            fcf2 = Decimal(str(data.get("free_cash_flow_year2", 0) or 0))
            fcf3 = Decimal(str(data.get("free_cash_flow_year3", 0) or 0))
            
            return (
                de < Decimal("1.0") and
                pledging == Decimal("0") and
                fcf1 > 0 and fcf2 > 0 and fcf3 > 0
            )
        except Exception:
            return False
    
    def _calculate_pattaasu_score(self, data: dict[str, Any]) -> Decimal:
        """Calculate Pattaasu compliance score (0-100)."""
        score = Decimal("0")
        
        try:
            de = Decimal(str(data.get("debt_to_equity", 99) or 99))
            
            # Debt score (max 30)
            if de == 0:
                score += Decimal("30")
            elif de < Decimal("0.1"):
                score += Decimal("25")
            elif de < Decimal("0.3"):
                score += Decimal("20")
            elif de < Decimal("0.5"):
                score += Decimal("15")
            elif de < Decimal("1.0"):
                score += Decimal("10")
            
            # Pledging score (max 25)
            pledging = Decimal(str(data.get("promoter_pledging_pct", 100) or 0))
            if pledging == 0:
                score += Decimal("25")
            
            # FCF score (max 25)
            fcf1 = Decimal(str(data.get("free_cash_flow_year1", 0) or 0))
            fcf2 = Decimal(str(data.get("free_cash_flow_year2", 0) or 0))
            fcf3 = Decimal(str(data.get("free_cash_flow_year3", 0) or 0))
            
            positive_years = sum([1 for f in [fcf1, fcf2, fcf3] if f > 0])
            score += Decimal(str(positive_years * 8))  # ~8 per year
            
            # PE ratio sanity (max 20)
            pe = data.get("pe_ratio")
            if pe and Decimal(str(pe)) > 0:
                if Decimal(str(pe)) < Decimal("25"):
                    score += Decimal("20")
                elif Decimal(str(pe)) < Decimal("50"):
                    score += Decimal("10")
            
        except Exception as e:
            logger.warning(f"Score calculation error: {e}")
        
        return min(score, Decimal("100"))
