import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache(maxsize=1)
def sb() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
