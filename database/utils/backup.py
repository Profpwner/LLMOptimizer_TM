"""Database backup and restore utilities."""

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from shared.database.manager import db_manager
from shared.database.config import db_config

logger = logging.getLogger(__name__)


class DatabaseBackup:
    """Handles backup and restore operations for all databases."""
    
    def __init__(self, backup_dir: Optional[Path] = None):
        """Initialize backup utility."""
        self.backup_dir = backup_dir or Path("/tmp/llmoptimizer_backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def backup_all(self, tenant_id: Optional[str] = None) -> Dict[str, str]:
        """Backup all databases for a tenant or globally."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{tenant_id or 'global'}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)
        
        results = {}
        
        # Backup PostgreSQL
        results["postgresql"] = await self.backup_postgresql(backup_path, tenant_id)
        
        # Backup MongoDB
        results["mongodb"] = await self.backup_mongodb(backup_path, tenant_id)
        
        # Backup Redis
        results["redis"] = await self.backup_redis(backup_path, tenant_id)
        
        # Backup Neo4j
        results["neo4j"] = await self.backup_neo4j(backup_path, tenant_id)
        
        # Create manifest
        manifest = {
            "timestamp": timestamp,
            "tenant_id": tenant_id,
            "databases": results,
            "version": "1.0"
        }
        
        manifest_path = backup_path / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Backup completed: {backup_path}")
        return results
    
    async def backup_postgresql(self, backup_path: Path, tenant_id: Optional[str] = None) -> str:
        """Backup PostgreSQL data."""
        output_file = backup_path / "postgresql.sql"
        
        if tenant_id:
            # Backup specific tenant data
            tables = [
                "organizations",
                "users",
                "user_organizations",
                "api_keys",
                "content",
                "content_optimizations",
                "user_sessions"
            ]
            
            # Export data as SQL inserts
            async with db_manager.postgresql.get_raw_connection() as conn:
                with open(output_file, "w") as f:
                    for table in tables:
                        # Get table data
                        if table in ["organizations", "users", "user_sessions"]:
                            # These tables don't have org_id
                            if table == "organizations":
                                query = f"SELECT * FROM {table} WHERE id = $1"
                                rows = await conn.fetch(query, tenant_id)
                            else:
                                continue  # Skip user tables for tenant-specific backup
                        else:
                            query = f"SELECT * FROM {table} WHERE org_id = $1"
                            rows = await conn.fetch(query, tenant_id)
                        
                        if rows:
                            f.write(f"\n-- {table}\n")
                            for row in rows:
                                columns = ", ".join(row.keys())
                                values = ", ".join([
                                    f"'{v}'" if isinstance(v, str) else str(v)
                                    for v in row.values()
                                ])
                                f.write(f"INSERT INTO {table} ({columns}) VALUES ({values});\n")
        else:
            # Full database backup using pg_dump
            cmd = [
                "pg_dump",
                "-h", db_config.postgresql.host,
                "-p", str(db_config.postgresql.port),
                "-U", db_config.postgresql.user,
                "-d", db_config.postgresql.database,
                "-f", str(output_file),
                "--no-owner",
                "--no-privileges"
            ]
            
            env = {"PGPASSWORD": db_config.postgresql.password}
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"PostgreSQL backup failed: {result.stderr}")
                raise Exception("PostgreSQL backup failed")
        
        return str(output_file)
    
    async def backup_mongodb(self, backup_path: Path, tenant_id: Optional[str] = None) -> str:
        """Backup MongoDB data."""
        output_dir = backup_path / "mongodb"
        output_dir.mkdir(exist_ok=True)
        
        if tenant_id:
            # Export tenant-specific data
            from database.schemas.mongodb.models import (
                ContentDocument, OptimizationResult, AnalyticsEvent,
                ContentPerformance, AIModelUsage
            )
            
            collections = [
                ("content", ContentDocument),
                ("optimization_results", OptimizationResult),
                ("analytics_events", AnalyticsEvent),
                ("content_performance", ContentPerformance),
                ("ai_model_usage", AIModelUsage)
            ]
            
            for collection_name, model_class in collections:
                data = await db_manager.mongodb.export_collection(model_class, tenant_id)
                
                output_file = output_dir / f"{collection_name}.json"
                with open(output_file, "w") as f:
                    json.dump(data, f, indent=2, default=str)
        else:
            # Full database backup using mongodump
            cmd = [
                "mongodump",
                "--host", f"{db_config.mongodb.host}:{db_config.mongodb.port}",
                "--db", db_config.mongodb.database,
                "--out", str(output_dir)
            ]
            
            if db_config.mongodb.username:
                cmd.extend(["--username", db_config.mongodb.username])
                cmd.extend(["--password", db_config.mongodb.password])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"MongoDB backup failed: {result.stderr}")
                raise Exception("MongoDB backup failed")
        
        return str(output_dir)
    
    async def backup_redis(self, backup_path: Path, tenant_id: Optional[str] = None) -> str:
        """Backup Redis data."""
        output_file = backup_path / "redis.json"
        
        if tenant_id:
            # Export tenant-specific keys
            pattern = f"tenant:{tenant_id}:*"
            cursor = 0
            all_data = {}
            
            while True:
                cursor, keys = await db_manager.redis._client.scan(
                    cursor, match=pattern, count=100
                )
                
                for key in keys:
                    # Get key type
                    key_type = await db_manager.redis._client.type(key)
                    
                    if key_type == "string":
                        value = await db_manager.redis._client.get(key)
                        ttl = await db_manager.redis._client.ttl(key)
                        all_data[key] = {"type": "string", "value": value, "ttl": ttl}
                    
                    elif key_type == "hash":
                        value = await db_manager.redis._client.hgetall(key)
                        ttl = await db_manager.redis._client.ttl(key)
                        all_data[key] = {"type": "hash", "value": value, "ttl": ttl}
                    
                    elif key_type == "list":
                        value = await db_manager.redis._client.lrange(key, 0, -1)
                        ttl = await db_manager.redis._client.ttl(key)
                        all_data[key] = {"type": "list", "value": value, "ttl": ttl}
                    
                    elif key_type == "set":
                        value = list(await db_manager.redis._client.smembers(key))
                        ttl = await db_manager.redis._client.ttl(key)
                        all_data[key] = {"type": "set", "value": value, "ttl": ttl}
                
                if cursor == 0:
                    break
            
            with open(output_file, "w") as f:
                json.dump(all_data, f, indent=2)
        else:
            # Use Redis BGSAVE for full backup
            await db_manager.redis._client.bgsave()
            
            # Wait for backup to complete
            while True:
                info = await db_manager.redis._client.info("persistence")
                if info["rdb_bgsave_in_progress"] == 0:
                    break
                await asyncio.sleep(1)
            
            # Note: The actual RDB file location depends on Redis config
            logger.info("Redis BGSAVE completed")
        
        return str(output_file)
    
    async def backup_neo4j(self, backup_path: Path, tenant_id: Optional[str] = None) -> str:
        """Backup Neo4j data."""
        output_file = backup_path / "neo4j.json"
        
        if tenant_id:
            # Export tenant-specific graph
            backup_data = {}
            
            async with db_manager.neo4j.get_session() as session:
                # Export nodes
                result = await session.run(
                    "MATCH (n {org_id: $org_id}) RETURN n",
                    org_id=tenant_id
                )
                
                nodes = []
                async for record in result:
                    node = dict(record["n"])
                    node["_labels"] = list(record["n"].labels)
                    nodes.append(node)
                
                backup_data["nodes"] = nodes
                
                # Export relationships
                result = await session.run(
                    """
                    MATCH (a {org_id: $org_id})-[r]-(b {org_id: $org_id})
                    RETURN a.uid as from_uid, type(r) as rel_type, b.uid as to_uid, properties(r) as props
                    """,
                    org_id=tenant_id
                )
                
                relationships = []
                async for record in result:
                    relationships.append({
                        "from_uid": record["from_uid"],
                        "to_uid": record["to_uid"],
                        "type": record["rel_type"],
                        "properties": dict(record["props"] or {})
                    })
                
                backup_data["relationships"] = relationships
            
            with open(output_file, "w") as f:
                json.dump(backup_data, f, indent=2, default=str)
        else:
            # Note: Full Neo4j backup requires neo4j-admin tool
            logger.warning("Full Neo4j backup requires neo4j-admin tool")
        
        return str(output_file)
    
    async def restore_all(self, backup_path: Path) -> Dict[str, bool]:
        """Restore all databases from backup."""
        manifest_path = backup_path / "manifest.json"
        
        if not manifest_path.exists():
            raise FileNotFoundError(f"Backup manifest not found: {manifest_path}")
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        results = {}
        tenant_id = manifest.get("tenant_id")
        
        # Restore databases
        results["postgresql"] = await self.restore_postgresql(
            Path(manifest["databases"]["postgresql"]), tenant_id
        )
        
        results["mongodb"] = await self.restore_mongodb(
            Path(manifest["databases"]["mongodb"]), tenant_id
        )
        
        results["redis"] = await self.restore_redis(
            Path(manifest["databases"]["redis"]), tenant_id
        )
        
        results["neo4j"] = await self.restore_neo4j(
            Path(manifest["databases"]["neo4j"]), tenant_id
        )
        
        logger.info(f"Restore completed from: {backup_path}")
        return results
    
    async def restore_postgresql(self, backup_file: Path, tenant_id: Optional[str] = None) -> bool:
        """Restore PostgreSQL from backup."""
        if not backup_file.exists():
            logger.error(f"PostgreSQL backup file not found: {backup_file}")
            return False
        
        if backup_file.suffix == ".sql":
            # Restore from SQL file
            cmd = [
                "psql",
                "-h", db_config.postgresql.host,
                "-p", str(db_config.postgresql.port),
                "-U", db_config.postgresql.user,
                "-d", db_config.postgresql.database,
                "-f", str(backup_file)
            ]
            
            env = {"PGPASSWORD": db_config.postgresql.password}
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"PostgreSQL restore failed: {result.stderr}")
                return False
        
        return True
    
    async def restore_mongodb(self, backup_dir: Path, tenant_id: Optional[str] = None) -> bool:
        """Restore MongoDB from backup."""
        if not backup_dir.exists():
            logger.error(f"MongoDB backup directory not found: {backup_dir}")
            return False
        
        if tenant_id:
            # Restore from JSON files
            from database.schemas.mongodb.models import (
                ContentDocument, OptimizationResult, AnalyticsEvent,
                ContentPerformance, AIModelUsage
            )
            
            collections = [
                ("content.json", ContentDocument),
                ("optimization_results.json", OptimizationResult),
                ("analytics_events.json", AnalyticsEvent),
                ("content_performance.json", ContentPerformance),
                ("ai_model_usage.json", AIModelUsage)
            ]
            
            for filename, model_class in collections:
                file_path = backup_dir / filename
                if file_path.exists():
                    with open(file_path) as f:
                        data = json.load(f)
                    
                    await db_manager.mongodb.import_collection(
                        model_class, data, tenant_id
                    )
        else:
            # Restore using mongorestore
            cmd = [
                "mongorestore",
                "--host", f"{db_config.mongodb.host}:{db_config.mongodb.port}",
                "--db", db_config.mongodb.database,
                str(backup_dir / db_config.mongodb.database)
            ]
            
            if db_config.mongodb.username:
                cmd.extend(["--username", db_config.mongodb.username])
                cmd.extend(["--password", db_config.mongodb.password])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"MongoDB restore failed: {result.stderr}")
                return False
        
        return True
    
    async def restore_redis(self, backup_file: Path, tenant_id: Optional[str] = None) -> bool:
        """Restore Redis from backup."""
        if not backup_file.exists():
            logger.error(f"Redis backup file not found: {backup_file}")
            return False
        
        if backup_file.suffix == ".json":
            # Restore from JSON
            with open(backup_file) as f:
                data = json.load(f)
            
            for key, info in data.items():
                if info["type"] == "string":
                    await db_manager.redis._client.set(
                        key, info["value"],
                        ex=info["ttl"] if info["ttl"] > 0 else None
                    )
                elif info["type"] == "hash":
                    await db_manager.redis._client.hset(key, mapping=info["value"])
                    if info["ttl"] > 0:
                        await db_manager.redis._client.expire(key, info["ttl"])
                elif info["type"] == "list":
                    await db_manager.redis._client.rpush(key, *info["value"])
                    if info["ttl"] > 0:
                        await db_manager.redis._client.expire(key, info["ttl"])
                elif info["type"] == "set":
                    await db_manager.redis._client.sadd(key, *info["value"])
                    if info["ttl"] > 0:
                        await db_manager.redis._client.expire(key, info["ttl"])
        
        return True
    
    async def restore_neo4j(self, backup_file: Path, tenant_id: Optional[str] = None) -> bool:
        """Restore Neo4j from backup."""
        if not backup_file.exists():
            logger.error(f"Neo4j backup file not found: {backup_file}")
            return False
        
        if backup_file.suffix == ".json":
            # Restore from JSON
            with open(backup_file) as f:
                data = json.load(f)
            
            async with db_manager.neo4j.get_session() as session:
                # Restore nodes
                for node in data.get("nodes", []):
                    labels = node.pop("_labels", [])
                    labels_str = ":".join(labels)
                    
                    props_str = ", ".join([
                        f"{k}: ${k}" for k in node.keys()
                    ])
                    
                    query = f"CREATE (n:{labels_str} {{{props_str}}})"
                    await session.run(query, **node)
                
                # Restore relationships
                for rel in data.get("relationships", []):
                    query = f"""
                    MATCH (a {{uid: $from_uid, org_id: $org_id}})
                    MATCH (b {{uid: $to_uid, org_id: $org_id}})
                    CREATE (a)-[r:{rel['type']}]->(b)
                    SET r = $props
                    """
                    
                    await session.run(
                        query,
                        from_uid=rel["from_uid"],
                        to_uid=rel["to_uid"],
                        org_id=tenant_id,
                        props=rel.get("properties", {})
                    )
        
        return True


# Global backup utility instance
db_backup = DatabaseBackup()