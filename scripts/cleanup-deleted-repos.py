#!/usr/bin/env python3
"""
Cleanup script to remove repositories from index that no longer exist on GitHub.
Compares all indexed repos against current GitHub repos and removes deleted ones.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import re

def get_current_repos():
    """Fetch current list of repos from GitHub using gh CLI."""
    print("📡 Fetching current repository list from GitHub...")
    try:
        result = subprocess.run(
            ['gh', 'repo', 'list', 'danielrosehill', '--limit', '1000', '--json',
             'name,nameWithOwner,description,createdAt,updatedAt,url,stargazerCount,forkCount,repositoryTopics'],
            capture_output=True,
            text=True,
            check=True
        )
        repos = json.loads(result.stdout)
        print(f"✓ Found {len(repos)} repositories on GitHub")
        return {repo['nameWithOwner']: repo for repo in repos}
    except subprocess.CalledProcessError as e:
        print(f"❌ Error fetching repos from GitHub: {e}")
        print(f"❌ Error output: {e.stderr if hasattr(e, 'stderr') else 'No stderr'}")
        sys.exit(1)

def extract_repo_name(line):
    """Extract repository nameWithOwner from markdown link."""
    # Match patterns like [repo-name](https://github.com/owner/repo-name)
    match = re.search(r'\[([^\]]+)\]\(https://github\.com/([^/]+)/([^)]+)\)', line)
    if match:
        owner = match.group(2)
        repo = match.group(3)
        return f"{owner}/{repo}"
    return None

def scan_section_files(sections_dir):
    """Scan all section files and extract indexed repos."""
    print("\n🔍 Scanning section files for indexed repositories...")
    indexed_repos = {}  # {nameWithOwner: [list of file paths where it appears]}

    for md_file in sections_dir.rglob('*.md'):
        if md_file.name == 'README.md' or md_file.name == 'index.md':
            continue

        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        for line in content.split('\n'):
            repo_name = extract_repo_name(line)
            if repo_name:
                if repo_name not in indexed_repos:
                    indexed_repos[repo_name] = []
                indexed_repos[repo_name].append(md_file)

    print(f"✓ Found {len(indexed_repos)} unique repositories indexed across section files")
    return indexed_repos

def find_deleted_repos(current_repos, indexed_repos):
    """Compare indexed repos against current repos to find deleted ones."""
    print("\n🗑️  Identifying deleted repositories...")
    deleted = {}

    for repo_name, file_paths in indexed_repos.items():
        if repo_name not in current_repos:
            deleted[repo_name] = file_paths

    if deleted:
        print(f"❌ Found {len(deleted)} deleted repositories:")
        for repo_name in sorted(deleted.keys()):
            print(f"   - {repo_name}")
    else:
        print("✓ No deleted repositories found - index is up to date!")

    return deleted

def remove_repo_from_file(file_path, repo_name):
    """Remove all lines mentioning a specific repo from a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    removed_count = 0

    for line in lines:
        if extract_repo_name(line) == repo_name:
            removed_count += 1
            continue
        new_lines.append(line)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    return removed_count

def cleanup_deleted_repos(deleted_repos, dry_run=True):
    """Remove deleted repos from all section files."""
    if not deleted_repos:
        return

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n🧹 Cleanup mode: {mode}")

    total_removed = 0

    for repo_name, file_paths in deleted_repos.items():
        print(f"\n📝 Processing: {repo_name}")
        for file_path in file_paths:
            try:
                rel_path = file_path.relative_to(Path.cwd())
            except ValueError:
                rel_path = file_path

            if dry_run:
                print(f"   Would remove from: {rel_path}")
            else:
                count = remove_repo_from_file(file_path, repo_name)
                total_removed += count
                print(f"   ✓ Removed {count} line(s) from: {rel_path}")

    if not dry_run:
        print(f"\n✅ Cleanup complete! Removed {total_removed} entries total.")
    else:
        print(f"\n💡 This was a dry run. Use --execute to perform actual cleanup.")

def save_report(deleted_repos, current_repos, indexed_repos):
    """Save a cleanup report."""
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    report_file = Path('scripts') / f'cleanup-report-{timestamp}.json'

    report = {
        'timestamp': timestamp,
        'current_repos_count': len(current_repos),
        'indexed_repos_count': len(indexed_repos),
        'deleted_repos_count': len(deleted_repos),
        'deleted_repos': {
            repo: [str(p) for p in paths]
            for repo, paths in deleted_repos.items()
        }
    }

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    print(f"\n📄 Report saved to: {report_file}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Clean up deleted repositories from index')
    parser.add_argument('--execute', action='store_true',
                       help='Actually perform cleanup (default is dry run)')
    args = parser.parse_args()

    print("🧹 GitHub Repository Cleanup Tool")
    print("=" * 50)

    # Get current repos from GitHub
    current_repos = get_current_repos()

    # Scan section files for indexed repos
    sections_dir = Path('sections')
    indexed_repos = scan_section_files(sections_dir)

    # Find deleted repos
    deleted_repos = find_deleted_repos(current_repos, indexed_repos)

    # Save report
    save_report(deleted_repos, current_repos, indexed_repos)

    # Cleanup
    if deleted_repos:
        cleanup_deleted_repos(deleted_repos, dry_run=not args.execute)

        if args.execute:
            print("\n🔄 Regenerating indexes...")
            print("Run: ./scripts/sync-all.sh")
    else:
        print("\n✨ Index is clean - no action needed!")

if __name__ == '__main__':
    main()
