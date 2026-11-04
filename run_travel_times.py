
import datetime
import io
import sys
import time
import zipfile
from pathlib import Path

DATA = Path(__file__).resolve().parent
PROC = DATA / "processed"
LOG = open(DATA / "travel_times_log.txt", "w", encoding="utf-8")


def _log_crash(kind, value, tb):
    import traceback
    text = "".join(traceback.format_exception(kind, value, tb))
    LOG.write("\nERROR:\n" + text)
    LOG.flush()
    sys.__excepthook__(kind, value, tb)


sys.excepthook = _log_crash


def say(*parts):
    msg = " ".join(str(p) for p in parts)
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


start = time.time()
say("Step 2: travel times", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

say("[1/5] Preparing timetables...")
GTFS_DIR = DATA / "gtfs"
GTFS_DIR.mkdir(exist_ok=True)
names = {"2": "metro_train", "3": "tram", "4": "metro_bus"}
feeds = []
with zipfile.ZipFile(DATA / "gtfs.zip") as z:
    for mode, name in names.items():
        inner = zipfile.ZipFile(io.BytesIO(z.read(f"{mode}/google_transit.zip")))
        target = GTFS_DIR / f"{name}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
            for f in inner.namelist():
                data = inner.read(f)
                if len(data.strip().splitlines()) <= 1:  
                    say(f"       {name}: leaving out empty {f}")
                    continue
                out.writestr(f, data)
        feeds.append(str(target))
say("      ", ", ".join(Path(f).name for f in feeds))


say("[2/5] Loading suburbs and campuses...")
import pandas as pd
import geopandas as gpd

pts = pd.read_csv(PROC / "suburb_points.csv", dtype={"id": str})
origins = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts.lon, pts.lat), crs=4326)
camp = pd.read_csv(PROC / "campuses.csv")
dests = gpd.GeoDataFrame(camp.rename(columns={"campus": "id"}),
                         geometry=gpd.points_from_xy(camp.lon, camp.lat), crs=4326)
say(f"       {len(origins)} suburbs, {len(dests)} campuses")


say("[3/5] Building the transport network (5-20 minutes, the window may look frozen)...")
import r5py

say("       r5py", r5py.__version__)
t0 = time.time()
network = r5py.TransportNetwork(str(DATA / "Melbourne.osm.pbf"), feeds, allow_errors=True)
say(f"       network ready in {(time.time() - t0) / 60:.1f} min")


say("[4/5] Calculating travel times, Tue 17 Nov 2026, 8-9am...")
settings = dict(
    origins=origins,
    destinations=dests,
    departure=datetime.datetime(2026, 11, 17, 8, 0),
    departure_time_window=datetime.timedelta(hours=1),
    transport_modes=[r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK],
    max_time=datetime.timedelta(hours=2),
)
if hasattr(r5py, "TravelTimeMatrix"):
    tt = r5py.TravelTimeMatrix(network, **settings)
else:
    tt = r5py.TravelTimeMatrixComputer(network, **settings).compute_travel_times()
tt = pd.DataFrame(tt)


say("[5/5] Saving...")
tt.to_csv(PROC / "travel_times.csv", index=False)
say(f"       saved {len(tt)} rows to processed\\travel_times.csv")
say(f"       empty (no trip under 2 hours): {tt.travel_time.isna().sum()}")
check = tt.merge(pts[["id", "suburb"]], left_on="from_id", right_on="id")
sample = check[check.suburb.isin(["Footscray", "Clayton", "Box Hill", "Brunswick"])].pivot(
    index="suburb", columns="to_id", values="travel_time")
say("\nSample (minutes):\n" + sample.to_string())
say(f"\nDONE in {(time.time() - start) / 60:.1f} min")
LOG.close()
