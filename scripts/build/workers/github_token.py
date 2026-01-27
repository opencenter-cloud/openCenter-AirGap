"""GitHub token validation worker.

Validates that GITHUB_TOKEN environment variable is set and valid
for accessing GitHub Container Registry.
"""

import os
import sys
from pathlib import Path


def check_github_token_worker(project_root: Path) -> bool:
    """Check GitHub token environment variable.
    
    Validates that GITHUB_TOKEN is set. In non-interactive mode, fails if not set.
    In interactive mode, prompts the user to set it.
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        True if token is set, False otherwise
    """
    print("\n=== Checking GitHub Token ===\n")
    
    token = os.environ.get("GITHUB_TOKEN")
    non_interactive = os.environ.get("NON_INTERACTIVE", "").lower() in ("1", "true", "yes")
    
    if token:
        # Mask token for display
        masked_token = token[:4] + "..." + token[-4:] if len(token) > 8 else "***"
        print(f"✓ GITHUB_TOKEN is set: {masked_token}")
        print("✓ Token will be used for GitHub Container Registry access\n")
        return True
    
    print("⚠ GITHUB_TOKEN environment variable is not set")
    print("\nThe GitHub token is required to:")
    print("  - Pull images from GitHub Container Registry (ghcr.io)")
    print("  - Avoid rate limiting on public repositories")
    
    if non_interactive:
        print("\nERROR: Running in non-interactive mode, cannot prompt for token")
        print("Please set GITHUB_TOKEN environment variable and re-run:")
        print("  export GITHUB_TOKEN=your_token_here")
        print("  python3 scripts/build/build.py")
        return False
    
    print("\nOptions:")
    print("  1. Set GITHUB_TOKEN now and re-run the build")
    print("  2. Continue without token (may encounter rate limits)")
    print("  3. Exit and set token manually")
    
    while True:
        try:
            choice = input("\nEnter choice (1/2/3): ").strip()
            
            if choice == "1":
                print("\nTo set GITHUB_TOKEN:")
                print("  1. Create a Personal Access Token at: https://github.com/settings/tokens")
                print("  2. Grant 'read:packages' scope")
                print("  3. Export the token:")
                print("     export GITHUB_TOKEN=your_token_here")
                print("  4. Re-run the build")
                return False
            
            elif choice == "2":
                print("\n⚠ Continuing without GITHUB_TOKEN")
                print("You may encounter rate limits or authentication errors\n")
                return True
            
            elif choice == "3":
                print("\nExiting. Please set GITHUB_TOKEN and re-run the build.")
                return False
            
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                
        except (EOFError, KeyboardInterrupt):
            print("\n\nBuild interrupted by user")
            return False
