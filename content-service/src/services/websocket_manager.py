from typing import Dict, Set, List
from fastapi import WebSocket, WebSocketDisconnect
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Store active connections by user_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Store connection metadata
        self.connection_metadata: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        # Add to user's connections
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
        # Store metadata
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "connected_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"User {user_id} connected. Total connections: {len(self.active_connections[user_id])}")
        
        # Send initial connection confirmation
        await self.send_personal_message(
            {
                "type": "connection",
                "status": "connected",
                "message": "WebSocket connection established"
            },
            websocket
        )
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        metadata = self.connection_metadata.get(websocket)
        if metadata:
            user_id = metadata["user_id"]
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            del self.connection_metadata[websocket]
            logger.info(f"User {user_id} disconnected")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message to websocket: {e}")
            self.disconnect(websocket)
    
    async def send_user_message(self, message: dict, user_id: str):
        """Send a message to all connections of a specific user"""
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")
                    disconnected.append(connection)
            
            # Clean up disconnected connections
            for conn in disconnected:
                self.disconnect(conn)
    
    async def broadcast(self, message: dict, exclude_user: str = None):
        """Broadcast a message to all connected users"""
        for user_id, connections in list(self.active_connections.items()):
            if exclude_user and user_id == exclude_user:
                continue
            await self.send_user_message(message, user_id)
    
    async def send_content_update(self, user_id: str, content_id: str, update_type: str, data: dict):
        """Send content-specific updates to a user"""
        message = {
            "type": "content_update",
            "content_id": content_id,
            "update_type": update_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_user_message(message, user_id)
    
    async def send_job_update(self, user_id: str, job_id: str, status: str, progress: float = None, data: dict = None):
        """Send job processing updates to a user"""
        message = {
            "type": "job_update",
            "job_id": job_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if progress is not None:
            message["progress"] = progress
        
        if data:
            message["data"] = data
        
        await self.send_user_message(message, user_id)
    
    async def handle_websocket(self, websocket: WebSocket, user_id: str):
        """Handle WebSocket connection lifecycle"""
        await self.connect(websocket, user_id)
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_json()
                
                # Handle different message types
                if data.get("type") == "ping":
                    await self.send_personal_message({"type": "pong"}, websocket)
                elif data.get("type") == "subscribe":
                    # Handle subscription to specific content/job updates
                    await self.handle_subscription(websocket, user_id, data)
                else:
                    # Echo back unknown messages with error
                    await self.send_personal_message(
                        {
                            "type": "error",
                            "message": f"Unknown message type: {data.get('type')}"
                        },
                        websocket
                    )
                    
        except WebSocketDisconnect:
            self.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error for user {user_id}: {e}")
            self.disconnect(websocket)
    
    async def handle_subscription(self, websocket: WebSocket, user_id: str, data: dict):
        """Handle subscription requests"""
        subscription_type = data.get("subscription_type")
        target_id = data.get("target_id")
        
        if not subscription_type or not target_id:
            await self.send_personal_message(
                {
                    "type": "error",
                    "message": "Missing subscription_type or target_id"
                },
                websocket
            )
            return
        
        # Store subscription in metadata
        if "subscriptions" not in self.connection_metadata[websocket]:
            self.connection_metadata[websocket]["subscriptions"] = {}
        
        self.connection_metadata[websocket]["subscriptions"][subscription_type] = target_id
        
        await self.send_personal_message(
            {
                "type": "subscription_confirmed",
                "subscription_type": subscription_type,
                "target_id": target_id
            },
            websocket
        )

# Global instance
manager = ConnectionManager()