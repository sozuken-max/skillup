#!/usr/bin/env python3
"""
SkillUP Notebook Migration Helper

This script helps migrate evaluation notebooks from scattered locations into the
consolidated skillup/notebooks/ directory.

Usage:
    python migrate_notebooks.py --check    # Check current status
    python migrate_notebooks.py --help     # Show detailed migration steps
"""

import os
import subprocess
from pathlib import Path
from typing import List, Tuple

# Configuration
WORKSPACE_ROOT = "/Workspace/Users/yzouyang-iss@u.nus.edu"
REPO_ROOT = f"{WORKSPACE_ROOT}/skillup"
TARGET_DIR = f"{REPO_ROOT}/notebooks"

# Notebooks to migrate
NOTEBOOKS = [
    {
        "name": "Technique_Validation",
        "old_path": f"{WORKSPACE_ROOT}/Technique_Validation",
        "new_path": f"{TARGET_DIR}/Technique_Validation",
        "notebook_id": "1353956204946915",
        "priority": "HIGH",
        "description": "IRS technique validation (8 methods)"
    },
    {
        "name": "Test_Runner",
        "old_path": f"{WORKSPACE_ROOT}/notebooks/Test_Runner",
        "new_path": f"{TARGET_DIR}/Test_Runner",
        "notebook_id": "984473343373211",
        "priority": "MEDIUM",
        "description": "Comprehensive test suite"
    },
    {
        "name": "Quick_Smoke_Tests",
        "old_path": f"{WORKSPACE_ROOT}/notebooks/Quick_Smoke_Tests",
        "new_path": f"{TARGET_DIR}/Quick_Smoke_Tests",
        "notebook_id": "984473343373212",
        "priority": "MEDIUM",
        "description": "Fast health checks (<30s)"
    },
    {
        "name": "Coverage_Analysis",
        "old_path": f"{WORKSPACE_ROOT}/notebooks/Coverage_Analysis",
        "new_path": f"{TARGET_DIR}/Coverage_Analysis",
        "notebook_id": "984473343373213",
        "priority": "MEDIUM",
        "description": "Detailed coverage reporting"
    },
]


def check_notebook_status() -> List[Tuple[str, str, str]]:
    """
    Check the current location status of all notebooks.
    
    Returns:
        List of (notebook_name, status, location) tuples
    """
    results = []
    
    print("="*70)
    print("🔍 NOTEBOOK MIGRATION STATUS CHECK")
    print("="*70)
    print()
    
    for nb in NOTEBOOKS:
        name = nb["name"]
        old_exists = os.path.exists(nb["old_path"])
        new_exists = os.path.exists(nb["new_path"])
        
        if new_exists:
            status = "✅ MIGRATED"
            location = nb["new_path"]
        elif old_exists:
            status = "⚠️  NEEDS MIGRATION"
            location = nb["old_path"]
        else:
            status = "❌ NOT FOUND"
            location = "Unknown"
        
        results.append((name, status, location))
        
        # Print detailed status
        print(f"[{nb['priority']}] {name}")
        print(f"   Status: {status}")
        print(f"   Location: {location}")
        print(f"   Description: {nb['description']}")
        
        if status == "⚠️  NEEDS MIGRATION":
            print(f"   👉 Action: Move to {nb['new_path']}")
        
        print()
    
    return results


def show_migration_instructions():
    """
    Display detailed migration instructions.
    """
    print("="*70)
    print("📦 NOTEBOOK MIGRATION INSTRUCTIONS")
    print("="*70)
    print()
    print("🔑 Prerequisites:")
    print("   1. Databricks CLI installed and authenticated")
    print("   2. Access to workspace notebooks")
    print("   3. Git repo cloned to correct location")
    print()
    print("="*70)
    print("🚀 Migration Methods")
    print("="*70)
    print()
    
    print("🎯 METHOD 1: Databricks CLI (Recommended)")
    print("-" * 70)
    print()
    
    for nb in NOTEBOOKS:
        if nb["name"] == "Technique_Validation":  # Only needs migration
            print(f"# {nb['name']} - {nb['description']}")
            print(f"databricks workspace mv \\")
            print(f"  {nb['old_path']} \\")
            print(f"  {nb['new_path']}")
            print()
    
    print()
    print("🔧 METHOD 2: Databricks UI (Manual)")
    print("-" * 70)
    print()
    print("For each notebook that needs migration:")
    print("   1. Navigate to the old notebook location in Databricks UI")
    print("   2. Right-click notebook → Export → Download as .ipynb")
    print(f"   3. Navigate to {TARGET_DIR} in Databricks UI")
    print("   4. Import the downloaded .ipynb file")
    print("   5. Verify the notebook opens and works correctly")
    print("   6. Delete the old notebook from original location")
    print()
    
    print()
    print("📝 METHOD 3: Git-Based (If notebooks in Git)")
    print("-" * 70)
    print()
    print("If notebooks are tracked in Git:")
    print("   1. cd /Workspace/Users/yzouyang-iss@u.nus.edu/skillup")
    print("   2. git mv ../Technique_Validation.ipynb notebooks/")
    print("   3. git commit -m 'Relocate notebooks to notebooks/ directory'")
    print("   4. git push")
    print()
    
    print("="*70)
    print("✅ POST-MIGRATION VERIFICATION")
    print("="*70)
    print()
    print("After migration, verify:")
    print("   1. Run this script again: python migrate_notebooks.py --check")
    print("   2. Open each migrated notebook and verify it loads")
    print("   3. Run Quick_Smoke_Tests.ipynb to verify functionality")
    print("   4. Update any bookmarks or external references")
    print()
    print("📚 Documentation: See EVALUATION_SETUP.md for full details")
    print()


def show_summary(results: List[Tuple[str, str, str]]):
    """
    Display migration summary.
    """
    migrated = sum(1 for _, status, _ in results if "✅" in status)
    needs_migration = sum(1 for _, status, _ in results if "⚠️" in status)
    not_found = sum(1 for _, status, _ in results if "❌" in status)
    total = len(results)
    
    print("="*70)
    print("📊 MIGRATION SUMMARY")
    print("="*70)
    print()
    print(f"Total Notebooks:      {total}")
    print(f"✅ Migrated:            {migrated}")
    print(f"⚠️  Needs Migration:     {needs_migration}")
    print(f"❌ Not Found:           {not_found}")
    print()
    
    if needs_migration > 0:
        print("👉 Next Steps:")
        print("   Run: python migrate_notebooks.py --help")
        print("   To see detailed migration instructions")
        print()
    elif migrated == total:
        print("✅ All notebooks successfully migrated!")
        print()
        print("👉 Next Steps:")
        print("   1. Run Quick_Smoke_Tests.ipynb to verify functionality")
        print("   2. Update EVALUATION_SETUP.md checklist")
        print("   3. Update any external references or documentation")
        print()


def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        show_migration_instructions()
        return
    
    # Check status
    results = check_notebook_status()
    show_summary(results)
    
    # Show path configuration
    print("="*70)
    print("📁 PATH CONFIGURATION")
    print("="*70)
    print()
    print(f"Workspace Root:  {WORKSPACE_ROOT}")
    print(f"Skillup Repo:    {REPO_ROOT}")
    print(f"Target Directory: {TARGET_DIR}")
    print()
    print(f"Evaluation Artifacts (Volumes):")
    print(f"                 /Volumes/workspace/default/iss-scratchpad/evaluation/")
    print()


if __name__ == "__main__":
    main()
