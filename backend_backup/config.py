import os
from dotenv import load_dotenv
import psycopg2
import time

# Load environment variables - try local first, then production
if os.path.exists('env.local'):
    load_dotenv('env.local')
elif os.path.exists('env.production'):
    load_dotenv('env.production')
else:
    load_dotenv()

# Database Configuration
class DatabaseConfig:
    DB_NAME = os.getenv('DB_NAME', 'testdb')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '123456')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')

# Email Configuration
class EmailConfig:
    SMTP_SERVER = os.getenv('SMTP_SERVER')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    FROM_EMAIL = os.getenv('FROM_EMAIL', 'ray6330099@gmail.com')

# OCR Configuration
class OCRConfig:
    pass  # No longer needed, but kept for compatibility

# File Paths
class PathConfig:
    UPLOADS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    REPORTS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')

# JWT Configuration
class JWTConfig:
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'change-this-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 86400))  # 24 hours

# Update database connection function to use config with timeout and retry
def get_db_conn(max_retries=3, retry_delay=2):
    for attempt in range(max_retries):
        try:
            print(f"Connecting to database: {DatabaseConfig.DB_NAME} at {DatabaseConfig.DB_HOST}:{DatabaseConfig.DB_PORT} (attempt {attempt + 1})")
            conn = psycopg2.connect(
                dbname=DatabaseConfig.DB_NAME,
                user=DatabaseConfig.DB_USER,
                password=DatabaseConfig.DB_PASSWORD,
                host=DatabaseConfig.DB_HOST,
                port=DatabaseConfig.DB_PORT,
                connect_timeout=10,  # 10 second connection timeout
                options='-c statement_timeout=30000'  # 30 second query timeout
            )
            print("Database connection established successfully")
            return conn
        except Exception as e:
            print(f"Error connecting to database (attempt {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Failed to connect to database after {max_retries} attempts")
                print(f"Database config: {DatabaseConfig.DB_NAME}, {DatabaseConfig.DB_USER}, {DatabaseConfig.DB_HOST}, {DatabaseConfig.DB_PORT}")
                return None
