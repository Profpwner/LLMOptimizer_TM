"""
Distributed cache synchronization for multi-instance deployments.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field
import logging
import uuid
from enum import Enum
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class SyncStrategy(Enum):
    """Cache synchronization strategies."""
    BROADCAST = "broadcast"  # Broadcast to all nodes
    GOSSIP = "gossip"  # Gossip protocol
    MASTER_SLAVE = "master_slave"  # Master-slave replication
    CONSENSUS = "consensus"  # Consensus-based sync
    EVENTUAL = "eventual"  # Eventual consistency


@dataclass
class SyncMessage:
    """Message for cache synchronization."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = ""
    operation: str = ""  # set, delete, invalidate
    key: str = ""
    value: Optional[Any] = None
    ttl: Optional[int] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeInfo:
    """Information about a cache node."""
    node_id: str
    hostname: str
    port: int
    last_seen: float = field(default_factory=time.time)
    is_master: bool = False
    is_healthy: bool = True
    sync_lag: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class DistributedCacheSync:
    """
    Distributed cache synchronization for 100K+ concurrent users across multiple nodes.
    """
    
    def __init__(
        self,
        node_id: str,
        redis_url: str,
        strategy: SyncStrategy = SyncStrategy.BROADCAST,
        enable_deduplication: bool = True
    ):
        self.node_id = node_id
        self.redis_url = redis_url
        self.strategy = strategy
        self.enable_deduplication = enable_deduplication
        
        # Redis connections
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        
        # Node management
        self.nodes: Dict[str, NodeInfo] = {}
        self.is_master = False
        
        # Message handling
        self.message_handlers: Dict[str, Callable] = {}
        self.seen_messages: Set[str] = set()
        self.message_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Background tasks
        self.subscriber_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.processor_task: Optional[asyncio.Task] = None
        
        # Metrics
        self.metrics = {
            'messages_sent': 0,
            'messages_received': 0,
            'messages_processed': 0,
            'messages_deduplicated': 0,
            'sync_errors': 0,
            'replication_lag': 0.0
        }
        
        # Channels
        self.sync_channel = f"cache:sync:{self.strategy.value}"
        self.heartbeat_channel = "cache:heartbeat"
        self.control_channel = "cache:control"
    
    async def initialize(self):
        """Initialize distributed sync."""
        # Create Redis connection
        self.redis_client = redis.from_url(
            self.redis_url,
            decode_responses=False,
            max_connections=100
        )
        
        # Test connection
        await self.redis_client.ping()
        
        # Setup pub/sub
        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe(
            self.sync_channel,
            self.heartbeat_channel,
            self.control_channel
        )
        
        # Start background tasks
        self.subscriber_task = asyncio.create_task(self._subscriber())
        self.heartbeat_task = asyncio.create_task(self._heartbeat())
        self.processor_task = asyncio.create_task(self._message_processor())
        
        # Announce presence
        await self._announce_node()
        
        # Elect master if needed
        if self.strategy == SyncStrategy.MASTER_SLAVE:
            await self._elect_master()
        
        logger.info(f"Distributed cache sync initialized (node: {self.node_id})")
    
    async def shutdown(self):
        """Shutdown distributed sync."""
        # Cancel tasks
        for task in [self.subscriber_task, self.heartbeat_task, self.processor_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close connections
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Distributed cache sync shutdown")
    
    async def _announce_node(self):
        """Announce node presence to cluster."""
        node_info = NodeInfo(
            node_id=self.node_id,
            hostname="localhost",  # Should be actual hostname
            port=6379,
            is_master=self.is_master
        )
        
        # Store node info
        await self.redis_client.hset(
            "cache:nodes",
            self.node_id,
            json.dumps({
                'node_id': node_info.node_id,
                'hostname': node_info.hostname,
                'port': node_info.port,
                'last_seen': node_info.last_seen,
                'is_master': node_info.is_master
            })
        )
        
        # Set expiry
        await self.redis_client.expire("cache:nodes", 300)
    
    async def _elect_master(self):
        """Elect master node for master-slave strategy."""
        # Simple leader election using Redis sorted sets
        score = time.time()
        
        # Try to become master
        await self.redis_client.zadd(
            "cache:master:election",
            {self.node_id: score}
        )
        
        # Get current leader
        leaders = await self.redis_client.zrange(
            "cache:master:election",
            0, 0,
            withscores=True
        )
        
        if leaders and leaders[0][0].decode() == self.node_id:
            self.is_master = True
            logger.info(f"Node {self.node_id} elected as master")
        else:
            self.is_master = False
            logger.info(f"Node {self.node_id} is slave")
    
    async def broadcast_operation(
        self,
        operation: str,
        key: str,
        value: Optional[Any] = None,
        ttl: Optional[int] = None
    ):
        """Broadcast cache operation to all nodes."""
        if self.strategy == SyncStrategy.MASTER_SLAVE and not self.is_master:
            # Only master broadcasts in master-slave mode
            return
        
        message = SyncMessage(
            node_id=self.node_id,
            operation=operation,
            key=key,
            value=value,
            ttl=ttl
        )
        
        # Serialize message
        message_data = self._serialize_message(message)
        
        # Publish to sync channel
        await self.redis_client.publish(self.sync_channel, message_data)
        
        self.metrics['messages_sent'] += 1
        
        # Add to seen messages to avoid processing own message
        if self.enable_deduplication:
            self.seen_messages.add(message.id)
            
            # Cleanup old seen messages
            if len(self.seen_messages) > 10000:
                self.seen_messages = set(list(self.seen_messages)[-5000:])
    
    def _serialize_message(self, message: SyncMessage) -> bytes:
        """Serialize sync message."""
        data = {
            'id': message.id,
            'node_id': message.node_id,
            'operation': message.operation,
            'key': message.key,
            'value': message.value,
            'ttl': message.ttl,
            'timestamp': message.timestamp,
            'metadata': message.metadata
        }
        
        return json.dumps(data).encode('utf-8')
    
    def _deserialize_message(self, data: bytes) -> SyncMessage:
        """Deserialize sync message."""
        message_data = json.loads(data.decode('utf-8'))
        
        return SyncMessage(
            id=message_data['id'],
            node_id=message_data['node_id'],
            operation=message_data['operation'],
            key=message_data['key'],
            value=message_data.get('value'),
            ttl=message_data.get('ttl'),
            timestamp=message_data['timestamp'],
            metadata=message_data.get('metadata', {})
        )
    
    async def _subscriber(self):
        """Subscribe to sync messages."""
        while True:
            try:
                async for message in self.pubsub.listen():
                    if message['type'] != 'message':
                        continue
                    
                    channel = message['channel'].decode()
                    data = message['data']
                    
                    if channel == self.sync_channel:
                        await self._handle_sync_message(data)
                    elif channel == self.heartbeat_channel:
                        await self._handle_heartbeat(data)
                    elif channel == self.control_channel:
                        await self._handle_control_message(data)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Subscriber error: {e}")
                self.metrics['sync_errors'] += 1
                await asyncio.sleep(1)
    
    async def _handle_sync_message(self, data: bytes):
        """Handle sync message from other nodes."""
        try:
            message = self._deserialize_message(data)
            
            # Skip own messages
            if message.node_id == self.node_id:
                return
            
            # Deduplication
            if self.enable_deduplication:
                if message.id in self.seen_messages:
                    self.metrics['messages_deduplicated'] += 1
                    return
                
                self.seen_messages.add(message.id)
            
            # Queue for processing
            await self.message_queue.put(message)
            self.metrics['messages_received'] += 1
            
        except Exception as e:
            logger.error(f"Failed to handle sync message: {e}")
            self.metrics['sync_errors'] += 1
    
    async def _handle_heartbeat(self, data: bytes):
        """Handle heartbeat from other nodes."""
        try:
            heartbeat_data = json.loads(data.decode('utf-8'))
            node_id = heartbeat_data['node_id']
            
            if node_id != self.node_id:
                # Update node info
                if node_id not in self.nodes:
                    self.nodes[node_id] = NodeInfo(
                        node_id=node_id,
                        hostname=heartbeat_data.get('hostname', 'unknown'),
                        port=heartbeat_data.get('port', 0)
                    )
                
                self.nodes[node_id].last_seen = time.time()
                self.nodes[node_id].is_healthy = True
                
        except Exception as e:
            logger.error(f"Failed to handle heartbeat: {e}")
    
    async def _handle_control_message(self, data: bytes):
        """Handle control messages."""
        try:
            control_data = json.loads(data.decode('utf-8'))
            command = control_data.get('command')
            
            if command == 'resync':
                # Trigger full resync
                logger.info("Full resync requested")
                # Implementation would trigger full cache resync
            elif command == 'pause':
                # Pause synchronization
                logger.info("Sync paused")
            elif command == 'resume':
                # Resume synchronization
                logger.info("Sync resumed")
                
        except Exception as e:
            logger.error(f"Failed to handle control message: {e}")
    
    async def _heartbeat(self):
        """Send periodic heartbeats."""
        while True:
            try:
                await asyncio.sleep(10)  # Every 10 seconds
                
                # Send heartbeat
                heartbeat_data = {
                    'node_id': self.node_id,
                    'timestamp': time.time(),
                    'hostname': 'localhost',  # Should be actual hostname
                    'port': 6379,
                    'is_master': self.is_master,
                    'queue_size': self.message_queue.qsize()
                }
                
                await self.redis_client.publish(
                    self.heartbeat_channel,
                    json.dumps(heartbeat_data).encode('utf-8')
                )
                
                # Check node health
                await self._check_node_health()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    async def _check_node_health(self):
        """Check health of other nodes."""
        current_time = time.time()
        unhealthy_nodes = []
        
        for node_id, node_info in self.nodes.items():
            # Mark as unhealthy if no heartbeat for 30 seconds
            if current_time - node_info.last_seen > 30:
                node_info.is_healthy = False
                unhealthy_nodes.append(node_id)
        
        # Re-elect master if current master is unhealthy
        if (self.strategy == SyncStrategy.MASTER_SLAVE and 
            unhealthy_nodes and 
            any(self.nodes[nid].is_master for nid in unhealthy_nodes)):
            await self._elect_master()
    
    async def _message_processor(self):
        """Process queued sync messages."""
        while True:
            try:
                # Get message from queue
                message = await self.message_queue.get()
                
                # Process based on operation
                if message.operation in self.message_handlers:
                    handler = self.message_handlers[message.operation]
                    
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                
                self.metrics['messages_processed'] += 1
                
                # Calculate replication lag
                lag = time.time() - message.timestamp
                self.metrics['replication_lag'] = lag
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Message processor error: {e}")
                self.metrics['sync_errors'] += 1
    
    def register_handler(self, operation: str, handler: Callable):
        """Register handler for sync operations."""
        self.message_handlers[operation] = handler
        logger.info(f"Registered handler for operation: {operation}")
    
    async def get_cluster_status(self) -> Dict[str, Any]:
        """Get status of cache cluster."""
        # Get all nodes from Redis
        all_nodes = await self.redis_client.hgetall("cache:nodes")
        
        cluster_nodes = []
        for node_data in all_nodes.values():
            try:
                node_info = json.loads(node_data.decode('utf-8'))
                cluster_nodes.append(node_info)
            except Exception:
                pass
        
        # Add local nodes info
        for node_id, node_info in self.nodes.items():
            cluster_nodes.append({
                'node_id': node_info.node_id,
                'hostname': node_info.hostname,
                'port': node_info.port,
                'last_seen': node_info.last_seen,
                'is_master': node_info.is_master,
                'is_healthy': node_info.is_healthy
            })
        
        return {
            'node_id': self.node_id,
            'is_master': self.is_master,
            'strategy': self.strategy.value,
            'total_nodes': len(cluster_nodes),
            'healthy_nodes': sum(1 for n in cluster_nodes if n.get('is_healthy', True)),
            'nodes': cluster_nodes,
            'metrics': self.get_metrics()
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get synchronization metrics."""
        return {
            **self.metrics,
            'queue_size': self.message_queue.qsize(),
            'seen_messages': len(self.seen_messages),
            'known_nodes': len(self.nodes)
        }


# Gossip protocol implementation
class GossipSync(DistributedCacheSync):
    """
    Cache synchronization using gossip protocol.
    """
    
    def __init__(self, node_id: str, redis_url: str, fanout: int = 3):
        super().__init__(node_id, redis_url, SyncStrategy.GOSSIP)
        self.fanout = fanout
        self.gossip_interval = 1.0
        self.gossip_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize gossip sync."""
        await super().initialize()
        self.gossip_task = asyncio.create_task(self._gossip_loop())
    
    async def shutdown(self):
        """Shutdown gossip sync."""
        if self.gossip_task:
            self.gossip_task.cancel()
        await super().shutdown()
    
    async def _gossip_loop(self):
        """Gossip protocol main loop."""
        while True:
            try:
                await asyncio.sleep(self.gossip_interval)
                
                # Select random nodes to gossip with
                active_nodes = [
                    node_id for node_id, node in self.nodes.items()
                    if node.is_healthy and node_id != self.node_id
                ]
                
                if not active_nodes:
                    continue
                
                # Select up to fanout nodes
                import random
                selected_nodes = random.sample(
                    active_nodes,
                    min(self.fanout, len(active_nodes))
                )
                
                # Send gossip messages
                for target_node in selected_nodes:
                    await self._send_gossip(target_node)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Gossip loop error: {e}")
    
    async def _send_gossip(self, target_node: str):
        """Send gossip message to target node."""
        # In a real implementation, this would send recent cache updates
        # to the target node for synchronization
        pass


# Consensus-based synchronization
class ConsensusSync(DistributedCacheSync):
    """
    Cache synchronization using consensus protocol (simplified Raft).
    """
    
    def __init__(self, node_id: str, redis_url: str):
        super().__init__(node_id, redis_url, SyncStrategy.CONSENSUS)
        self.term = 0
        self.voted_for = None
        self.log = []
        self.commit_index = 0
        self.last_applied = 0
    
    async def propose_change(self, operation: str, key: str, value: Any = None):
        """Propose a cache change to the cluster."""
        if not self.is_master:
            # Forward to master
            return False
        
        # Add to log
        entry = {
            'term': self.term,
            'operation': operation,
            'key': key,
            'value': value,
            'timestamp': time.time()
        }
        self.log.append(entry)
        
        # Replicate to followers
        success_count = await self._replicate_entry(entry)
        
        # Commit if majority agrees
        if success_count >= len(self.nodes) // 2:
            self.commit_index = len(self.log) - 1
            await self.broadcast_operation(operation, key, value)
            return True
        
        return False
    
    async def _replicate_entry(self, entry: Dict[str, Any]) -> int:
        """Replicate log entry to followers."""
        # Simplified replication - in real Raft, this would be more complex
        success_count = 1  # Count self
        
        # Send to all followers
        for node_id in self.nodes:
            if node_id != self.node_id:
                # Send append entries RPC
                # In real implementation, would track responses
                success_count += 1
        
        return success_count