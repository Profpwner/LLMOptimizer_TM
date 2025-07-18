package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
)

var logger *zap.Logger

func init() {
	// Load environment variables
	if err := godotenv.Load(); err != nil {
		log.Printf("Warning: .env file not found")
	}

	// Initialize logger
	var err error
	if os.Getenv("ENVIRONMENT") == "production" {
		logger, err = zap.NewProduction()
	} else {
		logger, err = zap.NewDevelopment()
	}
	if err != nil {
		log.Fatalf("Failed to initialize logger: %v", err)
	}
}

func main() {
	defer logger.Sync()

	// Set Gin mode
	if os.Getenv("ENVIRONMENT") == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	// Create router
	router := gin.New()
	
	// Middleware
	router.Use(gin.Recovery())
	router.Use(RequestLogger())
	router.Use(CORSMiddleware())

	// Health check endpoints
	router.GET("/health", healthCheck)
	router.GET("/ready", readinessCheck)

	// Metrics endpoint
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// API routes
	v1 := router.Group("/api/v1")
	{
		// Auth service proxy
		auth := v1.Group("/auth")
		{
			auth.POST("/register", proxyToAuthService("/register"))
			auth.POST("/login", proxyToAuthService("/login"))
			auth.POST("/refresh", proxyToAuthService("/refresh"))
			auth.POST("/logout", proxyToAuthService("/logout"))
		}

		// Content service proxy
		content := v1.Group("/content")
		content.Use(AuthMiddleware())
		{
			content.GET("", proxyToContentService(""))
			content.POST("", proxyToContentService(""))
			content.GET("/:id", proxyToContentService("/:id"))
			content.PUT("/:id", proxyToContentService("/:id"))
			content.DELETE("/:id", proxyToContentService("/:id"))
		}

		// Analytics service proxy
		analytics := v1.Group("/analytics")
		analytics.Use(AuthMiddleware())
		{
			analytics.GET("/dashboard", proxyToAnalyticsService("/dashboard"))
			analytics.GET("/reports", proxyToAnalyticsService("/reports"))
			analytics.POST("/track", proxyToAnalyticsService("/track"))
		}

		// ML service proxy
		ml := v1.Group("/ml")
		ml.Use(AuthMiddleware())
		{
			ml.POST("/optimize", proxyToMLService("/optimize"))
			ml.POST("/analyze", proxyToMLService("/analyze"))
			ml.GET("/models", proxyToMLService("/models"))
		}
	}

	// Swagger documentation
	router.Static("/docs", "./docs/swagger")

	// Start server
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	srv := &http.Server{
		Addr:    ":" + port,
		Handler: router,
	}

	// Graceful shutdown
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("Failed to start server", zap.Error(err))
		}
	}()

	logger.Info("API Gateway started", zap.String("port", port))

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("Shutting down server...")

	// Graceful shutdown with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		logger.Fatal("Server forced to shutdown", zap.Error(err))
	}

	logger.Info("Server exited")
}

func healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":  "healthy",
		"service": "api-gateway",
		"version": os.Getenv("VERSION"),
	})
}

func readinessCheck(c *gin.Context) {
	// Check if all dependent services are reachable
	services := map[string]string{
		"auth":      getServiceURL("auth-service"),
		"content":   getServiceURL("content-service"),
		"analytics": getServiceURL("analytics-service"),
		"ml":        getServiceURL("ml-service"),
	}

	allHealthy := true
	serviceStatus := make(map[string]bool)

	for name, url := range services {
		resp, err := http.Get(url + "/health")
		if err != nil || resp.StatusCode != http.StatusOK {
			allHealthy = false
			serviceStatus[name] = false
		} else {
			serviceStatus[name] = true
		}
		if resp != nil {
			resp.Body.Close()
		}
	}

	status := http.StatusOK
	if !allHealthy {
		status = http.StatusServiceUnavailable
	}

	c.JSON(status, gin.H{
		"ready":    allHealthy,
		"services": serviceStatus,
	})
}

// Middleware functions
func RequestLogger() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		raw := c.Request.URL.RawQuery

		c.Next()

		latency := time.Since(start)
		if raw != "" {
			path = path + "?" + raw
		}

		logger.Info("Request",
			zap.Int("status", c.Writer.Status()),
			zap.String("method", c.Request.Method),
			zap.String("path", path),
			zap.String("ip", c.ClientIP()),
			zap.Duration("latency", latency),
			zap.String("user-agent", c.Request.UserAgent()),
		)
	}
}

func CORSMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Requested-With")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, DELETE")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}

func AuthMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		token := c.GetHeader("Authorization")
		if token == "" {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Authorization token required"})
			c.Abort()
			return
		}

		// TODO: Validate token with auth service
		// For now, just pass through
		c.Next()
	}
}

// Proxy functions
func proxyToAuthService(path string) gin.HandlerFunc {
	return createProxy("auth-service", path)
}

func proxyToContentService(path string) gin.HandlerFunc {
	return createProxy("content-service", path)
}

func proxyToAnalyticsService(path string) gin.HandlerFunc {
	return createProxy("analytics-service", path)
}

func proxyToMLService(path string) gin.HandlerFunc {
	return createProxy("ml-service", path)
}

func createProxy(service, path string) gin.HandlerFunc {
	return func(c *gin.Context) {
		// TODO: Implement proper reverse proxy
		// For now, just return a placeholder response
		c.JSON(http.StatusOK, gin.H{
			"message": fmt.Sprintf("Proxy to %s%s", service, path),
			"status":  "not_implemented",
		})
	}
}

func getServiceURL(service string) string {
	// In Kubernetes, services are accessible by their name
	if os.Getenv("KUBERNETES_SERVICE_HOST") != "" {
		return fmt.Sprintf("http://%s", service)
	}
	// In Docker Compose, use service names
	return fmt.Sprintf("http://%s:8000", service)
}