import os
import json
import argparse
import datetime
from dateutil.relativedelta import relativedelta
from collections import Counter, defaultdict
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_calendar_service():
    """Create and return a Google Calendar service using credentials.json file."""
    
    # Load the credentials from the file
    with open('credentials.json', 'r') as cred_file:
        cred_data = json.load(cred_file)
    
    # Create credentials object from the loaded data
    creds = Credentials(
        None,  # No token as we'll use the refresh token
        refresh_token=cred_data['refresh_token'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=cred_data['client_id'],
        client_secret=cred_data['client_secret'],
        quota_project_id=cred_data.get('quota_project_id')
    )
    
    # Build the Google Calendar service
    return build('calendar', 'v3', credentials=creds)

def list_calendars(service):
    """Lists all calendars the user has access to."""
    
    calendars_result = service.calendarList().list().execute()
    calendars = calendars_result.get('items', [])
    
    if not calendars:
        print('No calendars found.')
        return []
    
    print(f"\nAvailable Calendars:")
    for i, calendar in enumerate(calendars, 1):
        summary = calendar.get('summary', 'Unnamed Calendar')
        calendar_id = calendar.get('id', 'No ID')
        access_role = calendar.get('accessRole', 'Unknown')
        
        print(f"{i}. {summary} ({calendar_id}) - {access_role}")
    
    return calendars

def get_events(service, calendar_id, time_min, time_max):
    """Retrieve events from a specific calendar within a time range."""
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min.isoformat() + 'Z',  # 'Z' indicates UTC time
        timeMax=time_max.isoformat() + 'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    return events_result.get('items', [])

def analyze_calendar(service, calendar_id, period_months=3):
    """Analyze calendar events and return metrics."""
    
    # Calculate time range
    now = datetime.datetime.utcnow()
    time_min = now - relativedelta(months=period_months)
    time_max = now + relativedelta(months=1)  # Include upcoming month
    
    # Get events
    events = get_events(service, calendar_id, time_min, time_max)
    
    if not events:
        return {
            "total_events": 0,
            "message": "No events found in the specified time period."
        }
    
    # Initialize metrics
    metrics = {
        "total_events": len(events),
        "past_events": 0,
        "upcoming_events": 0,
        "events_by_day": defaultdict(int),
        "events_by_hour": defaultdict(int),
        "events_by_month": defaultdict(int),
        "event_durations": [],
        "attendees_count": [],
        "recurring_events": 0,
        "all_day_events": 0,
        "top_attendees": Counter(),
        "busy_days": [],
        "longest_event": {"duration": 0, "title": ""},
        "shortest_event": {"duration": float('inf'), "title": ""},
    }
    
    # Current time for comparing past vs upcoming
    current_time = datetime.datetime.utcnow().isoformat() + 'Z'
    
    # Analyze each event
    for event in events:
        # Past or upcoming
        if 'start' in event and 'dateTime' in event['start']:
            if event['start']['dateTime'] < current_time:
                metrics["past_events"] += 1
            else:
                metrics["upcoming_events"] += 1
            
            # Process events with specific times (not all-day)
            start_time = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
            
            # Day of week analysis
            day_of_week = start_time.strftime('%A')
            metrics["events_by_day"][day_of_week] += 1
            
            # Hour analysis
            hour = start_time.hour
            metrics["events_by_hour"][hour] += 1
            
            # Month analysis
            month = start_time.strftime('%B')
            metrics["events_by_month"][month] += 1
            
            # Duration analysis if end time exists
            if 'end' in event and 'dateTime' in event['end']:
                end_time = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                duration_minutes = (end_time - start_time).total_seconds() / 60
                metrics["event_durations"].append(duration_minutes)
                
                # Track longest and shortest events
                if duration_minutes > metrics["longest_event"]["duration"]:
                    metrics["longest_event"] = {
                        "duration": duration_minutes,
                        "title": event.get('summary', 'Untitled Event')
                    }
                if duration_minutes < metrics["shortest_event"]["duration"]:
                    metrics["shortest_event"] = {
                        "duration": duration_minutes,
                        "title": event.get('summary', 'Untitled Event')
                    }
        
        # All-day events
        elif 'start' in event and 'date' in event['start']:
            metrics["all_day_events"] += 1
        
        # Recurring events
        if 'recurringEventId' in event:
            metrics["recurring_events"] += 1
        
        # Attendees analysis
        if 'attendees' in event:
            attendees = event.get('attendees', [])
            metrics["attendees_count"].append(len(attendees))
            
            for attendee in attendees:
                if 'email' in attendee:
                    metrics["top_attendees"][attendee['email']] += 1
    
    # Calculate average duration
    if metrics["event_durations"]:
        metrics["avg_duration"] = sum(metrics["event_durations"]) / len(metrics["event_durations"])
    else:
        metrics["avg_duration"] = 0
    
    # Calculate average attendees
    if metrics["attendees_count"]:
        metrics["avg_attendees"] = sum(metrics["attendees_count"]) / len(metrics["attendees_count"])
    else:
        metrics["avg_attendees"] = 0
    
    # Find busiest days
    if metrics["events_by_day"]:
        max_events = max(metrics["events_by_day"].values())
        metrics["busy_days"] = [day for day, count in metrics["events_by_day"].items() if count == max_events]
    
    # Get top 5 attendees
    metrics["top_attendees"] = dict(metrics["top_attendees"].most_common(5))
    
    return metrics

def print_report(calendar_name, metrics):
    """Print a formatted report for calendar metrics."""
    print("\n" + "=" * 60)
    print(f" CALENDAR REPORT: {calendar_name}")
    print("=" * 60)
    
    print(f"\nTOTAL EVENTS: {metrics['total_events']}")
    print(f"- Past events: {metrics['past_events']}")
    print(f"- Upcoming events: {metrics['upcoming_events']}")
    print(f"- All-day events: {metrics['all_day_events']}")
    print(f"- Recurring events: {metrics['recurring_events']}")
    
    if metrics['total_events'] > 0:
        # Time patterns
        print("\nTIME PATTERNS:")
        
        # Busiest days
        if metrics['events_by_day']:
            sorted_days = sorted(metrics['events_by_day'].items(), 
                                key=lambda x: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(x[0]))
            print("  Events by day of week:")
            for day, count in sorted_days:
                print(f"  - {day}: {count}")
            print(f"  - Busiest day(s): {', '.join(metrics['busy_days'])}")
        
        # Hours distribution
        if metrics['events_by_hour']:
            print("\n  Events by hour:")
            sorted_hours = sorted(metrics['events_by_hour'].items())
            for hour, count in sorted_hours:
                am_pm = "AM" if hour < 12 else "PM"
                display_hour = hour if hour <= 12 else hour - 12
                if display_hour == 0:
                    display_hour = 12
                print(f"  - {display_hour} {am_pm}: {count}")
        
        # Duration stats
        if metrics["event_durations"]:
            print("\nDURATION STATS:")
            print(f"  - Average duration: {metrics['avg_duration']:.1f} minutes")
            print(f"  - Longest event: {metrics['longest_event']['title']} ({metrics['longest_event']['duration']:.1f} minutes)")
            if metrics['shortest_event']['duration'] != float('inf'):
                print(f"  - Shortest event: {metrics['shortest_event']['title']} ({metrics['shortest_event']['duration']:.1f} minutes)")
        
        # Attendee stats
        if metrics["top_attendees"]:
            print("\nTOP ATTENDEES:")
            for email, count in metrics["top_attendees"].items():
                print(f"  - {email}: {count} events")
            print(f"  - Average attendees per event: {metrics['avg_attendees']:.1f}")
    else:
        print("\n" + metrics["message"])
    
    print("\n" + "-" * 60)

def main():
    parser = argparse.ArgumentParser(description='Generate calendar metrics report.')
    parser.add_argument('--calendars', nargs='+', help='List of calendar IDs or names to analyze')
    parser.add_argument('--months', type=int, default=3, help='Number of months to analyze (default: 3)')
    args = parser.parse_args()
    
    # Get calendar service
    service = get_calendar_service()
    
    # List available calendars
    available_calendars = list_calendars(service)
    
    # Determine which calendars to analyze
    calendars_to_analyze = []
    
    if args.calendars:
        # Match by ID or name
        for cal_input in args.calendars:
            found = False
            for calendar in available_calendars:
                if (calendar.get('id') == cal_input or 
                    calendar.get('summary', '').lower() == cal_input.lower()):
                    calendars_to_analyze.append(calendar)
                    found = True
                    break
            if not found:
                print(f"Warning: Calendar '{cal_input}' not found")
    else:
        # If no calendars specified, use primary calendar
        for calendar in available_calendars:
            if calendar.get('primary', False):
                print(f"No calendars specified. Using primary calendar: {calendar.get('summary')}")
                calendars_to_analyze.append(calendar)
                break
        
        if not calendars_to_analyze:
            print("No calendars specified and no primary calendar found.")
            print("Please specify calendars using --calendars option.")
            return
    
    # Generate reports for each calendar
    for calendar in calendars_to_analyze:
        calendar_id = calendar.get('id')
        calendar_name = calendar.get('summary', 'Unknown Calendar')
        
        print(f"\nAnalyzing calendar: {calendar_name}...")
        try:
            metrics = analyze_calendar(service, calendar_id, args.months)
            print_report(calendar_name, metrics)
        except Exception as e:
            print(f"Error analyzing calendar '{calendar_name}': {e}")

if __name__ == '__main__':
    main()