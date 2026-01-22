"""
Master agents for Cortex platform.

Masters orchestrate workers to accomplish complex tasks.
"""

from masters.coordinator_master import CoordinatorMaster
from masters.security_master import SecurityMaster

__all__ = ["CoordinatorMaster", "SecurityMaster"]
