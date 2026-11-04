# Student Rent Finder: Melbourne

**Live app:** <paste your Streamlit link here>

![App screenshot](screenshot.png)

## The problem
Students choose a rental on price, then discover the commute. A cheap suburb with a 70-minute trip
can cost more in time than it saves in rent. This app ranks Melbourne suburbs by **true weekly cost**:
your share of the rent plus the value of the time you spend getting to campus by public transport.

## What I found
- **Hidden gems:** <2–3 suburbs that are cheap and under 40 minutes from a campus, and why (for example, a direct train line)>
- **Traps:** <2–3 suburbs that look close on a map but take 50+ minutes by public transport>

## How it works
1. **Rents:** Homes Victoria Rental Report (rental bond data), moving annual median rent for new leases,
   2000 to September 2025, by suburb area and property type. Areas with fewer than 10 new leases are excluded.
2. **Matching:** 145 rental areas linked to 213 ABS suburbs (2021 boundaries), with 14 names fixed by hand.
3. **Commute:** door-to-door public transport and walking times from 163 Melbourne suburbs to 7 campuses,
   Tuesday 8–9am, calculated with r5py from PTV timetables (GTFS) and OpenStreetMap.
4. **Score:** rent per person + (minutes ÷ 60) × trips per week × value of time. Students can change the inputs.

## Limitations
- Medians hide the range: half of new leases cost more than the median.
- Only suburbs named in the rental report are covered.
- Travel times come from timetables, not real-time delays, and start from each suburb's centre.

## Run it yourself
1. `pip install -r requirements.txt` (plus `r5py geopandas` and Java 21 to recalculate travel times)
2. Download the raw data: Homes Victoria Rental Report, PTV GTFS Schedule, ABS Suburbs and Localities 2021, a Melbourne OpenStreetMap extract
3. Run the notebooks in order: `01_load_data`, `03_travel_times`, `04_score`
4. `streamlit run app.py`

## Data sources
- Homes Victoria, Rental Report (CC BY 4.0)
- Department of Transport and Planning, GTFS Schedule (CC BY 4.0)
- Australian Bureau of Statistics, ASGS Edition 3 Suburbs and Localities (CC BY 4.0)
- OpenStreetMap contributors (ODbL)
