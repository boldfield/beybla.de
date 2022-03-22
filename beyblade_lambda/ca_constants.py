## EPI DATA CONSTANTS ##
EPI_DATA_URL = "https://data.chhs.ca.gov/dataset/f333528b-4d38-4814-bebb-12db1f10f535/resource/046cdd2b-31e5-4d34-9ed3-b48cdbc4be7a/download/covid19cases_test.csv"
EPI_AREA_OF_INTEREST = "California"

EPI_COLUMNS = [
    "date",
    "area",
    "reported_deaths",
]

## BREAKTHROUGH DATA CONSTANTS ##

BREAKTHROUGH_DATA_URL = "https://data.chhs.ca.gov/dataset/e39edc8e-9db1-40a7-9e87-89169401c3f5/resource/c5978614-6a23-450b-b637-171252052214/download/covid19postvaxstatewidestats.csv"
BREAKTHROUGH_AREA_OF_INTEREST = "California"

BREAKTHROUGH_COLUMNS = [
    "date",
    "area",
    "vaccinated_deaths",
    "boosted_deaths",
]
