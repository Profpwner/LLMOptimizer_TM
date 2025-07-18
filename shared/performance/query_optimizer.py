"""
Query optimization utilities for high-performance database operations.
"""

import asyncio
import hashlib
import json
import time
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
import asyncpg
from motor.motor_asyncio import AsyncIOMotorDatabase
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueryPlan:
    """Represents an optimized query execution plan."""
    query: str
    params: tuple
    use_prepared: bool = True
    cache_key: Optional[str] = None
    cache_ttl: int = 300
    partition_key: Optional[str] = None
    indexes_used: List[str] = None
    estimated_cost: float = 0.0


class QueryOptimizer:
    """
    Query optimization for PostgreSQL and MongoDB with caching and analysis.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.query_stats: Dict[str, Dict[str, Any]] = {}
        self.prepared_statements: Dict[str, str] = {}
        
    def _generate_cache_key(self, query: str, params: tuple) -> str:
        """Generate cache key for query results."""
        key_data = f"{query}:{json.dumps(params, sort_keys=True, default=str)}"
        return f"query:cache:{hashlib.sha256(key_data.encode()).hexdigest()}"
    
    async def optimize_postgresql_query(
        self,
        query: str,
        params: tuple = (),
        analyze: bool = False
    ) -> QueryPlan:
        """Optimize PostgreSQL query."""
        # Normalize query
        normalized_query = self._normalize_query(query)
        
        # Check if query should use prepared statement
        use_prepared = self._should_use_prepared(normalized_query)
        
        # Generate cache key
        cache_key = self._generate_cache_key(normalized_query, params) if self.redis_client else None
        
        # Determine partition key for sharded tables
        partition_key = self._extract_partition_key(normalized_query, params)
        
        # Estimate query cost
        estimated_cost = await self._estimate_query_cost(normalized_query)
        
        return QueryPlan(
            query=normalized_query,
            params=params,
            use_prepared=use_prepared,
            cache_key=cache_key,
            partition_key=partition_key,
            estimated_cost=estimated_cost
        )
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for better caching and preparation."""
        # Remove extra whitespace
        query = ' '.join(query.split())
        
        # Common optimizations
        optimizations = {
            'SELECT * FROM': 'SELECT /* SPECIFY COLUMNS */ FROM',
            'LIKE \'%': 'LIKE /* USE FTS */ \'%',
            'ORDER BY RANDOM()': 'ORDER BY /* USE TABLESAMPLE */ RANDOM()',
        }
        
        for pattern, replacement in optimizations.items():
            if pattern in query:
                logger.warning(f"Query optimization suggested: {pattern} -> {replacement}")
        
        return query
    
    def _should_use_prepared(self, query: str) -> bool:
        """Determine if query should use prepared statement."""
        # Don't prepare DDL or utility commands
        non_preparable = ['CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'VACUUM', 'ANALYZE']
        first_word = query.strip().split()[0].upper()
        
        return first_word not in non_preparable
    
    def _extract_partition_key(self, query: str, params: tuple) -> Optional[str]:
        """Extract partition key from query for sharded tables."""
        # Simple extraction logic - can be enhanced based on schema
        if 'WHERE user_id =' in query or 'WHERE user_id IN' in query:
            # Assuming first parameter is user_id for partitioning
            if params:
                return f"user_{params[0] % 10}"  # Simple hash partitioning
        return None
    
    async def _estimate_query_cost(self, query: str) -> float:
        """Estimate query execution cost."""
        # Simple cost estimation based on query complexity
        cost = 1.0
        
        # Increase cost for complex operations
        if 'JOIN' in query.upper():
            cost += query.upper().count('JOIN') * 2.0
        if 'GROUP BY' in query.upper():
            cost += 3.0
        if 'ORDER BY' in query.upper():
            cost += 2.0
        if 'DISTINCT' in query.upper():
            cost += 2.0
        
        return cost
    
    async def execute_with_cache(
        self,
        conn: Union[asyncpg.Connection, asyncpg.Pool],
        plan: QueryPlan,
        fetch_method: str = 'fetch'
    ) -> Any:
        """Execute query with caching support."""
        # Check cache first
        if self.redis_client and plan.cache_key:
            cached_result = await self._get_cached_result(plan.cache_key)
            if cached_result is not None:
                return cached_result
        
        # Execute query
        start_time = time.time()
        
        if plan.use_prepared:
            # Use prepared statement
            stmt_name = self._get_prepared_statement_name(plan.query)
            if stmt_name not in self.prepared_statements:
                await conn.execute(f"PREPARE {stmt_name} AS {plan.query}")
                self.prepared_statements[stmt_name] = plan.query
            
            execute_query = f"EXECUTE {stmt_name}({', '.join(['$' + str(i+1) for i in range(len(plan.params))])})"
            result = await getattr(conn, fetch_method)(execute_query, *plan.params)
        else:
            result = await getattr(conn, fetch_method)(plan.query, *plan.params)
        
        execution_time = time.time() - start_time
        
        # Update query statistics
        self._update_query_stats(plan.query, execution_time)
        
        # Cache result if applicable
        if self.redis_client and plan.cache_key and fetch_method in ['fetch', 'fetchval', 'fetchrow']:
            await self._cache_result(plan.cache_key, result, plan.cache_ttl)
        
        return result
    
    def _get_prepared_statement_name(self, query: str) -> str:
        """Generate prepared statement name from query."""
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        return f"stmt_{query_hash}"
    
    async def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Get cached query result."""
        try:
            cached = await self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")
        return None
    
    async def _cache_result(self, cache_key: str, result: Any, ttl: int):
        """Cache query result."""
        try:
            serialized = json.dumps(result, default=str)
            await self.redis_client.setex(cache_key, ttl, serialized)
        except Exception as e:
            logger.error(f"Cache storage error: {e}")
    
    def _update_query_stats(self, query: str, execution_time: float):
        """Update query execution statistics."""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        
        if query_hash not in self.query_stats:
            self.query_stats[query_hash] = {
                'query': query,
                'count': 0,
                'total_time': 0,
                'min_time': float('inf'),
                'max_time': 0,
                'avg_time': 0
            }
        
        stats = self.query_stats[query_hash]
        stats['count'] += 1
        stats['total_time'] += execution_time
        stats['min_time'] = min(stats['min_time'], execution_time)
        stats['max_time'] = max(stats['max_time'], execution_time)
        stats['avg_time'] = stats['total_time'] / stats['count']
    
    def get_slow_queries(self, threshold: float = 1.0) -> List[Dict[str, Any]]:
        """Get queries that exceed execution time threshold."""
        slow_queries = []
        for query_hash, stats in self.query_stats.items():
            if stats['avg_time'] > threshold:
                slow_queries.append(stats)
        
        return sorted(slow_queries, key=lambda x: x['avg_time'], reverse=True)
    
    async def analyze_query_plan(
        self,
        conn: asyncpg.Connection,
        query: str,
        params: tuple = ()
    ) -> Dict[str, Any]:
        """Analyze PostgreSQL query execution plan."""
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
        result = await conn.fetchval(explain_query, *params)
        
        plan = json.loads(result)[0]
        
        # Extract key metrics
        analysis = {
            'total_time': plan.get('Execution Time', 0),
            'planning_time': plan.get('Planning Time', 0),
            'shared_blocks_hit': plan.get('Shared Hit Blocks', 0),
            'shared_blocks_read': plan.get('Shared Read Blocks', 0),
            'recommendations': []
        }
        
        # Generate recommendations
        if analysis['shared_blocks_read'] > 1000:
            analysis['recommendations'].append("High disk I/O detected. Consider adding indexes.")
        
        if analysis['total_time'] > 1000:
            analysis['recommendations'].append("Slow query detected. Review query structure and indexes.")
        
        return analysis
    
    def optimize_mongodb_aggregation(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optimize MongoDB aggregation pipeline."""
        optimized = []
        
        # Move $match stages early
        match_stages = [stage for stage in pipeline if '$match' in stage]
        other_stages = [stage for stage in pipeline if '$match' not in stage]
        
        optimized.extend(match_stages)
        
        # Optimize $project stages
        project_stages = []
        for stage in other_stages:
            if '$project' in stage:
                project_stages.append(stage)
            else:
                optimized.append(stage)
        
        # Combine multiple $project stages
        if len(project_stages) > 1:
            combined_project = {'$project': {}}
            for stage in project_stages:
                combined_project['$project'].update(stage['$project'])
            optimized.append(combined_project)
        else:
            optimized.extend(project_stages)
        
        # Add index hints
        if match_stages and '$match' in match_stages[0]:
            # Suggest indexes based on match fields
            match_fields = list(match_stages[0]['$match'].keys())
            logger.info(f"Consider creating index on fields: {match_fields}")
        
        return optimized
    
    async def batch_execute(
        self,
        conn: Union[asyncpg.Connection, asyncpg.Pool],
        queries: List[Tuple[str, tuple]],
        batch_size: int = 100
    ) -> List[Any]:
        """Execute multiple queries in batches for better performance."""
        results = []
        
        for i in range(0, len(queries), batch_size):
            batch = queries[i:i + batch_size]
            
            # Execute batch in transaction
            async with conn.transaction():
                batch_results = await asyncio.gather(*[
                    conn.fetch(query, *params) for query, params in batch
                ])
                results.extend(batch_results)
        
        return results


class IndexAdvisor:
    """Advises on index creation based on query patterns."""
    
    def __init__(self):
        self.query_patterns: Dict[str, int] = {}
        self.table_access_patterns: Dict[str, Dict[str, int]] = {}
    
    def analyze_query(self, query: str):
        """Analyze query to determine index recommendations."""
        # Extract WHERE clause conditions
        where_conditions = self._extract_where_conditions(query)
        
        # Extract JOIN conditions
        join_conditions = self._extract_join_conditions(query)
        
        # Extract ORDER BY columns
        order_by_columns = self._extract_order_by_columns(query)
        
        # Update access patterns
        for table, columns in where_conditions.items():
            if table not in self.table_access_patterns:
                self.table_access_patterns[table] = {}
            
            for column in columns:
                self.table_access_patterns[table][column] = \
                    self.table_access_patterns[table].get(column, 0) + 1
    
    def _extract_where_conditions(self, query: str) -> Dict[str, List[str]]:
        """Extract WHERE clause conditions from query."""
        # Simplified extraction - in production, use proper SQL parser
        conditions = {}
        # Implementation would use sqlparse or similar
        return conditions
    
    def _extract_join_conditions(self, query: str) -> List[Tuple[str, str]]:
        """Extract JOIN conditions from query."""
        # Simplified extraction
        return []
    
    def _extract_order_by_columns(self, query: str) -> List[str]:
        """Extract ORDER BY columns from query."""
        # Simplified extraction
        return []
    
    def get_index_recommendations(self) -> List[str]:
        """Generate index recommendations based on query patterns."""
        recommendations = []
        
        for table, columns in self.table_access_patterns.items():
            # Recommend indexes for frequently accessed columns
            frequent_columns = sorted(
                columns.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]  # Top 3 columns
            
            if frequent_columns:
                columns_str = ', '.join([col[0] for col in frequent_columns])
                recommendations.append(
                    f"CREATE INDEX idx_{table}_{frequent_columns[0][0]} "
                    f"ON {table} ({columns_str});"
                )
        
        return recommendations