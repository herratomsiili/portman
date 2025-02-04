import os

# Default PostgreSQL settings
DATABASE_CONFIG = {
    "dbname": os.getenv("DB_NAME", "portman"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 5432))
}
