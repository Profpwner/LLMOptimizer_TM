#!/bin/sh
set -e

# Function to create userlist.txt from environment variables
create_userlist() {
    echo "Creating userlist.txt from environment variables..."
    
    # Clear existing userlist
    > /etc/pgbouncer/userlist.txt
    
    # Add users from environment variables
    if [ -n "$PGBOUNCER_USERS" ]; then
        echo "$PGBOUNCER_USERS" > /etc/pgbouncer/userlist.txt
    else
        # Default user
        echo '"llmoptimizer_app" "md5$(echo -n "${DB_PASSWORD:-password}llmoptimizer_app" | md5sum | cut -d" " -f1)"' >> /etc/pgbouncer/userlist.txt
        echo '"pgbouncer_admin" "md5$(echo -n "${PGBOUNCER_ADMIN_PASSWORD:-admin}pgbouncer_admin" | md5sum | cut -d" " -f1)"' >> /etc/pgbouncer/userlist.txt
        echo '"pgbouncer_stats" "md5$(echo -n "${PGBOUNCER_STATS_PASSWORD:-stats}pgbouncer_stats" | md5sum | cut -d" " -f1)"' >> /etc/pgbouncer/userlist.txt
    fi
    
    chmod 600 /etc/pgbouncer/userlist.txt
    chown pgbouncer:pgbouncer /etc/pgbouncer/userlist.txt
}

# Function to update pgbouncer.ini with environment variables
update_config() {
    echo "Updating pgbouncer.ini with environment variables..."
    
    # Update database connections
    if [ -n "$DB_HOST" ]; then
        sed -i "s/host=postgres-primary/host=$DB_HOST/g" /etc/pgbouncer/pgbouncer.ini
    fi
    
    if [ -n "$DB_HOST_REPLICA" ]; then
        sed -i "s/host=postgres-replica/host=$DB_HOST_REPLICA/g" /etc/pgbouncer/pgbouncer.ini
    fi
    
    if [ -n "$DB_HOST_ANALYTICS" ]; then
        sed -i "s/host=postgres-analytics/host=$DB_HOST_ANALYTICS/g" /etc/pgbouncer/pgbouncer.ini
    fi
    
    # Update pool sizes based on environment
    if [ -n "$POOL_SIZE" ]; then
        sed -i "s/default_pool_size = .*/default_pool_size = $POOL_SIZE/" /etc/pgbouncer/pgbouncer.ini
    fi
    
    if [ -n "$MAX_CLIENT_CONN" ]; then
        sed -i "s/max_client_conn = .*/max_client_conn = $MAX_CLIENT_CONN/" /etc/pgbouncer/pgbouncer.ini
    fi
    
    if [ -n "$MAX_DB_CONNECTIONS" ]; then
        sed -i "s/max_db_connections = .*/max_db_connections = $MAX_DB_CONNECTIONS/" /etc/pgbouncer/pgbouncer.ini
    fi
    
    # Update pool mode if specified
    if [ -n "$POOL_MODE" ]; then
        sed -i "s/pool_mode = .*/pool_mode = $POOL_MODE/" /etc/pgbouncer/pgbouncer.ini
    fi
}

# Function to setup TLS certificates
setup_tls() {
    echo "Setting up TLS certificates..."
    
    # Check if certificates are mounted
    if [ -f "/run/secrets/pgbouncer-ca-cert" ]; then
        cp /run/secrets/pgbouncer-ca-cert /etc/pgbouncer/ca.crt
        chmod 644 /etc/pgbouncer/ca.crt
    fi
    
    if [ -f "/run/secrets/pgbouncer-server-cert" ]; then
        cp /run/secrets/pgbouncer-server-cert /etc/pgbouncer/server.crt
        chmod 644 /etc/pgbouncer/server.crt
    fi
    
    if [ -f "/run/secrets/pgbouncer-server-key" ]; then
        cp /run/secrets/pgbouncer-server-key /etc/pgbouncer/server.key
        chmod 600 /etc/pgbouncer/server.key
        chown pgbouncer:pgbouncer /etc/pgbouncer/server.key
    fi
}

# Main execution
create_userlist
update_config
setup_tls

# Log startup information
echo "Starting PgBouncer with configuration:"
echo "  Pool Mode: ${POOL_MODE:-transaction}"
echo "  Default Pool Size: ${POOL_SIZE:-25}"
echo "  Max Client Connections: ${MAX_CLIENT_CONN:-10000}"
echo "  Max DB Connections: ${MAX_DB_CONNECTIONS:-1000}"

# Execute PgBouncer
exec "$@"