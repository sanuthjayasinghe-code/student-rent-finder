r"""Student Rent Finder website (full version, 5 tabs).

Start it from 05_website.ipynb, or in Command Prompt:  .venv\Scripts\streamlit run website.py
"""
import json
from pathlib import Path

import altair as alt
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
    history = pd.read_csv(PROC / "rents_long.csv", parse_dates=["quarter_date"])
    return scores, shapes, campuses, history


scores, shapes, campuses, history = load()

st.title("Student Rent Finder: Melbourne")
st.write(
    "Find suburbs you can afford **and** get to quickly by public transport. "
    "Suburbs are ranked by **true weekly cost**: your share of the rent plus the value of your time spent commuting."
)

# ---- filters (shared by every tab) --------------------------------------------
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

# every suburb for this campus and option, with the cost recalculated from the sliders
pool = scores[(scores.campus == campus) & (scores.option == option)].copy()
pool["commute_cost"] = (pool.travel_time / 60 * days * 2 * vot).round(0)
pool["weekly_cost"] = pool.rent_pp + pool.commute_cost

hits = pool[(pool.rent_pp <= budget) & (pool.travel_time <= max_min)]
hits = hits.sort_values("weekly_cost").reset_index(drop=True)

tab_find, tab_trends, tab_plot, tab_gems, tab_about = st.tabs(
    ["Find a suburb", "Rent trends", "Rent vs commute", "Hidden gems and traps", "About the data"])

# ---- tab 1: find a suburb -------------------------------------------------------
with tab_find:
    c1, c2, c3 = st.columns(3)
    c1.metric("Matching suburbs", len(hits))
    if hits.empty:
        st.info("No suburbs match. Try a higher budget, a longer commute, or a share house.")
    else:
        best = hits.iloc[0]
        c2.metric("Best value", best.suburb, f"${best.weekly_cost:.0f} true weekly cost", delta_color="off")
        c3.metric("Cheapest rent", f"${hits.rent_pp.min():.0f} / week")

        cost = dict(zip(hits.SAL_CODE21, hits.weekly_cost))
        rank = {code: i + 1 for i, code in enumerate(hits.SAL_CODE21)}
        lo, hi = hits.weekly_cost.min(), hits.weekly_cost.max()
        palette = ["#1a9850", "#91cf60", "#d9ef8b", "#fee08b", "#fc8d59", "#d73027"]

        def colour(v):
            i = 0 if hi == lo else int((v - lo) / (hi - lo) * (len(palette) - 1))
            return palette[i]

        info = hits.set_index("SAL_CODE21")
        features = []
        for f in shapes["features"]:
            code = f["properties"]["SAL_CODE21"]
            if code in cost:
                row = info.loc[code]
                features.append({**f, "properties": {**f["properties"],
                    "rank": rank[code], "rent": f"${row.rent_pp:.0f}",
                    "commute": f"{row.travel_time:.0f} min", "cost": f"${row.weekly_cost:.0f}"}})

        c = campuses[campuses.campus == campus].iloc[0]
        m = folium.Map(location=[c.lat, c.lon], zoom_start=11, tiles="OpenStreetMap")
        folium.GeoJson(
            {"type": "FeatureCollection", "features": features},
            style_function=lambda f: {"fillColor": colour(cost[f["properties"]["SAL_CODE21"]]),
                                      "color": "#444", "weight": 0.6, "fillOpacity": 0.7},
            tooltip=folium.GeoJsonTooltip(["rank", "suburb", "rent", "commute", "cost"],
                                          aliases=["Rank", "Suburb", "Your rent", "Commute", "True weekly cost"]),
        ).add_to(m)
        folium.Marker([c.lat, c.lon], tooltip=campus,
                      icon=folium.Icon(color="blue", icon="graduation-cap", prefix="fa")).add_to(m)

        left, right = st.columns([3, 2])
        with left:
            st.caption("Green = best value, red = least value among your matches. Hover a suburb for details.")
            st_folium(m, height=560, use_container_width=True, returned_objects=[])
        with right:
            table = hits[["suburb", "rent_pp", "travel_time", "weekly_cost"]].rename(columns={
                "suburb": "Suburb", "rent_pp": "Your rent ($/wk)",
                "travel_time": "Commute (min)", "weekly_cost": "True weekly cost ($)"})
            table.index = table.index + 1
            st.dataframe(table.round(0), height=520, use_container_width=True)
            st.download_button("Download this list (CSV)", table.to_csv().encode(),
                               f"suburbs_{campus}.csv", "text/csv")

# ---- tab 2: rent trends ----------------------------------------------------------
with tab_trends:
    st.subheader("How rents have changed since 2000")
    ptype = st.selectbox("Property type", ["1 bedroom flat", "2 bedroom flat", "3 bedroom house", "All properties"])
    areas = sorted(history.suburb_group.unique())
    near = (pool.sort_values("travel_time").drop_duplicates("suburb_group").suburb_group.head(5).tolist())
    picked = st.multiselect("Areas to compare (default: the 5 closest to your campus)", areas,
                            default=[a for a in near if a in areas])
    h = history[(history.property_type == ptype) & history.suburb_group.isin(picked)]
    if h.empty:
        st.info("Pick at least one area.")
    else:
        line = alt.Chart(h).mark_line().encode(
            x=alt.X("quarter_date:T", title="Year"),
            y=alt.Y("median:Q", title="Median weekly rent ($)"),
            color=alt.Color("suburb_group:N", title="Area"),
            tooltip=[alt.Tooltip("suburb_group:N", title="Area"), alt.Tooltip("quarter:N", title="Quarter"),
                     alt.Tooltip("median:Q", title="Median rent ($)")],
        ).properties(height=420)
        st.altair_chart(line, use_container_width=True)

        latest = h.quarter_date.max()
        five_ago = latest - pd.DateOffset(years=5)
        now = h[h.quarter_date == latest].set_index("suburb_group")["median"]
        then = h[h.quarter_date == five_ago].set_index("suburb_group")["median"]
        change = ((now / then - 1) * 100).round(0).dropna().sort_values(ascending=False)
        st.write(f"**Change over the last 5 years** ({five_ago:%b %Y} to {latest:%b %Y})")
        st.dataframe(pd.DataFrame({"Rent now ($/wk)": now.reindex(change.index),
                                   "5 years ago ($/wk)": then.reindex(change.index),
                                   "Change (%)": change}), use_container_width=True)

# ---- tab 3: rent vs commute -----------------------------------------------------
cheap_line = pool.rent_pp.quantile(0.25)
pool["type"] = "Other suburbs"
pool.loc[(pool.rent_pp <= cheap_line) & (pool.travel_time <= 40), "type"] = "Hidden gem"
pool.loc[(pool.distance_km <= 12) & (pool.travel_time >= 50), "type"] = "Trap"

with tab_plot:
    st.subheader(f"Rent against commute: {campus}")
    st.caption(f"{option}. Each dot is a suburb. Best value is bottom-left: cheap and quick.")
    dots = alt.Chart(pool).mark_circle(size=90, opacity=0.8).encode(
        x=alt.X("travel_time:Q", title="Public transport time to campus (minutes)"),
        y=alt.Y("rent_pp:Q", title="Your rent ($ per week)", scale=alt.Scale(zero=False)),
        color=alt.Color("type:N", title="", scale=alt.Scale(
            domain=["Hidden gem", "Trap", "Other suburbs"], range=["#1a9850", "#d73027", "#9e9e9e"])),
        tooltip=[alt.Tooltip("suburb:N", title="Suburb"), alt.Tooltip("rent_pp:Q", title="Rent ($/wk)"),
                 alt.Tooltip("travel_time:Q", title="Commute (min)"),
                 alt.Tooltip("distance_km:Q", title="Distance (km)")],
    ).properties(height=480)
    st.altair_chart(dots, use_container_width=True)

# ---- tab 4: hidden gems and traps --------------------------------------------
with tab_gems:
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Hidden gems")
        st.caption(f"Rent in the cheapest quarter for this option (${cheap_line:.0f}/wk or less) "
                   "and 40 minutes or less to campus.")
        gems = pool[pool.type == "Hidden gem"].sort_values("weekly_cost")
        if gems.empty:
            st.info("No hidden gems for this campus and option.")
        else:
            st.dataframe(gems[["suburb", "rent_pp", "travel_time"]].rename(columns={
                "suburb": "Suburb", "rent_pp": "Rent ($/wk)", "travel_time": "Commute (min)"}),
                hide_index=True, use_container_width=True)
    with g2:
        st.subheader("Traps")
        st.caption("Within 12 km of campus in a straight line, but 50 minutes or more by public transport.")
        traps = pool[pool.type == "Trap"].sort_values("travel_time", ascending=False)
        if traps.empty:
            st.info("No traps for this campus and option.")
        else:
            st.dataframe(traps[["suburb", "distance_km", "travel_time", "rent_pp"]].rename(columns={
                "suburb": "Suburb", "distance_km": "Distance (km)",
                "travel_time": "Commute (min)", "rent_pp": "Rent ($/wk)"}),
                hide_index=True, use_container_width=True)

# ---- tab 5: about --------------------------------------------------------------
with tab_about:
    st.markdown(
        """
- **Rents:** Homes Victoria Rental Report, moving annual median of new leases to September 2025, from rental bond data.
  Half of new leases cost more than the median. Areas with fewer than 10 new leases are left out.
- **Shares:** a room's rent is the 2-bedroom flat median ÷ 2, or the 3-bedroom house median ÷ 3.
- **Commute:** door-to-door public transport and walking, Tuesday 17 November 2026, 8–9am departures,
  from each suburb's centre, using PTV timetables and OpenStreetMap (calculated with r5py). Real trips vary with delays.
- **True weekly cost:** rent per person + (minutes ÷ 60) × trips per week × value of your time.
- **Coverage:** only suburbs named in the rental report appear. Suburb boundaries: ABS 2021.
"""
    )
