# heli-bizz - FAA Helicopter Registry Tracker

## Project Overview

A data intelligence tool that tracks every US helicopter-owning entity (companies, individuals, agencies) from the FAA aircraft registry. Identifies government owners with specific focus on **state and local government** operators to facilitate B2B sales of pilot helmets and equipment.

## Business Purpose

- **Market Target**: State and local government helicopter operators
- **Goal**: Sell pilot helmets and protective equipment to operators
- **Prioritization**: By fleet size (larger fleets = higher priority)
- **Data Source**: FAA releasable aircraft registry database

## Features

- **Complete Registry**: All US helicopter-owning entities
- **Entity Classification**: Separate commercial, private, and government owners
- **Government Focus**: Flag state and local government operators
- **Fleet Size Tracking**: Identify operators with multiple aircraft
- **Contact Intelligence**: Business information for operators
- **Data Freshness**: Pulls latest FAA database on each run
- **Filtering & Search**: Find specific operators and locations

## Data Sources

- **FAA Aircraft Registry**: Official releasable database
- **Update Frequency**: Regular pulls for latest data
- **Scope**: United States only
- **Aircraft Type**: Rotorcraft (helicopters) only

## Architecture

- **Data Pipeline**: Fetch → Filter → Classify → Store
- **Processing**: Extract rotorcraft entries from FAA database
- **Classification**: Categorize owners (commercial, private, government)
- **Aggregation**: Group aircraft by owner for fleet analysis
- **Output**: Sortable database for sales prospecting

## Tech Stack

- **Data Processing**: Python (Pandas, NumPy)
- **Database**: SQLite or similar for storage
- **APIs**: FAA data APIs or public databases
- **Automation**: Scheduled data refresh jobs
- **Frontend**: Simple web UI for browsing (optional)

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure FAA data source access
4. Run data pipeline: `python fetch_and_process.py`
5. Query results via database

## Key Data Points Per Operator

- **Owner Name & Type**: Individual, company, or agency
- **Government Level**: State/local, federal, military
- **Aircraft Count**: Number of helicopters owned
- **Registration Numbers**: N-numbers for each aircraft
- **Aircraft Models**: Type and size (useful for equipment sales)
- **Location**: Primary operation base
- **Contact Info**: Business address and phone (if available)

## Database Schema

```sql
-- Operators (owners)
CREATE TABLE operators (
  id INTEGER PRIMARY KEY,
  name TEXT,
  owner_type TEXT (individual, commercial, state, local, federal),
  location TEXT,
  aircraft_count INTEGER,
  phone TEXT,
  address TEXT
);

-- Aircraft
CREATE TABLE aircraft (
  id INTEGER PRIMARY KEY,
  registration_number TEXT,
  operator_id INTEGER REFERENCES operators(id),
  model TEXT,
  manufacturer TEXT,
  year_manufactured INTEGER
);
```

## Usage

### Finding Target Customers

1. Filter by owner_type = 'state' or 'local'
2. Sort by aircraft_count (largest fleets first)
3. Extract contact information
4. Prepare outreach materials for helmet/equipment sales

### Fleet Analysis

- Average fleet size by region
- Concentration of government operators
- Growth trends in helicopter operations
- Equipment needs estimation

## Sales Applications

- **Prospecting Lists**: State/local government operators
- **Fleet Sales**: Target operators with multiple helicopters
- **Regional Analysis**: Identify high-concentration areas
- **Equipment Matching**: Match pilot protective equipment to aircraft types

## Code Style

- Clean, modular Python scripts
- Clear variable naming
- Well-commented data processing
- Error handling for API calls

## Known Limitations

- Limited to FAA releasable data (some info not public)
- Contact information may be outdated
- No real-time updates (batch refresh)
- Government aircraft may have restrictions on contact info
- Private operators may be less likely to have public contact data

## Data Privacy & Usage

- Uses only publicly available FAA data
- No scraping of non-public information
- Respects FAA terms of service
- Suitable for legitimate B2B sales prospecting
- Compliant with public records usage

## Future Enhancements

- Real-time FAA data stream integration
- Machine learning for operator classification
- Contact enrichment (phone, email lookup)
- Regional heat mapping
- Market size estimation
- Helmet sizing estimation by aircraft type
- Automated outreach workflow
- CRM integration
- Sales pipeline tracking

## Competition & Market

- **Market**: Pilot protective equipment and helmet sales
- **Differentiation**: Government operator focus
- **Scale**: All US helicopter operators covered
- **Automation**: Continuous data refresh vs. manual lists

## Deployment Status

- **GitHub**: [yerry262/heli-bizz](https://github.com/yerry262/heli-bizz)
- **Type**: Data intelligence tool (CLI/batch)
- **Frequency**: As-needed refresh runs

## Contact & More Info

- For sales questions: Contact operators directly via extracted data
- For data questions: See FAA FOIA procedures

## Last Updated

2026-07-05
