# Code Hotspot Detector

## Overview

The Code Hotspot Detector is a Python-based command-line tool that helps identify problematic files in a Git repository based on a combination of metrics: lines of code, number of revisions, and number of authors. These "hotspots" are files that deserve immediate attention as they are likely to harbor bugs, maintainability issues, and technical debt.

## How Hotspots Work

### The Hotspot Formula

The hotspot score is calculated using a multiplicative formula:

```
Hotspot Score = Lines of Code × Number of Revisions × Number of Authors
```

Each component of the formula represents a different risk factor:

* **Lines of Code** - Represents complexity and size. Larger files are harder to understand and maintain.
* **Number of Revisions** - Indicates instability and churn. Files that change frequently are more prone to bugs.
* **Number of Authors** - Reflects knowledge distribution. Files modified by many different people may lack consistent design or ownership.

### Why This Formula Works

This multiplicative formula identifies files with a dangerous combination of complexity and change frequency:

1. **Complexity without change** (large LOC but few revisions) isn't as risky
2. **Change without complexity** (small LOC but many revisions) is manageable
3. **Multiple authors on stable files** can be handled with good documentation
4. But when all three factors are high, the risk compounds exponentially

Research shows that typically 20% of a codebase generates 80% of the bugs and maintenance effort. This tool helps you identify that critical 20%.

## Installation

### Prerequisites

* Python 3.6+
* Git command-line tools

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd code-hotspot-detector
   ```

2. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Make the script executable (Linux/macOS):
   ```bash
   chmod +x hotspot_detector.py
   ```

## Usage

### Basic Command

```bash
python hotspot_detector.py analyze --repo-url=<git-repository-url>
```

### All Options

```
Usage:
  hotspot_detector.py analyze --repo-url=<url> [--branch=<branch>] [--ignore-file=<path>] 
                             [--output=<path>] [--top=<n>] [--full-report=<path>]
                             [--auth=<method>] [--username=<username>] [--ssh-key=<path>] [--token=<token>]
  hotspot_detector.py -h | --help
  hotspot_detector.py --version

Options:
  --repo-url=<url>       URL of the Git repository to analyze
  --branch=<branch>      Branch to analyze [default: main]
  --ignore-file=<path>   Path to ignore patterns file [default: ignore-files.txt]
  --output=<path>        Path to output CSV file [default: hotspots.csv]
  --top=<n>              Show only top N hotspots [default: 20]
  --full-report=<path>   Path to export full file data CSV [default: none]
  --auth=<method>        Authentication method: none, ssh, https, token [default: none]
  --username=<username>  Username for HTTPS authentication
  --ssh-key=<path>       Path to SSH private key file
  --token=<token>        Personal access token for authentication
  -h --help              Show this help message
  --version              Show version
```

### Authentication for Private Repositories

#### SSH Authentication

```bash
python hotspot_detector.py analyze --repo-url=git@github.com:username/private-repo.git --auth=ssh --ssh-key=/path/to/private_key
```

If you have an SSH agent running with your keys loaded, you can simply use:

```bash
python hotspot_detector.py analyze --repo-url=git@github.com:username/private-repo.git --auth=ssh
```

#### HTTPS Authentication with Username/Password

```bash
python hotspot_detector.py analyze --repo-url=https://github.com/username/private-repo.git --auth=https --username=your_username
```

You'll be prompted for your password during the clone operation.

#### Token-based Authentication

```bash
python hotspot_detector.py analyze --repo-url=https://github.com/username/private-repo.git --auth=token --token=your_personal_access_token
```

### Output Options

The tool provides two types of output files:

1. **Hotspots CSV** (`--output`): Contains only the files identified as hotspots, sorted by hotspot score in descending order.

2. **Full Report CSV** (`--full-report`): Contains metrics for all files in the repository, including those that aren't hotspots.

Example with full report:
```bash
python hotspot_detector.py analyze --repo-url=https://github.com/username/project.git --full-report=all_files.csv
```

## Ignore Patterns

To exclude files from analysis, create an `ignore-files.txt` file with patterns similar to `.gitignore` format:

```
# Comments start with a hash
*.min.js
node_modules/**
dist/**
**/*.test.*
```

The default file includes common patterns for build artifacts, third-party code, and test files.

## Example Output

The tool will display the top hotspots in the terminal and save the detailed data to CSV files:

```
Top 5 Hotspots:
+-----+-------------+-----------------+-------------+-----------+-----------------+
|   # | File        |   Lines of Code |   Revisions |   Authors |   Hotspot Score |
+=====+=============+=================+=============+===========+=================+
|   1 | process.sh  |             270 |         205 |         2 |          110700 |
+-----+-------------+-----------------+-------------+-----------+-----------------+
|   2 | cli-tool.py |            1045 |          33 |         2 |           68970 |
+-----+-------------+-----------------+-------------+-----------+-----------------+
|   3 | publish.sh  |             350 |          82 |         1 |           28700 |
+-----+-------------+-----------------+-------------+-----------+-----------------+
|   4 | example.bat |              28 |           5 |         1 |             140 |
+-----+-------------+-----------------+-------------+-----------+-----------------+
|   5 | parser.js   |              95 |          12 |         3 |            3420 |
+-----+-------------+-----------------+-------------+-----------+-----------------+

Recommended actions for hotspots:
1. Refactor into smaller, more focused components
2. Increase test coverage for these files
3. Document complex logic and design decisions
4. Schedule regular reviews of persistent hotspots
```

## Recommended Actions for Hotspots

When you identify hotspots in your codebase, consider the following remediation strategies:

1. **Refactoring**: Break large files into smaller, more modular components following the single responsibility principle.
2. **Test Coverage**: Prioritize adding comprehensive tests for hotspot files to prevent regressions.
3. **Documentation**: Add extensive comments and design documentation for complex logic.
4. **Code Reviews**: Schedule regular reviews of persistent hotspots with the whole team.
5. **Ownership Assignment**: Consider assigning clear owners to hotspot files to ensure consistent maintenance.
6. **Technical Debt Sprints**: Allocate specific time in your development cycle to address hotspots.

## Integrating with CI/CD

You can integrate the hotspot detector into your CI/CD pipeline to track hotspots over time:

```yaml
# Example GitHub Action
name: Code Hotspot Analysis

on:
  schedule:
    - cron: '0 0 * * 1'  # Run weekly on Mondays

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run hotspot analysis
        run: |
          python hotspot_detector.py analyze --repo-url=. --output=hotspots.csv --full-report=full_report.csv
      - name: Archive results
        uses: actions/upload-artifact@v3
        with:
          name: hotspot-analysis
          path: |
            hotspots.csv
            full_report.csv
```

## Troubleshooting

### Permission Issues on Windows

If you encounter permission issues with Git directories on Windows, try running the script with administrator privileges.

### Large Repositories

For very large repositories, consider using a local clone instead of cloning directly with the tool:

```bash
# First clone the repository
git clone https://github.com/username/large-project.git

# Then analyze the local repository
cd large-project
python /path/to/hotspot_detector.py analyze --repo-url=.
```

### Authentication Issues

If you encounter authentication issues with private repositories, try:

1. Ensuring your SSH key has the correct permissions
2. Verifying your personal access token has the correct scopes
3. Using the `--auth=https` method which leverages your local Git credentials

## Project Philosophy

This tool is based on research about code quality, maintainability, and team dynamics in software development. The key insights are:

1. **Code Quality**: Poor quality code has a high cost in terms of both developer time and user satisfaction.
2. **The Pareto Principle**: A small subset of files in most codebases cause a disproportionate number of issues.
3. **Evidence-Based Refactoring**: Refactoring decisions should be guided by data, not just feelings or preferences.

By identifying hotspots, teams can make informed decisions about where to focus their refactoring and quality improvement efforts.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
