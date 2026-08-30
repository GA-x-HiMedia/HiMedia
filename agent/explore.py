"""Explores HiMedia API endpoints and compares access between users.

Run with:

    python -m agent.explore
"""

from __future__ import annotations

import json

import httpx

from . import himedia
from .config import BASE_URL

KHALID = "+97333000003"  # Internal user.
FATIMA = "+97333000020"  # Client user.


def _show(label: str, data, limit: int = 1500) -> None:
    print(f"\n=== {label} ===")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:limit])


def main() -> None:
    # Check that the sandbox is available.
    health = httpx.get(f"{BASE_URL}/health", timeout=10.0).json()
    _show("GET /health", health)

    # Retrieve available roles and permissions.
    roles = himedia.get("/v1/roles")
    _show(
        f"GET /v1/roles ({len(roles['data'])} total, showing first 2)",
        roles["data"][:2],
    )

    # Retrieve the available companies.
    companies = himedia.get("/v1/companies")
    _show("GET /v1/companies", companies)

    # Retrieve the user's identity and permissions.
    khalid = himedia.get("/v1/permissions/by-phone", phone=KHALID)
    _show(f"GET /v1/permissions/by-phone ({KHALID}, Khalid)", khalid)

    # Compare project access for two different users.
    khalid_projects = himedia.get("/v1/projects", phone=KHALID)
    fatima_projects = himedia.get("/v1/projects", phone=FATIMA)

    _show(
        f"GET /v1/projects?phone={KHALID} (Khalid, internal)",
        khalid_projects,
    )
    _show(
        f"GET /v1/projects?phone={FATIMA} (Fatima, client)",
        fatima_projects,
    )

    khalid_ids = {p["id"] for p in khalid_projects["data"]}
    fatima_ids = {p["id"] for p in fatima_projects["data"]}

    print("\n" + "=" * 60)
    print("INTERNAL vs CLIENT COMPARISON — list_projects")
    print("=" * 60)

    print(f"Khalid (internal) sees {len(khalid_ids)} projects: {sorted(khalid_ids)}")
    print(f"Fatima (client)   sees {len(fatima_ids)} projects: {sorted(fatima_ids)}")

    if khalid_ids != fatima_ids:
        print(
            "CONFIRMED: internal and client callers get different data "
            "from the same endpoint."
        )
    else:
        print(
            "WARNING: identical results — investigate before trusting "
            "the filtering."
        )

    # Compare version access for the same users.
    khalid_versions = himedia.get("/v1/versions", phone=KHALID)
    fatima_versions = himedia.get("/v1/versions", phone=FATIMA)

    print("\n" + "=" * 60)
    print("INTERNAL vs CLIENT COMPARISON — list_versions")
    print("=" * 60)

    print(f"Khalid (internal) sees {khalid_versions['total']} versions.")
    print(f"Fatima (client)   sees {fatima_versions['total']} versions.")

    if khalid_versions["total"] != fatima_versions["total"]:
        print(
            "CONFIRMED: draft/internal_review versions are hidden from "
            "the client caller."
        )
    else:
        print(
            "WARNING: identical version counts — investigate before "
            "trusting the filtering."
        )


if __name__ == "__main__":
    main()