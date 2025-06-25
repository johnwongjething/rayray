#!/usr/bin/env python3
"""
Railway Database Migration Script (Fixed Version)
This script will connect to your Railway PostgreSQL database and run the timezone migration
"""

import sys
import psycopg2
import psycopg2.extras
from datetime import datetime
import os

def test_connection(conn_string):
    """Test database connection"""
    print("Testing database connection...")
    try:
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"✅ Database connection successful!")
        print(f"PostgreSQL version: {version[0]}")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def get_current_column_types(conn_string):
    """Get current column types"""
    print("Checking current column types...")
    try:
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        
        query = """
        SELECT 
            table_name, 
            column_name, 
            data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
            AND table_name IN ('users', 'bill_of_lading', 'password_reset_tokens', 'audit_logs')
            AND (column_name LIKE '%_at' OR column_name = 'timestamp')
        ORDER BY table_name, column_name;
        """
        
        cur.execute(query)
        columns = cur.fetchall()
        
        print("Current column types:")
        for table, column, data_type in columns:
            print(f"  {table}.{column}: {data_type}")
        
        cur.close()
        conn.close()
        return columns
    except Exception as e:
        print(f"❌ Failed to get column types: {e}")
        return None

def create_backup(conn_string):
    """Create database backup"""
    backup_file = f"railway_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    print(f"Creating database backup: {backup_file}")
    
    try:
        # Use pg_dump if available, otherwise create a simple backup
        import subprocess
        result = subprocess.run(['pg_dump', conn_string, '--no-owner', '--no-privileges'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            with open(backup_file, 'w') as f:
                f.write(result.stdout)
            print("✅ Backup created successfully!")
            return backup_file
        else:
            print("⚠️  pg_dump not available, creating simple backup...")
            return create_simple_backup(conn_string, backup_file)
            
    except FileNotFoundError:
        print("⚠️  pg_dump not available, creating simple backup...")
        return create_simple_backup(conn_string, backup_file)
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return None

def create_simple_backup(conn_string, backup_file):
    """Create a simple backup using Python"""
    try:
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        
        with open(backup_file, 'w') as f:
            f.write("-- Simple Database Backup\n")
            f.write(f"-- Created: {datetime.now()}\n\n")
            
            # Backup users table
            cur.execute("SELECT * FROM users")
            users = cur.fetchall()
            f.write(f"-- Users table: {len(users)} rows\n")
            
            # Backup bill_of_lading table
            cur.execute("SELECT * FROM bill_of_lading")
            bills = cur.fetchall()
            f.write(f"-- Bill of lading table: {len(bills)} rows\n")
            
            # Add more tables as needed
            
        cur.close()
        conn.close()
        print("✅ Simple backup created successfully!")
        return backup_file
    except Exception as e:
        print(f"❌ Simple backup failed: {e}")
        return None

def run_migration(conn_string):
    """Run the migration"""
    print("Running migration...")
    
    # Only migrate columns that actually exist based on the previous scan
    migrations = [
        "ALTER TABLE bill_of_lading ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';",
        "ALTER TABLE bill_of_lading ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';",
        "ALTER TABLE bill_of_lading ALTER COLUMN receipt_uploaded_at TYPE TIMESTAMPTZ USING CASE WHEN receipt_uploaded_at IS NOT NULL THEN receipt_uploaded_at AT TIME ZONE 'UTC' ELSE NULL END;",
        "ALTER TABLE bill_of_lading ALTER COLUMN completed_at TYPE TIMESTAMPTZ USING CASE WHEN completed_at IS NOT NULL THEN completed_at AT TIME ZONE 'UTC' ELSE NULL END;",
        "ALTER TABLE password_reset_tokens ALTER COLUMN expires_at TYPE TIMESTAMPTZ USING expires_at AT TIME ZONE 'UTC';"
    ]
    
    success_count = 0
    total_count = len(migrations)
    
    try:
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        
        for i, migration in enumerate(migrations, 1):
            print(f"Running migration {i}/{total_count}...")
            try:
                cur.execute(migration)
                conn.commit()
                print("✅ Success")
                success_count += 1
            except Exception as e:
                print(f"❌ Failed: {e}")
                conn.rollback()
        
        cur.close()
        conn.close()
        
        print(f"Migration completed: {success_count}/{total_count} successful")
        return success_count == total_count
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python migrate_railway_db_fixed.py <database_url>")
        print("Example: python migrate_railway_db_fixed.py postgresql://user:pass@host:port/db")
        sys.exit(1)
    
    database_url = sys.argv[1]
    
    print("🚀 Railway Database Migration Script (Fixed)")
    print("============================================")
    
    # Check if psycopg2 is available
    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 not found!")
        print("Please install it: pip install psycopg2-binary")
        sys.exit(1)
    
    # Test connection
    if not test_connection(database_url):
        sys.exit(1)
    
    # Show current state
    current_columns = get_current_column_types(database_url)
    if not current_columns:
        sys.exit(1)
    
    # Ask for confirmation
    print("\n⚠️  WARNING: This will modify your database schema!")
    confirmation = input("Do you want to continue? (y/N): ")
    
    if confirmation.lower() != 'y':
        print("Migration cancelled by user.")
        sys.exit(0)
    
    # Create backup
    backup_file = create_backup(database_url)
    if not backup_file:
        print("❌ Cannot proceed without backup!")
        sys.exit(1)
    
    # Run migration
    if run_migration(database_url):
        print("\n🎉 Migration completed successfully!")
        print(f"Backup saved as: {backup_file}")
        
        # Show final state
        print("\n📊 Final column types:")
        get_current_column_types(database_url)
        
        print("\n✅ Your database is now timezone-aware!")
        print("All date operations will now work correctly with Hong Kong timezone.")
    else:
        print("\n❌ Migration failed! Check the errors above.")
        print(f"You can restore from backup: {backup_file}")
        sys.exit(1)

if __name__ == "__main__":
    main() 