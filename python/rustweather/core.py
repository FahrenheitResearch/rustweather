"""Core one-liner functions -- the heart of rustweather.

Every function here follows the same pattern:
1. Resolve aliases and auto-detect model product
2. Create a Herbie object (via rusbie) and download
3. Open as xarray (via cfrust)
4. Optionally run calculations (via metrust)
5. Plot (via rustplots / matplotlib) or return data

All functions accept ``**kwargs`` forwarded to Herbie for maximum
flexibility (priority, save_dir, overwrite, verbose, etc.).
"""

from __future__ import annotations

import logging
from typing import Optional, Union

import numpy as np

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_herbie(model, date=None, fxx=0, product=None, search=None, **kw):
    """Create a Herbie object, auto-detecting product if needed.

    Parameters
    ----------
    model : str
        Model name.
    date : str or datetime, optional
        Init date.  ``None`` means latest.
    fxx : int
        Forecast hour.
    product : str, optional
        Product override.  ``None`` means auto-detect from *search*.
    search : str, optional
        GRIB search string (used for product guessing).
    **kw
        Extra kwargs forwarded to ``Herbie()``.

    Returns
    -------
    rusbie.core.Herbie
    """
    from rusbie import Herbie, HerbieLatest

    if product is None and search:
        from rustweather.models import guess_product
        product = guess_product(search, model)
    elif product is None:
        from rustweather.models import models as model_info
        m = model.lower()
        product = model_info.get(m, {}).get("product", "sfc")

    herbie_kw = dict(model=model, fxx=fxx, product=product, verbose=False)
    herbie_kw.update(kw)

    if date is None:
        try:
            return HerbieLatest(model=model, **{k: v for k, v in herbie_kw.items()
                                                 if k != "model"})
        except TimeoutError:
            raise RuntimeError(
                f"Could not find latest data for model={model!r}, "
                f"product={product!r}.  Try specifying a date."
            )
    else:
        return Herbie(date, **herbie_kw)


def _download_xarray(H, search):
    """Download a GRIB subset and return as xarray Dataset.

    Handles the case where ``H.xarray()`` returns a list of datasets
    (multiple hypercubes) by merging them.
    """
    import xarray as xr

    result = H.xarray(search)
    if isinstance(result, list):
        if len(result) == 1:
            return result[0]
        # Merge multiple hypercubes; drop conflicting coords
        try:
            return xr.merge(result, compat="override", join="outer")
        except Exception:
            log.warning("Could not merge %d datasets; returning the first.", len(result))
            return result[0]
    return result


def _resolve_search(search):
    """Resolve a possibly-aliased search string, handling pipe-separated multi-fields."""
    from rustweather.models import resolve_alias
    if "|" in search:
        parts = [resolve_alias(p.strip()) for p in search.split("|")]
        return "|".join(parts)
    return resolve_alias(search)


# ---------------------------------------------------------------------------
# plot()
# ---------------------------------------------------------------------------

def plot(model, search, **kwargs):
    """Plot any field from any model.  One line.

    Examples
    --------
    >>> plot("hrrr", "TMP:2 m")
    >>> plot("gfs", "HGT:500 mb")
    >>> plot("hrrr", "cape")
    >>> plot("hrrr", "REFC:entire")
    >>> plot("gfs", "UGRD:250 mb", date="2024-01-01 12:00", fxx=6)
    >>> plot("hrrr", "temp", area="mw", cmap="coolwarm")

    Parameters
    ----------
    model : str
        Model name (``"hrrr"``, ``"gfs"``, ``"nam"``, ...).
    search : str
        GRIB search string or alias (``"temp"``, ``"cape"``, ``"refl"``, ...).
    date : str or datetime, optional
        Init date.  Defaults to the latest available run.
    fxx : int
        Forecast hour.  Default 0.
    product : str, optional
        Model product override.
    area : str or tuple
        Map extent (``"us"``, ``"conus"``, ``"ne"``, or
        ``(west, east, south, north)``).  Default ``"us"``.
    save : str, optional
        File path to save instead of showing.
    native : bool
        Use Rust native renderer instead of matplotlib.
    cmap : str, optional
        Colormap name.
    levels : array-like, optional
        Contour levels.
    title : str, optional
        Custom title.
    barbs : bool or str
        Overlay wind barbs.
    figsize : tuple
        Figure size ``(width, height)`` in inches.
    **kwargs
        Extra args forwarded to Herbie (``priority``, ``verbose``, ...).
    """
    # Pop plotting kwargs before forwarding to Herbie
    date = kwargs.pop("date", None)
    fxx = kwargs.pop("fxx", 0)
    product = kwargs.pop("product", None)
    area = kwargs.pop("area", "us")
    save = kwargs.pop("save", None)
    native = kwargs.pop("native", False)
    cmap = kwargs.pop("cmap", None)
    levels = kwargs.pop("levels", None)
    title = kwargs.pop("title", None)
    barbs = kwargs.pop("barbs", False)
    figsize = kwargs.pop("figsize", (12, 8))

    resolved = _resolve_search(search)

    # Handle pipe-separated multi-field searches
    if "|" in resolved:
        searches = [s.strip() for s in resolved.split("|")]
    else:
        searches = [resolved]

    # Build Herbie and download
    H = _make_herbie(model, date=date, fxx=fxx, product=product,
                     search=searches[0], **kwargs)

    import xarray as xr
    datasets = []
    for s in searches:
        try:
            ds = _download_xarray(H, s)
            datasets.append(ds)
        except Exception as e:
            log.warning("Failed to download %r: %s", s, e)

    if not datasets:
        raise RuntimeError(f"Could not download any data for search={search!r}")

    if len(datasets) == 1:
        ds = datasets[0]
    else:
        try:
            ds = xr.merge(datasets, compat="override", join="outer")
        except Exception:
            ds = datasets[0]
            log.warning("Could not merge datasets; using first only.")

    # Overlay barbs from separate data if requested
    if barbs is True and "|" not in resolved:
        # Check if the dataset already has wind components
        vnames_upper = {str(v).upper() for v in ds.data_vars}
        has_wind = any("UGRD" in v or "VGRD" in v for v in vnames_upper)
        if not has_wind:
            try:
                wind_search = "UGRD:10 m above ground|VGRD:10 m above ground"
                for ws in wind_search.split("|"):
                    wind_ds = _download_xarray(H, ws.strip())
                    ds = xr.merge([ds, wind_ds], compat="override", join="outer")
            except Exception as e:
                log.warning("Could not download wind barbs: %s", e)

    from rustweather.plotting import auto_plot
    return auto_plot(ds, search=search, area=area, cmap=cmap, levels=levels,
                     title=title, barbs=barbs, save=save, native=native,
                     model=model, fxx=fxx, figsize=figsize)


# ---------------------------------------------------------------------------
# sounding()
# ---------------------------------------------------------------------------

def sounding(model, location, **kwargs):
    """Plot a SkewT sounding for a location.

    Downloads pressure-level T, Td, u, v from the model, extracts a
    vertical column at the nearest grid point, and renders with
    ``rustplots.SkewT``.

    Examples
    --------
    >>> sounding("hrrr", "OKC")
    >>> sounding("hrrr", (35.2, -97.5))
    >>> sounding("gfs", "DEN", fxx=24)

    Parameters
    ----------
    model : str
        Model name.
    location : str or tuple
        Station ID or ``(lat, lon)`` tuple.
    date : str or datetime, optional
        Init date (default: latest).
    fxx : int
        Forecast hour (default 0).
    save : str, optional
        Save to file instead of showing.
    title : str, optional
        Custom title.
    **kwargs
        Extra args forwarded to Herbie.
    """
    from rustweather.models import resolve_location

    date = kwargs.pop("date", None)
    fxx = kwargs.pop("fxx", 0)
    save = kwargs.pop("save", None)
    title = kwargs.pop("title", None)

    lat, lon = resolve_location(location)

    # Determine pressure-level product
    m = model.lower()
    if m in ("hrrr", "hrrrak"):
        product = "prs"
    elif m in ("gfs", "gdas"):
        product = "pgrb2.0p25"
    elif m == "nam":
        product = "awphys"
    elif m == "rap":
        product = "awp130"
    else:
        product = None  # Let Herbie figure it out

    H = _make_herbie(model, date=date, fxx=fxx, product=product, **kwargs)

    # Download temperature, dewpoint/RH, and wind at all pressure levels
    import xarray as xr

    # Build search for pressure-level data
    search_strings = [
        ":TMP:",
        ":DPT:|:RH:",
        ":UGRD:",
        ":VGRD:",
    ]

    datasets = {}
    for s in search_strings:
        try:
            ds = _download_xarray(H, s)
            for vname in ds.data_vars:
                datasets[vname] = ds[vname]
        except Exception as e:
            log.warning("Could not download %r: %s", s, e)

    if not datasets:
        raise RuntimeError(
            f"Could not download sounding data for model={model!r} at "
            f"({lat}, {lon}).  Check that the model has pressure-level data."
        )

    ds = xr.Dataset(datasets)

    # Find the nearest grid point
    try:
        lat_coord, lon_coord = None, None
        for name in ("latitude", "lat", "y"):
            if name in ds.coords:
                lat_coord = name
                break
        for name in ("longitude", "lon", "x"):
            if name in ds.coords:
                lon_coord = name
                break

        if lat_coord and lon_coord:
            # Handle 360-degree longitude convention
            target_lon = lon % 360 if ds[lon_coord].values.min() >= 0 else lon
            ds_point = ds.sel(
                **{lat_coord: lat, lon_coord: target_lon},
                method="nearest",
            )
        else:
            log.warning("Could not find lat/lon coords; using centroid.")
            ds_point = ds
    except Exception as e:
        log.warning("Nearest-point selection failed: %s", e)
        ds_point = ds

    # Extract profiles
    pressure, temperature, dewpoint, u_wind, v_wind = _extract_sounding_profiles(ds_point)

    if pressure is None or len(pressure) < 3:
        raise RuntimeError(
            "Insufficient pressure levels found for a sounding.  "
            "Ensure the model has multi-level pressure data."
        )

    # Sort by pressure descending (surface to top)
    sort_idx = np.argsort(pressure)[::-1]
    pressure = pressure[sort_idx]
    temperature = temperature[sort_idx]
    if dewpoint is not None:
        dewpoint = dewpoint[sort_idx]
    if u_wind is not None:
        u_wind = u_wind[sort_idx]
    if v_wind is not None:
        v_wind = v_wind[sort_idx]

    # Plot
    _plot_skewt(pressure, temperature, dewpoint, u_wind, v_wind,
                title=title, save=save, location=location, model=model, fxx=fxx)


def _extract_sounding_profiles(ds):
    """Extract T, Td, u, v profiles from a point dataset.

    Returns (pressure, temperature, dewpoint, u, v) as numpy arrays.
    Pressure in hPa, temperature/dewpoint in degC, wind in m/s.
    """
    pressure = None
    # Find pressure coordinate
    for name in ("isobaricInhPa", "isobaric", "level", "plev",
                 "pressure", "lv_ISBL0", "isobaric3"):
        if name in ds.coords or name in ds.dims:
            pressure = ds[name].values.astype(np.float64)
            break

    if pressure is None:
        log.warning("No pressure coordinate found.")
        return None, None, None, None, None

    # Convert Pa to hPa if needed
    if pressure.max() > 2000:
        pressure = pressure / 100.0

    # Temperature
    temperature = None
    for vname in ds.data_vars:
        vup = str(vname).upper()
        if "TMP" in vup or vup == "T" or "TEMPERATURE" in vup:
            vals = ds[vname].values.astype(np.float64).flatten()
            if len(vals) == len(pressure):
                # Convert K to C if needed
                if vals.mean() > 100:
                    vals = vals - 273.15
                temperature = vals
                break

    # Dewpoint or derive from RH
    dewpoint = None
    for vname in ds.data_vars:
        vup = str(vname).upper()
        if "DPT" in vup or "DEWPOINT" in vup or vup == "TD":
            vals = ds[vname].values.astype(np.float64).flatten()
            if len(vals) == len(pressure):
                if vals.mean() > 100:
                    vals = vals - 273.15
                dewpoint = vals
                break

    if dewpoint is None and temperature is not None:
        # Try RH
        for vname in ds.data_vars:
            vup = str(vname).upper()
            if "RH" in vup or "RELATIVE" in vup:
                rh = ds[vname].values.astype(np.float64).flatten()
                if len(rh) == len(pressure):
                    # Magnus formula: Td from T and RH
                    a, b = 17.271, 237.7
                    t_c = temperature
                    gamma = (a * t_c) / (b + t_c) + np.log(rh / 100.0)
                    dewpoint = (b * gamma) / (a - gamma)
                    break

    # Wind components
    u_wind = v_wind = None
    for vname in ds.data_vars:
        vup = str(vname).upper()
        if "UGRD" in vup or vup in ("U", "U_WIND"):
            vals = ds[vname].values.astype(np.float64).flatten()
            if len(vals) == len(pressure):
                u_wind = vals
        elif "VGRD" in vup or vup in ("V", "V_WIND"):
            vals = ds[vname].values.astype(np.float64).flatten()
            if len(vals) == len(pressure):
                v_wind = vals

    return pressure, temperature, dewpoint, u_wind, v_wind


def _plot_skewt(pressure, temperature, dewpoint, u_wind, v_wind,
                title=None, save=None, location=None, model="", fxx=None):
    """Render a SkewT diagram."""
    import matplotlib
    if save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from rustplots import SkewT

    fig = plt.figure(figsize=(9, 10))
    skew = SkewT(fig=fig, rotation=30)

    # Temperature (red)
    if temperature is not None:
        skew.plot(pressure, temperature, "r", linewidth=1.5, label="Temperature")

    # Dewpoint (green)
    if dewpoint is not None:
        skew.plot(pressure, dewpoint, "g", linewidth=1.5, label="Dewpoint")

    # Wind barbs
    if u_wind is not None and v_wind is not None:
        # Convert m/s to knots for display
        u_kt = u_wind * 1.94384
        v_kt = v_wind * 1.94384
        skew.plot_barbs(pressure, u_kt, v_kt)

    # Shade CAPE / CIN areas
    if temperature is not None and dewpoint is not None:
        try:
            from metrust.calc import parcel_profile as _parcel_profile
            profile = _parcel_profile(pressure, temperature[0], dewpoint[0])
            if hasattr(skew, "shade_cape"):
                skew.shade_cape(pressure, temperature, profile.magnitude
                                if hasattr(profile, "magnitude") else profile)
            if hasattr(skew, "shade_cin"):
                skew.shade_cin(pressure, temperature, profile.magnitude
                               if hasattr(profile, "magnitude") else profile)
        except Exception:
            pass  # CAPE shading is a nice-to-have

    # Labels
    if title is None:
        loc_str = location if isinstance(location, str) else f"({location[0]:.1f}, {location[1]:.1f})"
        parts = [model.upper(), loc_str]
        if fxx is not None and fxx > 0:
            parts.append(f"F{fxx:03d}")
        title = " | ".join(parts)

    skew.ax.set_title(title, fontsize=12, fontweight="bold")
    skew.ax.set_xlabel("Temperature (C)")
    skew.ax.set_ylabel("Pressure (hPa)")
    skew.ax.legend(loc="upper left", fontsize=8)

    plt.tight_layout()

    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        log.info("Saved sounding to %s", save)
        plt.close(fig)
    else:
        plt.show()


# ---------------------------------------------------------------------------
# hodograph()
# ---------------------------------------------------------------------------

def hodograph(model, location, **kwargs):
    """Plot a hodograph for a location.

    Examples
    --------
    >>> hodograph("hrrr", "OKC")
    >>> hodograph("gfs", (40, -105))

    Parameters
    ----------
    model : str
        Model name.
    location : str or tuple
        Station ID or ``(lat, lon)``.
    date : str or datetime, optional
        Init date.
    fxx : int
        Forecast hour.
    save : str, optional
        Save path.
    title : str, optional
        Custom title.
    """
    from rustweather.models import resolve_location

    date = kwargs.pop("date", None)
    fxx = kwargs.pop("fxx", 0)
    save = kwargs.pop("save", None)
    title = kwargs.pop("title", None)

    lat, lon = resolve_location(location)

    # Re-use sounding data path
    m = model.lower()
    if m in ("hrrr", "hrrrak"):
        product = "prs"
    elif m in ("gfs", "gdas"):
        product = "pgrb2.0p25"
    else:
        product = None

    H = _make_herbie(model, date=date, fxx=fxx, product=product, **kwargs)

    import xarray as xr
    datasets = {}
    for s in [":UGRD:", ":VGRD:", ":HGT:"]:
        try:
            ds = _download_xarray(H, s)
            for vname in ds.data_vars:
                datasets[vname] = ds[vname]
        except Exception as e:
            log.warning("Could not download %r: %s", s, e)

    if not datasets:
        raise RuntimeError("Could not download wind profile data.")

    ds = xr.Dataset(datasets)

    # Nearest grid point
    try:
        for name in ("latitude", "lat", "y"):
            if name in ds.coords:
                lat_coord = name
                break
        for name in ("longitude", "lon", "x"):
            if name in ds.coords:
                lon_coord = name
                break
        target_lon = lon % 360 if ds[lon_coord].values.min() >= 0 else lon
        ds_point = ds.sel(**{lat_coord: lat, lon_coord: target_lon}, method="nearest")
    except Exception:
        ds_point = ds

    # Extract profiles
    pressure, _, _, u_wind, v_wind = _extract_sounding_profiles(ds_point)

    # Also try to get height for colormapping
    height = None
    for vname in ds_point.data_vars:
        vup = str(vname).upper()
        if "HGT" in vup or "GEOPOTENTIAL" in vup:
            vals = ds_point[vname].values.astype(np.float64).flatten()
            if len(vals) == len(pressure):
                height = vals
                break

    if u_wind is None or v_wind is None or len(u_wind) < 3:
        raise RuntimeError("Insufficient wind data for hodograph.")

    # Sort by pressure descending
    sort_idx = np.argsort(pressure)[::-1]
    pressure = pressure[sort_idx]
    u_wind = u_wind[sort_idx]
    v_wind = v_wind[sort_idx]
    if height is not None:
        height = height[sort_idx]

    _plot_hodograph(pressure, u_wind, v_wind, height=height,
                    title=title, save=save, location=location,
                    model=model, fxx=fxx)


def _plot_hodograph(pressure, u, v, height=None, title=None, save=None,
                    location=None, model="", fxx=None):
    """Render a hodograph."""
    import matplotlib
    if save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from rustplots import Hodograph

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(1, 1, 1)
    hodo = Hodograph(ax=ax, component_range=60)

    if hasattr(hodo, "add_grid"):
        hodo.add_grid(increment=10)

    # Colour by height if available
    if height is not None:
        # Standard layers: 0-1km, 1-3km, 3-6km, 6-9km, 9km+
        intervals = np.array([0, 1000, 3000, 6000, 9000, 12000])
        colors = ["#E04040", "#E0A040", "#40C040", "#4080E0", "#A040E0"]
        try:
            hodo.plot_colormapped(u, v, height, intervals=intervals, colors=colors)
        except Exception:
            hodo.plot(u, v, linewidth=1.5)
    else:
        hodo.plot(u, v, linewidth=1.5)

    if title is None:
        loc_str = location if isinstance(location, str) else f"({location[0]:.1f}, {location[1]:.1f})"
        parts = [model.upper(), loc_str, "Hodograph"]
        if fxx is not None and fxx > 0:
            parts.append(f"F{fxx:03d}")
        title = " | ".join(parts)

    ax.set_title(title, fontsize=12, fontweight="bold")
    plt.tight_layout()

    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()


# ---------------------------------------------------------------------------
# surface()
# ---------------------------------------------------------------------------

def surface(model, fields=None, **kwargs):
    """Plot a standard surface analysis map.

    Default fields: 2m temperature (filled contours), MSLP (contour lines),
    10m wind (barbs).

    Examples
    --------
    >>> surface("hrrr")
    >>> surface("gfs", ["TMP", "MSLP"])

    Parameters
    ----------
    model : str
        Model name.
    fields : list[str], optional
        Override default fields.
    date, fxx, area, save, cmap, title, figsize
        See :func:`plot`.
    """
    date = kwargs.pop("date", None)
    fxx = kwargs.pop("fxx", 0)
    area = kwargs.pop("area", "us")
    save = kwargs.pop("save", None)
    cmap = kwargs.pop("cmap", None)
    title = kwargs.pop("title", None)
    figsize = kwargs.pop("figsize", (14, 9))
    native = kwargs.pop("native", False)

    if fields is None:
        fields = ["TMP:2 m above ground", "PRMSL:mean sea level",
                  "UGRD:10 m above ground", "VGRD:10 m above ground"]

    H = _make_herbie(model, date=date, fxx=fxx, search=fields[0], **kwargs)

    import xarray as xr
    datasets = []
    for f in fields:
        try:
            ds = _download_xarray(H, f)
            datasets.append(ds)
        except Exception as e:
            log.warning("Failed to download %r: %s", f, e)

    if not datasets:
        raise RuntimeError("Could not download any surface data.")

    ds = xr.merge(datasets, compat="override", join="outer")

    if title is None:
        title = f"{model.upper()} Surface Analysis"
        if fxx > 0:
            title += f" F{fxx:03d}"

    from rustweather.plotting import auto_plot
    return auto_plot(ds, search="TMP|PRMSL|UGRD|VGRD", area=area, cmap=cmap,
                     title=title, barbs=True, save=save, native=native,
                     model=model, fxx=fxx, figsize=figsize)


# ---------------------------------------------------------------------------
# upperair()
# ---------------------------------------------------------------------------

def upperair(model, level=500, fields=None, **kwargs):
    """Plot upper-air analysis at a pressure level.

    Defaults:
        500 mb -- heights + absolute vorticity
        250 mb -- heights + wind speed (jet stream)
        850 mb -- temperature + heights

    Examples
    --------
    >>> upperair("gfs", 500)
    >>> upperair("gfs", 250)
    >>> upperair("hrrr", 850)

    Parameters
    ----------
    model : str
        Model name.
    level : int
        Pressure level in mb.
    fields : list[str], optional
        Override default search strings.
    """
    date = kwargs.pop("date", None)
    fxx = kwargs.pop("fxx", 0)
    area = kwargs.pop("area", "us")
    save = kwargs.pop("save", None)
    cmap = kwargs.pop("cmap", None)
    title = kwargs.pop("title", None)
    figsize = kwargs.pop("figsize", (14, 9))
    native = kwargs.pop("native", False)

    if fields is None:
        if level == 500:
            fields = [f"HGT:{level} mb", f"ABSV:{level} mb",
                      f"UGRD:{level} mb", f"VGRD:{level} mb"]
        elif level == 250:
            fields = [f"HGT:{level} mb",
                      f"UGRD:{level} mb", f"VGRD:{level} mb"]
        elif level == 850:
            fields = [f"TMP:{level} mb", f"HGT:{level} mb",
                      f"UGRD:{level} mb", f"VGRD:{level} mb"]
        else:
            fields = [f"HGT:{level} mb", f"TMP:{level} mb",
                      f"UGRD:{level} mb", f"VGRD:{level} mb"]

    # Force pressure-level product
    m = model.lower()
    if m in ("hrrr", "hrrrak"):
        product = "prs"
    else:
        product = None

    H = _make_herbie(model, date=date, fxx=fxx, product=product,
                     search=fields[0], **kwargs)

    import xarray as xr
    datasets = []
    for f in fields:
        try:
            ds = _download_xarray(H, f)
            datasets.append(ds)
        except Exception as e:
            log.warning("Failed to download %r: %s", f, e)

    if not datasets:
        raise RuntimeError(f"Could not download {level} mb data.")

    ds = xr.merge(datasets, compat="override", join="outer")

    if title is None:
        title = f"{model.upper()} {level} mb Analysis"
        if fxx > 0:
            title += f" F{fxx:03d}"

    from rustweather.plotting import auto_plot
    return auto_plot(ds, search="|".join(fields), area=area, cmap=cmap,
                     title=title, barbs=True, save=save, native=native,
                     model=model, fxx=fxx, figsize=figsize)


# ---------------------------------------------------------------------------
# severe()
# ---------------------------------------------------------------------------

def severe(model, **kwargs):
    """Plot severe weather parameters.

    Downloads CAPE, CIN, SRH, bulk shear, and updraft helicity; plots
    a multi-panel summary or a single composite.

    Examples
    --------
    >>> severe("hrrr")
    >>> severe("hrrr", params=["CAPE", "STP", "SRH"])

    Parameters
    ----------
    model : str
        Model name.
    params : list[str], optional
        Which severe parameters to plot.  Default: CAPE, SRH, shear.
    """
    date = kwargs.pop("date", None)
    fxx = kwargs.pop("fxx", 0)
    area = kwargs.pop("area", "us")
    save = kwargs.pop("save", None)
    title = kwargs.pop("title", None)
    params = kwargs.pop("params", None)
    figsize = kwargs.pop("figsize", (16, 12))

    if params is None:
        params = ["CAPE", "SRH", "SHEAR"]

    # Map param names to GRIB search strings
    search_map = {
        "CAPE": "CAPE:surface",
        "CIN": "CIN:surface",
        "SRH": "HLCY:3000-0 m above ground level",
        "SRH01": "HLCY:1000-0 m above ground level",
        "SHEAR": "UGRD:0-6000 m above ground level|VGRD:0-6000 m above ground level",
        "UH": "MXUPHL:5000-2000 m above ground level",
        "STP": "CAPE:surface",  # STP needs to be calculated
    }

    H = _make_herbie(model, date=date, fxx=fxx, search="CAPE:surface", **kwargs)

    import matplotlib
    if save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n_panels = len(params)
    cols = min(n_panels, 3)
    rows = (n_panels + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=figsize)
    if n_panels == 1:
        axes = [axes]
    elif hasattr(axes, "flatten"):
        axes = axes.flatten()

    from rustweather.plotting import _parse_area, _get_lat_lon, _default_cmap

    for i, param in enumerate(params):
        if i >= len(axes):
            break
        ax = axes[i]

        search_str = search_map.get(param.upper(), f"{param}:surface")
        searches = [s.strip() for s in search_str.split("|")]

        import xarray as xr
        panel_datasets = []
        for s in searches:
            try:
                ds = _download_xarray(H, s)
                panel_datasets.append(ds)
            except Exception as e:
                log.warning("Failed to download %r: %s", s, e)

        if not panel_datasets:
            ax.text(0.5, 0.5, f"No data: {param}", ha="center", va="center",
                    transform=ax.transAxes, fontsize=12)
            ax.set_title(param)
            continue

        ds = xr.merge(panel_datasets, compat="override", join="outer") if len(panel_datasets) > 1 else panel_datasets[0]

        # Plot
        var_names = list(ds.data_vars)
        if not var_names:
            continue

        da = ds[var_names[0]]
        data = da.values
        while data.ndim > 2:
            data = data[0]

        try:
            lat, lon = _get_lat_lon(ds)
            if lon.ndim == 1 and lat.ndim == 1:
                lon, lat = np.meshgrid(lon, lat)
        except ValueError:
            lat = np.arange(data.shape[0])
            lon = np.arange(data.shape[1])

        chosen_cmap = _default_cmap(var_names, search_str)
        cf = ax.contourf(lon, lat, data, levels=20, cmap=chosen_cmap, extend="both")
        plt.colorbar(cf, ax=ax, shrink=0.7)
        ax.set_title(f"{param.upper()}", fontsize=11, fontweight="bold")

    # Remove unused axes
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    if title is None:
        title = f"{model.upper()} Severe Weather Parameters"
        if fxx > 0:
            title += f" F{fxx:03d}"
    fig.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout()

    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()


# ---------------------------------------------------------------------------
# forecast()
# ---------------------------------------------------------------------------

def forecast(model, search, hours=None, **kwargs):
    """Plot a field across multiple forecast hours.

    Downloads the same field at each forecast hour and tiles them
    in a multi-panel figure.

    Examples
    --------
    >>> forecast("hrrr", "TMP:2 m", hours=range(0, 19))
    >>> forecast("gfs", "APCP:surface", hours=[0, 6, 12, 18, 24])

    Parameters
    ----------
    model : str
        Model name.
    search : str
        GRIB search string or alias.
    hours : iterable[int], optional
        Forecast hours.  Default: model-dependent range.
    """
    date = kwargs.pop("date", None)
    area = kwargs.pop("area", "us")
    save = kwargs.pop("save", None)
    cmap = kwargs.pop("cmap", None)
    title = kwargs.pop("title", None)
    figsize = kwargs.pop("figsize", (18, 12))

    resolved = _resolve_search(search)

    if hours is None:
        m = model.lower()
        if m in ("hrrr", "hrrrak", "rap"):
            hours = range(0, 19, 3)
        elif m in ("gfs",):
            hours = range(0, 25, 6)
        else:
            hours = range(0, 25, 6)

    hours = list(hours)
    n = len(hours)
    cols = min(n, 4)
    rows = (n + cols - 1) // cols

    import matplotlib
    if save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(rows, cols, figsize=figsize)
    if n == 1:
        axes = np.array([axes])
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    from rustweather.plotting import _get_lat_lon, _default_cmap

    vmin = vmax = None  # Compute shared colour range

    # First pass: download all data
    all_data = []
    for fxx in hours:
        try:
            H = _make_herbie(model, date=date, fxx=fxx, search=resolved, **kwargs)
            ds = _download_xarray(H, resolved)
            all_data.append((fxx, ds))
        except Exception as e:
            log.warning("F%03d: %s", fxx, e)
            all_data.append((fxx, None))

    # Compute global min/max
    for fxx, ds in all_data:
        if ds is None:
            continue
        for vname in ds.data_vars:
            vals = ds[vname].values
            while vals.ndim > 2:
                vals = vals[0]
            lo, hi = np.nanmin(vals), np.nanmax(vals)
            if vmin is None or lo < vmin:
                vmin = lo
            if vmax is None or hi > vmax:
                vmax = hi

    # Second pass: plot
    for i, (fxx, ds) in enumerate(all_data):
        if i >= len(axes):
            break
        ax = axes[i]

        if ds is None:
            ax.text(0.5, 0.5, f"F{fxx:03d}\nNo data", ha="center", va="center",
                    transform=ax.transAxes)
            ax.set_title(f"F{fxx:03d}")
            continue

        var_names = list(ds.data_vars)
        if not var_names:
            continue

        da = ds[var_names[0]]
        data = da.values
        while data.ndim > 2:
            data = data[0]

        try:
            lat, lon = _get_lat_lon(ds)
            if lon.ndim == 1 and lat.ndim == 1:
                lon, lat = np.meshgrid(lon, lat)
        except ValueError:
            lat = np.arange(data.shape[0])
            lon = np.arange(data.shape[1])

        chosen_cmap = cmap or _default_cmap(var_names, search)
        try:
            plt.colormaps[chosen_cmap]
        except (KeyError, ValueError):
            chosen_cmap = "viridis"

        cf = ax.contourf(lon, lat, data, levels=20, cmap=chosen_cmap,
                         vmin=vmin, vmax=vmax, extend="both")
        ax.set_title(f"F{fxx:03d}", fontsize=10, fontweight="bold")

    # Shared colorbar
    if all_data and any(ds is not None for _, ds in all_data):
        fig.colorbar(cf, ax=axes.tolist() if hasattr(axes, "tolist") else list(axes),
                     shrink=0.6, pad=0.02)

    for j in range(len(all_data), len(axes)):
        fig.delaxes(axes[j])

    if title is None:
        title = f"{model.upper()} | {search} | Forecast Sequence"
    fig.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout()

    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()


# ---------------------------------------------------------------------------
# obs()
# ---------------------------------------------------------------------------

def obs(source="metar", **kwargs):
    """Plot current observations (placeholder).

    This function is a stub for future integration with real-time
    observation feeds (METAR, MOS, buoy, etc.).

    Parameters
    ----------
    source : str
        Observation source type.
    """
    raise NotImplementedError(
        "Real-time observation plotting is not yet implemented.  "
        "Use get() with rtma/urma models for gridded analysis instead."
    )


# ---------------------------------------------------------------------------
# cross_section()
# ---------------------------------------------------------------------------

def cross_section(model, search, start, end, **kwargs):
    """Plot a vertical cross-section between two points.

    Examples
    --------
    >>> cross_section("hrrr", "TMP", "OKC", "DFW")
    >>> cross_section("gfs", "RH", (35, -100), (40, -90))

    Parameters
    ----------
    model : str
        Model name.
    search : str
        GRIB search string or alias for the field to cross-section.
    start, end : str or tuple
        Start and end points (station ID or (lat, lon)).
    """
    from rustweather.models import resolve_location

    date = kwargs.pop("date", None)
    fxx = kwargs.pop("fxx", 0)
    save = kwargs.pop("save", None)
    title = kwargs.pop("title", None)
    n_points = kwargs.pop("n_points", 100)

    start_lat, start_lon = resolve_location(start)
    end_lat, end_lon = resolve_location(end)

    resolved = _resolve_search(search)

    # Force pressure-level product
    m = model.lower()
    if m in ("hrrr", "hrrrak"):
        product = "prs"
    else:
        product = None

    H = _make_herbie(model, date=date, fxx=fxx, product=product,
                     search=resolved, **kwargs)
    ds = _download_xarray(H, resolved)

    # Interpolate along the cross-section path
    lats = np.linspace(start_lat, end_lat, n_points)
    lons = np.linspace(start_lon, end_lon, n_points)
    distances = np.sqrt(
        ((lats - start_lat) * 111.0) ** 2 +
        ((lons - start_lon) * 111.0 * np.cos(np.radians(start_lat))) ** 2
    )

    import xarray as xr

    # Find lat/lon coord names
    lat_coord = lon_coord = None
    for name in ("latitude", "lat", "y"):
        if name in ds.coords:
            lat_coord = name
            break
    for name in ("longitude", "lon", "x"):
        if name in ds.coords:
            lon_coord = name
            break

    if lat_coord is None or lon_coord is None:
        raise ValueError("Cannot find lat/lon coordinates for cross-section.")

    # Interpolate
    target_lons = lons % 360 if ds[lon_coord].values.min() >= 0 else lons
    path_ds = ds.interp(
        **{lat_coord: xr.DataArray(lats, dims="points"),
           lon_coord: xr.DataArray(target_lons, dims="points")},
        method="linear",
    )

    # Find pressure dimension
    pressure = None
    pres_dim = None
    for name in ("isobaricInhPa", "isobaric", "level", "plev", "pressure"):
        if name in path_ds.dims or name in path_ds.coords:
            pressure = path_ds[name].values.astype(np.float64)
            pres_dim = name
            break

    if pressure is None:
        raise ValueError("No pressure coordinate found for cross-section.")

    if pressure.max() > 2000:
        pressure = pressure / 100.0

    # Plot
    import matplotlib
    if save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    var_names = list(path_ds.data_vars)
    if not var_names:
        raise RuntimeError("No data variables in cross-section dataset.")

    vname = var_names[0]
    data = path_ds[vname].values
    if data.ndim > 2:
        data = data.squeeze()

    from rustweather.plotting import _default_cmap

    fig, ax = plt.subplots(figsize=(12, 6))
    dist_grid, pres_grid = np.meshgrid(distances, pressure)
    cf = ax.contourf(dist_grid, pres_grid, data, levels=20,
                     cmap=_default_cmap([vname], search), extend="both")
    plt.colorbar(cf, ax=ax, shrink=0.8)

    ax.set_ylim(pressure.max(), pressure.min())
    ax.set_yscale("log")
    ax.set_ylabel("Pressure (hPa)")
    ax.set_xlabel("Distance (km)")

    start_str = start if isinstance(start, str) else f"({start[0]:.1f}, {start[1]:.1f})"
    end_str = end if isinstance(end, str) else f"({end[0]:.1f}, {end[1]:.1f})"

    if title is None:
        title = f"{model.upper()} | {search} | {start_str} to {end_str}"
    ax.set_title(title, fontsize=12, fontweight="bold")
    plt.tight_layout()

    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

def get(model, search, **kwargs):
    """Download and return xarray Dataset.  No plotting.

    Examples
    --------
    >>> ds = get("hrrr", "TMP:2 m")
    >>> ds = get("gfs", "HGT:500 mb", date="2024-01-01", fxx=12)

    Parameters
    ----------
    model : str
        Model name.
    search : str
        GRIB search string or alias.
    date : str or datetime, optional
        Init date.
    fxx : int
        Forecast hour.
    product : str, optional
        Product override.

    Returns
    -------
    xarray.Dataset
    """
    date = kwargs.pop("date", None)
    fxx = kwargs.pop("fxx", 0)
    product = kwargs.pop("product", None)

    resolved = _resolve_search(search)

    if "|" in resolved:
        searches = [s.strip() for s in resolved.split("|")]
    else:
        searches = [resolved]

    H = _make_herbie(model, date=date, fxx=fxx, product=product,
                     search=searches[0], **kwargs)

    import xarray as xr
    datasets = []
    for s in searches:
        try:
            ds = _download_xarray(H, s)
            datasets.append(ds)
        except Exception as e:
            log.warning("Failed to download %r: %s", s, e)

    if not datasets:
        raise RuntimeError(f"Could not download data for search={search!r}")

    if len(datasets) == 1:
        return datasets[0]

    try:
        return xr.merge(datasets, compat="override", join="outer")
    except Exception:
        log.warning("Could not merge datasets; returning the first.")
        return datasets[0]


# ---------------------------------------------------------------------------
# calc()
# ---------------------------------------------------------------------------

def calc(model, function, **kwargs):
    """Download data and run a metrust calculation.

    Downloads the appropriate fields for the requested calculation,
    then calls the corresponding ``metrust.calc`` function.

    Examples
    --------
    >>> ds = calc("hrrr", "cape_cin")
    >>> ds = calc("hrrr", "bulk_shear", depth=6000)
    >>> ds = calc("hrrr", "bunkers_storm_motion")

    Parameters
    ----------
    model : str
        Model name.
    function : str
        Name of the metrust.calc function to call.
    date : str or datetime, optional
        Init date.
    fxx : int
        Forecast hour.
    **kwargs
        Extra arguments passed to the metrust function (``depth``,
        ``bottom``, ``top``, etc.) and to Herbie.

    Returns
    -------
    Result from the metrust.calc function (varies by function).
    """
    import metrust.calc as mc

    date = kwargs.pop("date", None)
    fxx = kwargs.pop("fxx", 0)
    location = kwargs.pop("location", None)

    # Function-specific data requirements
    _FUNC_SEARCHES = {
        "cape_cin": [":TMP:", ":DPT:|:RH:"],
        "bulk_shear": [":UGRD:", ":VGRD:", ":HGT:"],
        "bunkers_storm_motion": [":UGRD:", ":VGRD:", ":HGT:"],
        "storm_relative_helicity": [":UGRD:", ":VGRD:", ":HGT:"],
        "significant_tornado_parameter": [
            "CAPE:surface", "HLCY:1000-0 m above ground",
            ":UGRD:", ":VGRD:", ":HGT:",
        ],
        "supercell_composite_parameter": [
            "CAPE:surface", "HLCY:3000-0 m above ground",
            ":UGRD:", ":VGRD:",
        ],
        "dewpoint_from_relative_humidity": [":TMP:", ":RH:"],
    }

    func_name = function.strip().lower()
    if not hasattr(mc, func_name):
        available = [f for f in dir(mc) if not f.startswith("_") and callable(getattr(mc, f, None))]
        raise ValueError(
            f"Unknown metrust function {function!r}.  Available: "
            f"{', '.join(available[:20])}..."
        )

    searches = _FUNC_SEARCHES.get(func_name, [":TMP:", ":DPT:"])

    # Force pressure-level product
    m = model.lower()
    if m in ("hrrr", "hrrrak"):
        product = "prs"
    else:
        product = None

    herbie_kw = {k: v for k, v in kwargs.items()
                 if k in ("priority", "verbose", "save_dir", "overwrite", "source")}
    calc_kw = {k: v for k, v in kwargs.items() if k not in herbie_kw}

    H = _make_herbie(model, date=date, fxx=fxx, product=product,
                     search=searches[0], **herbie_kw)

    import xarray as xr
    datasets = {}
    for s in searches:
        try:
            ds = _download_xarray(H, s)
            for vname in ds.data_vars:
                datasets[vname] = ds[vname]
        except Exception as e:
            log.warning("Could not download %r: %s", s, e)

    if not datasets:
        raise RuntimeError(f"Could not download data for calc({function!r})")

    ds = xr.Dataset(datasets)

    # Extract at location if specified
    if location is not None:
        from rustweather.models import resolve_location
        lat, lon = resolve_location(location)

        for name in ("latitude", "lat", "y"):
            if name in ds.coords:
                lat_coord = name
                break
        for name in ("longitude", "lon", "x"):
            if name in ds.coords:
                lon_coord = name
                break

        target_lon = lon % 360 if ds[lon_coord].values.min() >= 0 else lon
        ds = ds.sel(**{lat_coord: lat, lon_coord: target_lon}, method="nearest")

    # Extract profiles and call the function
    pressure, temperature, dewpoint, u_wind, v_wind = _extract_sounding_profiles(ds)

    func = getattr(mc, func_name)

    if func_name == "cape_cin":
        if temperature is None or dewpoint is None:
            raise RuntimeError("Need temperature and dewpoint for CAPE/CIN.")
        return func(pressure, temperature, dewpoint, **calc_kw)

    elif func_name in ("bulk_shear", "bunkers_storm_motion", "storm_relative_helicity"):
        if u_wind is None or v_wind is None:
            raise RuntimeError("Need wind data for this calculation.")
        # Extract height
        height = None
        for vname in ds.data_vars:
            vup = str(vname).upper()
            if "HGT" in vup:
                height = ds[vname].values.astype(np.float64).flatten()
                break
        if func_name == "bulk_shear":
            return func(pressure, u_wind, v_wind, height=height, **calc_kw)
        elif func_name == "bunkers_storm_motion":
            return func(pressure, u_wind, v_wind, height)
        else:
            return func(height, u_wind, v_wind, **calc_kw)

    elif func_name == "significant_tornado_parameter":
        return func(**calc_kw)

    elif func_name == "dewpoint_from_relative_humidity":
        if temperature is None:
            raise RuntimeError("Need temperature for dewpoint calculation.")
        for vname in ds.data_vars:
            vup = str(vname).upper()
            if "RH" in vup:
                rh = ds[vname].values.astype(np.float64).flatten()
                return func(temperature, rh, **calc_kw)
        raise RuntimeError("Need relative humidity data.")

    else:
        # Generic: try passing what we have
        try:
            return func(pressure, temperature, dewpoint, **calc_kw)
        except TypeError:
            return func(pressure, u_wind, v_wind, **calc_kw)
