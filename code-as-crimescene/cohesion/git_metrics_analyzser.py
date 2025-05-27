#!/usr/bin/env python3
import argparse
import subprocess
import tempfile
import os
import shutil
from collections import defaultdict, Counter
from pathlib import Path
import re
import csv # For CSV output

# --- Configuration ---
DEFAULT_FILE_EXTENSIONS = ['.py', '.js', '.java', '.c', '.cpp', '.h', '.rb', '.go', '.rs', '.swift', '.kt', '.kts', '.scala', '.php', '.ts']
DEFAULT_TRUCK_FACTOR_ORPHAN_THRESHOLD = 0.5 # 50% of files orphaned
DEFAULT_FRICTION_MIN_AUTHORS = 5 # Min authors for a file to be considered high friction
DEFAULT_SINCE_DATE = "1 year ago" # For friction analysis primarily

# --- Helper Functions ---
def run_git_command(command, cwd, capture_output=True, check_sysexit_on_error=True):
    """
    Runs a git command.
    If capture_output is True, returns stdout as a string, decoded as UTF-8.
    If check_sysexit_on_error is True, will exit script on git command error.
    Otherwise, returns stdout (even on error) or empty string.
    """
    try:
        # print(f"DEBUG: Running: {' '.join(command)} in {cwd}") # For debugging
        process = subprocess.run(
            command,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        if process.returncode != 0:
            error_message_parts = [
                f"Git command failed: {' '.join(command)}",
                f"Return Code: {process.returncode}"
            ]
            if capture_output and process.stderr:
                error_message_parts.append(f"Stderr: {process.stderr.strip()}")
            else:
                 error_message_parts.append("Stderr: (not captured or empty)")
            
            error_message = "\n".join(error_message_parts)
            print(f"Warning: {error_message}")

            if check_sysexit_on_error:
                print("Exiting due to git command error.")
                exit(1)
        
        return process.stdout.strip() if capture_output and process.stdout else ""

    except FileNotFoundError:
        print("Error: git command not found. Please ensure git is installed and in your PATH.")
        exit(1)
    except Exception as e:
        print(f"An unexpected Python error occurred while trying to run command {' '.join(command)}: {e}")
        if check_sysexit_on_error:
            print("Exiting due to unexpected error.")
            exit(1)
        return ""

def get_relevant_files(repo_path, extensions):
    all_files_str = run_git_command(["git", "ls-files"], cwd=repo_path, check_sysexit_on_error=True)
    relevant_files = []
    if all_files_str:
        normalized_extensions = [ext.lower() for ext in extensions]
        for f_path_str in all_files_str.splitlines():
            if Path(f_path_str).suffix.lower() in normalized_extensions:
                relevant_files.append(f_path_str)
    return relevant_files

def normalize_author_email(email_str):
    if not email_str or not isinstance(email_str, str):
        return "unknown@example.com"
    
    email = email_str.lower().strip()
    if '@users.noreply.github.com' in email:
        parts = email.split('+', 1) # Split only on the first '+'
        if len(parts) > 1 and parts[0].isdigit():
            # parts[1] should be like username@users.noreply.github.com
            # We want to keep this more informative noreply address
            return parts[1] 
        # If it doesn't match the digit+username pattern, return as is (after lower/strip)
        return email 
    
    if '@' in email:
        local_part, domain = email.split('@', 1)
        if "gmail.com" in domain or "googlemail.com" in domain:
            local_part = local_part.split('+', 1)[0].replace('.', '')
            return f"{local_part}@{domain}"
        elif "outlook.com" in domain or "hotmail.com" in domain or "live.com" in domain:
            local_part = local_part.split('+', 1)[0]
            return f"{local_part}@{domain}"
    return email

# --- Organisational Friction Metrics ---
def calculate_authors_per_file(repo_path, relevant_files, since_date):
    authors_by_file = defaultdict(set)
    print(f"\nAnalyzing author contributions per file (since {since_date})...")

    log_output = run_git_command(
        ["git", "log", f"--since='{since_date}'", "--pretty=format:%H%x1E%ae", "--name-only"],
        cwd=repo_path,
        check_sysexit_on_error=False
    )

    if not log_output:
        print(f"Warning: No git log output for authors per file (perhaps no commits since {since_date}, or an error occurred).")
        return {}

    current_commit_author_email = None
    
    for line in log_output.splitlines():
        line = line.strip()
        if not line:
            continue

        if '\x1E' in line:
            parts = line.split('\x1E', 1)
            if len(parts) == 2 and '@' in parts[1]:
                current_commit_author_email = normalize_author_email(parts[1])
            else:
                current_commit_author_email = None
        elif current_commit_author_email:
            if line in relevant_files:
                 authors_by_file[line].add(current_commit_author_email)
    return authors_by_file

def display_organizational_friction(authors_per_file, min_authors_threshold):
    print("\n--- Organisational Friction (Simplified) ---")
    if not authors_per_file:
        print("No author data to analyze for friction.")
        return

    high_friction_files = []
    for f_path, authors in authors_per_file.items():
        valid_authors = {author for author in authors if author and author != "unknown@example.com"}
        if len(valid_authors) >= min_authors_threshold:
            high_friction_files.append((f_path, len(valid_authors)))

    if high_friction_files:
        print(f"Files with {min_authors_threshold} or more distinct authors (potential coordination hotspots):")
        high_friction_files.sort(key=lambda x: x[1], reverse=True)
        for f_path, count in high_friction_files:
            print(f"  - {f_path}: {count} authors")
    else:
        print(f"No files found with {min_authors_threshold} or more distinct authors.")

# --- Truck Factor Metrics ---
def get_line_authorship(repo_path, file_path):
    authorship = Counter()
    blame_output = run_git_command(
        ["git", "blame", "-w", "-e", "--", file_path],
        cwd=repo_path,
        check_sysexit_on_error=False
    )
    if not blame_output:
        return None

    email_pattern = re.compile(r"^\S+\s+\((.*?)\s+\d{4}-\d{2}-\d{2}")

    for line_content in blame_output.splitlines():
        match = email_pattern.match(line_content)
        if match:
            potential_email_info = match.group(1).strip()
            email_extract_match = re.search(r'<([^>]+@[^>]+)>', potential_email_info)
            author_email_raw = None
            if email_extract_match:
                author_email_raw = email_extract_match.group(1)
            else:
                parts = potential_email_info.split()
                if parts and '@' in parts[-1]:
                    author_email_raw = parts[-1]
            
            if author_email_raw:
                author_email_normalized = normalize_author_email(author_email_raw)
                if author_email_normalized and author_email_normalized != "unknown@example.com":
                    authorship[author_email_normalized] += 1
            
    return authorship if authorship else None

def calculate_truck_factor(repo_path, relevant_files, orphan_threshold_percentage):
    print("\nCalculating line authorship for Truck Factor (this may take a while for large repos)...")
    if not relevant_files:
        print("No relevant files found to calculate truck factor.")
        return 0, []

    file_authorship_map = {}
    processed_files_count = 0
    for i, f_path in enumerate(relevant_files):
        print(f"  Processing file {i+1}/{len(relevant_files)}: {f_path[:100]}{'...' if len(f_path)>100 else ''}", end='\r')
        authorship = get_line_authorship(repo_path, f_path)
        if authorship:
            file_authorship_map[f_path] = authorship
            processed_files_count += 1
    print(f"\nLine authorship processing complete. Successfully processed {processed_files_count}/{len(relevant_files)} files for blame.")

    if not file_authorship_map:
        print("No authorship data could be collected for any relevant files.")
        return 0, []

    file_primary_owners = {}
    author_owned_files_initial = defaultdict(set)
    all_involved_authors = set()

    for f_path, authors_in_file in file_authorship_map.items():
        if not authors_in_file:
            continue
        primary_owner = max(authors_in_file, key=authors_in_file.get)
        file_primary_owners[f_path] = primary_owner
        author_owned_files_initial[primary_owner].add(f_path)
        all_involved_authors.update(authors_in_file.keys())

    if not file_primary_owners:
        print("No primary owners could be determined for any files.")
        return 0, []
    
    num_total_files_with_owners = len(file_primary_owners)
    print(f"Total files with identifiable primary owners: {num_total_files_with_owners}")
    print(f"Total unique authors involved in these files: {len(all_involved_authors)}")

    truck_factor_developer_details = []
    orphaned_files_count = 0
    current_truck_factor = 0

    active_author_owned_files = {
        author: set(files) for author, files in author_owned_files_initial.items() if files
    }
    covered_files = set(file_primary_owners.keys())

    while (orphaned_files_count / num_total_files_with_owners) < orphan_threshold_percentage:
        if not active_author_owned_files or not covered_files:
            break

        author_to_remove = None
        
        sorted_authors_by_current_coverage = sorted(
            active_author_owned_files.items(),
            key=lambda item: len(item[1].intersection(covered_files)),
            reverse=True
        )
        
        if not sorted_authors_by_current_coverage or len(sorted_authors_by_current_coverage[0][1].intersection(covered_files)) == 0:
            break
            
        author_to_remove, files_primarily_owned_by_selected = sorted_authors_by_current_coverage[0]
        files_impacted_by_this_removal = files_primarily_owned_by_selected.intersection(covered_files)
        num_files_impacted_this_round = len(files_impacted_by_this_removal)

        if num_files_impacted_this_round == 0:
             break

        loc_impacted_this_round = 0
        for f_path in files_impacted_by_this_removal:
            loc_impacted_this_round += file_authorship_map.get(f_path, {}).get(author_to_remove, 0)

        current_truck_factor += 1
        truck_factor_developer_details.append({
            'email': author_to_remove,
            'files_impacted': num_files_impacted_this_round,
            'loc_impacted': loc_impacted_this_round
        })
        
        print(f"  Truck Factor Developer #{current_truck_factor}: {author_to_remove} "
              f"(orphaning {num_files_impacted_this_round} files, impacting {loc_impacted_this_round} of their LoC in these files)")

        for f_path_orphaned in files_impacted_by_this_removal:
            if f_path_orphaned in covered_files:
                covered_files.remove(f_path_orphaned)
                orphaned_files_count += 1
        
        del active_author_owned_files[author_to_remove]
        
        print(f"  Files orphaned so far: {orphaned_files_count}/{num_total_files_with_owners} ({(orphaned_files_count / num_total_files_with_owners):.2%})")

    return current_truck_factor, truck_factor_developer_details

def display_truck_factor(truck_factor, developer_details_list):
    print("\n--- Truck Factor ---")
    print(f"Calculated Truck Factor: {truck_factor}")
    if developer_details_list:
        print("Developers contributing to this Truck Factor (in order of impact if they left):")
        for i, dev_details in enumerate(developer_details_list):
            print(f"  {i+1}. {dev_details['email']}:")
            print(f"     Impacted Files (became at-risk when removed): {dev_details['files_impacted']}")
            print(f"     Impacted LoC (authored by them in these files): {dev_details['loc_impacted']}")
    else:
        print("No specific developers identified for the truck factor (e.g., if TF is 0 or data was insufficient).")

def write_truck_factor_csv(filepath, developer_details_list):
    """Writes the detailed Truck Factor information to a CSV file."""
    if not developer_details_list:
        print(f"No Truck Factor developer details to write to CSV: {filepath}")
        return

    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ["Order", "Developer Email", "Files Impacted at Removal", "LoC Authored in Impacted Files"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for i, dev_details in enumerate(developer_details_list):
                writer.writerow({
                    "Order": i + 1,
                    "Developer Email": dev_details['email'],
                    "Files Impacted at Removal": dev_details['files_impacted'],
                    "LoC Authored in Impacted Files": dev_details['loc_impacted']
                })
        print(f"Truck Factor details successfully written to: {filepath}")
    except IOError as e:
        print(f"Error writing Truck Factor CSV to {filepath}: {e}")


# --- Main CLI Logic ---
def main():
    parser = argparse.ArgumentParser(
        description="Calculate Organisational Friction and Truck Factor for a public GitHub repository.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("repo_url", help="URL of the public GitHub repository (e.g., https://github.com/user/repo).")
    parser.add_argument("--branch", help="Specific branch to analyze (defaults to the repository's default branch).")
    parser.add_argument(
        "--extensions",
        nargs='+',
        default=DEFAULT_FILE_EXTENSIONS,
        help="List of file extensions to consider for analysis."
    )
    parser.add_argument(
        "--since",
        default=DEFAULT_SINCE_DATE,
        help="For friction analysis, consider commits since this date (e.g., '1 year ago', '2023-01-01')."
    )
    parser.add_argument(
        "--friction_min_authors",
        type=int,
        default=DEFAULT_FRICTION_MIN_AUTHORS,
        help="Minimum number of distinct authors for a file to be flagged in friction analysis."
    )
    parser.add_argument(
        "--truck_factor_orphan_threshold",
        type=float,
        default=DEFAULT_TRUCK_FACTOR_ORPHAN_THRESHOLD,
        help="Percentage of files that need to be 'orphaned' to determine the Truck Factor (0.0 to 1.0)."
    )
    parser.add_argument(
        "--clone_depth",
        type=int,
        default=0, 
        help="Depth for git clone. Use 0 for full history (needed for comprehensive blame/log), or a positive integer for a shallow clone (faster, less history)."
    )
    parser.add_argument(
        "--truck_factor_csv_output",
        metavar="FILEPATH",
        help="Optional filepath to save the detailed Truck Factor developer list as a CSV file."
    )
    parser.add_argument(
        "--keep_repo",
        action="store_true",
        help="Keep the cloned repository after analysis (useful for debugging). By default, it's deleted."
    )

    args = parser.parse_args()

    if not (0.0 < args.truck_factor_orphan_threshold <= 1.0):
        print("Error: --truck_factor_orphan_threshold must be between 0.0 (exclusive) and 1.0 (inclusive).")
        exit(1)

    temp_dir = tempfile.mkdtemp(prefix="gitmetrics_")
    repo_name = args.repo_url.split('/')[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    repo_path = os.path.join(temp_dir, repo_name)

    print(f"Temporary directory for clone: {temp_dir}")

    try:
        print(f"Cloning {args.repo_url} into {repo_path}...")
        clone_command = ["git", "clone"]
        if args.clone_depth > 0:
            clone_command.extend(["--depth", str(args.clone_depth)])
            print(f"Performing a shallow clone with depth: {args.clone_depth}.")
        else:
            print("Performing a full clone. This may take time for large repositories.")
        
        if args.branch:
            clone_command.extend(["--branch", args.branch])
        clone_command.append(args.repo_url)
        clone_command.append(repo_path)
        
        run_git_command(clone_command, cwd=temp_dir, capture_output=False, check_sysexit_on_error=True)
        print("Clone successful.")

        if args.clone_depth > 0:
            print("Attempting to fetch more history for shallow clone (unshallowing)...")
            run_git_command(["git", "fetch", "--unshallow"], cwd=repo_path, capture_output=False, check_sysexit_on_error=False)
            run_git_command(["git", "fetch", "--all", "--tags", "--force"], cwd=repo_path, capture_output=False, check_sysexit_on_error=False)

        if args.branch:
            current_branch_cmd = run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
            if current_branch_cmd != args.branch:
                print(f"Switching to branch: {args.branch}...")
                run_git_command(["git", "checkout", args.branch], cwd=repo_path, capture_output=False, check_sysexit_on_error=False)

        print(f"\nIdentifying relevant files with extensions: {', '.join(args.extensions)}")
        relevant_files = get_relevant_files(repo_path, args.extensions)
        if not relevant_files:
            print("No relevant files found for analysis based on specified extensions. Exiting.")
            return
        print(f"Found {len(relevant_files)} relevant files for analysis.")

        authors_per_file = calculate_authors_per_file(repo_path, relevant_files, args.since)
        display_organizational_friction(authors_per_file, args.friction_min_authors)

        truck_factor_val, tf_dev_details = calculate_truck_factor(repo_path, relevant_files, args.truck_factor_orphan_threshold)
        display_truck_factor(truck_factor_val, tf_dev_details)

        if args.truck_factor_csv_output:
            write_truck_factor_csv(args.truck_factor_csv_output, tf_dev_details)

    finally:
        if args.keep_repo:
            print(f"\nCloned repository kept at: {repo_path}")
        else:
            print(f"\nCleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()