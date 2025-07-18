// MongoDB initialization script
// This script runs when MongoDB container starts for the first time

// Switch to the llmoptimizer database
db = db.getSiblingDB('llmoptimizer');

// Create collections with validation
db.createCollection('users', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['email', 'hashed_password', 'full_name', 'is_active', 'created_at'],
      properties: {
        email: {
          bsonType: 'string',
          pattern: '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
        },
        hashed_password: {
          bsonType: 'string'
        },
        full_name: {
          bsonType: 'string'
        },
        is_active: {
          bsonType: 'bool'
        },
        created_at: {
          bsonType: 'date'
        },
        updated_at: {
          bsonType: 'date'
        }
      }
    }
  }
});

db.createCollection('content', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['user_id', 'title', 'content_type', 'original_content', 'status', 'created_at'],
      properties: {
        user_id: {
          bsonType: 'string'
        },
        title: {
          bsonType: 'string',
          maxLength: 200
        },
        content_type: {
          enum: ['article', 'blog_post', 'product_description', 'social_media', 'email', 'landing_page']
        },
        original_content: {
          bsonType: 'string'
        },
        optimized_content: {
          bsonType: ['string', 'null']
        },
        status: {
          enum: ['draft', 'published', 'archived']
        },
        optimization_score: {
          bsonType: ['number', 'null'],
          minimum: 0,
          maximum: 100
        },
        created_at: {
          bsonType: 'date'
        },
        updated_at: {
          bsonType: 'date'
        }
      }
    }
  }
});

db.createCollection('analytics_events', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['event_type', 'user_id', 'timestamp'],
      properties: {
        event_type: {
          enum: ['page_view', 'content_view', 'content_optimized', 'conversion', 'engagement', 'click']
        },
        content_id: {
          bsonType: ['string', 'null']
        },
        user_id: {
          bsonType: 'string'
        },
        session_id: {
          bsonType: 'string'
        },
        properties: {
          bsonType: 'object'
        },
        timestamp: {
          bsonType: 'date'
        }
      }
    }
  }
});

db.createCollection('ml_requests');
db.createCollection('ml_analysis');
db.createCollection('analytics_reports');

// Create indexes
db.users.createIndex({ email: 1 }, { unique: true });
db.users.createIndex({ created_at: -1 });

db.content.createIndex({ user_id: 1 });
db.content.createIndex({ status: 1 });
db.content.createIndex({ created_at: -1 });
db.content.createIndex({ content_type: 1 });

db.analytics_events.createIndex({ user_id: 1 });
db.analytics_events.createIndex({ content_id: 1 });
db.analytics_events.createIndex({ timestamp: -1 });
db.analytics_events.createIndex({ event_type: 1 });
db.analytics_events.createIndex({ user_id: 1, timestamp: -1 });

db.ml_requests.createIndex({ user_id: 1 });
db.ml_requests.createIndex({ created_at: -1 });
db.ml_requests.createIndex({ status: 1 });

// Create a read-write user for the application
db.createUser({
  user: 'llmoptimizer_app',
  pwd: 'app_password_change_me',
  roles: [
    {
      role: 'readWrite',
      db: 'llmoptimizer'
    }
  ]
});

print('MongoDB initialization completed successfully!');