"""Fail-closed rights authorization services.

Import concrete models and services from their focused modules. Keeping this
initializer side-effect free prevents infrastructure repositories from loading
the gate service and creating circular imports.
"""
