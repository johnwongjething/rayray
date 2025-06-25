#!/usr/bin/env python3
"""
Test script to verify Railway database connection
"""

import psycopg2
from config import DatabaseConfig

def test_railway_connection():
    """Test connection to Railway database"""
    try:
        # Create connection
        conn = psycopg2.connect(
            host=DatabaseConfig.DB_HOST,
            port=DatabaseConfig.DB_PORT,
            database=DatabaseConfig.DB_NAME,
            user=DatabaseConfig.DB_USER,
            password=DatabaseConfig.DB_PASSWORD
        )
        
        print("✅ Successfully connected to Railway database!")
        
        # Test a simple query
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"📊 PostgreSQL Version: {version[0]}")
        
        # Check if tables exist
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cur.fetchall()
        
        if tables:
            print("📋 Existing tables:")
            for table in tables:
                print(f"   - {table[0]}")
        else:
            print("📋 No tables found. You may need to run setup_railway_db.sql")
        
        cur.close()
        conn.close()
        print("✅ Database connection test completed successfully!")
        
    except Exception as e:
        print(f"❌ Failed to connect to Railway database: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔍 Testing Railway Database Connection...")
    print(f"Host: {DatabaseConfig.DB_HOST}")
    print(f"Port: {DatabaseConfig.DB_PORT}")
    print(f"Database: {DatabaseConfig.DB_NAME}")
    print(f"User: {DatabaseConfig.DB_USER}")
    print("-" * 50)
    
    test_railway_connection() 