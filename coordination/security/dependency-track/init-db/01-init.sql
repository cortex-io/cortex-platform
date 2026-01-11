-- Dependency-Track PostgreSQL Initialization
-- This script is executed automatically on first database creation

-- Set connection parameters
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For fuzzy text search

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE dtrack TO dtrack;

-- Create indexes for better performance
-- These will be created on tables that Dependency-Track creates
-- This is just a placeholder for custom optimizations

-- Log initialization
DO $$
BEGIN
  RAISE NOTICE 'Dependency-Track database initialized successfully';
END $$;
