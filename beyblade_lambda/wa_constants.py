import re

## EPI DATA CONSTANTS ##
EPI_DATA_URL = "https://doh.wa.gov/sites/default/files/legacy/Documents/1600/coronavirus/data-tables//EpiCurve_Count_Cases_Hospitalizations_Deaths.xlsx"
EPI_DEATHS_WORKSHEET_NAME = "Deaths"
EPI_COLUMNS = [
    "Earliest Specimen Collection Date",
    "County",
    "Deaths",
    "Deaths (7-Day Average)",
]
EPI_COLUMNS_NAME_MAP = {
    "Earliest Specimen Collection Date": "date",
    "County": "county",
    "Deaths": "deaths",
    "Deaths (7-Day Average)": "rolling_average",
}
EPI_COUNTY_OF_INTEREST = "Statewide"
EPI_DEATHS_FNAME_TMPL = "epi_deaths_data.{md5}.json"

## BREAKTHROUGH DATA CONSTANTS ##
BREAKTHROUGH_DATA_URL = "https://doh.wa.gov/sites/default/files/2022-02/420-339-VaccineBreakthroughReport.pdf"
BREAKTHROUGH_REPORT_FNAME_TMPL = "{date}-420-339-VaccineBreakthroughReport.pdf"
BREAKTHROUGH_REPORT_DATE_PATTERN = re.compile(
    r".*Washington State Department of Health\s?\s?([\w]+ [\d]{1,2}, [\d]{4}).*"
)
BREAKTHROUGH_DATE_PATTERN = re.compile(
    r".*At a Glance \(\s?data from ([\w]+ [\d]{1,2}, [\d]{4})\s?-?\s?([\w]+ [\d]{1,2}, [\d]{4})\s?\).*"
)
BREAKTHROUGH_CASE_COUNT_PATTERN = re.compile(
    r".*\s([\d,]+)\s+SARS-CoV-2\s?vaccine\s?breakthrough\s?cases\s?have\s?been\s?identified.*"
)
BREAKTHROUGH_HOSPITALIZED_PCT_PATTERN = re.compile(
    r".*\s([\d]{1,2})% were hospitalized.*"
)
BREAKTHROUGH_DEATH_COUNT_PATTERN = re.compile(
    r".*\s([\d]+) people died of COVID-related illness.*"
)
BREAKTHROUGH_DEATH_PCT_PATTERN = re.compile(
    r".*\s([\d\.]{1,3})% died of COVID-related illness.*"
)

