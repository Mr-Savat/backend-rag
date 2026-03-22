"""
Database connection and operations using Supabase client + direct PostgreSQL for pgvector.
"""
from supabase import create_client, Client
from config import settings

# Supabase client (for auth, storage, and regular CRUD)
supabase_client: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key or settings.supabase_anon_key,
)

# PostgreSQL connection string for pgvector operations
def get_pg_connection_string() -> str:
    """
    Build PostgreSQL connection string for pgvector.
    Falls back to DATABASE_URL if set, otherwise builds from Supabase URL.
    """
    if settings.database_url:
        return settings.database_url

    # Extract from Supabase URL if DATABASE_URL not provided
    # You can get the connection string from Supabase Dashboard → Settings → Database → Connection string
    # Format: postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
    raise ValueError(
        "DATABASE_URL is not set. "
        "Please set it in backend/.env with your Supabase PostgreSQL connection string. "
        "Find it in: Supabase Dashboard → Settings → Database → Connection string (URI)"
    )


def get_supabase() -> Client:
    """Get the Supabase client instance."""
    return supabase_client
