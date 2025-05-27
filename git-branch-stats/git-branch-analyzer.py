#!/usr/bin/env python3
"""
Git Branch Analyzer - A fast, efficient tool to analyze branch statistics in a git repository

This script analyzes a git repository to generate statistics about branches including:
- Number of unique commits per branch
- Number of unique committers per branch
- Branch creation and last commit dates
- Largest commits within each branch

Usage:
    git-branch-analyzer.py [OPTIONS] <repository-url>

Options:
    -o, --output FILE       Output CSV file (default: branch_stats.csv)
    -n, --top-count INT     Number of branches to show in top list (default: 20)
    -v, --verbose           Enable verbose output
    -h, --help              Show this help message and exit
"""

import argparse
import csv
import datetime
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class BranchStats:
    """Data class to store branch statistics"""
    name: str
    creation_date: datetime.datetime
    last_commit_date: datetime.datetime
    lifetime_days: float
    commit_count: int
    committer_count: int
    largest_commit_lines: int
    largest_commit_hash: str
    
    @property
    def inactive_days(self) -> float:
        """Calculate days since last commit."""
        now = datetime.datetime.now()
        return (now - self.last_commit_date).total_seconds() / (24 * 60 * 60)
    
    @property
    def is_active(self) -> bool:
        """Determine if a branch is active (has commits in the last 90 days)."""
        return self.inactive_days < 90


def run_git_command(cmd, cwd=None, verbose=False, check=True):
    """Run a git command and return the output."""
    if verbose:
        print(f"Running: git {' '.join(cmd)}")
    
    try:
        # Execute the command
        process = subprocess.run(
            ["git"] + cmd,
            cwd=cwd,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return process.stdout
    except subprocess.CalledProcessError as e:
        if check:
            print(f"Error: {e.stderr}")
            sys.exit(1)
        return ""


def analyze_repo(repo_url, output_file="branch_stats.csv", top_count=20, verbose=False):
    """Analyze a git repository and generate branch statistics."""
    # Create a temporary directory for the repository
    with tempfile.TemporaryDirectory() as temp_dir:
        if verbose:
            print(f"Cloning repository: {repo_url}")
        
        # Clone the repository
        run_git_command(["clone", repo_url, temp_dir], verbose=verbose)
        
        # Change to the repository directory
        os.chdir(temp_dir)
        
        # Get all branches
        if verbose:
            print("Getting all branches...")
        
        branch_output = run_git_command(["branch", "-r"], verbose=verbose)
        branches = []
        
        for line in branch_output.strip().split("\n"):
            branch = line.strip()
            if "->" not in branch:  # Exclude HEAD pointer
                branches.append(branch)
        
        if verbose:
            print(f"Found {len(branches)} branches")
        
        # Find the main or master branch
        main_branch = None
        for candidate in ["origin/main", "origin/master"]:
            if candidate in branches:
                main_branch = candidate
                break
        
        if verbose:
            print(f"Main branch: {main_branch}")
        
        # Initialize results
        branch_stats = []
        
        # Process each branch
        for i, branch in enumerate(branches):
            if verbose:
                print(f"Processing branch {i+1}/{len(branches)}: {branch}")
            
            # Get basic branch info
            try:
                # Get the earliest commit date (creation date)
                creation_date_output = run_git_command(
                    ["log", "--format=%at", "--reverse", branch, "--max-count=1"],
                    check=False, verbose=verbose
                )
                
                # Get the latest commit date
                last_commit_date_output = run_git_command(
                    ["log", "--format=%at", branch, "--max-count=1"],
                    check=False, verbose=verbose
                )
                
                # Skip if we can't get commit dates
                if not creation_date_output.strip() or not last_commit_date_output.strip():
                    if verbose:
                        print(f"Skipping branch {branch} - no commit info")
                    continue
                
                # Parse dates
                creation_timestamp = int(creation_date_output.strip())
                last_commit_timestamp = int(last_commit_date_output.strip())
                
                creation_date = datetime.datetime.fromtimestamp(creation_timestamp)
                last_commit_date = datetime.datetime.fromtimestamp(last_commit_timestamp)
                
                # Calculate branch lifetime
                now = datetime.datetime.now()
                lifetime_days = (now - creation_date).total_seconds() / (24 * 60 * 60)
                
                # Count commits unique to this branch
                commit_count = 0
                if main_branch:
                    # Get unique commits (not in main branch)
                    commit_count_output = run_git_command(
                        ["rev-list", "--count", branch, f"^{main_branch}"],
                        check=False, verbose=verbose
                    )
                    
                    if commit_count_output.strip():
                        commit_count = int(commit_count_output.strip())
                
                # If no unique commits found, count all commits
                if commit_count == 0:
                    commit_count_output = run_git_command(
                        ["rev-list", "--count", branch],
                        check=False, verbose=verbose
                    )
                    
                    if commit_count_output.strip():
                        commit_count = int(commit_count_output.strip())
                
                # Get unique committers
                committers_output = run_git_command(
                    ["log", "--format=%ae", branch],
                    check=False, verbose=verbose
                )
                
                committers = set()
                if committers_output.strip():
                    committers = set(committers_output.strip().split("\n"))
                
                committer_count = len(committers)
                
                # Find the largest commit
                largest_commit_lines = 0
                largest_commit_hash = ""
                
                # Get stats for each commit
                stats_output = run_git_command(
                    ["log", "--pretty=format:%h", "--numstat", branch],
                    check=False, verbose=verbose
                )
                
                if stats_output:
                    current_hash = None
                    current_lines = 0
                    lines = stats_output.strip().split("\n")
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # If line contains only hex characters and is 7-40 chars, it's a hash
                        if re.match(r"^[0-9a-f]{7,40}$", line):
                            # Save previous commit if it's the largest so far
                            if current_hash and current_lines > largest_commit_lines:
                                largest_commit_lines = current_lines
                                largest_commit_hash = current_hash
                            
                            # Start a new commit
                            current_hash = line
                            current_lines = 0
                        else:
                            # Parse stats line: <additions> <deletions> <file>
                            parts = line.split(None, 2)
                            if len(parts) >= 2:
                                # Skip binary files (shown as "-")
                                if parts[0] == "-" or parts[1] == "-":
                                    continue
                                
                                try:
                                    added = int(parts[0])
                                    deleted = int(parts[1])
                                    current_lines += added + deleted
                                except (ValueError, IndexError):
                                    pass
                    
                    # Check the last processed commit
                    if current_hash and current_lines > largest_commit_lines:
                        largest_commit_lines = current_lines
                        largest_commit_hash = current_hash
                
                # Add to results
                stats = BranchStats(
                    name=branch.replace("origin/", ""),  # Remove origin/ prefix for cleaner output
                    creation_date=creation_date,
                    last_commit_date=last_commit_date,
                    lifetime_days=lifetime_days,
                    commit_count=commit_count,
                    committer_count=committer_count,
                    largest_commit_lines=largest_commit_lines,
                    largest_commit_hash=largest_commit_hash
                )
                
                branch_stats.append(stats)
                
            except Exception as e:
                if verbose:
                    print(f"Error processing branch {branch}: {str(e)}")
        
        # Write results to CSV
        write_csv_report(branch_stats, output_file, verbose)
        
        # Print top branches
        print_top_branches(branch_stats, top_count)
        
        # Print summary statistics
        print_summary_statistics(branch_stats, output_file)
        
        return branch_stats


def write_csv_report(branch_stats, output_file, verbose=False):
    """Write branch statistics to a CSV file."""
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = [
            'branch_name', 
            'creation_date', 
            'last_commit_date', 
            'lifetime_days', 
            'inactive_days', 
            'is_active', 
            'commit_count', 
            'committer_count', 
            'largest_commit_lines', 
            'largest_commit_hash'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for stats in branch_stats:
            writer.writerow({
                'branch_name': stats.name,
                'creation_date': stats.creation_date.isoformat(),
                'last_commit_date': stats.last_commit_date.isoformat(),
                'lifetime_days': f"{stats.lifetime_days:.2f}",
                'inactive_days': f"{stats.inactive_days:.2f}",
                'is_active': str(stats.is_active),
                'commit_count': stats.commit_count,
                'committer_count': stats.committer_count,
                'largest_commit_lines': stats.largest_commit_lines,
                'largest_commit_hash': stats.largest_commit_hash
            })
    
    if verbose:
        print(f"Report written to {output_file}")


def print_top_branches(branch_stats, count):
    """Print top branches by commit count."""
    if not branch_stats:
        print("No branch data to display")
        return
    
    # Sort branches by commit count (descending)
    sorted_stats = sorted(branch_stats, key=lambda x: x.commit_count, reverse=True)
    
    # Determine actual count (may be less than requested)
    actual_count = min(count, len(sorted_stats))
    
    # Print header
    print(f"\nTop {actual_count} branches by commit count (unique commits only):")
    print(f"{'#':<3}{'Branch Name':<35} {'Age(d)':<6} {'Cmts':<5} {'Contrs':<6} {'Largest':<8} {'Commit':<7}")
    print("-" * 85)
    
    # Print top branches
    for i, stats in enumerate(sorted_stats[:actual_count]):
        branch_display = stats.name
        if len(branch_display) > 34:
            branch_display = branch_display[:31] + "..."
            
        print(f"{i+1:<3}{branch_display:<35} {stats.lifetime_days:6.1f} {stats.commit_count:<5} "
              f"{stats.committer_count:<6} {stats.largest_commit_lines:<8} {stats.largest_commit_hash:<7}")
    
    # Print a note about the metrics
    print("\nNotes:")
    print("- Commit counts show commits unique to each branch (not in main/master)")
    print("- Age is in days since branch creation")
    print("- Contrs is the number of unique committers to the branch")
    print("- Largest shows the lines changed (added+deleted) in the largest commit")
    print("- Full data for all branches has been written to the CSV file")


def print_summary_statistics(branch_stats, output_file):
    """Print summary statistics about the repository."""
    if not branch_stats:
        print("No branch data to display")
        return
    
    # Calculate statistics
    active_branches = sum(1 for s in branch_stats if s.is_active)
    inactive_branches = len(branch_stats) - active_branches
    total_commits = sum(s.commit_count for s in branch_stats)
    avg_commits = total_commits / len(branch_stats) if branch_stats else 0
    max_committers = max(s.committer_count for s in branch_stats) if branch_stats else 0
    avg_committers = sum(s.committer_count for s in branch_stats) / len(branch_stats) if branch_stats else 0
    max_commit_lines = max(s.largest_commit_lines for s in branch_stats) if branch_stats else 0
    
    # Print summary
    print(f"\nSummary statistics:")
    print(f"- Total branches: {len(branch_stats)}")
    print(f"- Active branches (commits in last 90 days): {active_branches}")
    print(f"- Inactive branches: {inactive_branches}")
    print(f"- Total unique commits across all branches: {total_commits}")
    print(f"- Average commits per branch: {avg_commits:.2f}")
    print(f"- Maximum committers on a single branch: {max_committers}")
    print(f"- Average committers per branch: {avg_committers:.2f}")
    print(f"- Largest single commit (lines changed): {max_commit_lines}")
    print(f"- Full report written to: {output_file}")


def main():
    """Main function to parse arguments and run the analysis."""
    parser = argparse.ArgumentParser(description="Analyze branch statistics in a git repository")
    parser.add_argument("repo_url", help="URL of the git repository to analyze")
    parser.add_argument("-o", "--output", default="branch_stats.csv",
                        help="Output CSV file (default: branch_stats.csv)")
    parser.add_argument("-n", "--top-count", type=int, default=20,
                        help="Number of branches to show in top list (default: 20)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Start timing
    start_time = datetime.datetime.now()
    
    # Analyze repository
    analyze_repo(
        repo_url=args.repo_url,
        output_file=args.output,
        top_count=args.top_count,
        verbose=args.verbose
    )
    
    # Show execution time
    end_time = datetime.datetime.now()
    execution_time = (end_time - start_time).total_seconds()
    print(f"\nExecution completed in {execution_time:.2f} seconds")


if __name__ == "__main__":
    main()
