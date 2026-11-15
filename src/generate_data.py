"""Generate synthetic NYC 311 style service request data.

Deterministic (seeded) generator that mirrors the schema of the
NYC Open Data 311 Service Requests dataset. The bundled data is
synthetic and labelled as such. It is not real 311 data.

Output: data/requests_311.csv with about 5000 rows.

Columns:
    unique_key, created_date, closed_date, agency, complaint_type,
    descriptor, borough, status, resolution_hours
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
N_ROWS = 5000

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BASE_DIR / "data" / "requests_311.csv"

BOROUGHS = ["BROOKLYN", "QUEENS", "MANHATTAN", "BRONX", "STATEN ISLAND"]
BOROUGH_WEIGHTS = [0.32, 0.27, 0.20, 0.15, 0.06]

# agency -> list of (complaint_type, [descriptors], base_resolution_hours)
AGENCY_CATALOG = {
    "NYPD": [
        ("Noise - Residential", ["Loud Music/Party", "Banging/Pounding", "Loud Talking"], 8),
        ("Noise - Street/Sidewalk", ["Loud Music/Party", "Loud Talking", "Car/Truck Music"], 6),
        ("Illegal Parking", ["Blocked Hydrant", "Double Parked Vehicle", "Blocked Driveway"], 10),
        ("Blocked Driveway", ["No Access", "Partial Access"], 12),
        ("Disorderly Conduct", ["Loud Party", "Public Urination"], 9),
    ],
    "DSNY": [
        ("Sanitation Condition", ["Dirty Condition", "Littering", "Overflowing Basket"], 28),
        ("Missed Collection", ["Missed Trash Collection", "Missed Recycling Collection"], 24),
        ("Recycling", ["Missed Recycling", "Recycling Basket Request"], 30),
        ("Street Cleaning", ["Missed Street Cleaning", "Mechanical Broom Request"], 36),
    ],
    "HPD": [
        ("HEAT/HOT WATER", ["Entire Building", "Apartment Only", "No Hot Water"], 18),
        ("PLUMBING", ["Leak", "Blocked Drain", "Broken Pipe"], 42),
        ("PAINT - PLASTER", ["Peeling Paint", "Cracked Walls"], 96),
        ("APPLIANCE", ["Stove Broken", "Refrigerator Broken"], 72),
        ("GENERAL CONSTRUCTION", ["Wall Crack", "Ceiling Leak"], 80),
    ],
    "DOT": [
        ("Street Condition", ["Pothole", "Cave In", "Rough Pavement"], 120),
        ("Street Light Condition", ["Light Out", "Flickering Light", "Damaged Pole"], 72),
        ("Traffic Signal Condition", ["Signal Out", "Signal Timing"], 24),
        ("Sidewalk Condition", ["Cracked Sidewalk", "Raised Sidewalk"], 168),
    ],
    "DEP": [
        ("Water System", ["Low Pressure", "No Water", "Discolored Water"], 36),
        ("Sewer", ["Sewer Backup", "Manhole Overflow", "Catch Basin Clogged"], 30),
        ("Air Quality", ["Smoke", "Odor", "Dust"], 48),
    ],
    "DOHMH": [
        ("Rodent", ["Rat Sighting", "Mouse Sighting", "Signs of Rodents"], 60),
        ("Food Establishment", ["Unsanitary Condition", "Pest Presence"], 84),
        ("Unsanitary Condition", ["Standing Water", "Sewage"], 55),
    ],
    "DOB": [
        ("Construction", ["Work Without Permit", "Unsafe Construction", "After Hours Work"], 90),
        ("Building/Use", ["Illegal Conversion", "Occupancy Violation"], 110),
    ],
    "DPR": [
        ("Tree Damage", ["Fallen Tree", "Damaged Branch", "Dead Tree"], 96),
        ("Park Condition", ["Damaged Bench", "Litter in Park", "Broken Playground"], 72),
    ],
}

AGENCIES = list(AGENCY_CATALOG.keys())
AGENCY_WEIGHTS = [0.24, 0.14, 0.18, 0.14, 0.09, 0.07, 0.07, 0.07]


def generate_rows(n_rows: int = N_ROWS, seed: int = SEED):
    rng = random.Random(seed)
    start = datetime(2024, 1, 1, 0, 0, 0)
    end_offset_seconds = 366 * 24 * 3600  # leap year 2024

    rows = []
    for i in range(1, n_rows + 1):
        borough = rng.choices(BOROUGHS, weights=BOROUGH_WEIGHTS, k=1)[0]
        agency = rng.choices(AGENCIES, weights=AGENCY_WEIGHTS, k=1)[0]
        complaint_type, descriptors, base_hours = rng.choice(AGENCY_CATALOG[agency])
        descriptor = rng.choice(descriptors)

        created_offset = rng.randint(0, end_offset_seconds - 1)
        created = start + timedelta(seconds=created_offset)
        # Round to minutes for cleaner timestamps
        created = created.replace(second=0, microsecond=0)

        status_roll = rng.random()
        if status_roll < 0.85:
            status = "Closed"
        elif status_roll < 0.95:
            status = "Open"
        else:
            status = "Pending"

        if status == "Closed":
            # Resolution time varies around the agency/complaint base
            factor = rng.lognormvariate(0, 0.6)
            resolution_hours = round(max(0.5, base_hours * factor), 2)
            closed = created + timedelta(hours=resolution_hours)
            closed_str = closed.strftime("%Y-%m-%d %H:%M:%S")
        else:
            resolution_hours = ""
            closed_str = ""

        rows.append(
            {
                "unique_key": 60000000 + i,
                "created_date": created.strftime("%Y-%m-%d %H:%M:%S"),
                "closed_date": closed_str,
                "agency": agency,
                "complaint_type": complaint_type,
                "descriptor": descriptor,
                "borough": borough,
                "status": status,
                "resolution_hours": resolution_hours,
            }
        )

    rows.sort(key=lambda r: r["created_date"])
    # Reassign unique_key in chronological order for realism
    for idx, row in enumerate(rows, start=1):
        row["unique_key"] = 60000000 + idx
    return rows


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = generate_rows()
    fieldnames = [
        "unique_key",
        "created_date",
        "closed_date",
        "agency",
        "complaint_type",
        "descriptor",
        "borough",
        "status",
        "resolution_hours",
    ]
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
