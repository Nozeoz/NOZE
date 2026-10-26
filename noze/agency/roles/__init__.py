"""The team. Each role = an SOP (``sop/<role>.md``) + its playbook + a Claude call
with a JSON contract, and a deterministic fallback so work never stops."""

from .analyst import Analyst
from .editor import Editor
from .manager import Manager
from .reviewer import Reviewer
from .scout import Scout

__all__ = ["Analyst", "Editor", "Manager", "Reviewer", "Scout"]
