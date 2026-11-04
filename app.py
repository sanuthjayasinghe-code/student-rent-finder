
import json
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

HERE = Path(__file__).parent
PROC = HERE / "processed"

st.set_page_config(page_title="Student Rent Finder", page_icon="🏠", layout="wide")


@st.cache_data
def load():
    scores = pd.read_csv(PROC / "suburb_scores.csv", dtype={"SAL_CODE21": str})
    shapes = json.loads((PROC / "suburb_shapes.geojson").read_text())
    campuses = pd.read_csv(PROC / "campuses.csv")
    return scores, shapes, campuses


scores, shapes, campuses = load()

st.title("Student Rent Finder: Melbourne")
st.write(
    "Find suburbs you can afford **and** get to quickly by public transport. "
    "Suburbs are ranked by **true weekly cost**: your share of the rent plus the value of your time spent commuting."
)

with st.sidebar:
    st.header("Your situation")
    campus = st.selectbox("Campus", sorted(scores.campus.unique()))
    option = st.radio("Housing", sorted(scores.option.unique(), key=lambda o: ("Own" not in o, o)))
    budget = st.slider("Your rent budget ($ per week)", 100, 700, 300, step=10)
    max_min = st.slider("Longest commute you'd accept (minutes)", 10, 120, 45, step=5)
    st.header("How the cost is worked out")
    days = st.slider("Days on campus per week", 1, 5, 4)
    vot = st.slider("Value of your time ($ per hour)", 0, 40, 15,
                    help="What an hour of your time is worth to you. Set to 0 to rank by rent only.")

hits = scores[(scores.campus == campus) & (scores.option == option)
              & (scores.rent_pp <= budget) & (scores.travel_time <= max_min)].copy()
hits["commute_cost"] = (hits.travel_time / 60 * days * 2 * vot).round(0)
hits["weekly_cost"] = hits.rent_pp + hits.commute_cost
hits = hits.sort_values("weekly_cost").reset_index(drop=True)


c1, c2, c3 = st.columns(3)
c1.metric("Matching suburbs", len(hits))
if len(hits):
    best = hits.iloc[0]
    c2.metric("Best value", best.suburb, f"${best.weekly_cost:.0f} true weekly cost", delta_color="off")
    c3.metric("Cheapest rent", f"${hits.rent_pp.min():.0f} / week")

if hits.empty:
    st.info("No suburbs match. Try a higher budget, a longer commute, or a share house.")
    st.stop()

# ---- map ---------------------------------------------------------------------
cost = dict(zip(hits.SAL_CODE21, hits.weekly_cost))
lo, hi = hits.weekly_cost.min(), hits.weekly_cost.max()
PALETTE = ["#1a9850", "#91cf60", "#d9ef8b", "#fee08b", "#fc8d59", "#d73027"]


def colour(v):
    if v is None:
        return None
    i = 0 if hi == lo else int((v - lo) / (hi - lo) * (len(PALETTE) - 1))
    return PALETTE[i]


info = hits.set_index("SAL_CODE21")
features = []
for f in shapes["features"]:
    code = f["properties"]["SAL_CODE21"]
    if code in cost:
        row = info.loc[code]
        f = {**f, "properties": {**f["properties"],
             "rent": f"${row.rent_pp:.0f}", "commute": f"{row.travel_time:.0f} min",
             "cost": f"${row.weekly_cost:.0f}", "rank": int(hits.index[hits.SAL_CODE21 == code][0]) + 1}}
        features.append(f)

c = campuses[campuses.campus == campus].iloc[0]
m = folium.Map(location=[c.lat, c.lon], zoom_start=11, tiles="CartoDB positron")
folium.GeoJson(
    {"type": "FeatureCollection", "features": features},
    style_function=lambda f: {"fillColor": colour(cost.get(f["properties"]["SAL_CODE21"])),
                              "color": "#444", "weight": 0.6, "fillOpacity": 0.7},
    tooltip=folium.GeoJsonTooltip(["rank", "suburb", "rent", "commute", "cost"],
                                  aliases=["Rank", "Suburb", "Your rent", "Commute", "True weekly cost"]),
).add_to(m)
folium.Marker([c.lat, c.lon], tooltip=campus,
              icon=folium.Icon(color="blue", icon="graduation-cap", prefix="fa")).add_to(m)

left, right = st.columns([3, 2])
with left:
    st.subheader("Map")
    st.caption("Green = best value, red = least value among your matches. Hover a suburb for details.")
    st_folium(m, height=560, use_container_width=True, returned_objects=[])
with right:
    st.subheader("Ranked suburbs")
    table = hits[["suburb", "rent_pp", "travel_time", "weekly_cost"]].rename(columns={
        "suburb": "Suburb", "rent_pp": "Your rent ($/wk)",
        "travel_time": "Commute (min)", "weekly_cost": "True weekly cost ($)"})
    table.index = table.index + 1
    st.dataframe(table.round(0), height=560, use_container_width=True)
    st.download_button("Download this list (CSV)", table.to_csv().encode(), f"suburbs_{campus}.csv", "text/csv")


with st.expander("About the data and its limits"):
    st.markdown(
        """
- **Rents:** Homes Victoria Rental Report, moving annual median of new leases to September 2025, from rental bond data.
  Half of new leases cost more than the median. Areas with fewer than 10 new leases are left out.
- **Shares:** a room's rent is the 2-bedroom flat median ÷ 2, or the 3-bedroom house median ÷ 3.
- **Commute:** door-to-door public transport and walking, Tuesday 17 November 2026, 8–9am departures,
  from each suburb's centre, using PTV timetables and OpenStreetMap (calculated with r5py). Real trips vary with delays.
- **Coverage:** only suburbs named in the rental report appear. Suburb boundaries: ABS 2021.
"""
    )
