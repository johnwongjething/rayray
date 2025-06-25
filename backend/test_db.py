import psycopg2

try:
    print("psycopg2 is installed")
    print("psycopg2 version:", psycopg2.__version__)
except ImportError as e:
    print("Error:", str(e))
