### Filter out files with too few changes:

```bash
./change_coupling.py --repo https://github.com/someuser/awesome-project.git --min-changes 5
```

### Set both minimum changes and minimum coupling threshold:

```bash
./change_coupling.py --repo https://github.com/someuser/awesome-project.git --min-changes 5 --coupling-threshold 40
```# Change Coupling Analyzer

A Python CLI tool that analyzes Git repositories to identify change coupling (also known as temporal coupling) between files. Change coupling reveals implicit dependencies between files that tend to change together, which can help identify potential design issues, code clones, and areas that might benefit from refactoring.

## What is Change Coupling?

Change coupling (or temporal coupling) refers to files in your codebase that tend to change together in commits. Unlike traditional code coupling which is visible in the source code, change coupling reveals hidden dependencies that might not be apparent from the code structure alone.

High change coupling between files that belong to different modules or components often indicates:
- Hidden dependencies that may need to be made explicit
- Potential design issues or architectural decay
- Code that violates the single responsibility principle
- Candidates for refactoring

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/change-coupling-analyzer.git
cd change-coupling-analyzer

# Make the script executable
chmod +x change_coupling.py

# Install dependencies (only standard library is used, so no additional dependencies)
```

## Usage

```bash
./change_coupling.py --repo <repository-url> [OPTIONS]
```

### Options

- `--repo URL`: URL of the Git repository to analyze (required)
- `--branch BRANCH`: Branch to analyze [default: main]
- `--since DAYS`: Only consider commits from the last N days [default: 90]
- `--coupling-threshold PERCENT`: Minimum coupling percentage to report [default: 30]
- `--min-changes N`: Minimum number of changes required for a file to be considered [default: 3]
- `--output FORMAT`: Output format for display: text, csv, or json [default: text]
- `--output-file FILE`: File to save CSV results [default: change_coupling_results.csv]
- `--top N`: Show top N results with highest coupling [default: 20]
- `--ignore-file FILE`: Path to file containing patterns of files to ignore
- `-h, --help`: Show help message

## Examples

### Basic usage:

```bash
./change_coupling.py --repo https://github.com/someuser/awesome-project.git
```

This will:
1. Analyze the repository's main branch for the last 90 days
2. Save all results to `change_coupling_results.csv` in the current directory
3. Display the top 20 most coupled file pairs in text format

### Analyze a specific branch for the last 60 days:

```bash
./change_coupling.py --repo https://github.com/someuser/awesome-project.git --branch develop --since 60
```

### Generate JSON output with a higher coupling threshold and display top 10 results:

```bash
./change_coupling.py --repo https://github.com/someuser/awesome-project.git --coupling-threshold 50 --output json --top 10
```

### Save CSV results to a custom file and ignore certain files:

```bash
./change_coupling.py --repo https://github.com/someuser/awesome-project.git --output-file my_results.csv --ignore-file .gitignore
```

### Use a custom ignore file:

```bash
./change_coupling.py --repo https://github.com/someuser/awesome-project.git --ignore-file ignore-patterns.txt
```

The ignore file should contain glob patterns, one per line. For example:
```
# Configuration files
**/.eslintrc*
**/.prettierrc*
**/package.json
**/package-lock.json

# Build outputs
**/dist/**
**/build/**

# Tests
**/__tests__/**
**/*.test.js
```

## Sample Output

### Text Format (default):

```
Top 20 Change Coupling Results:
--------------------------------------------------------------------------------
File 1                          File 2                          Coupling %  Together   File1 Chg  File2 Chg  
--------------------------------------------------------------------------------
src/components/Header.js        src/styles/header.css           85.71      6          7          8          
src/utils/validation.js         src/components/Form.js          78.33      47         55         60         
src/api/endpoints.js            src/services/api.js             65.22      30         40         46         
...

Full results saved to change_coupling_results.csv
```

### JSON Format:

```json
[
  {
    "file1": "src/components/Header.js",
    "file2": "src/styles/header.css",
    "coupling_percent": 85.71,
    "changes_together": 6,
    "file1_changes": 7,
    "file2_changes": 8
  },
  ...
]
```

### CSV File (automatically generated):

The tool always saves complete results to a CSV file (regardless of display format), with columns:
- `file1`: First file in the coupled pair
- `file2`: Second file in the coupled pair
- `coupling_percent`: Percentage indicating strength of coupling
- `changes_together`: Number of commits where both files changed together
- `file1_changes`: Total number of commits where file1 changed
- `file2_changes`: Total number of commits where file2 changed

## Understanding the Results

- **File 1 & File 2**: The pair of files that exhibit change coupling
- **Coupling %**: The percentage of times these files change together, relative to their individual change frequencies
- **Together**: Number of commits where both files changed together
- **File1 Chg**: Total number of commits where File 1 changed
- **File2 Chg**: Total number of commits where File 2 changed
- **Score**: Weighted coupling score calculated as `coupling_percent * log(changes_together + 1)`

The weighted score helps prioritize results by considering both the coupling percentage and the frequency of changes. Files with high coupling percentages AND many changes together will have higher scores than files with high percentages but few changes.

Higher coupling percentages indicate stronger implicit dependencies between files. These might be candidates for refactoring, especially if they belong to different modules or components.

### How Files Are Filtered

The tool applies several filters to provide more meaningful results:

1. **Minimum changes threshold**: Files must have changed at least N times to be included (default: 3)
2. **Minimum coupling percentage**: Only file pairs with coupling above the threshold are included (default: 30%)
3. **Configuration file exclusion**: Common configuration files (like `.eslintrc.js`) are automatically excluded
4. **Custom ignore patterns**: Additional files can be excluded using the `--ignore-file` parameter

## How It Works

The tool:

1. Clones the specified Git repository to a temporary directory
2. Retrieves the commit history for the specified time period
3. For each commit, identifies which files changed
4. Tracks how often each file changes and how often pairs of files change together
5. Calculates coupling percentages and identifies pairs that exceed the threshold
6. Saves all results to a CSV file
7. Displays the top N results in the specified format
8. Cleans up temporary files once analysis is complete

## Use Cases

- **Identify Refactoring Candidates**: Files with high change coupling across module boundaries may indicate design issues
- **Find Hidden Dependencies**: Discover implicit relationships that aren't visible in the code structure
- **Code Quality Assessment**: Use as part of code quality metrics for legacy systems
- **Architectural Analysis**: Understand how changes propagate through your system
- **Team Coordination**: Identify areas where multiple teams need to coordinate changes

## Limitations

- Only considers source code files (based on file extensions)
- Doesn't analyze the content of changes, only which files changed together
- Temporary cloning of repositories may be slow for large repositories
- Single-branch analysis only

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
