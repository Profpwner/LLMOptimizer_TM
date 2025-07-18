"""Database performance monitoring utilities."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict

from shared.database.manager import db_manager

logger = logging.getLogger(__name__)


class DatabaseMonitor:
    """Monitors database performance and health metrics."""
    
    def __init__(self):
        """Initialize database monitor."""
        self.metrics_history = defaultdict(list)
        self.alert_thresholds = {
            "postgresql_connections": 80,  # percentage
            "mongodb_query_time": 1000,    # milliseconds
            "redis_memory_usage": 80,      # percentage
            "neo4j_transaction_time": 2000 # milliseconds
        }
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics from all databases."""
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "databases": {}
        }
        
        # PostgreSQL metrics
        try:
            pg_metrics = await self._collect_postgresql_metrics()
            metrics["databases"]["postgresql"] = pg_metrics
        except Exception as e:
            logger.error(f"Failed to collect PostgreSQL metrics: {e}")
            metrics["databases"]["postgresql"] = {"error": str(e)}
        
        # MongoDB metrics
        try:
            mongo_metrics = await self._collect_mongodb_metrics()
            metrics["databases"]["mongodb"] = mongo_metrics
        except Exception as e:
            logger.error(f"Failed to collect MongoDB metrics: {e}")
            metrics["databases"]["mongodb"] = {"error": str(e)}
        
        # Redis metrics
        try:
            redis_metrics = await self._collect_redis_metrics()
            metrics["databases"]["redis"] = redis_metrics
        except Exception as e:
            logger.error(f"Failed to collect Redis metrics: {e}")
            metrics["databases"]["redis"] = {"error": str(e)}
        
        # Neo4j metrics
        try:
            neo4j_metrics = await self._collect_neo4j_metrics()
            metrics["databases"]["neo4j"] = neo4j_metrics
        except Exception as e:
            logger.error(f"Failed to collect Neo4j metrics: {e}")
            metrics["databases"]["neo4j"] = {"error": str(e)}
        
        # Store in history
        self.metrics_history["all"].append(metrics)
        
        # Keep only last 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.metrics_history["all"] = [
            m for m in self.metrics_history["all"]
            if datetime.fromisoformat(m["timestamp"]) > cutoff
        ]
        
        return metrics
    
    async def _collect_postgresql_metrics(self) -> Dict[str, Any]:
        """Collect PostgreSQL metrics."""
        metrics = {}
        
        # Connection statistics
        conn_stats = await db_manager.postgresql.get_connection_stats()
        metrics["connections"] = conn_stats
        
        # Database size
        size_query = """
        SELECT 
            pg_database_size(current_database()) as database_size,
            pg_size_pretty(pg_database_size(current_database())) as database_size_pretty
        """
        size_result = await db_manager.postgresql.execute_query(size_query)
        metrics["size"] = size_result[0] if size_result else {}
        
        # Table statistics
        table_stats_query = """
        SELECT 
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
            n_live_tup as row_count,
            n_dead_tup as dead_rows,
            last_vacuum,
            last_autovacuum
        FROM pg_stat_user_tables
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        LIMIT 10
        """
        table_stats = await db_manager.postgresql.execute_query(table_stats_query)
        metrics["top_tables"] = table_stats
        
        # Query performance
        slow_queries = await db_manager.postgresql.get_slow_queries(threshold_ms=100)
        metrics["slow_queries"] = slow_queries[:10]  # Top 10
        
        # Cache hit ratio
        cache_query = """
        SELECT 
            sum(heap_blks_hit) / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0) as cache_hit_ratio
        FROM pg_statio_user_tables
        """
        cache_result = await db_manager.postgresql.execute_query(cache_query)
        metrics["cache_hit_ratio"] = cache_result[0]["cache_hit_ratio"] if cache_result else 0
        
        # Active queries
        active_query = """
        SELECT 
            pid,
            usename,
            application_name,
            client_addr,
            backend_start,
            state,
            query_start,
            query
        FROM pg_stat_activity
        WHERE state != 'idle'
        ORDER BY query_start
        """
        active_queries = await db_manager.postgresql.execute_query(active_query)
        metrics["active_queries"] = active_queries
        
        return metrics
    
    async def _collect_mongodb_metrics(self) -> Dict[str, Any]:
        """Collect MongoDB metrics."""
        metrics = {}
        
        # Server status
        server_status = await db_manager.mongodb._database.command("serverStatus")
        
        # Connection metrics
        metrics["connections"] = {
            "current": server_status.get("connections", {}).get("current", 0),
            "available": server_status.get("connections", {}).get("available", 0),
            "total_created": server_status.get("connections", {}).get("totalCreated", 0)
        }
        
        # Memory usage
        metrics["memory"] = {
            "resident_mb": server_status.get("mem", {}).get("resident", 0),
            "virtual_mb": server_status.get("mem", {}).get("virtual", 0)
        }
        
        # Operation counters
        opcounters = server_status.get("opcounters", {})
        metrics["operations"] = {
            "insert": opcounters.get("insert", 0),
            "query": opcounters.get("query", 0),
            "update": opcounters.get("update", 0),
            "delete": opcounters.get("delete", 0),
            "command": opcounters.get("command", 0)
        }
        
        # Collection statistics
        collections = await db_manager.mongodb._database.list_collection_names()
        collection_stats = []
        
        for collection in collections[:10]:  # Top 10 collections
            stats = await db_manager.mongodb._database.command("collStats", collection)
            collection_stats.append({
                "name": collection,
                "count": stats.get("count", 0),
                "size": stats.get("size", 0),
                "avg_obj_size": stats.get("avgObjSize", 0),
                "storage_size": stats.get("storageSize", 0),
                "indexes": stats.get("nindexes", 0)
            })
        
        metrics["collections"] = sorted(
            collection_stats,
            key=lambda x: x["size"],
            reverse=True
        )
        
        # Slow queries from profiler
        slow_queries = await db_manager.mongodb.get_slow_queries(threshold_ms=100)
        metrics["slow_queries"] = slow_queries[:10]
        
        return metrics
    
    async def _collect_redis_metrics(self) -> Dict[str, Any]:
        """Collect Redis metrics."""
        metrics = {}
        
        # Get INFO from Redis
        info = await db_manager.redis.get_info()
        
        # Memory metrics
        memory_info = info.get("memory", {})
        metrics["memory"] = {
            "used_memory": memory_info.get("used_memory", 0),
            "used_memory_human": memory_info.get("used_memory_human", "0B"),
            "used_memory_peak": memory_info.get("used_memory_peak", 0),
            "used_memory_peak_human": memory_info.get("used_memory_peak_human", "0B"),
            "mem_fragmentation_ratio": memory_info.get("mem_fragmentation_ratio", 1.0),
            "maxmemory": memory_info.get("maxmemory", 0),
            "maxmemory_human": memory_info.get("maxmemory_human", "0B"),
            "memory_usage_percentage": (
                memory_info.get("used_memory", 0) / memory_info.get("maxmemory", 1) * 100
                if memory_info.get("maxmemory", 0) > 0 else 0
            )
        }
        
        # Client connections
        client_info = info.get("clients", {})
        metrics["clients"] = {
            "connected_clients": client_info.get("connected_clients", 0),
            "blocked_clients": client_info.get("blocked_clients", 0),
            "client_longest_output_list": client_info.get("client_longest_output_list", 0)
        }
        
        # Stats
        stats_info = info.get("stats", {})
        metrics["stats"] = {
            "total_connections_received": stats_info.get("total_connections_received", 0),
            "total_commands_processed": stats_info.get("total_commands_processed", 0),
            "instantaneous_ops_per_sec": stats_info.get("instantaneous_ops_per_sec", 0),
            "total_net_input_bytes": stats_info.get("total_net_input_bytes", 0),
            "total_net_output_bytes": stats_info.get("total_net_output_bytes", 0),
            "rejected_connections": stats_info.get("rejected_connections", 0),
            "keyspace_hits": stats_info.get("keyspace_hits", 0),
            "keyspace_misses": stats_info.get("keyspace_misses", 0),
            "hit_rate": (
                stats_info.get("keyspace_hits", 0) / 
                (stats_info.get("keyspace_hits", 0) + stats_info.get("keyspace_misses", 1)) * 100
            )
        }
        
        # Persistence
        persistence_info = info.get("persistence", {})
        metrics["persistence"] = {
            "rdb_last_save_time": persistence_info.get("rdb_last_save_time", 0),
            "rdb_changes_since_last_save": persistence_info.get("rdb_changes_since_last_save", 0),
            "aof_enabled": persistence_info.get("aof_enabled", 0),
            "aof_rewrite_in_progress": persistence_info.get("aof_rewrite_in_progress", 0)
        }
        
        # Key statistics by pattern
        key_patterns = ["session:*", "cache:*", "ratelimit:*", "lock:*"]
        key_stats = []
        
        for pattern in key_patterns:
            count = 0
            memory = 0
            cursor = 0
            
            while True:
                cursor, keys = await db_manager.redis._client.scan(
                    cursor, match=pattern, count=100
                )
                count += len(keys)
                
                for key in keys[:10]:  # Sample memory usage
                    try:
                        mem = await db_manager.redis._client.memory_usage(key)
                        memory += mem or 0
                    except:
                        pass
                
                if cursor == 0:
                    break
            
            key_stats.append({
                "pattern": pattern,
                "count": count,
                "estimated_memory": memory * (count / 10) if count > 0 else 0
            })
        
        metrics["key_patterns"] = key_stats
        
        return metrics
    
    async def _collect_neo4j_metrics(self) -> Dict[str, Any]:
        """Collect Neo4j metrics."""
        metrics = {}
        
        async with db_manager.neo4j.get_session() as session:
            # Database size
            size_query = """
            CALL dbms.database.size()
            YIELD size, sizeInBytes
            RETURN size, sizeInBytes
            """
            size_result = await session.run(size_query)
            size_record = await size_result.single()
            if size_record:
                metrics["size"] = {
                    "bytes": size_record["sizeInBytes"],
                    "human": size_record["size"]
                }
            
            # Node and relationship counts
            count_query = """
            MATCH (n)
            WITH count(n) as nodeCount
            MATCH ()-[r]->()
            RETURN nodeCount, count(r) as relationshipCount
            """
            count_result = await session.run(count_query)
            count_record = await count_result.single()
            if count_record:
                metrics["counts"] = {
                    "nodes": count_record["nodeCount"],
                    "relationships": count_record["relationshipCount"]
                }
            
            # Label statistics
            label_query = """
            CALL db.labels() YIELD label
            CALL {
                WITH label
                MATCH (n)
                WHERE label IN labels(n)
                RETURN count(n) as count
            }
            RETURN label, count
            ORDER BY count DESC
            """
            label_result = await session.run(label_query)
            label_stats = []
            async for record in label_result:
                label_stats.append({
                    "label": record["label"],
                    "count": record["count"]
                })
            metrics["labels"] = label_stats
            
            # Relationship type statistics
            rel_query = """
            CALL db.relationshipTypes() YIELD relationshipType
            CALL {
                WITH relationshipType
                MATCH ()-[r]->()
                WHERE type(r) = relationshipType
                RETURN count(r) as count
            }
            RETURN relationshipType, count
            ORDER BY count DESC
            """
            rel_result = await session.run(rel_query)
            rel_stats = []
            async for record in rel_result:
                rel_stats.append({
                    "type": record["relationshipType"],
                    "count": record["count"]
                })
            metrics["relationship_types"] = rel_stats
            
            # Index usage
            index_query = """
            SHOW INDEXES
            YIELD name, state, type, labelsOrTypes, properties, options
            """
            try:
                index_result = await session.run(index_query)
                indexes = []
                async for record in index_result:
                    indexes.append({
                        "name": record["name"],
                        "state": record["state"],
                        "type": record["type"],
                        "labels": record["labelsOrTypes"],
                        "properties": record["properties"]
                    })
                metrics["indexes"] = indexes
            except:
                metrics["indexes"] = []
        
        return metrics
    
    async def check_health(self) -> Dict[str, Any]:
        """Check health status of all databases."""
        health = await db_manager.health_check()
        
        # Add detailed health information
        detailed_health = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy" if all(health.values()) else "unhealthy",
            "databases": {}
        }
        
        for db_name, is_healthy in health.items():
            detailed_health["databases"][db_name] = {
                "status": "healthy" if is_healthy else "unhealthy",
                "last_check": datetime.utcnow().isoformat()
            }
            
            # Add specific health checks
            if db_name == "postgresql" and is_healthy:
                conn_stats = await db_manager.postgresql.get_connection_stats()
                pool_stats = conn_stats.get("pool", {})
                pool_usage = (
                    pool_stats.get("pool_used", 0) / 
                    pool_stats.get("pool_size", 1) * 100
                )
                
                detailed_health["databases"][db_name].update({
                    "connection_pool_usage": pool_usage,
                    "warning": pool_usage > self.alert_thresholds["postgresql_connections"]
                })
            
            elif db_name == "redis" and is_healthy:
                info = await db_manager.redis.get_info()
                memory_usage = (
                    info.get("memory", {}).get("used_memory", 0) /
                    info.get("memory", {}).get("maxmemory", 1) * 100
                    if info.get("memory", {}).get("maxmemory", 0) > 0 else 0
                )
                
                detailed_health["databases"][db_name].update({
                    "memory_usage_percentage": memory_usage,
                    "warning": memory_usage > self.alert_thresholds["redis_memory_usage"]
                })
        
        return detailed_health
    
    async def generate_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate a performance report for the specified time period."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Filter metrics history
        relevant_metrics = [
            m for m in self.metrics_history["all"]
            if datetime.fromisoformat(m["timestamp"]) > cutoff
        ]
        
        if not relevant_metrics:
            return {
                "error": "No metrics available for the specified period",
                "period_hours": hours
            }
        
        report = {
            "period_hours": hours,
            "start_time": relevant_metrics[0]["timestamp"],
            "end_time": relevant_metrics[-1]["timestamp"],
            "total_samples": len(relevant_metrics),
            "databases": {}
        }
        
        # Aggregate metrics by database
        for db_name in ["postgresql", "mongodb", "redis", "neo4j"]:
            db_metrics = []
            
            for metric in relevant_metrics:
                if db_name in metric.get("databases", {}):
                    db_metrics.append(metric["databases"][db_name])
            
            if not db_metrics:
                continue
            
            # Calculate aggregates based on database type
            if db_name == "postgresql":
                report["databases"][db_name] = self._aggregate_postgresql_metrics(db_metrics)
            elif db_name == "mongodb":
                report["databases"][db_name] = self._aggregate_mongodb_metrics(db_metrics)
            elif db_name == "redis":
                report["databases"][db_name] = self._aggregate_redis_metrics(db_metrics)
            elif db_name == "neo4j":
                report["databases"][db_name] = self._aggregate_neo4j_metrics(db_metrics)
        
        return report
    
    def _aggregate_postgresql_metrics(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate PostgreSQL metrics."""
        aggregated = {
            "avg_active_connections": 0,
            "max_active_connections": 0,
            "avg_cache_hit_ratio": 0,
            "total_slow_queries": 0,
            "unique_slow_queries": set()
        }
        
        for m in metrics:
            if "connections" in m:
                active = sum(
                    v for k, v in m["connections"].get("database", {}).items()
                    if k == "active"
                )
                aggregated["avg_active_connections"] += active
                aggregated["max_active_connections"] = max(
                    aggregated["max_active_connections"], active
                )
            
            if "cache_hit_ratio" in m:
                aggregated["avg_cache_hit_ratio"] += m["cache_hit_ratio"] or 0
            
            if "slow_queries" in m:
                aggregated["total_slow_queries"] += len(m["slow_queries"])
                for q in m["slow_queries"]:
                    aggregated["unique_slow_queries"].add(q.get("query", ""))
        
        # Calculate averages
        num_samples = len(metrics)
        if num_samples > 0:
            aggregated["avg_active_connections"] /= num_samples
            aggregated["avg_cache_hit_ratio"] /= num_samples
        
        aggregated["unique_slow_queries"] = len(aggregated["unique_slow_queries"])
        
        return aggregated
    
    def _aggregate_mongodb_metrics(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate MongoDB metrics."""
        aggregated = {
            "avg_connections": 0,
            "max_connections": 0,
            "total_operations": defaultdict(int),
            "avg_memory_mb": 0
        }
        
        for m in metrics:
            if "connections" in m:
                current = m["connections"].get("current", 0)
                aggregated["avg_connections"] += current
                aggregated["max_connections"] = max(
                    aggregated["max_connections"], current
                )
            
            if "operations" in m:
                for op_type, count in m["operations"].items():
                    aggregated["total_operations"][op_type] += count
            
            if "memory" in m:
                aggregated["avg_memory_mb"] += m["memory"].get("resident_mb", 0)
        
        # Calculate averages
        num_samples = len(metrics)
        if num_samples > 0:
            aggregated["avg_connections"] /= num_samples
            aggregated["avg_memory_mb"] /= num_samples
        
        aggregated["total_operations"] = dict(aggregated["total_operations"])
        
        return aggregated
    
    def _aggregate_redis_metrics(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate Redis metrics."""
        aggregated = {
            "avg_memory_usage": 0,
            "max_memory_usage": 0,
            "avg_ops_per_sec": 0,
            "avg_hit_rate": 0,
            "total_commands": 0
        }
        
        for m in metrics:
            if "memory" in m:
                usage = m["memory"].get("memory_usage_percentage", 0)
                aggregated["avg_memory_usage"] += usage
                aggregated["max_memory_usage"] = max(
                    aggregated["max_memory_usage"], usage
                )
            
            if "stats" in m:
                aggregated["avg_ops_per_sec"] += m["stats"].get("instantaneous_ops_per_sec", 0)
                aggregated["avg_hit_rate"] += m["stats"].get("hit_rate", 0)
                aggregated["total_commands"] += m["stats"].get("total_commands_processed", 0)
        
        # Calculate averages
        num_samples = len(metrics)
        if num_samples > 0:
            aggregated["avg_memory_usage"] /= num_samples
            aggregated["avg_ops_per_sec"] /= num_samples
            aggregated["avg_hit_rate"] /= num_samples
        
        return aggregated
    
    def _aggregate_neo4j_metrics(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate Neo4j metrics."""
        aggregated = {
            "total_nodes": 0,
            "total_relationships": 0,
            "avg_nodes": 0,
            "avg_relationships": 0
        }
        
        for m in metrics:
            if "counts" in m:
                nodes = m["counts"].get("nodes", 0)
                rels = m["counts"].get("relationships", 0)
                
                aggregated["avg_nodes"] += nodes
                aggregated["avg_relationships"] += rels
                aggregated["total_nodes"] = max(aggregated["total_nodes"], nodes)
                aggregated["total_relationships"] = max(aggregated["total_relationships"], rels)
        
        # Calculate averages
        num_samples = len(metrics)
        if num_samples > 0:
            aggregated["avg_nodes"] /= num_samples
            aggregated["avg_relationships"] /= num_samples
        
        return aggregated


# Global monitor instance
db_monitor = DatabaseMonitor()


# Background monitoring task
async def start_monitoring(interval_seconds: int = 60):
    """Start background monitoring task."""
    while True:
        try:
            await db_monitor.collect_metrics()
            
            # Check for alerts
            health = await db_monitor.check_health()
            
            for db_name, db_health in health["databases"].items():
                if db_health.get("warning"):
                    logger.warning(
                        f"Performance warning for {db_name}: {db_health}"
                    )
            
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
        
        await asyncio.sleep(interval_seconds)