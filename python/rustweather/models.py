"""Model metadata, field aliases, and station locations.

Provides:
    models          -- dict of supported NWP models and default products
    FIELD_ALIASES   -- natural-language names -> GRIB search strings
    STATIONS        -- upper-air station IDs -> (lat, lon) tuples
    latest()        -- find the latest available model run
"""

# ---------------------------------------------------------------------------
# Supported models
# ---------------------------------------------------------------------------
models = {
    # HRRR family
    "hrrr": {"product": "sfc", "description": "HRRR 3km CONUS"},
    "hrrrak": {"product": "sfc", "description": "HRRR-Alaska 3km"},
    # GFS family
    "gfs": {"product": "pgrb2.0p25", "description": "GFS 0.25deg Global"},
    "gfs_wave": {"product": "global.0p16", "description": "GFS Wave Global 0.16deg"},
    "gdas": {"product": "pgrb2.0p25", "description": "GDAS 0.25deg"},
    "graphcast": {"product": "pgrb2.0p25", "description": "GraphCast ML Global"},
    "aigfs": {"product": "sfc", "description": "AI-GFS Global"},
    # GEFS family
    "gefs": {"product": "atmos.5", "description": "GEFS Ensemble 0.5deg"},
    "gefs_reforecast": {"product": "Days:1-10", "description": "GEFS Reforecast"},
    "aigefs": {"product": "pgrb2sp25", "description": "AI-GEFS Ensemble"},
    "hgefs": {"product": "pgrb2sp25", "description": "High-Res GEFS Ensemble"},
    # ECMWF
    "ifs": {"product": "oper", "description": "ECMWF IFS Global"},
    "aifs": {"product": "oper", "description": "ECMWF AIFS ML Global"},
    # RAP
    "rap": {"product": "wrfprs", "description": "RAP 13km CONUS"},
    "rap_historical": {"product": "analysis", "description": "RAP Historical Archive"},
    "rap_ncei": {"product": "rap-130-13km", "description": "RAP NCEI Archive"},
    # NAM
    "nam": {"product": "awphys", "description": "NAM 12km CONUS"},
    # NBM
    "nbm": {"product": "co", "description": "National Blend of Models CONUS"},
    "nbmqmd": {"product": "co", "description": "NBM Quantile-Mapped"},
    # RRFS
    "rrfs": {"product": "natlev", "description": "RRFS 3km CONUS"},
    # RTMA / URMA
    "rtma": {"product": "anl", "description": "RTMA CONUS Analysis"},
    "rtma_ru": {"product": "anl", "description": "RTMA Rapid Update"},
    "rtma_ak": {"product": "anl", "description": "RTMA Alaska"},
    "urma": {"product": "anl", "description": "URMA CONUS Analysis"},
    "urma_ak": {"product": "anl", "description": "URMA Alaska"},
    # HiResW / HREF
    "hiresw": {"product": "arw_5km", "description": "HiResW 5km CONUS"},
    "href": {"product": "mean", "description": "HREF Ensemble Mean"},
    # CFS
    "cfs": {"product": "6_hourly", "description": "CFS Seasonal Forecast"},
    # HAFS
    "hafsa": {"product": "hafsa", "description": "HAFS-A Hurricane"},
    "hafsb": {"product": "hafsb", "description": "HAFS-B Hurricane"},
    # NEXRAD (special — not a GRIB model)
    "nexrad": {"product": "Level2", "description": "NEXRAD Level-II Radar"},
    # Canada (require variable= kwarg)
    "gdps": {"product": "15km/grib2/lat_lon", "description": "Canadian GDPS Global", "needs_variable": True, "needs_level": True},
    "hrdps": {"product": "continental", "description": "Canadian HRDPS 2.5km", "needs_variable": True, "needs_level": True},
    "rdps": {"product": "15km/grib2/lat_lon", "description": "Canadian RDPS 10km", "needs_variable": True, "needs_level": True},
    # US Navy
    "navgem_godae": {"product": "global", "description": "NAVGEM via GODAE"},
    "navgem_nomads": {"product": "none", "description": "NAVGEM via NOMADS"},
}

# ---------------------------------------------------------------------------
# Field aliases -- natural names -> GRIB search strings
# ---------------------------------------------------------------------------
FIELD_ALIASES = {
    # Surface temperature
    "temp": "TMP:2 m above ground",
    "temperature": "TMP:2 m above ground",
    "t2m": "TMP:2 m above ground",
    # Dewpoint
    "dewpoint": "DPT:2 m above ground",
    "td": "DPT:2 m above ground",
    "td2m": "DPT:2 m above ground",
    # Surface wind
    "wind": "UGRD:10 m above ground|VGRD:10 m above ground",
    "u10": "UGRD:10 m above ground",
    "v10": "VGRD:10 m above ground",
    "gust": "GUST:surface",
    # Pressure
    "pressure": "PRMSL:mean sea level",
    "mslp": "PRMSL:mean sea level",
    "altimeter": "PRES:surface",
    # Instability
    "cape": "CAPE:surface",
    "cin": "CIN:surface",
    "mlcape": "CAPE:90-0 mb above ground",
    "mlcin": "CIN:90-0 mb above ground",
    "mucape": "CAPE:255-0 mb above ground",
    "sbcape": "CAPE:surface",
    "sbcin": "CIN:surface",
    # Reflectivity
    "reflectivity": "REFC:entire atmosphere",
    "refl": "REFC:entire atmosphere",
    "composite_reflectivity": "REFC:entire atmosphere",
    # Precipitation
    "precip": "APCP:surface",
    "precipitation": "APCP:surface",
    "snow": "WEASD:surface",
    "frozen_precip": "CFRZR:surface",
    # Moisture
    "pwat": "PWAT:entire atmosphere",
    "precipitable_water": "PWAT:entire atmosphere",
    "rh": "RH:2 m above ground",
    "relative_humidity": "RH:2 m above ground",
    # Visibility
    "visibility": "VIS:surface",
    "vis": "VIS:surface",
    # Helicity / shear
    "srh": "HLCY:3000-0 m above ground",
    "srh03": "HLCY:3000-0 m above ground",
    "srh01": "HLCY:1000-0 m above ground",
    "helicity": "HLCY:3000-0 m above ground",
    "updraft_helicity": "MXUPHL:5000-2000 m above ground",
    "uh": "MXUPHL:5000-2000 m above ground",
    # Upper air
    "heights_500": "HGT:500 mb",
    "heights_250": "HGT:250 mb",
    "heights_850": "HGT:850 mb",
    "heights_700": "HGT:700 mb",
    "vorticity_500": "ABSV:500 mb",
    "jet": "UGRD:250 mb|VGRD:250 mb",
    "wind_250": "UGRD:250 mb|VGRD:250 mb",
    "wind_850": "UGRD:850 mb|VGRD:850 mb",
    "temp_850": "TMP:850 mb",
    "temp_700": "TMP:700 mb",
    "rh_700": "RH:700 mb",
    # Cloud
    "cloud_cover": "TCDC:entire atmosphere",
    "ceiling": "HGT:cloud ceiling",
    # Boundary layer
    "pbl_height": "HPBL:surface",
}

# IFS/ECMWF uses eccodes-style parameter names in their index
IFS_FIELD_ALIASES = {
    "temp": ":2t:sfc:",
    "temperature": ":2t:sfc:",
    "t2m": ":2t:sfc:",
    "dewpoint": ":2d:sfc:",
    "td": ":2d:sfc:",
    "wind": ":10u:sfc:|:10v:sfc:",
    "u10": ":10u:sfc:",
    "v10": ":10v:sfc:",
    "pressure": ":sp:sfc:",
    "mslp": ":msl:sfc:",
    "cape": ":cape:sfc:",
    "precip": ":tp:sfc:",
    "cloud_cover": ":tcc:sfc:",
    "pwat": ":tcwv:sfc:",
    "heights_500": ":z:500:pl:",
    "temp_850": ":t:850:pl:",
    "temp_500": ":t:500:pl:",
    "wind_850": ":u:850:pl:|:v:850:pl:",
    "jet": ":u:250:pl:|:v:250:pl:",
    "vorticity_500": ":vo:500:pl:",
}


# ---------------------------------------------------------------------------
# Upper-air / radiosonde station locations (lat, lon)
# ---------------------------------------------------------------------------
STATIONS = {
    # Central / Southern Plains
    "OKC": (35.23, -97.46),
    "OUN": (35.23, -97.46),
    "DDC": (37.77, -99.97),
    "AMA": (35.23, -101.71),
    "LBB": (33.67, -101.82),
    "MAF": (31.94, -102.19),
    "DRT": (29.37, -100.92),
    "CRP": (27.77, -97.51),
    "BRO": (25.91, -97.42),
    "SHV": (32.45, -93.84),
    "LIT": (34.73, -92.22),
    "SGF": (37.24, -93.39),
    "TOP": (39.07, -95.63),
    "OAX": (41.32, -96.37),
    # Texas / DFW
    "DFW": (32.90, -97.04),
    "FWD": (32.83, -97.30),
    "EPZ": (31.87, -106.70),
    # Southeast
    "JAN": (32.32, -90.08),
    "BMX": (33.17, -86.77),
    "FFC": (33.36, -84.57),
    "ATL": (33.64, -84.43),
    "GSP": (34.88, -82.22),
    "RNK": (37.21, -80.41),
    "MHX": (34.78, -76.88),
    "CHS": (32.90, -80.03),
    "JAX": (30.49, -81.69),
    "TBW": (27.71, -82.40),
    "MFL": (25.75, -80.38),
    "MIA": (25.79, -80.29),
    "KEY": (24.55, -81.75),
    "BNA": (36.12, -86.68),
    "SDF": (38.17, -85.74),
    # Northeast
    "IAD": (38.95, -77.45),
    "WAL": (37.94, -75.47),
    "OKX": (40.87, -72.87),
    "JFK": (40.64, -73.78),
    "ALY": (42.75, -73.80),
    "BUF": (42.94, -78.74),
    "CHH": (41.67, -69.97),
    "GYX": (43.89, -70.26),
    "CAR": (46.87, -68.02),
    # Great Lakes / Midwest
    "ORD": (41.97, -87.91),
    "ILX": (40.15, -89.34),
    "DVN": (41.61, -90.58),
    "MPX": (44.85, -93.57),
    "MSP": (44.88, -93.22),
    "STL": (38.75, -90.37),
    "APX": (44.91, -84.72),
    # Northern Plains
    "ABR": (45.45, -98.41),
    "BIS": (46.77, -100.75),
    "GGW": (48.21, -106.63),
    "TFX": (47.46, -111.38),
    # Rockies / Intermountain
    "DEN": (39.74, -104.99),
    "DNR": (39.77, -104.87),
    "GJT": (39.12, -108.53),
    "RIW": (43.07, -108.48),
    "SLC": (40.77, -111.97),
    "BOI": (43.57, -116.21),
    "LKN": (40.87, -115.73),
    "ABQ": (35.04, -106.62),
    "FGZ": (35.23, -111.82),
    "TUS": (32.12, -110.94),
    "VEF": (36.05, -115.18),
    "REV": (39.57, -119.80),
    # Pacific
    "SEA": (47.45, -122.31),
    "UIL": (47.94, -124.56),
    "OTX": (47.68, -117.63),
    "MFR": (42.37, -122.87),
    "OAK": (37.75, -122.22),
    "VBG": (34.74, -120.57),
    "NKX": (32.85, -117.12),
    "LAX": (33.94, -118.41),
}


def latest(model="hrrr"):
    """Find the latest available run for a model.

    Parameters
    ----------
    model : str
        Model name (e.g. ``"hrrr"``, ``"gfs"``).

    Returns
    -------
    rusbie.core.Herbie
        A Herbie object pointing at the latest available run.
    """
    from rusbie import HerbieLatest
    return HerbieLatest(model=model)


def resolve_alias(search, model=None):
    """Expand a field alias to a GRIB search string.

    If *search* is already a GRIB search string (contains ``:``) it is
    returned unchanged.  Otherwise it is looked up in ``FIELD_ALIASES``.

    Parameters
    ----------
    search : str
        Field alias (e.g. ``"temp"``) or GRIB search string.

    Returns
    -------
    str
        The resolved GRIB search string.

    Raises
    ------
    KeyError
        If the alias is not recognised.
    """
    if ":" in search:
        return search
    key = search.strip().lower().replace(" ", "_").replace("-", "_")
    # Check model-specific aliases first
    if model and model.lower() in ("ifs", "aifs", "ecmwf"):
        if key in IFS_FIELD_ALIASES:
            return IFS_FIELD_ALIASES[key]
    if key in FIELD_ALIASES:
        return FIELD_ALIASES[key]
    raise KeyError(
        f"Unknown field alias {search!r}.  Use a GRIB search string "
        f"(e.g. 'TMP:2 m') or one of: {', '.join(sorted(FIELD_ALIASES))}"
    )


def resolve_location(location):
    """Convert a station ID or coordinate tuple to (lat, lon).

    Parameters
    ----------
    location : str or tuple
        Station ID (e.g. ``"OKC"``) or ``(lat, lon)`` tuple.

    Returns
    -------
    tuple[float, float]
        ``(lat, lon)``
    """
    if isinstance(location, str):
        key = location.strip().upper()
        if key in STATIONS:
            return STATIONS[key]
        raise KeyError(
            f"Unknown station {location!r}.  Use (lat, lon) or one of: "
            f"{', '.join(sorted(STATIONS))}"
        )
    lat, lon = float(location[0]), float(location[1])
    return (lat, lon)


def guess_product(search, model="hrrr"):
    """Guess the appropriate model product from a GRIB search string.

    Heuristic: if the search mentions a pressure level (e.g. ``500 mb``)
    and the model supports a separate pressure-level product, return that.
    Otherwise return the default surface/analysis product.

    Parameters
    ----------
    search : str
        GRIB search string.
    model : str
        Model name.

    Returns
    -------
    str
        Product string.
    """
    s = search.lower()
    has_pressure_level = any(
        tok in s for tok in ("mb", "millibar", "isobaric")
    )

    m = model.lower()
    if m in ("hrrr", "hrrrak"):
        return "prs" if has_pressure_level else "sfc"
    if m in ("gfs", "gdas"):
        return "pgrb2.0p25"
    if m == "nam":
        return "awphys"
    if m == "rap":
        return "wrfprs"
    if m in ("rap_historical",):
        return "analysis"
    if m in ("rap_ncei",):
        return "rap-130-13km"
    if m in ("gefs", "aigefs", "hgefs"):
        return "atmos.5"
    if m in ("ifs", "aifs"):
        return "oper"
    if m in ("rrfs",):
        return "prslev" if has_pressure_level else "natlev"
    if m in models:
        return models[m]["product"]
    return "sfc"
