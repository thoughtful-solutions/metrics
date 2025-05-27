import argparse
import subprocess
import tempfile
import shutil
import os
import re
from datetime import datetime

# --- Helper Functions to Run Git Commands ---

def run_git_command(command, cwd):
    """
    Runs a Git command in a specified directory and returns its output.
    Handles potential errors during command execution.
    """
    try:
        process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"Error executing command: {' '.join(command)}")
            print(f"Stderr: {stderr.strip()}")
            return None
        return stdout.strip()
    except FileNotFoundError:
        print("Error: Git command not found. Please ensure Git is installed and in your PATH.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while running git command: {e}")
        return None

# --- Metric Calculation Functions ---

def get_total_commits(repo_path):
    """Calculates the total number of commits in the repository."""
    output = run_git_command(["git", "rev-list", "--all", "--count"], repo_path)
    return int(output) if output and output.isdigit() else 0

def get_commit_activity(repo_path, days):
    """
    Calculates commit frequency (commits in the last N days) and
    active contributors (unique authors in the last N days).
    """
    since_date = f"{days} days ago"
    # Get commit logs with author names
    # Using %aN for author name according to git-log documentation for better parsing
    log_output = run_git_command(
        ["git", "log", f"--since={since_date}", "--pretty=format:%aN"], # Removed extra quotes around since_date
        repo_path
    )
    if log_output is None:
        return 0, 0, []

    commits_in_period = log_output.count('\n') + 1 if log_output else 0
    
    authors_in_period = set(log_output.splitlines()) if log_output else set()
    active_contributors_count = len(authors_in_period)
    
    return commits_in_period, active_contributors_count, sorted(list(authors_in_period))


def get_total_contributors(repo_path):
    """Calculates the total number of unique contributors."""
    output = run_git_command(["git", "shortlog", "-sn", "--all"], repo_path)
    if output is None:
        return 0, []
    
    contributors = []
    if output:
        lines = output.splitlines()
        for line in lines:
            match = re.match(r'\s*\d+\s+(.+)', line)
            if match:
                contributors.append(match.group(1).strip())
        return len(contributors), sorted(contributors)
    return 0, []


def get_branch_count(repo_path):
    """Counts the number of remote branches."""
    output = run_git_command(["git", "branch", "-r"], repo_path)
    if output is None:
        return 0
    branches = [b.strip() for b in output.splitlines() if b.strip() and 'HEAD ->' not in b]
    return len(branches)

def get_tag_count(repo_path):
    """Counts the number of tags."""
    output = run_git_command(["git", "tag"], repo_path)
    if output is None:
        return 0
    return len(output.splitlines()) if output else 0

def get_code_churn(repo_path, days):
    """
    Calculates code churn (lines added/deleted) in the last N days.
    Uses git log --numstat.
    """
    since_date = f"{days} days ago"
    output = run_git_command(
        ["git", "log", f"--since={since_date}", "--numstat", "--pretty=tformat:"], # Removed extra quotes
        repo_path
    )
    if output is None:
        return 0, 0

    lines_added = 0
    lines_deleted = 0
    if output:
        for line in output.splitlines():
            if not line.strip(): 
                continue
            parts = line.split('\t')
            if len(parts) == 3: 
                try:
                    if parts[0] != '-':
                        lines_added += int(parts[0])
                    if parts[1] != '-':
                        lines_deleted += int(parts[1])
                except ValueError:
                    print(f"Warning: Could not parse numstat line: {line}")
                    continue
    return lines_added, lines_deleted

def get_commit_dates(repo_path):
    """Gets the date of the first and latest commit."""
    first_commit_date_str = run_git_command(
        ["git", "log", "--reverse", "--pretty=format:%ci", "--max-count=1"],
        repo_path
    )
    latest_commit_date_str = run_git_command(
        ["git", "log", "--pretty=format:%ci", "--max-count=1"],
        repo_path
    )

    first_commit_date = None
    latest_commit_date = None

    try:
        if first_commit_date_str:
            first_commit_date = datetime.strptime(first_commit_date_str.split(' ')[0], "%Y-%m-%d").strftime("%Y-%m-%d")
        if latest_commit_date_str:
            latest_commit_date = datetime.strptime(latest_commit_date_str.split(' ')[0], "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError as e:
        print(f"Warning: Could not parse commit date: {e}")

    return first_commit_date, latest_commit_date

# --- Main CLI Logic ---

def main():
    parser = argparse.ArgumentParser(description="Fetch Git repository metrics.")
    # repo_url is a positional argument, it should be provided for the script to run as intended.
    # For sandbox/testing where args might be an issue, it's handled by parse_known_args.
    parser.add_argument("repo_url", help="URL of the remote Git repository.")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of past days to consider for time-windowed metrics (default: 30)."
    )
    parser.add_argument(
        "--show-contributors",
        action="store_true",
        help="Show lists of contributors (can be long for large repos)."
    )

    # Use parse_known_args() to separate known arguments from unknown ones (e.g., sandbox args)
    # This will parse the arguments defined above and put any others into the 'unknown_args' list.
    args, unknown_args = parser.parse_known_args()

    if unknown_args:
        print(f"Warning: Unrecognized arguments were found and ignored: {unknown_args}")
        print("This can happen if the script is run in a specific environment that adds its own arguments.")

    # Note: The script requires network access to clone the repository and
    # file system access to create a temporary directory.
    # If run in a restricted sandbox, these operations might fail.

    print(f"Attempting to clone '{args.repo_url}'...")
    print("This might take a moment for large repositories.\n")

    # Create a temporary directory to clone the repo
    # tempfile.TemporaryDirectory() handles creation and cleanup.
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                clone_command = ["git", "clone", "--quiet", args.repo_url, temp_dir]
                # It's good practice to handle potential errors from Popen/communicate itself
                clone_process = subprocess.Popen(clone_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
                stdout, stderr = clone_process.communicate(timeout=300) # Added timeout

                if clone_process.returncode != 0:
                    print(f"Error cloning repository: {args.repo_url}")
                    print(f"Stderr: {stderr.strip()}")
                    return # Exit if clone fails

                print(f"Successfully cloned to temporary directory: {temp_dir}\n")
                print("--- Git Repository Metrics ---")
                print(f"Repository URL: {args.repo_url}")
                print(f"Metrics based on the last {args.days} days where applicable.\n")

                total_commits_val = get_total_commits(temp_dir)
                print(f"Total Commits: {total_commits_val}")

                first_commit, last_commit = get_commit_dates(temp_dir)
                if first_commit:
                    print(f"First Commit Date: {first_commit}")
                if last_commit:
                    print(f"Latest Commit Date: {last_commit}")

                total_contributors_count, total_contributor_names = get_total_contributors(temp_dir)
                print(f"Total Unique Contributors: {total_contributors_count}")
                if args.show_contributors and total_contributor_names:
                    print(f"  Contributors: {', '.join(total_contributor_names)}")

                branch_count_val = get_branch_count(temp_dir)
                print(f"Remote Branches: {branch_count_val}")

                tag_count_val = get_tag_count(temp_dir)
                print(f"Tags: {tag_count_val}")

                print(f"\n--- Activity in the Last {args.days} Days ---")

                commits_last_n_days, active_contrib_count, active_contrib_names = get_commit_activity(temp_dir, args.days)
                print(f"Commits in Last {args.days} Days: {commits_last_n_days}")
                print(f"Active Contributors (Last {args.days} Days): {active_contrib_count}")
                if args.show_contributors and active_contrib_names:
                     print(f"  Active Contributors: {', '.join(active_contrib_names)}")

                lines_added, lines_deleted = get_code_churn(temp_dir, args.days)
                print(f"Lines Added (Last {args.days} Days): {lines_added}")
                print(f"Lines Deleted (Last {args.days} Days): {lines_deleted}")
                print(f"Net Change (Last {args.days} Days): {lines_added - lines_deleted} lines")

            except subprocess.TimeoutExpired:
                print(f"Error: Git clone operation timed out for {args.repo_url}.")
            except FileNotFoundError: # Should be caught by run_git_command, but good for Popen directly
                print("Error: Git command not found. Please ensure Git is installed and in your PATH.")
            except Exception as e: # Catch other potential errors during git operations or processing
                print(f"An error occurred during repository processing: {e}")
            finally:
                # TemporaryDirectory cleans itself up on exit from the 'with' block
                print(f"\nProcessing finished. Temporary directory '{temp_dir}' will be cleaned up.")

    except Exception as e: # Catch errors related to TemporaryDirectory creation itself
        print(f"An critical error occurred: {e}")


    print("\nDone.")

if __name__ == "__main__":
    main()
