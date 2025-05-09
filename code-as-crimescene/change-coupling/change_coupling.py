#!/usr/bin/env python3
"""
Change Coupling Analyzer - A CLI tool to identify change coupling in Git repositories.

Change coupling identifies files that change together frequently, indicating hidden dependencies.

Usage:
  change_coupling_analyzer.py analyze --repo-url=<url> [--branch=<branch>] [--ignore-file=<path>] [--output=<path>] [--top=<n>] [--threshold=<percent>] [--auth=<method>] [--username=<username>] [--ssh-key=<path>] [--token=<token>]
  change_coupling_analyzer.py -h | --help
  change_coupling_analyzer.py --version

Options:
  --repo-url=<url>       URL of the Git repository to analyze
  --branch=<branch>      Branch to analyze [default: main]
  --ignore-file=<path>   Path to ignore patterns file [default: ignore-files.txt]
  --output=<path>        Path to output CSV file [default: change_coupling.csv]
  --top=<n>              Show only top N coupled pairs [default: 20]
  --threshold=<percent>  Minimum coupling percentage [default: 30]
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
from itertools import combinations


__version__ = "1.0.0"


class ChangeCouplingAnalyzer:
    def __init__(self, repo_url, branch="main", ignore_file="ignore-files.txt", output_file="change_coupling.csv", 
                 threshold=30, auth_method="none", username=None, ssh_key=None, token=None):
        self.repo_url = repo_url
        self.branch = branch
        self.ignore_file = ignore_file
        self.output_file = output_file
        self.threshold = threshold
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
            
            # Check if we need to unshallow
            os.chdir(self.temp_dir)
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

    def get_commit_history(self):
        """Get the commit history from the Git repository."""
        # Store the original directory to return to it later
        original_dir = os.getcwd()
        
        try:
            os.chdir(self.temp_dir)
            
            print("Analyzing commit history...")
            
            # Check if we have any commits in the repo
            try:
                cmd_check = subprocess.run(
                    ["git", "rev-list", "--count", "HEAD"],
                    capture_output=True, check=True
                )
                commit_count = int(cmd_check.stdout.decode('utf-8').strip())
                print(f"Found {commit_count} commits in repository.")
                
                if commit_count == 0:
                    print("WARNING: Repository has no commits! Cannot analyze change coupling.")
                    return []
            except subprocess.CalledProcessError as e:
                print(f"Error checking commit count: {e}")
                if e.stderr:
                    print(f"Git error: {e.stderr.decode('utf-8', errors='replace')}")
                return []
            
            # Fetch the list of tracked files to validate against
            try:
                cmd_files = subprocess.run(
                    ["git", "ls-files"],
                    capture_output=True, check=True
                )
                valid_files = set(cmd_files.stdout.decode('utf-8').strip().splitlines())
                print(f"Repository contains {len(valid_files)} tracked files.")
            except subprocess.CalledProcessError as e:
                print(f"Error getting file list: {e}")
                if e.stderr:
                    print(f"Git error: {e.stderr.decode('utf-8', errors='replace')}")
                return []
            
            # Get commit history with files that changed in each commit
            print("Retrieving commit history with changed files (this might take a while)...")
            try:
                # Format: commit hash + file names
                cmd = ["git", "log", "--name-only", "--format=%H"]
                result = subprocess.run(cmd, capture_output=True, check=True)
                output = result.stdout.decode('utf-8', errors='replace').splitlines()
                
                # Process the output to group files by commit
                commits = []
                current_commit = None
                current_files = []
                
                for line in output:
                    line = line.strip()
                    if not line:
                        # Empty line, skip
                        continue
                    
                    if re.match(r'^[0-9a-f]{40}$', line):
                        # This is a commit hash
                        
                        # First, save the previous commit if we have one
                        if current_commit and current_files:
                            # Filter out files that should be ignored
                            filtered_files = [f for f in current_files if f in valid_files and not self.should_ignore(f)]
                            if filtered_files:
                                commits.append({
                                    'hash': current_commit,
                                    'files': filtered_files
                                })
                        
                        # Start a new commit
                        current_commit = line
                        current_files = []
                    else:
                        # This is a file name
                        current_files.append(line)
                
                # Don't forget to add the last commit
                if current_commit and current_files:
                    filtered_files = [f for f in current_files if f in valid_files and not self.should_ignore(f)]
                    if filtered_files:
                        commits.append({
                            'hash': current_commit,
                            'files': filtered_files
                        })
                
                print(f"Processed {len(commits)} commits with changes to tracked files.")
                
                # Quick stats about the data
                file_count = Counter()
                for commit in commits:
                    for file in commit['files']:
                        file_count[file] += 1
                
                top_changed_files = file_count.most_common(5)
                if top_changed_files:
                    print("\nTop 5 most frequently changed files:")
                    for file, count in top_changed_files:
                        print(f"  {file}: {count} changes")
                
                return commits
                
            except subprocess.CalledProcessError as e:
                print(f"Error retrieving commit history: {e}")
                if e.stderr:
                    print(f"Git error: {e.stderr.decode('utf-8', errors='replace')}")
                return []
                
        except Exception as e:
            print(f"Error in get_commit_history: {e}")
            import traceback
            traceback.print_exc()
            return []
            
        finally:
            # Always change back to the original directory
            os.chdir(original_dir)

    def analyze_change_coupling(self, commits):
        """Analyze change coupling between files based on commit history."""
        if not commits:
            print("No commit data available for analysis.")
            return []
        
        print("Analyzing change coupling between files...")
        
        # Count how many times each file appears in commits
        file_counts = defaultdict(int)
        # Count how many times each pair of files appears together
        pair_counts = defaultdict(int)
        
        # Process each commit
        for commit in commits:
            files = commit['files']
            
            # Update individual file counts
            for file in files:
                file_counts[file] += 1
            
            # Update pair counts (only for commits with multiple files)
            if len(files) > 1:
                for file1, file2 in combinations(sorted(files), 2):  # Use combinations to avoid duplicates
                    pair_key = (file1, file2)
                    pair_counts[pair_key] += 1
        
        print(f"Found {len(file_counts)} unique files and {len(pair_counts)} file pairs in commits.")
        
        # Calculate coupling metrics
        coupling_results = []
        for (file1, file2), pair_count in pair_counts.items():
            file1_count = file_counts[file1]
            file2_count = file_counts[file2]
            
            # Calculate coupling percentage: how often file2 changes when file1 changes
            coupling_pct_1to2 = (pair_count / file1_count) * 100
            coupling_pct_2to1 = (pair_count / file2_count) * 100
            
            # Average coupling
            avg_coupling = (coupling_pct_1to2 + coupling_pct_2to1) / 2
            
            # Apply threshold filter
            if avg_coupling >= self.threshold:
                coupling_results.append({
                    'file1': file1,
                    'file2': file2,
                    'commits_together': pair_count,
                    'file1_commits': file1_count,
                    'file2_commits': file2_count,
                    'coupling_1_to_2': coupling_pct_1to2,
                    'coupling_2_to_1': coupling_pct_2to1,
                    'avg_coupling': avg_coupling
                })
        
        # Sort by average coupling percentage (descending)
        coupling_results.sort(key=lambda x: x['avg_coupling'], reverse=True)
        
        print(f"Identified {len(coupling_results)} file pairs with coupling percentage >= {self.threshold}%")
        
        return coupling_results

    def analyze(self):
        """Main analysis function to find change coupling in the repository."""
        try:
            self.clone_repo()
            commits = self.get_commit_history()
            coupling_results = self.analyze_change_coupling(commits)
            return coupling_results
        except Exception as e:
            print(f"Error during analysis: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            self.cleanup()

    def save_results(self, coupling_results, top_n=20):
        """Save the coupling results to a CSV file and display top results."""
        try:
            # Ensure output path is properly resolved
            output_file = self.output_file
            if not os.path.isabs(output_file) and not (len(output_file) > 1 and output_file[1] == ':'):
                if output_file.startswith('./') or output_file.startswith('.\\'):
                    output_file = output_file[2:]
                output_file = os.path.join(os.getcwd(), output_file)
                print(f"Using absolute path for output: {output_file}")
            
            # Ensure output directory exists
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    print(f"Created output directory: {output_dir}")
                except Exception as e:
                    print(f"Warning: Could not create output directory {output_dir}: {e}")
            
            if not coupling_results:
                print("No change coupling found above the threshold.")
                # Create an empty CSV file with headers
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        'file1', 'file2', 'commits_together', 'file1_commits', 
                        'file2_commits', 'coupling_1_to_2', 'coupling_2_to_1', 'avg_coupling'
                    ])
                    writer.writeheader()
                print(f"Created empty report file: {output_file}")
                return
            
            print(f"Writing results to CSV file: {output_file}")
            try:
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        'file1', 'file2', 'commits_together', 'file1_commits', 
                        'file2_commits', 'coupling_1_to_2', 'coupling_2_to_1', 'avg_coupling'
                    ])
                    writer.writeheader()
                    for result in coupling_results:
                        writer.writerow(result)
                
                file_size = os.path.getsize(output_file)
                print(f"Results saved to {output_file} ({file_size} bytes)")
            except Exception as e:
                print(f"Error writing to CSV file: {e}")
                print(f"Attempting to save to current directory...")
                # Try saving to current directory with a fixed filename
                alt_output = os.path.join(os.getcwd(), "change_coupling_report.csv")
                with open(alt_output, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        'file1', 'file2', 'commits_together', 'file1_commits', 
                        'file2_commits', 'coupling_1_to_2', 'coupling_2_to_1', 'avg_coupling'
                    ])
                    writer.writeheader()
                    for result in coupling_results:
                        writer.writerow(result)
                print(f"Results saved to alternative file: {alt_output}")
            
            # Display the top N coupling results
            if coupling_results:
                print(f"\nTop {min(top_n, len(coupling_results))} Change Coupling Pairs:")
                table_data = []
                for i, result in enumerate(coupling_results[:top_n], 1):
                    table_data.append([
                        i,
                        result['file1'],
                        result['file2'],
                        f"{result['commits_together']} / {result['file1_commits']} / {result['file2_commits']}",
                        f"{result['avg_coupling']:.1f}%"
                    ])
                    
                headers = ["#", "File 1", "File 2", "Together/File1/File2", "Avg Coupling %"]
                print(tabulate.tabulate(table_data, headers=headers, tablefmt="grid"))
                
                print("\nRecommended actions for highly coupled files:")
                print("1. Consider if the files should be merged or further separated")
                print("2. Document dependencies between these files")
                print("3. Ensure comprehensive tests cover both files together")
                print("4. Look for hidden dependencies or design issues")
                print("5. Consider creating abstractions to reduce coupling")
                print("\nNote: File pairs with high coupling percentages (>70%) often indicate:")
                print("- Files that should be refactored together")
                print("- Potential violations of the Single Responsibility Principle")
                print("- Hidden architectural dependencies")
            else:
                print("\nNo change coupling detected above the threshold percentage.")
                print(f"Try lowering the threshold (currently {self.threshold}%) to see more results.")
                
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
        args = docopt(__doc__, version=f"Change Coupling Analyzer v{__version__}")
        
        repo_url = args['--repo-url']
        branch = args['--branch'] or 'main'
        ignore_file = args['--ignore-file']
        output_file = args['--output']
        top_n = int(args['--top'])
        threshold = float(args['--threshold'])
        auth_method = args['--auth'] or 'none'
        username = args['--username']
        ssh_key = args['--ssh-key']
        token = args['--token']
        
        # Store the current working directory
        current_working_dir = os.getcwd()
        
        # Make paths absolute
        if ignore_file and not os.path.isabs(ignore_file) and not (len(ignore_file) > 1 and ignore_file[1] == ':'):
            if ignore_file.startswith('./') or ignore_file.startswith('.\\'):
                ignore_file = ignore_file[2:]
            ignore_file = os.path.join(current_working_dir, ignore_file)
        
        # Ensure output path is fully qualified
        if output_file and not os.path.isabs(output_file) and not (len(output_file) > 1 and output_file[1] == ':'):
            if output_file.startswith('./') or output_file.startswith('.\\'):
                output_file = output_file[2:]
            output_file = os.path.join(current_working_dir, output_file)
        
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
        
        print(f"=== Change Coupling Analyzer v{__version__} ===")
        print(f"Current working directory: {current_working_dir}")
        # Hide credentials when printing the URL
        display_url = repo_url.split('@')[-1] if '@' in repo_url else repo_url
        print(f"Repository: {display_url}")
        print(f"Branch: {branch}")
        print(f"Ignore file: {ignore_file}")
        print(f"Output file: {output_file}")
        print(f"Coupling threshold: {threshold}%")
        print(f"Authentication: {auth_method}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 40)
        
        # Check if git is installed
        try:
            subprocess.run(["git", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error: Git is not installed or not available in PATH.")
            print("Please install Git and make sure it's available in your PATH.")
            return 1
            
        analyzer = ChangeCouplingAnalyzer(
            repo_url, 
            branch, 
            ignore_file, 
            output_file,
            threshold,
            auth_method,
            username,
            ssh_key,
            token
        )
        
        # Make sure to return to the original directory
        os.chdir(current_working_dir)
        
        coupling_results = analyzer.analyze()
        
        # Reset to original directory again
        os.chdir(current_working_dir)
        
        analyzer.save_results(coupling_results, top_n)
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
