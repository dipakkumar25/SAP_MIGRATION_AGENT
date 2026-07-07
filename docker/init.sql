-- Initialize SAP Migration database
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE sap_migration TO sap_agent;
