# Technology Value Review Toolkit

This repository contains a collection of analysis tools that support the Technology Value Review Framework. These tools help organizations gain visibility into their technical delivery, infrastructure, and team collaboration patterns to drive better business outcomes and ROI from technology investments.

## Technology Value Review Framework

Our framework helps answer critical questions about technology value:
- **Prove the Value**: Is your tech spend driving value, or quietly draining your resources?
- **What would clarity on your tech ROI mean for your next strategic decision?**

We build **timely, reproducible dashboards** that give leaders consistent insights into where their tech spend is going—along with clear levers to improve technical delivery through a three-step process:

1. **Initial Discovery** - Fast, clear, and actionable assessment of technical delivery, infrastructure, and team processes
2. **Visualise Value** - Connect engineering metrics to business outcomes through real-time tracking
3. **Continuous Improvement** - Ongoing support and advanced reporting to keep technology optimized

## Repository Structure

```
|   .gitignore
|   LICENSE
|   README.md
|
+---code-as-crimescene
|   \---hotspots
|
\---meetings-calendar
```

This repository is organized into two main components:

- **code-as-crimescene**: Tools for analyzing code quality, technical debt, and development patterns
- **meetings-calendar**: Tools for analyzing team collaboration, meeting efficiency, and work patterns

## Code Quality Metrics (Code as Crime Scene)

This section contains tools based on Adam Tornhill's "Code as a Crime Scene" methodology, which applies forensic analysis techniques to identify high-risk areas in your codebase. These data-driven approaches provide objective measurements rather than relying on subjective opinions.

### Hotspots Analysis

Located in: `code-as-crimescene/hotspots/`

The Hotspot Detector analyzes Git repositories to identify "hotspots" - files with a dangerous combination of complexity and change frequency. These files typically account for a disproportionate number of bugs and maintenance issues.

**Key Business Value:**
- Identify where technical debt is accumulating fastest
- Prioritize refactoring efforts based on data rather than opinions
- Reduce maintenance costs by addressing the most problematic 20% of code
- Improve stability and reduce unplanned work

**Key Metrics:**
- **Lines of Code**: Measures complexity and size
- **Number of Revisions**: Indicates instability and churn
- **Number of Authors**: Reflects knowledge distribution
- **Hotspot Score**: LOC × Revisions × Authors

**Usage:**
```bash
python hotspot_detector.py analyze --repo-url=<repository-url>
```

See the [hotspot_detector.md](code-as-crimescene/hotspots/hotspot_detector.md) documentation for complete details.

### Planned Code Quality Tools

Additional metrics tools being developed:

- **Change Coupling Detector**: Identifies files that change together frequently, exposing hidden dependencies and architectural issues
- **Knowledge Distribution Maps**: Visualizes how code knowledge is distributed across teams to identify knowledge silos and bus factor risks
- **Temporal Coupling Analysis**: Reveals implicit dependencies that aren't visible in the code structure
- **Code Churn vs. Impact Analysis**: Measures productive vs. wasteful code changes
- **Technical Debt Quantification**: Translates code quality issues into financial terms

## Team Collaboration Metrics

Located in: `meetings-calendar/`

The Google Calendar Analyzer provides insights into collaboration patterns, meeting efficiency, and work-life balance by analyzing calendar data.

**Key Business Value:**
- Quantify meeting ROI and overhead costs
- Identify collaboration bottlenecks
- Protect focused work time
- Improve work-life balance and reduce burnout risk
- Optimize synchronous vs. asynchronous communication

**Key Metrics:**
- **Meeting Volume and Distribution**: Analysis by day of week, hour of day, and month
- **Meeting Duration**: Statistics on time spent in meetings
- **Collaboration Patterns**: Who works with whom and how frequently
- **Focus Time Analysis**: Identification of uninterrupted work blocks
- **Work-Life Boundary Metrics**: After-hours and weekend meeting frequency

**Usage:**
```bash
python gcallist.py --calendars "Work" "Personal" --months 6
```

See the [gcallist.md](meetings-calendar/gcallist.md) documentation for complete details on setup and usage.

### Planned Collaboration Metrics

Future collaboration analytics being developed:

- **Meeting Cost Calculator**: Financial impact of meetings based on attendee roles
- **Decision Velocity Tracker**: Time from discussion to implementation
- **Context Switching Analysis**: Impact of fragmented schedules on productivity
- **Team Availability Optimizer**: Finding optimal meeting times that preserve focus blocks
- **Meeting Effectiveness Scoring**: Correlation between meeting patterns and delivery outcomes

## Connecting Metrics to Business Outcomes

These tools are designed to support the Technology Value Review Framework by providing objective data on:

1. **Technical Quality** - Codebase health, maintainability, and risk assessment
2. **Team Effectiveness** - Collaboration patterns, communication efficiency, and focus time
3. **Delivery Performance** - How technical and team factors affect delivery speed and quality

When combined with business metrics in our dashboards, these insights create a complete picture of technology ROI, enabling:

- Evidence-based technology investment decisions
- Early detection of delivery risks
- Clear justification of improvement initiatives
- Objective measurement of technology value

## Getting Started

1. Clone this repository
2. Install the required dependencies for the tool you want to use
   - For hotspot detection: `pip install docopt tabulate`
   - For calendar analysis: `pip install -r meetings-calendar/requirements.txt`
3. Follow the specific setup instructions in each tool's documentation

## Contributing

Contributions are welcome! If you'd like to add more tools or enhance the existing ones:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
