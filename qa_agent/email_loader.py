from __future__ import annotations

import importlib.util
from pathlib import Path


def load_email_sender_class():
    sender_path = Path(__file__).resolve().parent.parent / "email" / "email_sender.py"
    spec = importlib.util.spec_from_file_location("qa_agent_manual_email_sender", sender_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load email sender from {sender_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.EmailSender

