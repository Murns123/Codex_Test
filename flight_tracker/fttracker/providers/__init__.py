from .base import FareProvider
from .ignav import IgnavProvider
from .serpapi import SerpApiProvider

# Order matters: primary first. Providers without a key are skipped. Add new providers here.
PROVIDERS: list[type[FareProvider]] = [IgnavProvider, SerpApiProvider]

__all__ = ["FareProvider", "IgnavProvider", "SerpApiProvider", "PROVIDERS"]
