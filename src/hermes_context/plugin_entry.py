"""Opt-in Hermes ContextEngine plugin, copied by hermes-context install-hermes.

This module does not edit Hermes config. Select context.engine: hermes_context
only after installing the library into the same Python environment as Hermes.
"""
from pathlib import Path


def register(ctx):
    from hermes_context.installation import create_engine, read_options
    options = read_options(Path(__file__).with_name("options.json"))
    ctx.register_context_engine(create_engine(options))
