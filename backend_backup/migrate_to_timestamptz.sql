-- Migration script to convert TIMESTAMP columns to TIMESTAMPTZ
-- Run this on your Railway database to update existing schema

-- First, let's check the current column types
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_schema = 'public' 
    AND table_name IN ('users', 'bill_of_lading', 'password_reset_tokens', 'audit_logs')
    AND column_name LIKE '%_at' OR column_name = 'timestamp'
ORDER BY table_name, column_name;

-- Migration for users table
ALTER TABLE users 
ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';

-- Migration for bill_of_lading table
ALTER TABLE bill_of_lading 
ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';

ALTER TABLE bill_of_lading 
ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';

-- Handle receipt_uploaded_at and completed_at columns (they might be NULL)
ALTER TABLE bill_of_lading 
ALTER COLUMN receipt_uploaded_at TYPE TIMESTAMPTZ USING 
    CASE 
        WHEN receipt_uploaded_at IS NOT NULL 
        THEN receipt_uploaded_at AT TIME ZONE 'UTC' 
        ELSE NULL 
    END;

ALTER TABLE bill_of_lading 
ALTER COLUMN completed_at TYPE TIMESTAMPTZ USING 
    CASE 
        WHEN completed_at IS NOT NULL 
        THEN completed_at AT TIME ZONE 'UTC' 
        ELSE NULL 
    END;

-- Migration for password_reset_tokens table
ALTER TABLE password_reset_tokens 
ALTER COLUMN expires_at TYPE TIMESTAMPTZ USING expires_at AT TIME ZONE 'UTC';

ALTER TABLE password_reset_tokens 
ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';

-- Migration for audit_logs table
ALTER TABLE audit_logs 
ALTER COLUMN timestamp TYPE TIMESTAMPTZ USING timestamp AT TIME ZONE 'UTC';

-- Verify the changes
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_schema = 'public' 
    AND table_name IN ('users', 'bill_of_lading', 'password_reset_tokens', 'audit_logs')
    AND column_name LIKE '%_at' OR column_name = 'timestamp'
ORDER BY table_name, column_name; 