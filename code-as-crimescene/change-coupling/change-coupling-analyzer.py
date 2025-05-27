#!/usr/bin/env python3
"""
Change Coupling Analyzer - A tool to analyze change coupling in Git repositories

This tool clones a remote Git repository and analyzes the commit history to identify
files that tend to change together (change coupling or temporal coupling).

Usage:
  change_coupling.py --repo URL [--branch BRANCH] [--since DAYS] [--coupling-threshold PERCENT]
                    [--min-changes N] [--output FORMAT] [--output-file FILE] [--top N] [--ignore-file FILE]
  change_coupling.py -h | --help

Options:
  --repo URL                   URL of the Git repository to analyze
  --branch BRANCH              Branch to analyze [default: main]
  --since DAYS                 Only consider commits from the last N days [default: 90]
  --coupling-threshold PERCENT Minimum coupling percentage to report [default: 30]
  --min-changes N              Minimum number of changes required for a file to be considered [default: 3]
  --output FORMAT              Output format: text, csv, or json [default: text]
  --output-file FILE           File to save CSV results [default: change_coupling_results.csv]
  --top N                      Show top N results with highest coupling [default: 20]
  --ignore-file FILE           Path to file containing patterns of files to ignore
  -h --help                    Show this help message
"""

import argparse
import os
import sys
import tempfile
import subprocess
import datetime
import json
import csv
import fnmatch
import re
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional


class GitChangeAnalyzer:
    def __init__(self, repo_url: str, branch: str = "main", since_days: int = 90, ignore_file: Optional[str] = None):
        """Initialize the analyzer with repository details."""
        self.repo_url = repo_url
        self.branch = branch
        self.since_days = since_days
        self.temp_dir = None
        self.ignore_patterns = []
        
        # Load ignore patterns if specified
        if ignore_file and os.path.exists(ignore_file):
            self._load_ignore_patterns(ignore_file)
            
    def _load_ignore_patterns(self, ignore_file_path: str):
        """Load ignore patterns from file."""
        with open(ignore_file_path, 'r') as file:
            for line in file:
                # Skip empty lines and comments
                line = line.strip()
                if line and not line.startswith('#'):
                    self.ignore_patterns.append(line)
        print(f"Loaded {len(self.ignore_patterns)} ignore patterns from {ignore_file_path}")
    
    def _should_ignore(self, file_path: str) -> bool:
        """Check if a file should be ignored based on ignore patterns."""
        if not self.ignore_patterns:
            return False
            
        # Convert file_path to use forward slashes for consistent matching
        file_path = file_path.replace('\\', '/')
        
        for pattern in self.ignore_patterns:
            # Handle glob patterns (with ** for directories)
            if '**' in pattern:
                # Convert glob pattern to regex
                regex_pattern = pattern.replace('.', '\\.').replace('**', '.*').replace('*', '[^/]*')
                if re.match(f"^{regex_pattern}$", file_path):
                    return True
            # Standard glob patterns
            elif fnmatch.fnmatch(file_path, pattern):
                return True
        return False
        
    def clone_repository(self) -> str:
        """Clone the repository to a temporary directory and return the path."""
        print(f"Cloning repository {self.repo_url}...")
        self.temp_dir = tempfile.mkdtemp()
        subprocess.run(
            ["git", "clone", "--single-branch", "--branch", self.branch, self.repo_url, self.temp_dir],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return self.temp_dir
    
    def get_commit_history(self) -> List[str]:
        """Get the commit history for the specified time period."""
        since_date = (datetime.datetime.now() - datetime.timedelta(days=self.since_days)).strftime("%Y-%m-%d")
        
        result = subprocess.run(
            ["git", "log", f"--since={since_date}", "--format=%H"],
            cwd=self.temp_dir,
            check=True,
            stdout=subprocess.PIPE,
            text=True
        )
        
        commits = result.stdout.strip().split('\n')
        # Filter out empty strings in case there are no commits
        return [commit for commit in commits if commit]
    
    def get_changed_files(self, commit_hash: str) -> List[str]:
        """Get the list of files changed in a specific commit."""
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
            cwd=self.temp_dir,
            check=True,
            stdout=subprocess.PIPE,
            text=True
        )
        
        files = result.stdout.strip().split('\n')
        # Filter out empty strings, non-source files, and ignored files
        return [file for file in files if file and self._is_source_file(file) and not self._should_ignore(file)]
    
    def _is_source_file(self, filename: str) -> bool:
        """Check if a file is a source code file (exclude binaries, images, etc.)."""
        _, ext = os.path.splitext(filename)
        
        # Automatically exclude common configuration files
        config_patterns = [
            '.eslintrc.js', '.eslintrc.json', '.eslintrc.yml', '.eslintrc',
            '.prettierrc.js', '.prettierrc.json', '.prettierrc.yml', '.prettierrc',
            '.babelrc', '.editorconfig', '.gitignore', '.travis.yml', '.gitlab-ci.yml',
            'package.json', 'package-lock.json', 'yarn.lock', 'tsconfig.json'
        ]
        
        for pattern in config_patterns:
            if filename.endswith(pattern):
                return False
        
        # Add or remove extensions as needed for your project
        source_extensions = {
            '.py', '.java', '.js', '.jsx', '.ts', '.tsx', '.c', '.cpp', '.h', '.hpp',
            '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.rs', '.scala', '.sh',
            '.html', '.css', '.scss', '.sql', '.xml', '.json', '.yaml', '.yml'
        }
        return ext.lower() in source_extensions
    
    def analyze_coupling(self, min_coupling_percent: int = 30, min_changes: int = 3) -> List[Dict]:
        """
        Analyze the repository for change coupling.
        
        Args:
            min_coupling_percent: Minimum coupling percentage to report
            min_changes: Minimum number of changes required for a file to be considered
            
        Returns:
            List of dictionaries with coupling information
        """
        try:
            repo_path = self.clone_repository()
            commits = self.get_commit_history()
            
            if not commits:
                print("No commits found in the specified time period.")
                return []
            
            print(f"Analyzing {len(commits)} commits...")
            
            # Track how many times each file was changed
            file_change_count = defaultdict(int)
            
            # Track how many times each pair of files changed together
            file_coupling = defaultdict(int)
            
            # Process each commit
            for commit in commits:
                changed_files = self.get_changed_files(commit)
                
                # Update file change counts
                for file in changed_files:
                    file_change_count[file] += 1
                
                # Update coupling for each pair of files
                for i, file1 in enumerate(changed_files):
                    for file2 in changed_files[i+1:]:
                        # Create a sorted tuple to ensure consistent keys
                        pair = tuple(sorted([file1, file2]))
                        file_coupling[pair] += 1
            
            # Calculate coupling percentages and weighted scores
            results = []
            for (file1, file2), coupled_count in file_coupling.items():
                file1_count = file_change_count[file1]
                file2_count = file_change_count[file2]
                
                # Skip files with too few changes
                if file1_count < min_changes or file2_count < min_changes:
                    continue
                
                # Calculate coupling as percentage of time these files change together
                # relative to how often each changes individually
                coupling_percent1 = round((coupled_count / file1_count) * 100, 2)
                coupling_percent2 = round((coupled_count / file2_count) * 100, 2)
                
                # Use the minimum of the two percentages as the coupling strength
                coupling_percent = min(coupling_percent1, coupling_percent2)
                
                # Only report coupling above the threshold
                if coupling_percent >= min_coupling_percent:
                    # Calculate weighted score: coupling_percent * log(changes_together + 1)
                    # This balances high coupling percentage with frequency of changes
                    import math
                    weighted_score = coupling_percent * math.log(coupled_count + 1)
                    
                    results.append({
                        'file1': file1,
                        'file2': file2,
                        'coupling_percent': coupling_percent,
                        'changes_together': coupled_count,
                        'file1_changes': file1_count,
                        'file2_changes': file2_count,
                        'weighted_score': round(weighted_score, 2)
                    })
            
            # Sort by weighted score (descending)
            results.sort(key=lambda x: x['weighted_score'], reverse=True)
            return results
            
        finally:
            # Clean up temporary directory
            if self.temp_dir and os.path.exists(self.temp_dir):
                subprocess.run(["rm", "-rf", self.temp_dir], check=True)
    
    def cleanup(self):
        """Clean up temporary resources."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            subprocess.run(["rm", "-rf", self.temp_dir], check=True)


def output_results(results: List[Dict], format_type: str, output_file: str = 'change_coupling_results.csv', top_n: int = 20):
    """
    Output the results in the specified format.
    
    Args:
        results: List of dictionaries with coupling information
        format_type: Output format (text, csv, or json)
        output_file: File to save CSV results
        top_n: Number of top results to display
    """
    # Always save complete results to CSV file
    if results:
        try:
            with open(output_file, 'w', newline='') as csvfile:
                fieldnames = results[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in results:
                    writer.writerow(row)
            print(f"Full results saved to {output_file}")
        except Exception as e:
            print(f"Error saving results to CSV: {str(e)}", file=sys.stderr)
    
    # Limit displayed results to top N
    top_results = results[:min(top_n, len(results))] if results else []
    
    # Display only top results in the requested format
    if format_type == 'json':
        print(json.dumps(top_results, indent=2))
    
    elif format_type == 'csv':
        if not top_results:
            print("No results to output.")
            return
            
        fieldnames = top_results[0].keys()
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        for row in top_results:
            writer.writerow(row)
    
    else:  # text format
        if not top_results:
            print("No change coupling found above the threshold.")
            return
            
        print(f"\nTop {len(top_results)} Change Coupling Results:")
        print("-" * 100)
        print(f"{'File 1':<40} {'File 2':<40} {'Coupling %':<10} {'Together':<10} {'File1 Chg':<10} {'File2 Chg':<10} {'Score':<10}")
        print("-" * 100)
        
        for item in top_results:
            # Truncate long filenames to fit in column width
            file1 = item['file1']
            file2 = item['file2']
            if len(file1) > 39:
                file1 = "..." + file1[-36:]
            if len(file2) > 39:
                file2 = "..." + file2[-36:]
                
            print(f"{file1:<40} {file2:<40} {item['coupling_percent']:<10.2f} "
                  f"{item['changes_together']:<10} {item['file1_changes']:<10} {item['file2_changes']:<10} "
                  f"{item['weighted_score']:<10.2f}")


def main():
    parser = argparse.ArgumentParser(description='Analyze change coupling in Git repositories')
    parser.add_argument('--repo', required=True, help='URL of the Git repository to analyze')
    parser.add_argument('--branch', default='main', help='Branch to analyze [default: main]')
    parser.add_argument('--since', type=int, default=90, help='Only consider commits from the last N days [default: 90]')
    parser.add_argument('--coupling-threshold', type=int, default=30, 
                        help='Minimum coupling percentage to report [default: 30]')
    parser.add_argument('--min-changes', type=int, default=3,
                        help='Minimum number of changes required for a file to be considered [default: 3]')
    parser.add_argument('--output', choices=['text', 'csv', 'json'], default='text',
                        help='Output format: text, csv, or json [default: text]')
    parser.add_argument('--output-file', default='change_coupling_results.csv',
                        help='File to save CSV results [default: change_coupling_results.csv]')
    parser.add_argument('--top', type=int, default=20,
                        help='Show top N results with highest coupling [default: 20]')
    parser.add_argument('--ignore-file', help='Path to file containing patterns of files to ignore')
    
    args = parser.parse_args()
    
    try:
        analyzer = GitChangeAnalyzer(args.repo, args.branch, args.since, args.ignore_file)
        results = analyzer.analyze_coupling(args.coupling_threshold, args.min_changes)
        output_results(results, args.output, args.output_file, args.top)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1
    finally:
        if 'analyzer' in locals():
            analyzer.cleanup()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
