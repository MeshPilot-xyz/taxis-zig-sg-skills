#!/usr/bin/env python3
"""Standalone entry point — run from any directory.

Usage: python3 ${CLAUDE_SKILL_DIR}/scripts/run.py <command> [args]
"""
import sys
import os

# Ensure the scripts package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.cli import main

main()
