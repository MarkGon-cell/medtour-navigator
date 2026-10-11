"""Repair `state` on rows that `GET /hospitals/discover` persisted.

Background
----------
`_infer_state()` first copied the state of the *single nearest* directory row.
That was wrong, because the CSV's own `state` column is corrupt in places: all
six of its Lucknow rows read "Bihar", "Chhattisgarh", "Haryana" or "Jammu and
Kashmir", never "Uttar Pradesh". The first Lucknow discovery run therefore
wrote two facilities stamped with those fabricated states.

The provider, by contrast, is reliable here -- Overpass declares
`addr:state = Uttar Pradesh` on 181 of 214 Lucknow hospitals. So the rule is
now a supermajority vote **over provider-discovered rows**, which is also what
this script votes over. It deliberately does not consult `csv_import` rows,
because near Lucknow they would vote a facility *into* the wrong state.

Rows whose state the provider reported directly are left alone.

    python scripts/repair_discovery_state.py           # dry run, prints a diff
    python scripts/repair_discovery_state.py --apply   # write the fixes
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database.database import SessionLocal
from app.models.hospital import Hospital
from app.services.discovery import state_consensus


def main() -> None:
    apply_changes = "--apply" in sys.argv

    db = SessionLocal()
    try:
        # The voting population: everything search has discovered. Directory
        # rows are excluded on purpose -- see the module docstring.
        discovered = (
            db.query(Hospital)
            .filter(Hospital.source != "csv_import")
            .all()
        )

        print(f"voting population: {len(discovered)} provider-discovered rows")
        print(f"csv_import rows consulted: 0")
        print(f"mode: {'APPLY' if apply_changes else 'DRY RUN'}\n")

        changes = 0
        unresolved = 0

        for row in discovered:
            consensus = state_consensus(row.latitude, row.longitude, discovered)
            if consensus is None:
                unresolved += 1
                continue
            if consensus == (row.state or "").strip():
                continue

            changes += 1
            print(f"  id={row.id:6} {row.name[:36]:38} "
                  f"{(row.state or '(blank)'):22} -> {consensus}")
            if apply_changes:
                row.state = consensus

        if apply_changes and changes:
            db.commit()

        print(f"\n{changes} row(s) disagree with the consensus"
              f"{'' if apply_changes else ' (not applied)'}")
        print(f"{unresolved} row(s) left alone: no provider consensus nearby")
    finally:
        db.close()


if __name__ == "__main__":
    main()
