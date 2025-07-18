FROM pgbouncer/pgbouncer:1.21.0

# Install additional tools
USER root
RUN apk add --no-cache \
    postgresql-client \
    curl \
    ca-certificates \
    openssl

# Create necessary directories
RUN mkdir -p /etc/pgbouncer /var/log/pgbouncer /var/run/pgbouncer && \
    chown -R pgbouncer:pgbouncer /etc/pgbouncer /var/log/pgbouncer /var/run/pgbouncer

# Copy configuration files
COPY pgbouncer.ini /etc/pgbouncer/
COPY userlist.txt /etc/pgbouncer/
COPY --chmod=755 docker-entrypoint.sh /

# Copy TLS certificates (these should be mounted as secrets in production)
# COPY certs/ca.crt /etc/pgbouncer/
# COPY certs/server.crt /etc/pgbouncer/
# COPY certs/server.key /etc/pgbouncer/

# Set proper permissions
RUN chmod 600 /etc/pgbouncer/userlist.txt && \
    chmod 644 /etc/pgbouncer/pgbouncer.ini && \
    chown -R pgbouncer:pgbouncer /etc/pgbouncer

# Health check
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD pg_isready -h localhost -p 6432 || exit 1

# Switch back to pgbouncer user
USER pgbouncer

# Expose PgBouncer port
EXPOSE 6432

# Use custom entrypoint for environment variable substitution
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["pgbouncer", "/etc/pgbouncer/pgbouncer.ini"]