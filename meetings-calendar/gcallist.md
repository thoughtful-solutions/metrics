# Google Calendar Analyzer

## Overview

The Google Calendar Analyzer is a Python-based command-line tool that helps you gain insights into your calendar usage patterns. It analyzes events from your Google Calendar accounts and generates comprehensive metrics about your scheduling habits, meeting frequency, time allocation, and collaboration patterns.

## Metrics and Insights Provided

The tool generates a comprehensive report with the following metrics:

### Event Counts

* **Total Events**: Overall number of calendar events in the analyzed period
* **Past Events**: Events that have already occurred
* **Upcoming Events**: Events scheduled for the future
* **All-Day Events**: Events spanning the entire day
* **Recurring Events**: Events set up as recurring meetings

### Time Distribution

* **Events by Day of Week**: Count of events occurring on each day of the week
* **Busiest Day(s)**: Day(s) with the highest number of events
* **Events by Hour**: Distribution of events across hours of the day

### Duration Statistics

* **Average Duration**: Mean length of your calendar events
* **Longest Event**: Title and duration of your longest meeting
* **Shortest Event**: Title and duration of your shortest meeting

### Attendee Analysis

* **Top Attendees**: List of people who appear most frequently in your meetings
* **Average Attendees Per Event**: Mean number of participants in your events

## How Calendar Analysis Works

The tool accesses your Google Calendar data through the Google Calendar API and calculates various metrics across several dimensions:

### Time-Based Metrics

* **Event Distribution**: Analysis of events by day of week, hour of day, and month
* **Past vs. Upcoming**: Breakdown of events that have already occurred versus upcoming events
* **Duration Analysis**: Statistics on meeting lengths, identifying your shortest and longest events

### Event Type Metrics

* **All-Day Events**: Count of full-day events like holidays, PTO, or day-long workshops
* **Recurring Events**: Identification of regularly scheduled meetings
* **Attendee Patterns**: Analysis of who you meet with most frequently

### Patterns and Insights

The metrics reveal important patterns such as:
* Your busiest days of the week
* Your peak meeting hours 
* Your most frequent collaborators
* Your typical meeting duration

## Example Output

```
====================================================================
 CALENDAR REPORT: Work Calendar
====================================================================

TOTAL EVENTS: 87
- Past events: 78
- Upcoming events: 9
- All-day events: 5
- Recurring events: 42

TIME PATTERNS:
  Events by day of week:
  - Monday: 18
  - Tuesday: 22
  - Wednesday: 17
  - Thursday: 15
  - Friday: 12
  - Saturday: 2
  - Sunday: 1
  - Busiest day(s): Tuesday

  Events by hour:
  - 9 AM: 10
  - 10 AM: 15
  - 11 AM: 12
  - 12 PM: 4
  - 1 PM: 11
  - 2 PM: 14
  - 3 PM: 9
  - 4 PM: 8

DURATION STATS:
  - Average duration: 45.3 minutes
  - Longest event: Quarterly Planning (180.0 minutes)
  - Shortest event: Daily Standup (15.0 minutes)

TOP ATTENDEES:
  - manager@company.com: 28 events
  - teammate1@company.com: 24 events
  - teammate2@company.com: 22 events
  - client1@client.com: 12 events
  - client2@client.com: 8 events
  - Average attendees per event: 4.2
```

## Interpreting the Results

The calendar metrics can provide valuable insights:

### Time Management

* **Meeting Concentration**: If certain days or hours show high concentrations of meetings, consider implementing meeting-free blocks to protect focus time.
* **Meeting Duration**: If your average meeting duration is long, you might want to experiment with shorter meeting formats.

### Work-Life Balance

* **Weekend Events**: A high number of weekend events might indicate work-life boundary issues.
* **After-Hours Meetings**: Events during early morning or late evening hours can highlight potential burnout risks.

### Collaboration Patterns

* **Recurring Meetings**: A high percentage of recurring meetings might suggest opportunities to reduce meeting overhead.
* **Top Attendees**: This shows your key collaborators and might identify opportunities for more efficient communication methods.

## Practical Applications

### Personal Productivity

Use the insights to optimize your calendar:
* Block out your most productive hours for focused work
* Schedule meetings during your less productive times
* Identify and reduce unnecessary recurring meetings

### Team Coordination

Share anonymous, aggregated metrics with your team to improve collaboration:
* Find optimal meeting times that work for everyone
* Identify meeting overload and implement no-meeting days
* Set standards for meeting durations based on actual data

### Organizational Planning

For managers and leaders:
* Track meeting patterns across teams to identify collaboration bottlenecks
* Measure the impact of meeting policies by analyzing trends over time
* Identify teams with excessive meeting loads that might need intervention

## Installation and Setup

### Prerequisites

* Python 3.6+
* Google account with Calendar access
* Google Cloud project with Calendar API enabled
* Google Cloud CLI (gcloud)

### Python Setup

1. Clone the repository:
   ```
   git clone <repository-url>
   cd google-calendar-analyzer
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Basic Command

```bash
python gcallist.py
```

Without any parameters, the tool will analyze your primary calendar for the past 3 months.

### All Options

```
Usage: gcallist.py [OPTIONS]

Generate calendar metrics report.

Options:
  --calendars CALENDAR [CALENDAR ...]  List of calendar IDs or names to analyze
  --months MONTHS                      Number of months to analyze (default: 3)
  -h, --help                           Show this help message
```

### Multiple Calendars

To analyze multiple calendars:

```
python gcallist.py --calendars "Work" "Personal"
```

You can specify calendars by their display name or ID.

### Custom Time Range

To change the analysis period:

```
python gcallist.py --months 6
```

This would analyze the past 6 months of calendar data.

## Google Cloud Configuration

To use this tool, you need to set up Google Cloud with the appropriate permissions. This section provides step-by-step instructions for configuring Google Cloud for use with the Google Calendar Analyzer.

### Install Google Cloud CLI

On Windows using Scoop:
```
scoop install gcloud
```

For other platforms, follow the [official Google Cloud SDK installation guide](https://cloud.google.com/sdk/docs/install).

### Authenticate with Google Cloud

Log in to your Google account:
```
gcloud auth login
```

### Configure Project

List available projects:
```
gcloud projects list
```

Set an existing project:
```
gcloud config set project PROJECT_ID
```

Or create a new project:
```
gcloud projects create PROJECT_ID --name="Project Name"
```

### Enable Google Calendar API

Enable the Calendar API for your project:
```
gcloud services enable calendar-json.googleapis.com --project=PROJECT_ID
```

### Configure Quotas

Set up your application default quota project:
```
gcloud auth application-default set-quota-project PROJECT_ID
```

### Set Up Application Default Credentials

Basic login for application default credentials:
```
gcloud auth application-default login
```

For specific scopes (recommended for this tool):
```bash
gcloud auth application-default login --scopes=https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/cloud-platform
```

## Understanding Google Cloud Setup

The Google Cloud setup described above is essential for the tool's operation. Here's why each step matters:

### Project Setup

A Google Cloud project serves as a container for all your Google Cloud resources and APIs. For this tool:
- It defines API quota limits
- It tracks API usage
- It provides a security boundary

### API Enablement

The `calendar-json.googleapis.com` service is the specific API endpoint that allows the tool to:
- List your calendars
- Retrieve event data
- Access calendar metadata

By enabling this service for your project, you're allowing authenticated applications to make Google Calendar API requests under your project's quota.

### Authentication and Authorization

The tool uses OAuth 2.0 for authentication and authorization:
- `gcloud auth login` - Authenticates you as a user to Google Cloud
- `gcloud auth application-default login` - Creates credentials for applications running on your local machine
- The `--scopes` parameter restricts what the application can access:
  - `calendar.readonly` - Allows read-only access to calendar data
  - `cloud-platform` - Provides access to Google Cloud resources

### Quota Configuration

Setting the quota project with `gcloud auth application-default set-quota-project` ensures that:
- API requests are properly attributed to your project
- You can monitor usage in the Google Cloud Console
- You don't unexpectedly hit API limits

Without proper quota configuration, you might encounter "quota exceeded" errors or have API requests rejected.

## Authentication Methods

The Google Calendar Analyzer supports two authentication methods:

### Method 1: Application Default Credentials (Recommended)

This method uses the credentials you've set up with the gcloud CLI and makes the setup process simpler.

After setting up the gcloud CLI as described in the installation section, the script will automatically use your application default credentials.

Benefits:
- Easier setup - no need to manage JSON credential files
- Better integration with Google Cloud
- More secure - no credentials stored in your project directory

### Method 2: OAuth JSON Credentials File

Alternatively, you can use a credentials.json file:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Navigate to "APIs & Services" > "Credentials"
4. Create an OAuth 2.0 Client ID
5. Download the credentials as JSON
6. Rename the file to `credentials.json` and place it in the tool's directory

This method requires modifying the script to use the file-based credentials instead of application default credentials.

## Troubleshooting

### Google Cloud Configuration Issues

#### "Project Not Found" Error
If you see an error like "Project 'PROJECT_ID' not found or permission denied":
```
# Verify you're authenticated with the correct account
gcloud auth list

# Check if the project exists
gcloud projects list

# Create the project if needed
gcloud projects create PROJECT_ID --name="Project Name"
```

#### API Enablement Failure
If enabling the API fails:
```
# Verify you have permissions to enable APIs
gcloud projects get-iam-policy PROJECT_ID

# Try using the Google Cloud Console instead
# Visit: https://console.cloud.google.com/apis/library/calendar-json.googleapis.com
```

#### Authentication Problems
If you encounter authentication issues:
```
# Clear and redo application default credentials
gcloud auth application-default revoke
gcloud auth application-default login --scopes=https://www.googleapis.com/auth/calendar.readonly

# Check active credentials
gcloud auth list
```

#### Quota Errors
If you receive errors about exceeding API quotas:
* Verify your quota project is correctly set
* Try analyzing fewer months of data
* Analyze one calendar at a time
* Wait a while before running again

### Script-Specific Issues

#### "Invalid Grant" Errors
If you see "invalid_grant" errors:
* Your refresh token may have expired
* Regenerate credentials or reauthorize with:
  ```
  gcloud auth application-default login
  ```

#### Calendar Access Issues
If the script can't access certain calendars:
* Verify you have permission to access the calendar
* Check that the calendar is listed in your Google Calendar
* Try specifying the calendar ID directly

## Privacy and Security

The tool runs locally on your machine and accesses your calendar data through Google's API using OAuth. Your calendar data is not sent to any third-party servers. The credentials file stores a refresh token that allows the tool to access your calendar when you run it.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
