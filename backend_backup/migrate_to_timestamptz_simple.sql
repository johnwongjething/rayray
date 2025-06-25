-- Simple Migration Script for Railway Database
-- Run these commands one by one in your Railway database

-- Step 1: Check current column types
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_schema = 'public' 
    AND table_name IN ('users', 'bill_of_lading', 'password_reset_tokens', 'audit_logs')
    AND (column_name LIKE '%_at' OR column_name = 'timestamp')
ORDER BY table_name, column_name;

-- Step 2: Convert users.created_at
ALTER TABLE users 
ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';

-- Step 3: Convert bill_of_lading.created_at
ALTER TABLE bill_of_lading 
ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';

-- Step 4: Convert bill_of_lading.updated_at
ALTER TABLE bill_of_lading 
ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';

-- Step 5: Convert bill_of_lading.receipt_uploaded_at (if exists)
ALTER TABLE bill_of_lading 
ALTER COLUMN receipt_uploaded_at TYPE TIMESTAMPTZ USING 
    CASE 
        WHEN receipt_uploaded_at IS NOT NULL 
        THEN receipt_uploaded_at AT TIME ZONE 'UTC' 
        ELSE NULL 
    END;

-- Step 6: Convert bill_of_lading.completed_at (if exists)
ALTER TABLE bill_of_lading 
ALTER COLUMN completed_at TYPE TIMESTAMPTZ USING 
    CASE 
        WHEN completed_at IS NOT NULL 
        THEN completed_at AT TIME ZONE 'UTC' 
        ELSE NULL 
    END;

-- Step 7: Convert password_reset_tokens.expires_at
ALTER TABLE password_reset_tokens 
ALTER COLUMN expires_at TYPE TIMESTAMPTZ USING expires_at AT TIME ZONE 'UTC';

-- Step 8: Convert password_reset_tokens.created_at
ALTER TABLE password_reset_tokens 
ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';

-- Step 9: Convert audit_logs.timestamp
ALTER TABLE audit_logs 
ALTER COLUMN timestamp TYPE TIMESTAMPTZ USING timestamp AT TIME ZONE 'UTC';

-- Step 10: Verify all changes
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_schema = 'public' 
    AND table_name IN ('users', 'bill_of_lading', 'password_reset_tokens', 'audit_logs')
    AND (column_name LIKE '%_at' OR column_name = 'timestamp')
ORDER BY table_name, column_name; 