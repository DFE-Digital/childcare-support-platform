"""Shared helpers for OS Places API geocoding."""

import math
import time

import requests

RATE_LIMIT_SECONDS = 0.15  # ~6.6 req/sec, well under OS Places' ~600/min
POSTCODE_VALIDATION_KM = (
    5.0  # reject query result if further than this from postcode centroid
)

OS_PLACES_FIND_URL = "https://api.os.uk/search/places/v1/find"
OS_PLACES_POSTCODE_URL = "https://api.os.uk/search/places/v1/postcode"


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Approximate great-circle distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def build_query(parts: list[str]) -> str | None:
    """Build an address query string from non-empty, non-REDACTED parts."""
    cleaned = [
        p.strip() for p in parts if p and p.strip() and p.strip().upper() != "REDACTED"
    ]
    return ", ".join(cleaned) if cleaned else None


def geocode(
    session: requests.Session, api_key: str, query: str, postcode: str | None, log=None
) -> dict:
    """Geocode an address via OS Places API with postcode validation and fallback.

    When a postcode is available, always fetches the postcode centroid and uses it
    to validate the query result. If the query result is more than POSTCODE_VALIDATION_KM
    away from the centroid, it likely matched the wrong place and the centroid is used
    instead (status: success_postcode_override). If the query fails entirely, the centroid
    is used as a fallback (status: success_postcode_fallback).
    """
    valid_postcode = bool(
        postcode and postcode.strip() and postcode.strip().upper() != "REDACTED"
    )

    # Step 1: full address query
    find_error = None
    query_lat = query_lng = None
    try:
        resp = session.get(
            OS_PLACES_FIND_URL,
            params={"query": query, "key": api_key, "output_srs": "EPSG:4326"},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            dpa = results[0].get("DPA", {})
            query_lat = dpa.get("LAT")
            query_lng = dpa.get("LNG")
    except requests.HTTPError as e:
        find_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        find_error = str(e)

    # Step 2: postcode centroid (always fetched when postcode available — used for
    # validation of a successful query result, or as fallback if query failed)
    pc_lat = pc_lng = None
    if valid_postcode:
        time.sleep(RATE_LIMIT_SECONDS)
        try:
            resp = session.get(
                OS_PLACES_POSTCODE_URL,
                params={
                    "postcode": postcode.strip(),
                    "key": api_key,
                    "output_srs": "EPSG:4326",
                },
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                dpa = results[0].get("DPA", {})
                pc_lat = dpa.get("LAT")
                pc_lng = dpa.get("LNG")
        except requests.HTTPError as e:
            if log:
                log.warning(
                    f"Postcode lookup failed — HTTP {e.response.status_code}: {e.response.text[:200]}"
                )
        except Exception as e:
            if log:
                log.warning(f"Postcode lookup failed — {e}")

    # Step 3: return best result
    if query_lat is not None and query_lng is not None:
        if pc_lat is not None and pc_lng is not None:
            dist = _haversine_km(query_lat, query_lng, pc_lat, pc_lng)
            if dist > POSTCODE_VALIDATION_KM:
                if log:
                    log.warning(
                        f"Query result {dist:.1f} km from postcode centroid — "
                        f"overriding with postcode centroid: {postcode}"
                    )
                return {
                    "latitude": pc_lat,
                    "longitude": pc_lng,
                    "geocode_status": "success_postcode_override",
                }
        return {
            "latitude": query_lat,
            "longitude": query_lng,
            "geocode_status": "success",
        }

    if pc_lat is not None and pc_lng is not None:
        return {
            "latitude": pc_lat,
            "longitude": pc_lng,
            "geocode_status": "success_postcode_fallback",
        }

    if find_error:
        return {
            "latitude": None,
            "longitude": None,
            "geocode_status": "api_error",
            "_error": find_error,
        }

    return {"latitude": None, "longitude": None, "geocode_status": "no_results"}


def make_session() -> requests.Session:
    """Create a requests session with a standard User-Agent."""
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "BSIL-DataPipeline/1.0 (research; best-start-in-life)"}
    )
    return session


def outward_code(postcode: str | None) -> str | None:
    """Extract the outward (district) code from a postcode.

    'SW1A 1AA' → 'SW1A', 'EC1A2BN' → 'EC1A', None → None.
    """
    if not postcode:
        return None
    pc = postcode.strip().upper()
    if not pc:
        return None
    if " " in pc:
        return pc.split()[0]
    # No space — inward code is always last 3 characters
    if len(pc) >= 5:
        return pc[:-3].strip()
    return None


def bbox_fallback(
    conn, postcode: str | None, lad25cd: str | None, la_name: str | None = None
) -> dict | None:
    """Look up a bounding box from os.bounding_boxes for a provider.

    Tries in order: postcode → postcode_district → local_authority (code) →
    LA name lookup (os.la_name_lookup).
    Returns dict with geocode_status, bbox_geo_type, bbox_geo_code,
    or None if nothing found.

    Each step is a single indexed PK lookup — no scanning.
    """
    # 1. Full postcode
    if postcode and postcode.strip():
        pc = postcode.strip().upper()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM os.bounding_boxes WHERE geo_type = 'postcode' AND geo_code = %s",
                (pc,),
            )
            if cur.fetchone():
                return {
                    "geocode_status": "bbox_postcode",
                    "bbox_geo_type": "postcode",
                    "bbox_geo_code": pc,
                }

    # 2. Postcode district (outward code)
    #    outward_code() extracts from full postcodes; also try the raw postcode
    #    directly as a district code (handles outward-only postcodes like "BT28")
    oc = outward_code(postcode)
    candidates = [oc] if oc else []
    if postcode and postcode.strip():
        raw = postcode.strip().upper()
        if raw not in candidates:
            candidates.append(raw)
    for candidate in candidates:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM os.bounding_boxes WHERE geo_type = 'postcode_district' AND geo_code = %s",
                (candidate,),
            )
            if cur.fetchone():
                return {
                    "geocode_status": "bbox_postcode_district",
                    "bbox_geo_type": "postcode_district",
                    "bbox_geo_code": candidate,
                }

    # 3. Local authority (ONS code)
    if lad25cd and lad25cd.strip():
        code = lad25cd.strip()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM os.bounding_boxes WHERE geo_type = 'local_authority' AND geo_code = %s",
                (code,),
            )
            if cur.fetchone():
                return {
                    "geocode_status": "bbox_local_authority",
                    "bbox_geo_type": "local_authority",
                    "bbox_geo_code": code,
                }

    # 4. LA name lookup (Ofsted local_authority field → os.la_name_lookup)
    if la_name and la_name.strip():
        name = la_name.strip()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT geo_type, geo_code FROM os.la_name_lookup WHERE la_name = %s",
                (name,),
            )
            row = cur.fetchone()
            if row:
                geo_type, geo_code = row
                status = (
                    "bbox_county" if geo_type == "county" else "bbox_local_authority"
                )
                return {
                    "geocode_status": status,
                    "bbox_geo_type": geo_type,
                    "bbox_geo_code": geo_code,
                }

    return None
