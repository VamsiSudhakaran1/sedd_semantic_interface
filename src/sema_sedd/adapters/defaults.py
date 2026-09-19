"""Composition of shipped adapters; no concrete adapter is imported until requested."""

from sema_sedd.adapters.registry import AdapterRegistry


def default_registry() -> AdapterRegistry:
    from sema_sedd.adapters.e172_0225 import E172_0225Adapter

    return AdapterRegistry((E172_0225Adapter(),))
