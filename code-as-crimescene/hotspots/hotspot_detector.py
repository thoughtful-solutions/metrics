#!/usr/bin/env python3
"""
Hotspot Detector - A CLI tool to identify code hotspots in Git repositories.

Hotspot score = Lines of Code × Number of Revisions × Number of Authors

Usage:
  hotspot_detector.py analyze --repo-url=<url> [--branch=<branch>] [--ignore-file=<path>] [--output=<path>] [--top=<n>] [--full-report=<path>] [--auth=<method>] [--username=<username>] [--ssh-key=<path>] [--token=<token>]
  hotspot_detector.py -h | --help
  hotspot_detector.py --version

Options:
  --repo-url=<url>       URL of the Git repository to analyze
  --branch=<branch>      Branch to analyze [default: main]
  --ignore-file=<path>   Path to ignore patterns file [default: ignore-files.txt]
  --output=<path>        Path to output CSV file [default: hotspots.csv]
  --top=<n>              Show only top N hotspots [default: 20]
  --full-report=<path>   Path to export full file data [default: none]
  --auth=<method>        Authentication method: none, ssh, https, token [default: none]
  --username=<username>  Username for HTTPS authentication
  --ssh-key=<path>       Path to SSH private key file
  --token=<token>        Personal access token for authentication
  -h --help              Show this help message
  --version              Show version
"""

import os
import sys
import csv
import re
import shutil
import tempfile
import subprocess
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
import fnmatch
from docopt import docopt
import tabulate


__version__ = "1.0.0"


class HotspotDetector:
    def __init__(self, repo_url, branch="main", ignore_file="ignore-files.txt", output_file="hotspots.csv", 
                 auth_method="none", username=None, ssh_key=None, token=None):
        self.repo_url = repo_url
        self.branch = branch
        self.ignore_file = ignore_file
        self.output_file = output_file
        self.temp_dir = None
        self.ignore_patterns = []
        self.auth_method = auth_method
        self.username = username
        self.ssh_key = ssh_key
        self.token = token
        self.load_ignore_patterns()
        
    def load_ignore_patterns(self):
        """Load ignore patterns from the specified file."""
        if not os.path.exists(self.ignore_file):
            print(f"Warning: Ignore file {self.ignore_file} not found. No files will be ignored.")
            return

        with open(self.ignore_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                self.ignore_patterns.append(line)
        
        print(f"Loaded {len(self.ignore_patterns)} ignore patterns from {self.ignore_file}")
        
    def should_ignore(self, file_path):
        """Check if a file should be ignored based on the patterns."""
        for pattern in self.ignore_patterns:
            # Convert glob patterns to regex patterns
            if pattern.startswith('**/'):
                if fnmatch.fnmatch(file_path, pattern[3:]) or any(fnmatch.fnmatch(part, pattern[3:]) for part in file_path.split('/')):
                    return True
            elif '/**' in pattern:
                prefix = pattern.split('/**')[0]
                if file_path.startswith(prefix):
                    return True
            elif fnmatch.fnmatch(file_path, pattern):
                return True
        return False
        
    def prepare_git_env(self):
        """Prepare the Git environment based on authentication method."""
        env = os.environ.copy()
        
        if self.auth_method == "ssh":
            if self.ssh_key:
                # Create a custom SSH command that uses the specified key
                ssh_command = f'ssh -i "{self.ssh_key}" -o StrictHostKeyChecking=no'
                env['GIT_SSH_COMMAND'] = ssh_command
                print(f"Using SSH authentication with key: {self.ssh_key}")
            else:
                print("Using default SSH configuration.")
                
        elif self.auth_method == "https" and self.username:
            # For HTTPS with username/password, Git will prompt for password
            # We modify the URL to include the username
            if '@' not in self.repo_url and '://' in self.repo_url:
                protocol, rest = self.repo_url.split('://', 1)
                self.repo_url = f"{protocol}://{self.username}@{rest}"
                print(f"Using HTTPS authentication with username: {self.username}")
                print("You may be prompted for a password during clone.")
        elif self.auth_method == "https":
            # Using HTTPS but no username provided - using Git's stored credentials
            print("Using HTTPS authentication with stored Git credentials.")
                
        elif self.auth_method == "token" and self.token:
            # For token-based authentication (GitHub, GitLab, etc.)
            if 'github.com' in self.repo_url:
                # For GitHub
                if 'https://' in self.repo_url:
                    self.repo_url = self.repo_url.replace('https://', f'https://{self.token}:x-oauth-basic@')
                    print("Using GitHub token authentication")
            elif 'gitlab.com' in self.repo_url:
                # For GitLab
                if 'https://' in self.repo_url:
                    self.repo_url = self.repo_url.replace('https://', f'https://oauth2:{self.token}@')
                    print("Using GitLab token authentication")
            else:
                # Generic token authentication
                if 'https://' in self.repo_url:
                    if self.username:
                        self.repo_url = self.repo_url.replace('https://', f'https://{self.username}:{self.token}@')
                    else:
                        self.repo_url = self.repo_url.replace('https://', f'https://x-access-token:{self.token}@')
                    print("Using token-based authentication")
        
        return env
        
    def clone_repo(self):
        """Clone the repository to a temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        # Hide credentials when printing the URL
        display_url = self.repo_url.split('@')[-1] if '@' in self.repo_url else self.repo_url
        print(f"Cloning repository {display_url} to {self.temp_dir}...")
        
        # Prepare environment variables for authentication
        env = self.prepare_git_env()
        
        try:
            # For very small repositories, we don't need --depth=1
            # This ensures we get all commits right away
            clone_cmd = ["git", "clone", "--branch", self.branch, self.repo_url, self.temp_dir]
            
            # Print the exact command we're running (hiding credentials)
            display_cmd = " ".join(["git", "clone", "--branch", self.branch, display_url, self.temp_dir])
            print(f"Running: {display_cmd}")
            
            result = subprocess.run(
                clone_cmd,
                check=True, capture_output=True, timeout=600,  # 10-minute timeout
                env=env  # Pass the environment variables
            )
            print("Repository cloned successfully.")
            
            # Debugging: List the contents of the cloned directory
            print("Contents of the cloned repository:")
            for root, dirs, files in os.walk(self.temp_dir):
                # Skip .git internals when printing
                if ".git" in root.split(os.sep)[1:]:
                    continue
                level = root.replace(self.temp_dir, '').count(os.sep)
                indent = ' ' * 4 * level
                print(f"{indent}{os.path.basename(root)}/")
                sub_indent = ' ' * 4 * (level + 1)
                for f in files:
                    print(f"{sub_indent}{f}")
            
            # If repository is too small, --unshallow might fail, so we'll skip it
            os.chdir(self.temp_dir)
            
            # Check if we need to unshallow
            try:
                is_shallow = subprocess.run(
                    ["git", "rev-parse", "--is-shallow-repository"],
                    capture_output=True, check=True
                ).stdout.decode('utf-8').strip()
                
                if is_shallow == "true":
                    print("Fetching full commit history (this might take a while for large repositories)...")
                    subprocess.run(
                        ["git", "fetch", "--unshallow", "origin", self.branch],
                        check=True, capture_output=True, timeout=600,
                        env=env
                    )
                    print("Commit history fetched successfully.")
                else:
                    print("Repository already has full history.")
            except:
                print("Repository appears to have full history already.")
            
            os.chdir("..")
            
        except subprocess.CalledProcessError as e:
            print(f"Error cloning repository: {e}")
            if e.stderr:
                print(f"Git error: {e.stderr.decode('utf-8', errors='replace')}")
            self.cleanup()
            
            # Provide more specific error messages for authentication failures
            stderr = e.stderr.decode('utf-8', errors='replace').lower()
            if 'authentication failed' in stderr or 'could not read password' in stderr:
                print("\nAuthentication Error: Please check your credentials.")
                print("For private repositories, make sure to use one of these authentication methods:")
                print("  --auth=ssh --ssh-key=/path/to/private_key")
                print("  --auth=https --username=your_username")
                print("  --auth=token --token=your_personal_access_token")
            
            sys.exit(1)
        except subprocess.TimeoutExpired:
            print("Error: Git operation timed out after 10 minutes.")
            print("The repository might be too large or your network connection is slow.")
            print("Try cloning the repository manually and use a local path instead.")
            self.cleanup()
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error during repository clone: {e}")
            self.cleanup()
            sys.exit(1)
            
    def get_file_revisions(self):
        """Get the number of revisions for each file in the repository."""
        # Store the original directory to return to it later
        original_dir = os.getcwd()
        
        try:
            os.chdir(self.temp_dir)
            
            print("Analyzing file revisions...")
            
            # Debug: Check if we have any commits in the repo
            try:
                cmd_check = subprocess.run(
                    ["git", "rev-list", "--count", "HEAD"],
                    capture_output=True, check=True
                )
                commit_count = int(cmd_check.stdout.decode('utf-8').strip())
                print(f"Found {commit_count} commits in repository.")
                
                if commit_count == 0:
                    print("WARNING: Repository has no commits! Cannot analyze file revisions.")
                    return defaultdict(int), defaultdict(set)
                    
                # Debug: Check the branch we're on
                cmd_branch = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, check=True
                )
                current_branch = cmd_branch.stdout.decode('utf-8').strip()
                print(f"Current branch is: {current_branch}")
                
                # Debug: List files in the repo
                cmd_files = subprocess.run(
                    ["git", "ls-files"],
                    capture_output=True, check=True
                )
                git_files = cmd_files.stdout.decode('utf-8').strip().splitlines()
                files_count = len(git_files)
                print(f"Repository contains {files_count} tracked files.")
                
                # Create a set of valid filenames for filtering
                valid_files = set(git_files)
                
                # Get revision count by file using git directly
                print("Getting file revision counts directly from Git...")
                cmd_revs = subprocess.run(
                    ["git", "log", "--name-only", "--pretty=format:"],
                    capture_output=True, check=True
                )
                
                # Process the output to count revisions
                files_with_revs = cmd_revs.stdout.decode('utf-8', errors='replace').strip().splitlines()
                files_with_revs = [f for f in files_with_revs if f.strip()]  # Remove empty lines
                
                # Validate files against git ls-files output to filter out non-file entries
                files_with_revs = [f for f in files_with_revs if f in valid_files or '/' in f or '\\' in f or '.' in f]
                
                # Count occurrences of each file
                rev_counts = Counter(files_with_revs)
                print(f"Direct count shows {len(rev_counts)} files with revisions:")
                
                # Print top 10 files by revision count
                for file_path, count in rev_counts.most_common(10):
                    print(f"  {file_path}: {count} revisions")
                
                # Get authors by file
                print("Getting author information by file...")
                cmd_authors = subprocess.run(
                    ["git", "log", "--pretty=format:%an", "--name-only"],
                    capture_output=True, check=True
                )
                
                authors_output = cmd_authors.stdout.decode('utf-8', errors='replace').strip().splitlines()
                
                revisions = defaultdict(int)
                authors = defaultdict(set)
                current_author = None
                in_files_section = False
                
                # Process the output to get authors for each file
                for line in authors_output:
                    if not line.strip():
                        in_files_section = True
                        continue
                    
                    if in_files_section:
                        # Check if this is actually a file, not just a name
                        if line in valid_files or '/' in line or '\\' in line or '.' in line:
                            file_path = line.strip()
                            if file_path and not self.should_ignore(file_path):
                                revisions[file_path] += 1
                                if current_author:
                                    authors[file_path].add(current_author)
                        else:
                            # Not a file, must be a new author
                            in_files_section = False
                            current_author = line.strip()
                    else:
                        # Author name
                        current_author = line.strip()
                
                # Override with the direct count for more accuracy
                for file_path, count in rev_counts.items():
                    if not self.should_ignore(file_path):
                        revisions[file_path] = count
                
                # Filter out any author names that accidentally got treated as files
                # by verifying against the valid_files set or known file patterns
                filtered_revisions = {}
                filtered_authors = {}
                
                for file_path in revisions:
                    # Only include if it's a valid file path (contains path separators or extension)
                    # or it's in the list of tracked files from git ls-files
                    if (file_path in valid_files or '/' in file_path or '\\' in file_path or '.' in file_path):
                        filtered_revisions[file_path] = revisions[file_path]
                        filtered_authors[file_path] = authors[file_path]
                
                print(f"Found {len(filtered_revisions)} files with revisions after filtering.")
                print(f"Found {len(set().union(*filtered_authors.values()) if filtered_authors else set())} unique authors.")
                
            except subprocess.CalledProcessError as e:
                print(f"Error getting repository info: {e}")
                if e.stderr:
                    print(f"Git error: {e.stderr.decode('utf-8', errors='replace')}")
                return defaultdict(int), defaultdict(set)
            
        finally:
            # Always change back to the original directory
            os.chdir(original_dir)
            
        return filtered_revisions, filtered_authors
        
    def count_lines(self, file_path):
        """Count the number of lines in a file."""
        try:
            # Check if file exists and is not a directory or symlink
            if not os.path.isfile(file_path) or os.path.islink(file_path):
                return 0
                
            # Try to open as text file with various encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        # Read a small chunk to check if it's text
                        sample = f.read(1024)
                        if '\0' in sample:  # Binary file
                            return 0
                        
                        # If we got here, reset the file pointer and count lines
                        f.seek(0)
                        line_count = sum(1 for _ in f)
                        return line_count
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"Warning: Error reading {file_path}: {e}")
                    return 0
                    
            # If we've tried all encodings and none worked, it's probably binary
            return 0
        except Exception as e:
            print(f"Warning: Error counting lines in {file_path}: {e}")
            return 0
            
    def analyze(self):
        """Analyze the repository and calculate hotspots."""
        try:
            self.clone_repo()
            
            print("Analyzing file revisions (this might take a while for large repos)...")
            revisions, authors = self.get_file_revisions()
            
            # Even if no revisions, we'll continue to scan files to produce a basic report
            if not revisions:
                print("No file revisions found. Will still scan files to produce a basic report.")
            else:
                print(f"Found {len(revisions)} files with revision history.")
            
            print("Calculating lines of code for each file...")
            loc = {}
            file_count = 0
            ignored_count = 0
            all_files = []
            
            # Get list of all files directly from Git
            try:
                os.chdir(self.temp_dir)
                git_files_cmd = subprocess.run(
                    ["git", "ls-files"],
                    capture_output=True, check=True
                )
                git_files = git_files_cmd.stdout.decode('utf-8', errors='replace').strip().splitlines()
                os.chdir("..")
                
                print(f"Git reports {len(git_files)} tracked files in the repository.")
                
                # Check each Git-tracked file
                for git_file in git_files:
                    # Skip ignored files
                    if self.should_ignore(git_file):
                        ignored_count += 1
                        continue
                    
                    full_path = os.path.join(self.temp_dir, git_file.replace('/', os.sep))
                    if os.path.exists(full_path) and os.path.isfile(full_path):
                        lines = self.count_lines(full_path)
                        if lines > 0:
                            loc[git_file] = lines
                        file_count += 1
                        all_files.append(git_file)
            except Exception as e:
                print(f"Error listing Git files: {e}")
                
                # Fallback to filesystem scan if Git listing fails
                for root, _, files in os.walk(self.temp_dir):
                    # Skip .git directory entirely
                    if ".git" in root.split(os.sep):
                        continue
                        
                    for file in files:
                        full_path = os.path.join(root, file)
                        # Use normpath to handle path separators consistently
                        rel_path = os.path.normpath(os.path.relpath(full_path, self.temp_dir))
                        # Convert Windows backslashes to forward slashes for consistency with Git
                        rel_path = rel_path.replace('\\', '/')
                        
                        # Track all files
                        all_files.append(rel_path)
                        
                        file_count += 1
                        if self.should_ignore(rel_path):
                            ignored_count += 1
                            continue
                        
                        lines = self.count_lines(full_path)
                        if lines > 0:
                            loc[rel_path] = lines
            
            # Scan revision files that might not have been found in filesystem
            for file_path in revisions:
                if file_path not in loc:
                    full_path = os.path.join(self.temp_dir, file_path.replace('/', os.sep))
                    if os.path.exists(full_path) and os.path.isfile(full_path):
                        lines = self.count_lines(full_path)
                        if lines > 0:
                            loc[file_path] = lines
                            if file_path not in all_files:
                                all_files.append(file_path)
            
            print(f"Processed {file_count} files, ignored {ignored_count} based on patterns.")
            print(f"Found {len(loc)} text files with line counts.")
            print(f"Total unique files tracked: {len(all_files)}")
            
            # Print summary of revisions for debug
            if revisions:
                print("\nTop 5 files by revision count:")
                for file_path, count in sorted(revisions.items(), key=lambda x: x[1], reverse=True)[:5]:
                    author_count = len(authors.get(file_path, set()))
                    line_count = loc.get(file_path, 0)
                    print(f"  {file_path}: {count} revisions, {author_count} authors, {line_count} lines")
            
            print("Calculating hotspot scores...")
            hotspots = []
            for file_path in revisions:
                if file_path in loc and loc[file_path] > 0:
                    score = loc[file_path] * revisions[file_path] * len(authors[file_path])
                    hotspots.append({
                        'file': file_path,
                        'lines_of_code': loc[file_path],
                        'revisions': revisions[file_path],
                        'authors': len(authors[file_path]),
                        'score': score
                    })
            
            # Add files with line counts but no revision history
            for file_path in loc:
                if file_path not in revisions:
                    hotspots.append({
                        'file': file_path,
                        'lines_of_code': loc[file_path],
                        'revisions': 0,
                        'authors': 0,
                        'score': 0  # No score for files without revision history
                    })
            
            # Sort by score in descending order
            hotspots.sort(key=lambda x: x['score'], reverse=True)
            
            print(f"Identified {len(hotspots)} files in report.")
            return hotspots, loc, revisions, authors
            
        except Exception as e:
            print(f"Error during analysis: {e}")
            import traceback
            traceback.print_exc()
            return [], {}, {}, {}
        finally:
            self.cleanup()
            
    def save_full_report(self, loc, revisions, authors, full_report_path):
        """Save a full report of all files with metrics."""
        print(f"Generating full report to {full_report_path}...")
        
        # Get the list of tracked git files to validate against
        tracked_files_set = set()
        try:
            original_dir = os.getcwd()
            os.chdir(self.temp_dir)
            cmd_files = subprocess.run(
                ["git", "ls-files"],
                capture_output=True, check=True
            )
            tracked_files_set = set(cmd_files.stdout.decode('utf-8', errors='replace').strip().splitlines())
            os.chdir(original_dir)
        except Exception as e:
            print(f"Warning: Could not get git file list: {e}")
        
        # Collect all unique file paths that are in either revisions or loc
        all_files = set()
        for file_path in revisions:
            # Only include actual files from the repo
            if file_path in tracked_files_set:
                all_files.add(file_path)
        
        for file_path in loc:
            # Only include actual files from the repo
            if file_path in tracked_files_set:
                all_files.add(file_path)
        
        print(f"Preparing report with {len(all_files)} validated files.")
        
        file_data = []
        for file_path in all_files:
            # Get metrics, defaulting to 0 if not present
            line_count = loc.get(file_path, 0)
            revision_count = revisions.get(file_path, 0)
            author_count = len(authors.get(file_path, set()))
            
            # Calculate score if all metrics are available
            if line_count > 0 and revision_count > 0 and author_count > 0:
                score = line_count * revision_count * author_count
            else:
                score = 0
                
            file_data.append({
                'file': file_path,
                'lines_of_code': line_count,
                'revisions': revision_count,
                'authors': author_count,
                'score': score
            })
            
        # Sort by file path for easier browsing
        file_data.sort(key=lambda x: x['file'])
        
        # Write to CSV
        with open(full_report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['file', 'lines_of_code', 'revisions', 'authors', 'score'])
            writer.writeheader()
            for data in file_data:
                writer.writerow(data)
                
        print(f"Full report with {len(file_data)} files saved to {full_report_path}")
        
    def save_results(self, hotspots, top_n=20, full_report_path=None, loc=None, revisions=None, authors=None):
        """Save the hotspot results to a CSV file."""
        try:
            # Ensure output path is properly resolved relative to current working directory
            output_file = self.output_file
            
            # If it's a relative path (not absolute and not starting with drive letter like C:), 
            # make it relative to current working directory
            if not os.path.isabs(output_file) and not (len(output_file) > 1 and output_file[1] == ':'):
                # Remove any leading ./ or .\ which can make files hidden
                if output_file.startswith('./') or output_file.startswith('.\\'):
                    output_file = output_file[2:]
                # Explicitly resolve against the current working directory
                output_file = os.path.join(os.getcwd(), output_file)
                print(f"Using absolute path for output: {output_file}")
            
            # Ensure the output directory exists
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    print(f"Created output directory: {output_dir}")
                except Exception as e:
                    print(f"Warning: Could not create output directory {output_dir}: {e}")
            
            if not hotspots:
                print("No files found for analysis.")
                # Create an empty CSV file with headers to avoid errors
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['file', 'lines_of_code', 'revisions', 'authors', 'score'])
                    writer.writeheader()
                print(f"Created empty report file: {output_file}")
                return
            
            print(f"Writing results to CSV file: {output_file}")
            try:
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['file', 'lines_of_code', 'revisions', 'authors', 'score'])
                    writer.writeheader()
                    for hotspot in hotspots:
                        writer.writerow(hotspot)
                
                file_size = os.path.getsize(output_file)
                print(f"Results saved to {output_file} ({file_size} bytes)")
            except Exception as e:
                print(f"Error writing to CSV file: {e}")
                print(f"Attempting to save to current directory...")
                # Try saving to current directory with fixed filename
                alt_output = os.path.join(os.getcwd(), "hotspots_report.csv")
                with open(alt_output, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['file', 'lines_of_code', 'revisions', 'authors', 'score'])
                    writer.writeheader()
                    for hotspot in hotspots:
                        writer.writerow(hotspot)
                print(f"Results saved to alternative file: {alt_output}")
            
            # Generate full report if requested
            if full_report_path and full_report_path.lower() != 'none' and loc is not None:
                # Handle relative paths for full report as well
                if not os.path.isabs(full_report_path) and not (len(full_report_path) > 1 and full_report_path[1] == ':'):
                    # Remove any leading ./ or .\
                    if full_report_path.startswith('./') or full_report_path.startswith('.\\'):
                        full_report_path = full_report_path[2:]
                    # Explicitly resolve against current working directory
                    full_report_path = os.path.join(os.getcwd(), full_report_path)
                    print(f"Using absolute path for full report: {full_report_path}")
                    
                # Ensure the directory exists
                full_report_dir = os.path.dirname(full_report_path)
                if full_report_dir and not os.path.exists(full_report_dir):
                    try:
                        os.makedirs(full_report_dir, exist_ok=True)
                        print(f"Created full report directory: {full_report_dir}")
                    except Exception as e:
                        print(f"Warning: Could not create full report directory {full_report_dir}: {e}")
                
                self.save_full_report(loc or {}, revisions or {}, authors or {}, full_report_path)
            
            # Only display table if we have actual hotspots (files with score > 0)
            actual_hotspots = [h for h in hotspots if h['score'] > 0]
            if actual_hotspots:
                # Display the top N hotspots
                print(f"\nTop {min(top_n, len(actual_hotspots))} Hotspots:")
                table_data = []
                for i, hotspot in enumerate(actual_hotspots[:top_n], 1):
                    table_data.append([
                        i,
                        hotspot['file'],
                        hotspot['lines_of_code'],
                        hotspot['revisions'],
                        hotspot['authors'],
                        hotspot['score']
                    ])
                    
                headers = ["#", "File", "Lines of Code", "Revisions", "Authors", "Hotspot Score"]
                print(tabulate.tabulate(table_data, headers=headers, tablefmt="grid"))
                
                print("\nRecommended actions for hotspots:")
                print("1. Refactor into smaller, more focused components")
                print("2. Increase test coverage for these files")
                print("3. Document complex logic and design decisions")
                print("4. Schedule regular reviews of persistent hotspots")
            else:
                print("\nNo hotspots identified with positive scores.")
                print("This may be because:")
                print("1. The repository is new or has very little commit history")
                print("2. All files are ignored based on the ignore patterns")
                print("3. The repository structure uses mostly binary files")
                print("\nCheck the generated CSV report for details on all files analyzed.")
        except Exception as e:
            print(f"Error in save_results: {e}")
            import traceback
            traceback.print_exc()
            
    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            print(f"Cleaning up temporary directory {self.temp_dir}...")
            try:
                # Fix read-only attributes on Windows before removing
                if os.name == 'nt':  # Windows
                    for root, dirs, files in os.walk(self.temp_dir):
                        for dir_name in dirs:
                            try:
                                os.chmod(os.path.join(root, dir_name), 0o777)
                            except:
                                pass
                        for file_name in files:
                            try:
                                os.chmod(os.path.join(root, file_name), 0o777)
                            except:
                                pass
                
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception as e:
                print(f"Warning: Could not completely clean up temporary directory: {e}")
                print("You may need to manually delete it later.")


def main():
    """Main entry point for the CLI tool."""
    try:
        args = docopt(__doc__, version=f"Hotspot Detector v{__version__}")
        
        repo_url = args['--repo-url']
        branch = args['--branch'] or 'main'  # Default to main if not specified
        ignore_file = args['--ignore-file']
        output_file = args['--output']
        top_n = int(args['--top'])
        full_report = args['--full-report']
        auth_method = args['--auth'] or 'none'
        username = args['--username']
        ssh_key = args['--ssh-key']
        token = args['--token']
        
        # Make sure to store the current working directory right at the start
        current_working_dir = os.getcwd()
        
        # For ignore file, if it's a relative path, make it relative to the current directory
        if ignore_file and not os.path.isabs(ignore_file) and not (len(ignore_file) > 1 and ignore_file[1] == ':'):
            if ignore_file.startswith('./') or ignore_file.startswith('.\\'):
                ignore_file = ignore_file[2:]
            ignore_file = os.path.join(current_working_dir, ignore_file)
        
        # Ensure output path is fully qualified
        if output_file and not os.path.isabs(output_file) and not (len(output_file) > 1 and output_file[1] == ':'):
            if output_file.startswith('./') or output_file.startswith('.\\'):
                output_file = output_file[2:]
            output_file = os.path.join(current_working_dir, output_file)
            
        # Same for full report path
        if full_report and full_report.lower() != 'none' and not os.path.isabs(full_report) and not (len(full_report) > 1 and full_report[1] == ':'):
            if full_report.startswith('./') or full_report.startswith('.\\'):
                full_report = full_report[2:]
            full_report = os.path.join(current_working_dir, full_report)
        
        # Validate authentication parameters
        if auth_method not in ['none', 'ssh', 'https', 'token']:
            print(f"Error: Invalid authentication method '{auth_method}'.")
            print("Supported methods are: none, ssh, https, token")
            return 1
            
        if auth_method == 'ssh' and ssh_key and not os.path.exists(ssh_key):
            print(f"Error: SSH key file not found: {ssh_key}")
            return 1
            
        if auth_method == 'token' and not token:
            print("Error: Token authentication requires a token.")
            return 1
        
        print(f"=== Hotspot Detector v{__version__} ===")
        print(f"Current working directory: {current_working_dir}")
        # Hide credentials when printing the URL
        display_url = repo_url.split('@')[-1] if '@' in repo_url else repo_url
        print(f"Repository: {display_url}")
        print(f"Branch: {branch}")
        print(f"Ignore file: {ignore_file}")
        print(f"Output file: {output_file}")
        print(f"Authentication: {auth_method}")
        if full_report and full_report.lower() != 'none':
            print(f"Full report: {full_report}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 40)
        
        # Check if git is installed
        try:
            subprocess.run(["git", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error: Git is not installed or not available in PATH.")
            print("Please install Git and make sure it's available in your PATH.")
            return 1
            
        detector = HotspotDetector(
            repo_url, 
            branch, 
            ignore_file, 
            output_file, 
            auth_method,
            username,
            ssh_key,
            token
        )
        
        # Make sure to return to the original directory after any directory changes
        os.chdir(current_working_dir)
        
        hotspots, loc, revisions, authors = detector.analyze()
        
        # After analysis, reset to original directory again
        os.chdir(current_working_dir)
        
        # Always save results even if no hotspots found
        if not hotspots:
            print("No files found or analysis failed.")
            return 1
        
        detector.save_results(hotspots, top_n, full_report, loc, revisions, authors)
        return 0
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 130
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
