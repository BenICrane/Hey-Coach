#!/usr/bin/env python3
"""
Sync the last 52 weeks of Garmin activities into a local SQLite database.

Steps:
  1. Create the database/table if it doesn't exist (otherwise open it)
  2. Exchange your Garmin Personal API key for a 24h access token
  3. List all activities from the last 8 weeks (paginated)
  4. Insert any activities not already in the table
  5. De-dupe check on activity_id
  6. Save (commit) and close

Setup:
  - Python 3.8+ only. No third-party packages needed (standard library only).
  - Your API key is taken from, in order: the GARMIN_API_KEY constant below,
    the GARMIN_API_KEY environment variable, or a hidden prompt.
    If you paste the key into this file, don't commit or share the file.

Run:
  python3 garmin_sync.py
"""

import getpass
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
try:
    DB_PATH = Path(__file__).resolve().parent / "garmin_activities.db"
except NameError:  # running in a notebook / interactive session
    DB_PATH = Path.cwd() / "garmin_activities.db"

WEEKS_BACK = 52
PAGE_SIZE = 50
MAX_PAGES = 100          # safety cap: 100 pages x 50 = 5,000 activities
ACTIVITY_TYPE = None     # e.g. "running" to fetch only runs; None = all types
TIMEOUT_S = 30

# Paste your Garmin Personal API key between the quotes. Don't commit this file
# to git (or share it) once the key is in it.
GARMIN_API_KEY = "GCDC_798bf017-df18-43db-b906-ee4f1d578a75.0ea7f0b6-c95f-4cee-aa41-b87364625f8d.xw5olmFu5Xy1pB88Zza0hblIxEA1zjUMN0Xt51fnwXs.3062017909"

TOKEN_URL = (
    "https://personal.connectapi.garmin.com/"
    "personalapitoken-service/personal-api/personal-api-key/token"
)
ACTIVITIES_URL = (
    "https://personal.connectapi.garmin.com/"
    "activitylist-service/activities/search/activities"
)

# --------------------------------------------------------------------------
# Schema: (column name, SQLite type, path into the Garmin JSON)
# Garmin omits fields it has no value for, so missing keys become NULL.
# Units: metres, seconds, m/s, cm (stride length), steps per minute.
# --------------------------------------------------------------------------
FIELDS = [
    ("activity_id",            "INTEGER PRIMARY KEY", ("activityId",)),
    ("name",                   "TEXT",                ("activityName",)),
    ("start_time_local",       "TEXT NOT NULL",       ("startTimeLocal",)),
    ("start_time_gmt",         "TEXT",                ("startTimeGMT",)),
    ("location_name",          "TEXT",                ("locationName",)),
    ("activity_type",          "TEXT",                ("activityType", "typeKey")),
    ("event_type",             "TEXT",                ("eventType", "typeKey")),
    ("is_pr",                  "INTEGER",             ("isPR",)),

    ("distance_m",             "REAL",                ("distance",)),
    ("duration_s",             "REAL",                ("duration",)),
    ("moving_duration_s",      "REAL",                ("movingDuration",)),
    ("elapsed_duration_s",     "REAL",                ("elapsedDuration",)),
    ("avg_speed_mps",          "REAL",                ("averageSpeed",)),
    ("max_speed_mps",          "REAL",                ("maxSpeed",)),

    ("elevation_gain_m",       "REAL",                ("elevationGain",)),
    ("elevation_loss_m",       "REAL",                ("elevationLoss",)),
    ("min_elevation_m",        "REAL",                ("minElevation",)),
    ("max_elevation_m",        "REAL",                ("maxElevation",)),
    ("avg_elevation_m",        "REAL",                ("avgElevation",)),

    ("avg_hr",                 "INTEGER",             ("averageHR",)),
    ("max_hr",                 "INTEGER",             ("maxHR",)),
    ("hr_zone1_s",             "REAL",                ("hrTimeInZone_1",)),
    ("hr_zone2_s",             "REAL",                ("hrTimeInZone_2",)),
    ("hr_zone3_s",             "REAL",                ("hrTimeInZone_3",)),
    ("hr_zone4_s",             "REAL",                ("hrTimeInZone_4",)),
    ("hr_zone5_s",             "REAL",                ("hrTimeInZone_5",)),

    ("avg_cadence_spm",        "REAL",                ("averageRunningCadenceInStepsPerMinute",)),
    ("max_cadence_spm",        "REAL",                ("maxRunningCadenceInStepsPerMinute",)),
    ("avg_stride_length_cm",   "REAL",                ("avgStrideLength",)),
    ("steps",                  "INTEGER",             ("steps",)),

    ("aerobic_te",             "REAL",                ("aerobicTrainingEffect",)),
    ("anaerobic_te",           "REAL",                ("anaerobicTrainingEffect",)),
    ("aerobic_te_message",     "TEXT",                ("aerobicTrainingEffectMessage",)),
    ("anaerobic_te_message",   "TEXT",                ("anaerobicTrainingEffectMessage",)),
    ("moderate_intensity_min", "INTEGER",             ("moderateIntensityMinutes",)),
    ("vigorous_intensity_min", "INTEGER",             ("vigorousIntensityMinutes",)),

    ("fastest_1k_s",           "REAL",                ("fastestSplit_1000",)),
    ("fastest_1mi_s",          "REAL",                ("fastestSplit_1609",)),
    ("fastest_5k_s",           "REAL",                ("fastestSplit_5000",)),
    ("fastest_10k_s",          "REAL",                ("fastestSplit_10000",)),
    ("fastest_half_s",         "REAL",                ("fastestSplit_21098",)),
    ("fastest_marathon_s",     "REAL",                ("fastestSplit_42195",)),

    ("calories",               "REAL",                ("calories",)),
    ("lap_count",              "INTEGER",             ("lapCount",)),
]

COLUMN_NAMES = [name for name, _, _ in FIELDS] + ["raw"]

CREATE_TABLE_SQL = (
    "CREATE TABLE IF NOT EXISTS activities (\n"
    + ",\n".join(f"  {name} {sqltype}" for name, sqltype, _ in FIELDS)
    + ",\n  raw TEXT\n)"
)

INSERT_SQL = (
    f"INSERT OR IGNORE INTO activities ({', '.join(COLUMN_NAMES)}) "
    f"VALUES ({', '.join('?' * len(COLUMN_NAMES))})"
)

# The view is dropped and recreated each run so any changes here take effect.
CREATE_VIEW_SQL = """
CREATE VIEW v_runs AS
SELECT *,
       ROUND(distance_m / 1000.0, 2)  AS distance_km,
       ROUND(1000.0 / avg_speed_mps)  AS pace_s_per_km,
       printf('%d:%02d',
              CAST(ROUND(1000.0 / avg_speed_mps) AS INT) / 60,
              CAST(ROUND(1000.0 / avg_speed_mps) AS INT) % 60) AS pace_mmss,
       CASE WHEN aerobic_te_message IS NOT NULL THEN
         upper(substr(replace(rtrim(aerobic_te_message, '0123456789_'), '_', ' '), 1, 1)) ||
         lower(substr(replace(rtrim(aerobic_te_message, '0123456789_'), '_', ' '), 2))
       END AS aerobic_te_label
FROM activities
WHERE activity_type LIKE '%running' AND avg_speed_mps > 0
"""


# --------------------------------------------------------------------------
# Step 1: database
# --------------------------------------------------------------------------
def open_database(path):
    existed = Path(path).exists()
    conn = sqlite3.connect(path)
    conn.execute(CREATE_TABLE_SQL)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_start ON activities (start_time_local)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_type ON activities (activity_type)")
    conn.execute("DROP VIEW IF EXISTS v_runs")
    conn.execute(CREATE_VIEW_SQL)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    if existed:
        print(f"[1/6] Loaded existing database {path} ({count} activities)")
    else:
        print(f"[1/6] Created new database {path}")
    return conn


# --------------------------------------------------------------------------
# HTTP helpers (standard library only)
# --------------------------------------------------------------------------
def http_request(method, url, headers):
    req = urllib.request.Request(
        url,
        data=b"" if method == "POST" else None,
        method=method,
        headers={"Accept": "application/json", "User-Agent": "garmin-sync/1.0", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        hint = ""
        if e.code in (401, 403):
            hint = " (key/token rejected - check the key hasn't expired or been deleted)"
        raise SystemExit(f"HTTP {e.code} from {url}{hint}\n{body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Could not reach {url}: {e.reason}")


# --------------------------------------------------------------------------
# Step 2: token
# --------------------------------------------------------------------------
def get_api_key():
    key = GARMIN_API_KEY.strip() or os.environ.get("GARMIN_API_KEY", "").strip()
    if not key or key == "paste-your-key-here":
        key = getpass.getpass("Garmin Personal API key (input hidden): ").strip()
    if not key:
        raise SystemExit("No API key provided.")
    return key


def get_access_token(api_key):
    # The token endpoint answers in text/plain and returns 406 to "Accept: application/json".
    text = http_request("POST", TOKEN_URL, {"Authorization": f"ApiKey {api_key}", "Accept": "*/*"})
    # The response format isn't documented in the pages I could read, so handle
    # both a JSON object ({"access_token": "..."}) and a bare token string.
    try:
        parsed = json.loads(text)
    except ValueError:
        token = text.strip().strip('"')
    else:
        if isinstance(parsed, dict):
            token = next(
                (parsed[k] for k in ("access_token", "accessToken", "token") if k in parsed),
                None,
            )
            if token is None:
                raise SystemExit(f"Token response had no recognised token field: {list(parsed)}")
        else:
            token = str(parsed)
    if not token:
        raise SystemExit("Token endpoint returned an empty token.")
    print("[2/6] Got access token (valid for 24h)")
    return token


# --------------------------------------------------------------------------
# Step 3: list activities
# --------------------------------------------------------------------------
def fetch_activities(token, start_date, end_date):
    activities = []
    offset = 0
    for _ in range(MAX_PAGES):
        params = {
            "start": offset,
            "limit": PAGE_SIZE,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        }
        if ACTIVITY_TYPE:
            params["activityType"] = ACTIVITY_TYPE
        url = f"{ACTIVITIES_URL}?{urllib.parse.urlencode(params)}"

        page = json.loads(http_request("GET", url, {"Authorization": f"Bearer {token}"}))
        if not isinstance(page, list):
            raise SystemExit(f"Unexpected activities response (expected a list): {str(page)[:300]}")
        if not page:
            break  # keep going until an empty page, since Garmin can return short pages
        activities.extend(page)
        offset += len(page)
    else:
        print(f"      Warning: stopped at MAX_PAGES={MAX_PAGES}; results may be incomplete")

    print(f"[3/6] Fetched {len(activities)} activities ({start_date} to {end_date})")
    return activities


# --------------------------------------------------------------------------
# Step 4: insert new activities
# --------------------------------------------------------------------------
def dig(obj, path):
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
        if obj is None:
            return None
    return obj


def to_row(activity):
    values = []
    for _, _, path in FIELDS:
        v = dig(activity, path)
        if isinstance(v, bool):
            v = int(v)
        values.append(v)
    values.append(json.dumps(activity))  # full original payload
    return tuple(values)


def insert_new_activities(conn, activities):
    existing = {row[0] for row in conn.execute("SELECT activity_id FROM activities")}
    new_rows, seen, skipped = [], set(), 0

    for a in activities:
        aid = a.get("activityId")
        if aid is None or not a.get("startTimeLocal"):
            skipped += 1
            continue
        if aid in existing or aid in seen:
            continue
        seen.add(aid)
        new_rows.append(to_row(a))

    with conn:  # one transaction
        conn.executemany(INSERT_SQL, new_rows)

    msg = f"[4/6] Added {len(new_rows)} new activities ({len(activities) - len(new_rows) - skipped} already stored or repeated in this fetch)"
    if skipped:
        msg += f", skipped {skipped} with no activityId/startTimeLocal"
    print(msg)
    return len(new_rows)


# --------------------------------------------------------------------------
# Step 5: de-dupe check
# --------------------------------------------------------------------------
def dedupe(conn):
    dupes = conn.execute(
        "SELECT activity_id, COUNT(*) FROM activities GROUP BY activity_id HAVING COUNT(*) > 1"
    ).fetchall()
    if not dupes:
        print("[5/6] De-dupe check passed: no duplicate activity_ids")
        return 0
    with conn:
        # Keep the first-inserted row for each activity_id
        cur = conn.execute(
            "DELETE FROM activities WHERE rowid NOT IN "
            "(SELECT MIN(rowid) FROM activities GROUP BY activity_id)"
        )
    print(f"[5/6] De-dupe removed {cur.rowcount} duplicate rows across {len(dupes)} activity_ids")
    return cur.rowcount


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    conn = open_database(DB_PATH)                      # 1
    try:
        token = get_access_token(get_api_key())        # 2

        today = date.today()
        start_date = today - timedelta(weeks=WEEKS_BACK)
        # +1 day on the end so today's activities are included even if endDate is exclusive
        activities = fetch_activities(token, start_date, today + timedelta(days=1))  # 3

        insert_new_activities(conn, activities)        # 4
        dedupe(conn)                                   # 5

        conn.commit()                                  # 6
        total = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        print(f"[6/6] Saved. {total} activities in {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())