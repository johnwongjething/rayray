# Railway Database Migration Script (Simple Version)
# This script will connect to your Railway PostgreSQL database and run the timezone migration

param(
    [Parameter(Mandatory=$true)]
    [string]$DatabaseUrl
)

Write-Host "Railway Database Migration Script" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green

# Check if psql is available
try {
    $psqlVersion = & psql --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "psql not found"
    }
    Write-Host "PostgreSQL client found: $psqlVersion" -ForegroundColor Green
} catch {
    Write-Host "PostgreSQL client (psql) not found!" -ForegroundColor Red
    Write-Host "Please install PostgreSQL client tools:" -ForegroundColor Yellow
    Write-Host "1. Download from: https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
    Write-Host "2. Or install via Chocolatey: choco install postgresql" -ForegroundColor Yellow
    Write-Host "3. Make sure psql is in your PATH" -ForegroundColor Yellow
    exit 1
}

# Function to test database connection
function Test-DatabaseConnection {
    param([string]$ConnectionString)
    
    Write-Host "Testing database connection..." -ForegroundColor Yellow
    
    $testQuery = "SELECT version();"
    $result = & psql $ConnectionString -c $testQuery 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Database connection successful!" -ForegroundColor Green
        return $true
    } else {
        Write-Host "Database connection failed!" -ForegroundColor Red
        Write-Host "Error: $result" -ForegroundColor Red
        return $false
    }
}

# Function to create backup
function Backup-Database {
    param([string]$ConnectionString)
    
    $backupFile = "railway_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
    Write-Host "Creating database backup..." -ForegroundColor Yellow
    Write-Host "Backup file: $backupFile" -ForegroundColor Yellow
    
    $result = & pg_dump $ConnectionString --no-owner --no-privileges > $backupFile 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Backup created successfully!" -ForegroundColor Green
        return $backupFile
    } else {
        Write-Host "Backup failed!" -ForegroundColor Red
        Write-Host "Error: $result" -ForegroundColor Red
        return $null
    }
}

# Function to check current column types
function Get-CurrentColumnTypes {
    param([string]$ConnectionString)
    
    Write-Host "Checking current column types..." -ForegroundColor Yellow
    
    $query = "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name IN ('users', 'bill_of_lading', 'password_reset_tokens', 'audit_logs') AND (column_name LIKE '%_at' OR column_name = 'timestamp') ORDER BY table_name, column_name;"
    
    $result = & psql $ConnectionString -c $query 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Current column types:" -ForegroundColor Cyan
        Write-Host $result -ForegroundColor White
        return $result
    } else {
        Write-Host "Failed to get column types!" -ForegroundColor Red
        return $null
    }
}

# Function to run migration
function Run-Migration {
    param([string]$ConnectionString)
    
    Write-Host "Running migration..." -ForegroundColor Yellow
    
    # Migration queries
    $migrations = @(
        "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';",
        "ALTER TABLE bill_of_lading ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';",
        "ALTER TABLE bill_of_lading ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';",
        "ALTER TABLE bill_of_lading ALTER COLUMN receipt_uploaded_at TYPE TIMESTAMPTZ USING CASE WHEN receipt_uploaded_at IS NOT NULL THEN receipt_uploaded_at AT TIME ZONE 'UTC' ELSE NULL END;",
        "ALTER TABLE bill_of_lading ALTER COLUMN completed_at TYPE TIMESTAMPTZ USING CASE WHEN completed_at IS NOT NULL THEN completed_at AT TIME ZONE 'UTC' ELSE NULL END;",
        "ALTER TABLE password_reset_tokens ALTER COLUMN expires_at TYPE TIMESTAMPTZ USING expires_at AT TIME ZONE 'UTC';",
        "ALTER TABLE password_reset_tokens ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';",
        "ALTER TABLE audit_logs ALTER COLUMN timestamp TYPE TIMESTAMPTZ USING timestamp AT TIME ZONE 'UTC';"
    )
    
    $successCount = 0
    $totalCount = $migrations.Count
    
    foreach ($migration in $migrations) {
        Write-Host "Running migration..." -ForegroundColor Yellow
        
        $result = & psql $ConnectionString -c $migration 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Success" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host "Failed: $result" -ForegroundColor Red
        }
    }
    
    Write-Host "Migration completed: $successCount/$totalCount successful" -ForegroundColor $(if ($successCount -eq $totalCount) { "Green" } else { "Yellow" })
    return $successCount -eq $totalCount
}

# Main execution
try {
    # Test connection
    if (-not (Test-DatabaseConnection -ConnectionString $DatabaseUrl)) {
        exit 1
    }
    
    # Show current state
    Get-CurrentColumnTypes -ConnectionString $DatabaseUrl
    
    # Ask for confirmation
    Write-Host ""
    Write-Host "WARNING: This will modify your database schema!" -ForegroundColor Red
    $confirmation = Read-Host "Do you want to continue? (y/N)"
    
    if ($confirmation -ne "y" -and $confirmation -ne "Y") {
        Write-Host "Migration cancelled by user." -ForegroundColor Yellow
        exit 0
    }
    
    # Create backup
    $backupFile = Backup-Database -ConnectionString $DatabaseUrl
    if (-not $backupFile) {
        Write-Host "Cannot proceed without backup!" -ForegroundColor Red
        exit 1
    }
    
    # Run migration
    if (Run-Migration -ConnectionString $DatabaseUrl) {
        Write-Host ""
        Write-Host "Migration completed successfully!" -ForegroundColor Green
        Write-Host "Backup saved as: $backupFile" -ForegroundColor Cyan
        
        # Show final state
        Write-Host ""
        Write-Host "Final column types:" -ForegroundColor Cyan
        Get-CurrentColumnTypes -ConnectionString $DatabaseUrl
        
        Write-Host ""
        Write-Host "Your database is now timezone-aware!" -ForegroundColor Green
        Write-Host "All date operations will now work correctly with Hong Kong timezone." -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "Migration failed! Check the errors above." -ForegroundColor Red
        Write-Host "You can restore from backup: $backupFile" -ForegroundColor Yellow
        exit 1
    }
    
} catch {
    Write-Host "Script error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} 