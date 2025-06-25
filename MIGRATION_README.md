# Railway Database Migration Instructions

This guide will help you migrate your Railway PostgreSQL database to use timezone-aware timestamps.

## Prerequisites

1. **PostgreSQL Client Tools**: You need `psql` and `pg_dump` installed on your system
   - Download from: https://www.postgresql.org/download/windows/
   - Or install via Chocolatey: `choco install postgresql`
   - Make sure `psql` is in your PATH

2. **Railway Database URL**: You need your Railway database connection string
   - Go to your Railway project dashboard
   - Navigate to your PostgreSQL service
   - Click "Connect" → "Connect with psql"
   - Copy the connection string (starts with `postgresql://`)

## Method 1: Easy Way (Recommended)

1. **Double-click** `run_migration.bat`
2. **Enter your Railway database URL** when prompted
3. **Follow the on-screen instructions**
4. **Confirm the migration** when asked

## Method 2: PowerShell Directly

1. **Open PowerShell** in the directory with the migration files
2. **Run the script**:
   ```powershell
   .\migrate_railway_db.ps1 -DatabaseUrl "postgresql://your-connection-string"
   ```

## What the Script Does

1. ✅ **Tests database connection**
2. ✅ **Shows current column types**
3. ✅ **Creates a backup** of your database
4. ✅ **Runs the migration** to convert TIMESTAMP to TIMESTAMPTZ
5. ✅ **Verifies the changes**
6. ✅ **Shows final column types**

## Migration Details

The script converts these columns:
- `users.created_at`
- `bill_of_lading.created_at`
- `bill_of_lading.updated_at`
- `bill_of_lading.receipt_uploaded_at`
- `bill_of_lading.completed_at`
- `password_reset_tokens.expires_at`
- `password_reset_tokens.created_at`
- `audit_logs.timestamp`

## Safety Features

- 🔒 **Automatic backup** before making changes
- 🔍 **Connection testing** before migration
- ⚠️ **Confirmation prompt** before proceeding
- 📊 **Before/after verification** of column types
- 🔄 **Step-by-step progress** reporting

## Troubleshooting

### "psql not found" Error
- Install PostgreSQL client tools
- Make sure `psql` is in your system PATH

### Connection Failed
- Check your Railway database URL
- Make sure your Railway database is running
- Verify the connection string format

### Migration Failed
- Check the error messages
- You can restore from the backup file
- Contact support if needed

## After Migration

Once the migration is complete:
1. ✅ Your database will be timezone-aware
2. ✅ All date operations will work with Hong Kong timezone
3. ✅ Your application will handle dates correctly
4. ✅ Search and filtering will be accurate

## Backup File

The script creates a backup file named: `railway_backup_YYYYMMDD_HHMMSS.sql`

Keep this file safe in case you need to restore your database.

## Support

If you encounter any issues:
1. Check the error messages in the script output
2. Verify your database URL is correct
3. Make sure PostgreSQL client tools are installed
4. Contact support with the error details 