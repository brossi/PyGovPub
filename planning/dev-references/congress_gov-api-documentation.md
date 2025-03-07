# Congress.gov API Documentation

## Overview

The Congress.gov API provides programmatic access to accurate and timely legislative information from the Congress.gov website. This API allows developers to access congressional data for integration into their own applications and services.

The API provides access to various types of legislative content including bills, amendments, nominations, treaties, committee reports, committee meetings, and more.

## Authentication

To use the Congress.gov API, you need to obtain an API key. The API key must be included with each request in the request header.

Add your API key to the request header as follows:
```
X-API-Key: YOUR_API_KEY
```

## Base URL

All API requests should be made to:

```
https://api.congress.gov/v3
```

## Endpoint-Specific Documentation

Each endpoint has detailed interactive documentation available through the OpenAPI Specification at [https://api.congress.gov](https://api.congress.gov/). This documentation allows you to explore endpoints, parameters, and response schemas specific to each resource type.

For example:
- Bill API: [https://api.congress.gov/#/bill/bill_list_all](https://api.congress.gov/#/bill/bill_list_all)
- Amendment API: [https://api.congress.gov/#/amendments/Amendment](https://api.congress.gov/#/amendments/Amendment)
- Member API: [https://api.congress.gov/#/member/member_list](https://api.congress.gov/#/member/member_list)

## Common Response Format

All responses from the Congress.gov API follow a standard format:

```json
{
  "pagination": {
    "count": 20,
    "nextPage": "https://api.congress.gov/v3/resource?offset=20&limit=20"
  },
  "request": {
    "contentType": "application/json",
    "format": ""
  },
  "results": [
    // Resource-specific data
  ]
}
```

## Common Query Parameters

Many endpoints support the following parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `offset` | integer | Pagination offset. Default: 0 |
| `limit` | integer | Number of results to return. Default and maximum values may vary by endpoint |
| `format` | string | Response format (xml or json). Default: json |

## Endpoints

### Amendment

#### Coverage

Coverage information for amendment data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates) on Congress.gov.

#### Endpoints

- `GET /amendment` - Returns a list of all amendments
- `GET /amendment/{congress}` - Returns a list of amendments for a specific congress
- `GET /amendment/{congress}/{type}` - Returns a list of amendments for a specific congress and type
- `GET /amendment/{congress}/{type}/{number}` - Returns details for a specific amendment
- `GET /amendment/{congress}/{type}/{number}/actions` - Returns actions for a specific amendment
- `GET /amendment/{congress}/{type}/{number}/amendments` - Returns amendments to a specific amendment
- `GET /amendment/{congress}/{type}/{number}/cosponsors` - Returns cosponsors for a specific amendment

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number (e.g., 117) |
| `type` | string | The type of amendment. Possible values are "HAMDT" (House), "SAMDT" (Senate), and "SUAMDT" (only available for the 97th and 98th Congresses) |
| `number` | integer | The assigned amendment number |

#### Response Elements

Amendment responses include the following elements:

- `number` - The assigned amendment number
- `description` - The amendment's description (only for House amendments)
- `purpose` - The amendment's purpose
- `congress` - The congress during which an amendment was submitted or offered
- `type` - The type of amendment (HAMDT, SAMDT, or SUAMDT)
- `updateDate` - The date of update in Congress.gov
- `latestAction` - Container for the latest action taken on the amendment
  - `actionDate` - The date of the latest action
  - `text` - The text of the latest action
  - `actionTime` - The time of the latest action (for certain House actions)
- `sponsors` - Information about the amendment's sponsor
- `cosponsors` - Information about amendment cosponsors (only for Senate amendments)
- `proposedDate` - The date the amendment was proposed on the floor (only for proposed Senate amendments)
- `submittedDate` - The date the amendment was submitted or offered
- `chamber` - The chamber in which the amendment was submitted or offered
- `amendedBill` - Information about the bill amended by the amendment
- `amendedAmendment` - Information about the amendment amended by the amendment
- `amendedTreaty` - Information about the treaty amended by the amendment
- `actions` - Container for actions on the amendment

### Bill

#### Coverage

Coverage information for bill data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates) on Congress.gov. Projects to add more historical legislative data to Congress.gov are underway.

#### Important Notes

##### Historical Bills (1799-1873)
Records are available for some bills and joint resolutions from 1799 (6th Congress) to 1873 (42nd Congress). While these records have text, titles, and some actions, they do not have sponsors, cosponsors, summaries, amendments, committees, and related bill information. Bills from 1799 (6th Congress) to 1817 (14th Congress) were not numbered and appear as such on Congress.gov. The number that appears in the URL is not an authoritative bill number.

##### Reserved Bills
In recent Congresses, the resolution specifying House internal rules of procedure includes reserving bill numbers for assignment by the Speaker. In the 112th Congress (2011-2012) the practice was extended to reserve additional bill numbers for assignment by the Minority Leader. In the Senate, some of the lowest bill numbers are reserved for leadership.

##### Law Endpoints
For law endpoints, use the law number assigned by NARA when making a request by law number. Law numbers can be found for [Public Laws](https://www.congress.gov/public-laws/118th-congress) and for [Private Laws](https://www.congress.gov/private-laws/118th-congress) on Congress.gov.

#### Endpoints

- `GET /bill` - Returns a list of all bills and resolutions
- `GET /bill/{congress}` - Returns a list of bills and resolutions for a specific congress
- `GET /bill/{congress}/{type}` - Returns a list of bills or resolutions for a specific congress and type
- `GET /bill/{congress}/{type}/{number}` - Returns details for a specific bill or resolution
- `GET /bill/{congress}/{type}/{number}/actions` - Returns actions for a specific bill or resolution
- `GET /bill/{congress}/{type}/{number}/amendments` - Returns amendments for a specific bill or resolution
- `GET /bill/{congress}/{type}/{number}/committees` - Returns committees for a specific bill or resolution
- `GET /bill/{congress}/{type}/{number}/cosponsors` - Returns cosponsors for a specific bill or resolution
- `GET /bill/{congress}/{type}/{number}/relatedbills` - Returns related bills for a specific bill or resolution
- `GET /bill/{congress}/{type}/{number}/subjects` - Returns subjects for a specific bill or resolution
- `GET /bill/{congress}/{type}/{number}/summaries` - Returns summaries for a specific bill or resolution
- `GET /bill/{congress}/{type}/{number}/text` - Returns text versions for a specific bill or resolution
- `GET /bill/{congress}/{type}/{number}/titles` - Returns titles for a specific bill or resolution

#### Law Endpoints

- `GET /bill/law/{congress}` - Returns a list of bills that became law in a specific congress
- `GET /bill/law/{congress}/{lawType}` - Returns a list of bills that became law in a specific congress by law type
- `GET /bill/law/{congress}/{lawType}/{lawNumber}` - Returns details for a specific law

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number (e.g., 117) |
| `type` | string | The type of bill or resolution. Possible values are "HR", "S", "HJRES", "SJRES", "HCONRES", "SCONRES", "HRES", and "SRES" |
| `number` | integer | The assigned bill or resolution number |
| `lawType` | string | The type of law. Possible values are "public" or "private" |
| `lawNumber` | string | The law number assigned by NARA (e.g., "117-108") |

#### Response Elements

Bill responses include the following elements:

- `number` - The assigned bill or resolution number
- `updateDate` - The date of update on Congress.gov (excluding text updates)
- `updateDateIncludingText` - The date of update on Congress.gov (including text updates)
- `originChamber` - The chamber of origin (House or Senate)
- `type` - The type of bill or resolution
- `introducedDate` - The date the bill or resolution was submitted or introduced
- `congress` - The congress during which the bill or resolution was introduced
- `constitutionalAuthorityStatementText` - Text citing the constitutional authority for the bill (House bills only)
- `committees` - Information about committees with activity associated with the bill
- `committeeReports` - Information about committee reports associated with the bill
- `relatedBills` - Information about bills related to the bill
- `actions` - Information about actions taken on the bill
- `sponsors` - Information about the bill's sponsor
- `cosponsors` - Information about bill cosponsors
- `cboCostEstimates` - Information about Congressional Budget Office cost estimates
- `laws` - Information about the law if the bill became law
- `notes` - Supplemental information about the bill
- `policyArea` - The policy area term assigned to the bill
- `subjects` - Legislative subject terms assigned to the bill
- `summaries` - Bill summaries written by CRS
- `title` - The display title for the bill
- `titles` - Information about titles associated with the bill
- `amendments` - Information about amendments to the bill
- `textVersions` - Information about text versions of the bill
- `latestAction` - Information about the latest action taken on the bill

### Bound Congressional Record

#### Coverage

Coverage information for bound Congressional Record data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates).

#### Endpoints

- `GET /bound-congressional-record` - Returns a list of all bound Congressional Record issues
- `GET /bound-congressional-record/{year}` - Returns a list of bound Congressional Record issues for a specific year
- `GET /bound-congressional-record/{year}/{month}` - Returns a list of bound Congressional Record issues for a specific year and month
- `GET /bound-congressional-record/{year}/{month}/{day}` - Returns details for a specific bound Congressional Record issue

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `year` | integer | The year of the bound Congressional Record (e.g., 1990) |
| `month` | integer | The month of the bound Congressional Record (e.g., 05) |
| `day` | integer | The day of the bound Congressional Record (e.g., 21) |

#### Response Elements

Bound Congressional Record responses include the following elements:

- `date` - The bound Congressional Record's date
- `volumeNumber` - The bound Congressional Record's volume number
- `congress` - The Congress associated with the bound Congressional Record issue
- `sessionNumber` - The session number (1 or 2)
- `updateDate` - The date that the bound Congressional Record was updated
- `url` - The URL for the bound Congressional Record
- `dailyDigest` - Container for a bound Congressional Record's Daily Digest
  - `startPage` - The start page for the Daily Digest section
  - `endPage` - The end page for the Daily Digest section
  - `text` - Container for Daily Digest text
- `sections` - Container for a bound Congressional Record's sections
  - `n` - The name of the bound Congressional Record section (e.g., "Senate")
  - `startPage` - The start page for the section
  - `endPage` - The end page for the section

### Committee

#### Coverage

Coverage information for committee data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates).

#### Endpoints

- `GET /committee` - Returns a list of all committees and subcommittees
- `GET /committee/{congress}` - Returns a list of committees and subcommittees for a specific congress
- `GET /committee/{congress}/{chamber}` - Returns a list of committees and subcommittees for a specific congress and chamber
- `GET /committee/{chamber}/{systemCode}` - Returns details for a specific committee or subcommittee
- `GET /committee/{chamber}/{systemCode}/bills` - Returns bills associated with a specific committee
- `GET /committee/{chamber}/{systemCode}/reports` - Returns reports issued by a specific committee
- `GET /committee/{chamber}/{systemCode}/nominations` - Returns nominations associated with a specific committee (Senate only)
- `GET /committee/{chamber}/{systemCode}/house-communication` - Returns House communications for a specific committee
- `GET /committee/{chamber}/{systemCode}/senate-communication` - Returns Senate communications for a specific committee

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number (e.g., 117) |
| `chamber` | string | The chamber. Possible values are "house", "senate", and "joint" |
| `systemCode` | string | Unique ID value for the committee (e.g., "hspw00" for House Transportation and Infrastructure Committee) |

#### Response Elements

Committee responses include the following elements:

- `systemCode` - Unique ID value for the committee or subcommittee
- `parent` - Container for parent committee information (for subcommittees)
  - `url` - A referrer URL to the parent committee
  - `systemCode` - Unique ID value for the parent committee
  - `n` - The name of the parent committee
- `updateDate` - The date of update in Congress.gov
- `isCurrent` - Flag indicating whether the committee is currently active
- `subcommittees` - Container for the committee's subcommittees
- `reports` - Container for committee reports issued by the committee
- `communications` - Container for communications associated with the committee
- `bills` - Container for bills associated with the committee
- `nominations` - Container for nominations associated with the committee (Senate only)
- `history` - Container for the committee's activity/identification history across Congresses
- `type` - The type of committee (e.g., "Standing", "Select", "Joint", etc.)

### Committee Meeting

#### Coverage

Coverage information for committee meeting data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates).

#### Endpoints

- `GET /committee-meeting` - Returns a list of all committee meetings
- `GET /committee-meeting/{congress}` - Returns a list of committee meetings for a specific congress
- `GET /committee-meeting/{congress}/{chamber}` - Returns a list of committee meetings for a specific congress and chamber
- `GET /committee-meeting/{congress}/{chamber}/{eventId}` - Returns details for a specific committee meeting

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number (e.g., 117) |
| `chamber` | string | The chamber. Possible values are "house", "senate", and "nochamber" |
| `eventId` | integer | The event identifier of the committee meeting |

#### Response Elements

Committee Meeting responses include the following elements:

- `eventId` - The event identifier of the committee meeting
- `updateDate` - The date of update in Congress.gov
- `congress` - The congress during which the committee meeting took place
- `type` - The type of meeting (House: "Meeting", "Hearing", "Markup"; Senate: "Meeting")
- `title` - The title of the meeting
- `meetingStatus` - The status of the meeting ("Scheduled", "Canceled", "Postponed", "Rescheduled")
- `date` - The date of the meeting
- `chamber` - The chamber where the committee meeting was held
- `committees` - Information about the committees or subcommittees that held the meeting
  - `systemCode` - Unique ID value for the committee or subcommittee
  - `url` - A referrer URL to the committee or subcommittee
  - `n` - The name of the committee or subcommittee
- `location` - Information about the location of the meeting
  - `room` - The room number where the meeting was held
  - `building` - The building name where the meeting was held
  - `address` - The address for field meetings
- `videos` - Information about videos of the meeting
- `witnesses` - Information about witnesses at the meeting

### Committee Print

#### Coverage

Coverage information for committee print data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates).

#### Endpoints

- `GET /committee-print` - Returns a list of all committee prints
- `GET /committee-print/{congress}` - Returns a list of committee prints for a specific congress
- `GET /committee-print/{congress}/{chamber}` - Returns a list of committee prints for a specific congress and chamber
- `GET /committee-print/{congress}/{chamber}/{jacketNumber}` - Returns details for a specific committee print
- `GET /committee-print/{congress}/{chamber}/{jacketNumber}/text` - Returns text formats for a specific committee print

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number (e.g., 117) |
| `chamber` | string | The chamber. Possible values are "house", "senate", and "nochamber" |
| `jacketNumber` | integer | The jacket identifier of the committee print (usually five digits) |

#### Response Elements

Committee Print responses include the following elements:

- `jacketNumber` - The jacket identifier of the committee print
- `citation` - The committee print's citation
- `congress` - The congress during which the committee print was produced
- `number` - The assigned committee print number
- `title` - The title of the committee print
- `chamber` - The chamber where the committee print was produced
- `committees` - Information about the committees associated with the committee print
  - `url` - A referrer URL to the committee
  - `systemCode` - Unique ID value for the committee
  - `n` - The name of the committee
- `associatedBills` - Information about bills associated with the committee print
  - `congress` - The congress during which the bill was introduced
  - `type` - The type of bill or resolution
  - `number` - The assigned bill or resolution number
  - `url` - A referrer URL to the bill
- `text` - Information about text formats available for the committee print

### Committee Report

#### Coverage

Coverage information for committee report data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates).

#### Endpoints

- `GET /committee-report` - Returns a list of all committee reports
- `GET /committee-report/{congress}` - Returns a list of committee reports for a specific congress
- `GET /committee-report/{congress}/{type}` - Returns a list of committee reports for a specific congress and type
- `GET /committee-report/{congress}/{type}/{number}` - Returns details for a specific committee report
- `GET /committee-report/{congress}/{type}/{number}/{part}` - Returns details for a specific part of a committee report

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number (e.g., 117) |
| `type` | string | The type of report. Possible values are "HRPT", "SRPT", and "ERPT" |
| `number` | integer | The assigned committee report number |
| `part` | integer | The part number of the report |

#### Response Elements

Committee Report responses include the following elements:

- `citation` - The report's citation (e.g., H. Rept. 117-351)
- `congress` - The congress during which the committee report was produced
- `chamber` - The chamber where the committee report was produced (House or Senate)
- `sessionNumber` - The session of congress during which the report was produced (1 or 2)
- `number` - The assigned committee report number
- `part` - The part number of the report
- `type` - The type of report (HRPT, SRPT, or ERPT)
- `updateDate` - The date of update in Congress.gov
- `isConferenceReport` - Flag indicating whether the report is a conference report
- `title` - The title of the committee report
- `issueDate` - The date the report was issued
- `committees` - Information about the committees associated with the report
  - `url` - A referrer URL to the committee
  - `systemCode` - Unique ID value for the committee
  - `n` - The name of the committee

### Congress

#### Coverage

Coverage information for congress data in the API can be found at the [Congresses field values list](https://www.congress.gov/help/field-values/congresses) on Congress.gov. Information on past session dates can be found on Congress.gov at the [Dates of Past Sessions](https://www.congress.gov/past-days-in-session).

#### Endpoints

- `GET /congress` - Returns a list of all congresses
- `GET /congress/{number}` - Returns details for a specific congress

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `number` | integer | The congress number (e.g., 117) |

#### Response Elements

Congress responses include the following elements:

- `n` - The name of the congress (e.g., "116th Congress")
- `startYear` - The start year for the congress
- `endYear` - The end year for the congress
- `updateDate` - The date of update in Congress.gov
- `number` - The congress number
- `url` - A referrer URL to the congress item in the API
- `sessions` - Information about sessions of congress
  - `chamber` - The chamber associated with the session of congress (House of Representatives or Senate)
  - `type` - The type of session ("R" for Regular or "S" for Special)
  - `startDate` - The start date of the session
  - `endDate` - The end date of the session
  - `number` - The assigned session's number

### Daily Congressional Record

#### Coverage

Coverage information for daily Congressional Record data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates).

#### Endpoints

- `GET /daily-congressional-record` - Returns a list of all daily Congressional Record issues
- `GET /daily-congressional-record/{volumeNumber}` - Returns a list of daily Congressional Record issues for a specific volume
- `GET /daily-congressional-record/{volumeNumber}/{issueNumber}` - Returns details for a specific daily Congressional Record issue
- `GET /daily-congressional-record/{volumeNumber}/{issueNumber}/articles` - Returns articles for a specific daily Congressional Record issue

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `volumeNumber` | integer | The volume number of the daily Congressional Record (e.g., 167) |
| `issueNumber` | integer | The issue number of the daily Congressional Record (e.g., 21) |

#### Response Elements

Daily Congressional Record responses include the following elements:

- `issueNumber` - The daily Congressional Record's issue number
- `volumeNumber` - The daily Congressional Record's volume number
- `issueDate` - The date that the daily Congressional Record was issued
- `congress` - The congress associated with the daily Congressional Record issue
- `sessionNumber` - The session number (1 or 2)
- `url` - The URL to the entire issue of the daily Congressional Record
- `updateDate` - The date that the daily Congressional Record was updated
- `fullIssue` - Information about the full issue, sections, and articles
  - `entireIssue` - Information about the entire issue
    - `part` - The part of the daily Congressional Record issue
    - `type` - The type of document (e.g., PDF, "Formatted Text")
    - `url` - The URL for the document
  - `sections` - Information about sections of the daily Congressional Record
    - `n` - The section name
    - `startPage` - The start page of the section
    - `endPage` - The end page of the section
    - `text` - Container for section text items

### Hearing

#### Coverage

Coverage information for hearing data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates). Read more about hearing data at [About Committees and Committee Materials](https://www.congress.gov/help/committee-materials#committee-hearings) on Congress.gov.

#### Endpoints

- `GET /hearing` - Returns a list of all hearings
- `GET /hearing/{congress}` - Returns a list of hearings for a specific congress
- `GET /hearing/{congress}/{chamber}` - Returns a list of hearings for a specific congress and chamber
- `GET /hearing/{congress}/{chamber}/{jacketNumber}` - Returns details for a specific hearing

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number (e.g., 117) |
| `chamber` | string | The chamber. Possible values are "house", "senate", and "nochamber" |
| `jacketNumber` | integer | The jacket identifier of the hearing (usually five digits) |

#### Response Elements

Hearing responses include the following elements:

- `jacketNumber` - The jacket identifier of the hearing (usually five digits)
- `libraryOfCongressIdentifier` - The Library of Congress identifier for a hearing
- `number` - The hearing number (hearings may or may not be numbered by their associated committee)
- `part` - The hearing part number, if printed in parts
- `updateDate` - The date of update in Congress.gov
- `congress` - The congress during which the hearing was held
- `title` - The title of the hearing
- `citation` - The hearing's citation
- `chamber` - The chamber where the hearing was held
- `committees` - Information about the committees that held the hearing
  - `n` - The name of the committee
  - `systemCode` - Unique ID value for the committee
  - `url` - A referrer URL to the committee item in the API
- `dates` - Information about dates when the hearing was held
- `formats` - Information about the hearing transcript text formats
  - `type` - The format type for the hearing transcript text (e.g., "PDF", "Formatted Text")
  - `url` - The URL for the hearing transcript text in Congress.gov
- `associatedMeeting` - Information about the hearing meeting
  - `eventID` - The individual hearing meeting event identifier
  - `URL` - Referrer URL to the committee hearing meeting item in the API

### House Communication

#### Coverage

Coverage information for House communications data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates). Read more about House communications data at [About Communications to the House](https://www.congress.gov/help/house-communications) on Congress.gov.

#### Endpoints

- `GET /house-communication` - Returns a list of all House communications
- `GET /house-communication/{congress}` - Returns a list of House communications for a specific congress
- `GET /house-communication/{congress}/{type}` - Returns a list of House communications for a specific congress and type
- `GET /house-communication/{congress}/{type}/{number}` - Returns details for a specific House communication

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number (e.g., 117) |
| `type` | string | The type of communication. Possible values are "ec" (Executive Communication), "pm" (Presidential Message), "pt" (Petition), and "ml" (Memorial) |
| `number` | integer | The assigned communication number |

#### Response Elements

House Communication responses include the following elements:

- `chamber` - The chamber where the communication was received (always "House")
- `number` - The assigned communication number
- `communicationType` - Information about the type of communication
  - `code` - The code for the type of communication (EC, PM, PT, or ML)
  - `n` - The name of the type of communication
- `congress` - The congress during which the communication was received
- `updateDate` - The date the communication was updated
- `abstract` - The abstract text for the communication
- `congressionalRecordDate` - The date the communication was published in the Congressional Record
- `sessionNumber` - The session number (1 or 2)
- `isRulemaking` - Flag indicating whether the communication is related to rulemaking (Y or N)
- `committees` - Information about committees associated with the communication
  - `n` - The name of the committee
  - `referralDate` - The date the communication was referred to the committee
  - `systemCode` - The assigned code used in Congress.gov for the committee
- `matchingRequirements` - Information about matching requirements associated with the communication
- `reportNature` - The description of the nature of the report
- `submittingAgency` - The agency responsible for submitting the report
- `submittingOfficial` - The official responsible for submitting the report
- `legalAuthority` - The legal authority responsible for the report
- `houseDocument` - Information about house documents associated with the communication

### House Requirement

#### Coverage

Coverage information for House requirements data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates). Read more about House requirements data within [About Communications to the House](https://www.congress.gov/help/house-communications) on Congress.gov.

#### Endpoints

- `GET /house-requirement` - Returns a list of all House requirements
- `GET /house-requirement/{number}` - Returns details for a specific House requirement
- `GET /house-requirement/{number}/matching-communications` - Returns matching communications for a specific House requirement

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `number` | integer | The assigned House requirement number |

#### Response Elements

House Requirement responses include the following elements:

- `number` - The assigned House requirement number
- `updateDate` - The date of update in Congress.gov
- `parentAgency` - The government entity mandated to submit a report
- `frequency` - The set interval for when a report is mandated to be submitted
- `nature` - The brief description of the report
- `legalAuthority` - Citations to the statute associated with the House requirement
- `activeRecord` - Flag to indicate whether the requirement is active ("True" or "False")
- `submittingAgency` - The government agency mandated to submit a report
- `submittingOfficial` - The government official mandated to submit a report
- `matchingCommunications` - Information about matching communications to the requirement
  - `count` - The number of matching communications to the requirement
  - `url` - A referrer URL to the matching communications level of the house requirement API

Matching Communications responses include the following elements:

- `chamber` - The chamber where the communication was received (always "House")
- `number` - The assigned communication number
- `communicationType` - Information about the type of communication
  - `code` - The code for the type of communication (EC, PM, PT, or ML)
  - `n` - The name of the type of communication
- `congress` - The congress during which the communication was received
- `url` - A referrer URL to the communication item in the API

### Member

#### Coverage

Coverage information for member data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates). Read more about member data at [About Congressional Member Profiles](https://www.congress.gov/help/members) on Congress.gov. Vacancies and changes to membership in the House of Representatives can be found at the [current vacancies page](https://clerk.house.gov/Members#Vacancies) on the Office of the Clerk website.

#### Important Notes

- **Filtering members by Congress**: When calling for member data from prior congresses using the `/member/congress/{congress}` filters, use `currentMember=False` in your call to get the most complete data.

- **Filtering members by Congress, state, and district**: If you are looking for ONLY the current member of a particular district, use the `currentMember=True` filter to get the most accurate results, as there may be instances where a member has been redistricted but previously represented the district.

#### Endpoints

- `GET /member` - Returns a list of all members
- `GET /member/{bioguideId}` - Returns details for a specific member
- `GET /member/congress/{congress}` - Returns a list of members for a specific congress
- `GET /member/congress/{congress}/{state}` - Returns a list of members for a specific congress and state
- `GET /member/congress/{congress}/{state}/{district}` - Returns a list of members for a specific congress, state, and district
- `GET /member/{bioguideId}/sponsored-legislation` - Returns legislation sponsored by a specific member
- `GET /member/{bioguideId}/cosponsored-legislation` - Returns legislation cosponsored by a specific member

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `bioguideId` | string | The unique ID value that originates in the Biographical Directory of the United States Congress (e.g., "L000174") |
| `congress` | integer | The congress number (e.g., 117) |
| `state` | string | The two-letter state code (e.g., "VT" for Vermont) |
| `district` | integer | The congressional district number |
| `currentMember` | boolean | Filter to show only current members when set to "true" |

#### Response Elements

Member responses include the following elements:

- `currentMember` - Indicator of whether the member is currently serving ("True" or "False")
- `birthYear` - Member's year of birth
- `deathYear` - Member's year of death
- `updateDate` - The date of update in Congress.gov
- `depiction` - Information about the member's current official portrait
  - `imageUrl` - The member's current portrait on Congress.gov
  - `attribution` - The source of the image
- `terms` - Information about a member's terms of service in chronological order
  - `memberType` - The membership type ("Representative", "Resident Commissioner", "Delegate", or "Senator")
  - `congress` - The Congress during which the member served
  - `chamber` - The chamber in which the member served during that Congress
  - `stateCode` - The two-digit postal code abbreviation for the state represented by the member
  - `stateName` - The name of the state represented by the member
  - `partyName` - The political party of the member
  - `partyCode` - The single letter abbreviation for the political party of the member
  - `startYear` - The year in which the member's service in that Congress began
  - `endYear` - The year in which the member's service in that Congress ended
  - `district` - The Congressional district represented by the member (exclusive to the House)
- `bioguideID` - The unique ID value that originates in the Biographical Directory of the United States Congress
- `party` - The current political party of the member
- `state` - The state represented by the member
- `district` - The Congressional district represented by the member (exclusive to House)
- `officialUrl` - The member's official website
- `honorificName` - The honorific title of the member
- `firstName` - The member's first name
- `middleName` - The member's middle name
- `lastName` - The member's last name
- `suffixName` - The member's suffix
- `nickName` - The member's nickname
- `directOrderName` - The member's name in first-name-first order
- `invertedOrderName` - The member's name in last-name-first order
- `addressInformation` - The member's contact information
  - `officeAddress` - The member's mailing and physical office address in Washington, D.C.
  - `city` - The city of Washington
  - `district` - The two-letter postal abbreviation for the District of Columbia
  - `zipCode` - The postal zip code for the member's office
  - `phoneNumber` - The telephone number for the member's office
- `leadership` - Information about leadership positions held by the member
  - `type` - The title of the leadership position
  - `congress` - The Congress during which the leadership position was held
  - `current` - Indicator whether the leadership position is currently held
- `sponsoredLegislation` - Information about bills and resolutions sponsored by the member
  - `count` - The total number of bills and resolutions sponsored
  - `url` - A referrer URL to the sponsored legislation in the API
- `cosponsoredLegislation` - Information about bills and resolutions cosponsored by the member
  - `count` - The total number of bills and resolutions cosponsored
  - `url` - A referrer URL to the cosponsored legislation in the API

Sponsored and Cosponsored Legislation responses include:

- `introducedDate` - The date the bill or resolution was introduced
- `type` - The type of bill or resolution
- `congress` - The congress during which the bill or resolution was introduced
- `latestTitle` - The display title for the bill or resolution
- `number` - The assigned bill or resolution number
- `policyArea` - The policy area term assigned to the bill or resolution
- `latestAction` - Information about the latest action taken on the bill or resolution
  - `actionDate` - The date of the latest action
  - `text` - The text of the latest action
- `url` - A referrer URL to the bill item in the API

### Nomination

#### Coverage

Coverage information for nominations data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates). Read more about nominations data at [About Nominations by the U.S. President](https://www.congress.gov/help/nominations) on Congress.gov.

#### Important Notes

**Partitioned Nominations**: A presidential nomination (PN) with multiple nominees may be partitioned by the Senate if the nominees follow a different confirmation path. Partitions are identified with a suffix; for example, PN230-1 (114th Congress) and PN230-2 (114th Congress). Searching on a PN number without a partition designation will retrieve all partitions of a partitioned nomination.

#### Endpoints

- `GET /nomination` - Returns a list of all nominations
- `GET /nomination/{congress}` - Returns a list of nominations for a specific congress
- `GET /nomination/{congress}/{number}` - Returns details for a specific nomination
- `GET /nomination/{congress}/{number}/{partNumber}` - Returns details for a specific partitioned nomination
- `GET /nomination/{congress}/{number}/actions` - Returns actions for a specific nomination
- `GET /nomination/{congress}/{number}/committees` - Returns committees for a specific nomination
- `GET /nomination/{congress}/{number}/hearings` - Returns hearings for a specific nomination

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number (e.g., 117) |
| `number` | integer | The assigned nomination number |
| `partNumber` | integer | The part number for partitioned nominations |

#### Response Elements

Nomination responses include the following elements:

- `congress` - The congress during which the nomination was received
- `number` - The assigned nomination number
- `partNumber` - The part number for partitioned nominations
- `citation` - The citation identifying the nomination (e.g., "PN1064")
- `isPrivileged` - Flag indicating whether the nomination is privileged and entitled to expedited procedures
- `isList` - Flag indicating whether the nomination is for the Military, Foreign Service, NOAA, or Public Health
- `receivedDate` - The date the nomination was received from the President
- `description` - The description of the nomination
- `executiveCalendarNumber` - Executive calendar number information for the nomination
- `authorityDate` - The date when the Senate granted authority to receive nominations during recess
- `nominees` - Information about nominee positions
  - `ordinal` - Ordinal used for the display order of positions
  - `organization` - The name of the organization for which the nomination was submitted
  - `positionTitle` - The title of the position
  - `division` - The name of the division within the organization
  - `nomineeCount` - The count of nominees for a position
- `committees` - Information about committees with activity associated with the nomination
- `latestAction` - Information about the latest action taken by the Senate or the President
  - `actionDate` - The date of the latest action
  - `text` - The text of the latest action
- `actions` - Information about actions taken on the nomination
- `hearings` - Information about printed hearings associated with the nomination
- `updateDate` - The date of update in Congress.gov
- `nominationType` - Information about the type of nomination
  - `isCivilian` - Flag indicating whether the nomination is for a civilian position
  - `isMilitary` - Flag indicating whether the nomination is for a military nomination

Nominee responses include:
- `lastName` - Last name of a nominee
- `firstName` - The first name of a nominee
- `middleName` - The middle name of a nominee
- `prefix` - The name prefix for a nominee
- `suffix` - The name suffix for a nominee
- `state` - The two-digit postal code abbreviation for the nominee
- `effectiveDate` - The date when the appointment will become effective
- `predecessorName` - The name of the person who previously held the position
- `corpsCode` - The corps code assigned by the White House to identify Corps

Committee responses include:
- `systemCode` - Unique ID value for the committee
- `n` - The name of the committee
- `chamber` - The chamber where the committee operates (always "Senate")
- `type` - The type or status of the committee
- `activities` - Information about committee activities associated with the nomination

Action responses include:
- `actionDate` - The date of action taken on the nomination
- `text` - The text of the action taken on the nomination
- `type` - A short name representing stages or categories of more detailed actions
- `actionCode` - A Senate-provided code associated with the action

Hearing responses include:
- `chamber` - The chamber where the hearing took place (always "Senate")
- `number` - The number for the printed hearing
- `partNumber` - The part number for the hearing, if printed in parts
- `citation` - The printed hearing citation
- `jacketNumber` - The jacket number, as present on the paper and PDF formats
- `errataNumber` - If errata, the printed hearing's errata number
- `date` - The date when the hearing took place

### Senate Communication

#### Coverage

Coverage information for Senate communications data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates). Read more about Senate communications data at [About Senate Executive and Other Communications](https://www.congress.gov/help/senate-communications) on Congress.gov.

#### Endpoints

- `GET /senate-communication` - Returns a list of all Senate communications
- `GET /senate-communication/{congress}` - Returns a list of Senate communications for a specific congress
- `GET /senate-communication/{congress}/{type}` - Returns a list of Senate communications for a specific congress and type
- `GET /senate-communication/{congress}/{type}/{number}` - Returns details for a specific Senate communication

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number (e.g., 117) |
| `type` | string | The type of communication. Possible values are "ec" (Executive Communication), "pom" (Petition or Memorial), and "pm" (Presidential Message) |
| `number` | integer | The assigned communication number |

#### Response Elements

Senate Communication responses include the following elements:

- `chamber` - The chamber where the communication was received (always "Senate")
- `number` - The assigned communication number
- `communicationType` - Information about the type of communication
  - `code` - The code for the type of communication (EC, POM, or PM)
  - `n` - The name of the type of communication
- `congress` - The congress during which the communication was received
- `updateDate` - The date of update in Congress.gov
- `abstract` - The abstract text for the communication
- `congressionalRecordDate` - The date the communication was published in the Congressional Record
- `committees` - Information about committees associated with the communication
  - `n` - The name of the committee
  - `referralDate` - The date the communication was referred to the committee
  - `url` - A referrer URL to the committee item in the API

### Summaries

#### Coverage

Coverage information for bill summaries data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates). By default, only bill summaries published in the last day are available from this endpoint unless "fromDateTime" and/or "toDateTime" parameters are added to the API request. However, all bill summaries published for bills available on Congress.gov can be found at the bill endpoint.

#### Endpoints

- `GET /summaries` - Returns a list of bill summaries published in the last day
- `GET /summaries/{congress}` - Returns a list of bill summaries for a specific congress published in the last day
- `GET /summaries/{congress}/{type}` - Returns a list of bill summaries for a specific congress and bill type published in the last day

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number (e.g., 117) |
| `type` | string | The type of bill or resolution. Possible values are "hr", "s", "hjres", "sjres", "hconres", "sconres", "hres", and "sres" |
| `fromDateTime` | string | Filter to include bill summaries published on or after the specified date and time (ISO 8601 format) |
| `toDateTime` | string | Filter to include bill summaries published before the specified date and time (ISO 8601 format) |

#### Response Elements

Summaries responses include the following elements:

- `bill` - Information about the bill associated with the summary
  - `congress` - The congress during which the bill or resolution was introduced
  - `type` - The type of bill or resolution
  - `originChamber` - The chamber of origin where the bill or resolution was introduced
  - `originChamberCode` - The code for the chamber of origin
  - `number` - The assigned bill or resolution number
  - `url` - A referrer URL to the bill or resolution item in the API
  - `title` - The display title for the bill or resolution
  - `updateDateIncludingText` - The date of update for the bill, including updates to the text
- `text` - The text of the bill summary (contains HTML codes)
- `actionDate` - The date of the action associated with the bill summary
- `updateDate` - The date of update on Congress.gov
- `currentChamber` - The chamber that took the action associated with the bill summary
- `currentChamberCode` - The code for the chamber that took the action
- `actionDesc` - The description of the action associated with the bill summary
- `versionCode` - The internal code used by CRS to tag its bill summaries according to the action
- `lastSummaryUpdateDate` - The date the bill summary was last updated

#### Bill Summary Version Codes

Bill summary version codes correspond to specific actions and chambers. Some common ones include:

- `00` - Introduced in House/Senate
- `07` - Reported to House
- `25` - Reported to Senate
- `35` - Passed Senate amended
- `36` - Passed House amended
- `47` - Conference report filed in Senate
- `48` - Conference report filed in House
- `49` - Public Law
- `53` - Passed House
- `55` - Passed Senate

### Treaty

#### Coverage

Coverage information for treaty data in the API can be found at [Coverage Dates for Congress.gov Collections](https://www.congress.gov/help/coverage-dates). Read more about treaty data at [About Treaty Documents](https://www.congress.gov/help/treaty-documents) on Congress.gov.

#### Endpoints

- `GET /treaty` - Returns a list of all treaties
- `GET /treaty/{congress}` - Returns a list of treaties for a specific congress
- `GET /treaty/{congress}/{number}` - Returns details for a specific treaty
- `GET /treaty/{congress}/{number}/{suffix}` - Returns details for a specific treaty part
- `GET /treaty/{congress}/{number}/actions` - Returns actions for a specific treaty
- `GET /treaty/{congress}/{number}/committees` - Returns committees for a specific treaty

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `congress` | integer | The congress number during which the treaty was submitted (e.g., 117) |
| `number` | integer | The assigned treaty number |
| `suffix` | string | The treaty part, if the treaty was partitioned (e.g., "A", "B", "C", etc.) |

#### Response Elements

Treaty responses include the following elements:

- `congressReceived` - The congress during which the treaty was submitted
- `congressConsidered` - The congress during which the treaty was ratified or returned to the President
- `number` - The assigned treaty number
- `suffix` - The treaty part, if the treaty was partitioned
- `countriesParties` - The countries associated with a particular treaty
- `oldNumber` - The number assigned to treaties ratified prior to the 97th Congress
- `oldNumberDisplayName` - The original treaty number display string, prior to conversion
- `transmittedDate` - The date the treaty was transmitted to the Senate
- `inForceDate` - The date when the treaty agreement takes effect
- `indexTerms` - The index terms associated with a particular treaty
- `relatedDocs` - Information about executive reports associated with the treaty
- `resolutionText` - The text of the resolution of ratification
- `topic` - The assigned topic of the treaty
- `updateDate` - The date of update on Congress.gov
- `parts` - Information about treaty parts if the treaty was partitioned
- `titles` - Information about titles associated with the treaty
- `actions` - Information about actions taken on the treaty

Action responses include:
- `type` - A short name representing stages or categories of more detailed actions
- `committee` - Information about the committee associated with the action
- `actionCode` - A Senate-provided action code associated with the action
- `actionDate` - The date of action taken on the treaty
- `text` - The text of the action taken on the treaty

Committee responses include:
- `systemCode` - Unique ID value for the committee
- `n` - The name of the committee
- `chamber` - The chamber where the committee operates (always "Senate")
- `type` - The type or status of the committee (always "Standing")
- `activities` - Information about committee activities associated with the treaty
  - `n` - The committee activity (e.g., "Referred to", "Reported by")
  - `date` - The date of the committee activity

## Response Codes

| Code | Description |
|------|-------------|
| 200 | OK - Request was successful |
| 400 | Bad Request - The request could not be understood due to malformed syntax |
| 401 | Unauthorized - Authentication required (API key missing or invalid) |
| 403 | Forbidden - The server understood the request but refuses to authorize it |
| 404 | Not Found - The requested resource could not be found |
| 405 | Method Not Allowed - The method specified in the request is not allowed for the resource |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - The server encountered an unexpected condition |
| 503 | Service Unavailable - The server is currently unavailable |

## Rate Limits

The Congress.gov API implements rate limiting to ensure fair usage for all users. Rate limits are based on your API key and are applied on a per-key basis. If you exceed the rate limit, you will receive a 429 Too Many Requests response.

Best practices for working with rate limits:

1. Implement caching to reduce the number of API calls
2. Use pagination parameters appropriately
3. Include error handling for rate limit errors
4. Consider implementing exponential backoff for retries

## Additional Resources

- [Congress.gov](https://www.congress.gov/) - The official website for federal legislative information
- [OpenAPI Specification](https://api.congress.gov/) - Interactive API documentation
- [Coverage Dates](https://www.congress.gov/help/coverage-dates) - Information about data coverage in the API
- [GitHub Repository](https://github.com/LibraryOfCongress/api.congress.gov) - Official repository for the Congress.gov API documentation

## Versioning

The Congress.gov API uses versioning in its URL structure (v3) to ensure backward compatibility as the API evolves. When breaking changes are introduced, a new version of the API will be released. This allows developers to continue using the version they've built against while transitioning to newer versions.

The current version is v3. Users should include this version in all API calls.

### Changelog

Changes to the API are documented in the [GitHub repository](https://github.com/LibraryOfCongress/api.congress.gov) for the Congress.gov API. Developers are encouraged to watch this repository for updates and changes.

class DocumentAuthenticator:
    async def verify_document(self, package_id: str, digital_signature: str) -> bool:
        """Verify a document's digital signature"""
        # Fetch the public key from trusted source
        public_key = await self.get_govinfo_public_key()

        # Verify the signature
        is_valid = self.verify_signature(package_id, digital_signature, public_key)

        # Store verification result
        await self.store_verification_result(package_id, is_valid)

        return is_valid
