#!/usr/bin/env python3
import argparse
import datetime
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


class DORAMetricsCalculator:
    def __init__(self, repo_url: str, branch: str = "main", temp_dir: Optional[str] = None,
                 start_date: Optional[str] = None, end_date: Optional[str] = None):
        self.repo_url = repo_url
        self.branch = branch
        self.temp_dir = temp_dir or tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.temp_dir, "repo")
        self.start_date = start_date
        self.end_date = end_date or datetime.datetime.now().strftime("%Y-%m-%d")
        
    def clone_repo(self) -> None:
        """Clone the repository to a temporary directory."""
        print(f"Cloning {self.repo_url} into {self.repo_dir}...")
        subprocess.run(["git", "clone", self.repo_url, self.repo_dir], check=True)
        
    def get_date_range_args(self) -> List[str]:
        """Return git log date range arguments based on provided dates."""
        args = []
        if self.start_date:
            args.extend(["--since", self.start_date])
        if self.end_date:
            args.extend(["--until", self.end_date])
        return args
        
    def get_deployment_frequency(self) -> float:
        """Calculate deployment frequency (deployments per day)."""
        os.chdir(self.repo_dir)
        
        # Get all tags that look like releases or deployments
        tag_pattern = r"v?\d+\.\d+\.\d+|release-|deploy-|prod-"
        date_args = self.get_date_range_args()
        
        # Get all tags with their dates
        cmd = ["git", "log", "--tags", "--simplify-by-decoration", "--pretty=%ai %d"]
        cmd.extend(date_args)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")
        
        # Count deployments based on tags
        deployments = []
        for line in lines:
            if not line.strip():
                continue
            if re.search(tag_pattern, line):
                date_str = line.split(" ")[0]
                deployments.append(date_str)
        
        # Calculate days in range
        if self.start_date:
            start = datetime.datetime.strptime(self.start_date, "%Y-%m-%d")
        else:
            # If no start date, use the date of the first commit
            first_commit_cmd = ["git", "log", "--reverse", "--format=%ai", "-1"]
            first_commit = subprocess.run(first_commit_cmd, capture_output=True, text=True).stdout.strip()
            if first_commit:
                start = datetime.datetime.strptime(first_commit.split(" ")[0], "%Y-%m-%d")
            else:
                return 0
        
        end = datetime.datetime.strptime(self.end_date, "%Y-%m-%d")
        days = (end - start).days or 1  # Avoid division by zero
        
        # If no deployment tags found, try to use merge commits to main as deployments
        if not deployments:
            print("No deployment tags found. Using merges to main branch as proxy...")
            merge_cmd = ["git", "log", self.branch, "--merges"]
            merge_cmd.extend(date_args)
            merge_cmd.extend(["--pretty=%ai"])
            
            result = subprocess.run(merge_cmd, capture_output=True, text=True)
            lines = result.stdout.strip().split("\n")
            deployments = [line.split(" ")[0] for line in lines if line.strip()]
        
        return len(deployments) / days
    
    def get_lead_time_for_changes(self) -> float:
        """Calculate lead time for changes (time from commit to deployment)."""
        os.chdir(self.repo_dir)
        
        # Get all tags that look like releases or deployments
        date_args = self.get_date_range_args()
        
        # This is complex without CI/CD data, so we'll use time between commit and merge to main as proxy
        cmd = ["git", "log", self.branch, "--merges"]
        cmd.extend(date_args)
        cmd.extend(["--pretty=%H"])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        merge_commits = result.stdout.strip().split("\n")
        
        lead_times = []
        for merge_commit in merge_commits:
            if not merge_commit.strip():
                continue
                
            # Get merge date
            merge_date_cmd = ["git", "show", "-s", "--format=%ai", merge_commit]
            merge_date_str = subprocess.run(merge_date_cmd, capture_output=True, text=True).stdout.strip()
            merge_date = datetime.datetime.strptime(merge_date_str, "%Y-%m-%d %H:%M:%S %z")
            
            # Get the commits that were merged
            parents_cmd = ["git", "log", merge_commit, "-n1", "--pretty=%P"]
            parents = subprocess.run(parents_cmd, capture_output=True, text=True).stdout.strip().split()
            
            if len(parents) >= 2:  # It's a merge commit
                # Get the earliest commit in the feature branch
                feature_branch_base = parents[1]  # Usually the second parent is the feature branch
                
                commits_cmd = ["git", "log", f"{feature_branch_base}..{merge_commit}", "--pretty=%ai"]
                commits = subprocess.run(commits_cmd, capture_output=True, text=True).stdout.strip().split("\n")
                
                if commits:
                    earliest_commit_date_str = commits[-1].strip()
                    if earliest_commit_date_str:
                        earliest_commit_date = datetime.datetime.strptime(
                            earliest_commit_date_str, "%Y-%m-%d %H:%M:%S %z")
                        lead_time_hours = (merge_date - earliest_commit_date).total_seconds() / 3600
                        lead_times.append(lead_time_hours)
        
        return sum(lead_times) / len(lead_times) if lead_times else 0
    
    def get_change_failure_rate(self) -> float:
        """Calculate change failure rate (percentage of deployments causing incidents)."""
        os.chdir(self.repo_dir)
        date_args = self.get_date_range_args()
        
        # Without incident data, we'll use hotfix commits as proxy for failures
        # Count total deployments (merges to main)
        merge_cmd = ["git", "log", self.branch, "--merges"]
        merge_cmd.extend(date_args)
        merge_cmd.extend(["--pretty=%H"])
        
        result = subprocess.run(merge_cmd, capture_output=True, text=True)
        total_deployments = len([line for line in result.stdout.strip().split("\n") if line.strip()])
        
        # Count hotfix commits (commits with "fix", "hotfix", "bugfix" in message)
        hotfix_cmd = ["git", "log", self.branch]
        hotfix_cmd.extend(date_args)
        hotfix_cmd.extend(["--pretty=%s"])
        
        result = subprocess.run(hotfix_cmd, capture_output=True, text=True)
        commit_msgs = result.stdout.strip().split("\n")
        hotfix_pattern = r"\b(fix|hotfix|bugfix|bug|issue|incident)\b"
        hotfixes = len([msg for msg in commit_msgs if re.search(hotfix_pattern, msg.lower())])
        
        return (hotfixes / total_deployments) if total_deployments > 0 else 0
    
    def get_time_to_restore(self) -> float:
        """
        Calculate time to restore service (time from incident to resolution).
        This is hard to determine from git data alone, so we'll use time between
        hotfix branches and their merges as a proxy.
        """
        os.chdir(self.repo_dir)
        date_args = self.get_date_range_args()
        
        # Look for hotfix branches and calculate time to merge
        branch_cmd = ["git", "branch", "-r"]
        result = subprocess.run(branch_cmd, capture_output=True, text=True)
        branches = result.stdout.strip().split("\n")
        
        hotfix_pattern = r"\b(hotfix|bugfix)\b"
        restore_times = []
        
        for branch in branches:
            branch = branch.strip()
            if not branch or not re.search(hotfix_pattern, branch.lower()):
                continue
                
            # Get creation date (first commit in branch)
            clean_branch = branch.replace("origin/", "")
            first_commit_cmd = ["git", "log", "--reverse", clean_branch, "-1", "--pretty=%ai"]
            first_commit_result = subprocess.run(first_commit_cmd, capture_output=True, text=True)
            
            if first_commit_result.returncode != 0:
                continue
                
            first_commit_date_str = first_commit_result.stdout.strip()
            if not first_commit_date_str:
                continue
                
            first_commit_date = datetime.datetime.strptime(first_commit_date_str, "%Y-%m-%d %H:%M:%S %z")
            
            # Get merge date
            merge_cmd = ["git", "log", self.branch, "--merges", f"--grep=Merge.*{clean_branch}", "-1", "--pretty=%ai"]
            merge_result = subprocess.run(merge_cmd, capture_output=True, text=True)
            
            if merge_result.returncode == 0 and merge_result.stdout.strip():
                merge_date_str = merge_result.stdout.strip()
                merge_date = datetime.datetime.strptime(merge_date_str, "%Y-%m-%d %H:%M:%S %z")
                restore_time_hours = (merge_date - first_commit_date).total_seconds() / 3600
                restore_times.append(restore_time_hours)
        
        # If we can't find hotfix branches, try to use issue references in commit messages
        if not restore_times:
            print("No dedicated hotfix branches found. Using issue references as proxy...")
            issue_pattern = r"(fix|resolve|close)\s+#(\d+)"
            
            # Get all commits that mention fixing issues
            issue_cmd = ["git", "log", self.branch]
            issue_cmd.extend(date_args)
            issue_cmd.extend(["--pretty=%H %s"])
            
            result = subprocess.run(issue_cmd, capture_output=True, text=True)
            commits = result.stdout.strip().split("\n")
            
            issue_to_fix_commit = {}
            for commit in commits:
                if not commit.strip():
                    continue
                    
                parts = commit.split(" ", 1)
                if len(parts) < 2:
                    continue
                    
                commit_hash, message = parts
                match = re.search(issue_pattern, message.lower())
                
                if match:
                    issue_num = match.group(2)
                    issue_to_fix_commit[issue_num] = commit_hash
            
            # For each fixed issue, try to find when it was created
            for issue_num, fix_commit_hash in issue_to_fix_commit.items():
                # Get fix date
                fix_date_cmd = ["git", "show", "-s", "--format=%ai", fix_commit_hash]
                fix_date_str = subprocess.run(fix_date_cmd, capture_output=True, text=True).stdout.strip()
                
                if not fix_date_str:
                    continue
                    
                fix_date = datetime.datetime.strptime(fix_date_str, "%Y-%m-%d %H:%M:%S %z")
                
                # Search for the commit that might have created the issue (mentioning the issue number)
                issue_create_cmd = ["git", "log", self.branch, f"--grep=#{issue_num}", "--pretty=%ai", "-1"]
                create_result = subprocess.run(issue_create_cmd, capture_output=True, text=True)
                
                if create_result.returncode == 0 and create_result.stdout.strip():
                    create_date_str = create_result.stdout.strip()
                    create_date = datetime.datetime.strptime(create_date_str, "%Y-%m-%d %H:%M:%S %z")
                    
                    if create_date < fix_date:  # Ensure creation is before fix
                        restore_time_hours = (fix_date - create_date).total_seconds() / 3600
                        restore_times.append(restore_time_hours)
        
        return sum(restore_times) / len(restore_times) if restore_times else 0
    
    def calculate_metrics(self) -> Dict[str, float]:
        """Calculate all DORA metrics."""
        try:
            self.clone_repo()
            
            metrics = {
                "deployment_frequency": self.get_deployment_frequency(),
                "lead_time_for_changes": self.get_lead_time_for_changes(),
                "change_failure_rate": self.get_change_failure_rate(),
                "time_to_restore": self.get_time_to_restore()
            }
            
            return metrics
        except Exception as e:
            print(f"Error calculating metrics: {e}")
            return {
                "deployment_frequency": 0,
                "lead_time_for_changes": 0,
                "change_failure_rate": 0,
                "time_to_restore": 0
            }
    
    def generate_report(self, metrics: Dict[str, float]) -> str:
        """Generate a human-readable report of the DORA metrics."""
        def determine_performance_level(metric_name, value):
            # Based on 2021 DORA report performance levels
            if metric_name == "deployment_frequency":
                if value >= 1:  # Multiple deploys per day
                    return "Elite"
                elif value >= 1/7:  # Between once per day and once per week
                    return "High"
                elif value >= 1/30:  # Between once per week and once per month
                    return "Medium"
                else:  # Less than once per month
                    return "Low"
            elif metric_name == "lead_time_for_changes":
                if value <= 24:  # Less than one day
                    return "Elite"
                elif value <= 168:  # Less than one week
                    return "High"
                elif value <= 720:  # Less than one month
                    return "Medium"
                else:  # More than one month
                    return "Low"
            elif metric_name == "change_failure_rate":
                if value <= 0.15:  # 0-15%
                    return "Elite"
                elif value <= 0.30:  # 16-30%
                    return "High"
                elif value <= 0.45:  # 31-45%
                    return "Medium"
                else:  # 46-60%
                    return "Low"
            elif metric_name == "time_to_restore":
                if value <= 24:  # Less than one day
                    return "Elite"
                elif value <= 168:  # Less than one week
                    return "High"
                elif value <= 720:  # Less than one month
                    return "Medium"
                else:  # More than one month
                    return "Low"
            return "Unknown"
        
        report = """
DORA Metrics Report
==================

Repository: {repo_url}
Branch: {branch}
Date Range: {start_date} to {end_date}

Summary
-------
""".format(
            repo_url=self.repo_url,
            branch=self.branch,
            start_date=self.start_date or "repository beginning",
            end_date=self.end_date
        )
        
        # Add metrics details
        report += f"1. Deployment Frequency: {metrics['deployment_frequency']:.2f} deployments/day ({determine_performance_level('deployment_frequency', metrics['deployment_frequency'])})\n"
        report += f"2. Lead Time for Changes: {metrics['lead_time_for_changes']:.2f} hours ({determine_performance_level('lead_time_for_changes', metrics['lead_time_for_changes'])})\n"
        report += f"3. Change Failure Rate: {metrics['change_failure_rate'] * 100:.2f}% ({determine_performance_level('change_failure_rate', metrics['change_failure_rate'])})\n"
        report += f"4. Time to Restore Service: {metrics['time_to_restore']:.2f} hours ({determine_performance_level('time_to_restore', metrics['time_to_restore'])})\n"
        
        # Add notes about limitations
        report += """
Notes
-----
- These metrics are approximations based on Git history analysis.
- Deployment frequency is calculated using tags or merge commits.
- Lead time uses time between earliest feature branch commit and merge to main.
- Change failure rate uses commits containing keywords like "fix" or "hotfix".
- Time to restore uses time between hotfix branch creation and merge.

For more accurate metrics, integrate with your CI/CD and incident management systems.
"""
        return report


def main():
    parser = argparse.ArgumentParser(description="Calculate DORA metrics for a Git repository")
    parser.add_argument("repo_url", help="URL of the Git repository")
    parser.add_argument("--branch", "-b", default="main", help="Branch to analyze (default: main)")
    parser.add_argument("--temp-dir", "-t", help="Temporary directory to clone the repository")
    parser.add_argument("--start-date", "-s", help="Start date for analysis (YYYY-MM-DD)")
    parser.add_argument("--end-date", "-e", help="End date for analysis (YYYY-MM-DD)")
    parser.add_argument("--json", "-j", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    calculator = DORAMetricsCalculator(
        repo_url=args.repo_url,
        branch=args.branch,
        temp_dir=args.temp_dir,
        start_date=args.start_date,
        end_date=args.end_date
    )
    
    metrics = calculator.calculate_metrics()
    
    if args.json:
        import json
        print(json.dumps(metrics, indent=2))
    else:
        print(calculator.generate_report(metrics))


if __name__ == "__main__":
    main()