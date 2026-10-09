"""The search plugin: search notes and documents through configured providers (decision 11).

Every keyword and provider comes from the plugin's ``config.toml``: qmd, or any program
that takes the text as an argument and prints paths or hits. Providers that share a keyword
are searched at once under one deadline and their hits merged by rank. ``search.plugin`` is
the shell; ``schema``, ``kinds``, ``merge`` and ``answers`` are the pure core.
"""

from search.plugin import main

__all__ = ["main"]
