"""
WebSocket Consumers for Real-Time Updates

Implements Django Channels consumers for streaming market data
and analysis updates to the dashboard.
"""
import json
import logging
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("sentinel.dashboard.consumers")


class MarketDataConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time market data streaming.
    
    Clients connect to receive live updates on:
    - Stock prices
    - Volume changes
    - Market indices
    """
    
    async def connect(self) -> None:
        """Handle WebSocket connection."""
        self.room_group_name = "market_data"
        
        # Join the market data group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"Client connected to market data stream: {self.channel_name}")
        
        # Send initial status
        await self.send_json({
            "type": "connection",
            "status": "connected",
            "stream": "market_data",
        })
    
    async def disconnect(self, close_code: int) -> None:
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"Client disconnected: {self.channel_name}")
    
    async def receive(self, text_data: str) -> None:
        """Handle messages from client."""
        try:
            data = json.loads(text_data)
            action = data.get("action")
            
            if action == "subscribe":
                tickers = data.get("tickers", [])
                await self.subscribe_tickers(tickers)
            elif action == "unsubscribe":
                tickers = data.get("tickers", [])
                await self.unsubscribe_tickers(tickers)
            elif action == "ping":
                await self.send_json({"type": "pong"})
                
        except json.JSONDecodeError:
            await self.send_json({
                "type": "error",
                "message": "Invalid JSON",
            })
    
    async def subscribe_tickers(self, tickers: list[str]) -> None:
        """Subscribe to ticker updates."""
        # TODO: Implement ticker subscription
        await self.send_json({
            "type": "subscribed",
            "tickers": tickers,
        })
    
    async def unsubscribe_tickers(self, tickers: list[str]) -> None:
        """Unsubscribe from ticker updates."""
        await self.send_json({
            "type": "unsubscribed",
            "tickers": tickers,
        })
    
    async def market_update(self, event: dict[str, Any]) -> None:
        """
        Handle market update message from channel layer.
        
        Called when the backend pushes a market update.
        """
        await self.send_json(event["data"])
    
    async def send_json(self, data: dict[str, Any]) -> None:
        """Send JSON data to client."""
        await self.send(text_data=json.dumps(data))


class AnalysisConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for analysis progress and results.
    
    Streams:
    - Pattaasu analysis progress
    - LLM responses
    - Task completion status
    """
    
    async def connect(self) -> None:
        """Handle WebSocket connection."""
        self.room_group_name = "analysis"
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"Analysis consumer connected: {self.channel_name}")
        
        await self.send_json({
            "type": "connection",
            "status": "connected",
            "stream": "analysis",
        })
    
    async def disconnect(self, close_code: int) -> None:
        """Handle disconnection."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data: str) -> None:
        """Handle client messages."""
        try:
            data = json.loads(text_data)
            action = data.get("action")
            
            if action == "analyze":
                ticker = data.get("ticker")
                if ticker:
                    await self.start_analysis(ticker)
            elif action == "status":
                task_id = data.get("task_id")
                if task_id:
                    await self.check_status(task_id)
                    
        except json.JSONDecodeError:
            await self.send_json({
                "type": "error",
                "message": "Invalid JSON",
            })
    
    async def start_analysis(self, ticker: str) -> None:
        """Start analysis for a ticker and stream progress."""
        from src.ingestion.tasks import fetch_company_metrics
        
        # Submit the task
        result = fetch_company_metrics.delay(ticker)
        
        await self.send_json({
            "type": "analysis_started",
            "ticker": ticker,
            "task_id": result.id,
        })
    
    async def check_status(self, task_id: str) -> None:
        """Check and send task status."""
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id)
        
        await self.send_json({
            "type": "task_status",
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
            "result": result.result if result.ready() and result.successful() else None,
        })
    
    async def analysis_update(self, event: dict[str, Any]) -> None:
        """Handle analysis update from channel layer."""
        await self.send_json(event["data"])
    
    async def llm_stream(self, event: dict[str, Any]) -> None:
        """Handle LLM streaming token."""
        await self.send_json({
            "type": "llm_token",
            "content": event["content"],
        })
    
    async def send_json(self, data: dict[str, Any]) -> None:
        """Send JSON to client."""
        await self.send(text_data=json.dumps(data))
