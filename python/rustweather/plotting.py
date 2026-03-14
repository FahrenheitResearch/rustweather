"""Internal plotting helpers -- auto-detection and rendering.

This module decides *how* to visualise a given xarray Dataset based on
the variable names and the caller's preferences, then delegates to either
matplotlib (via rustplots) or the native Rust renderer.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Variable classification
# ---------------------------------------------------------------------------
_WIND_VARS = {"UGRD", "VGRD", "u-component_of_wind", "v-component_of_wind",
               "u10", "v10", "u", "v", "10u", "10v"}
_CONTOUR_LINE_VARS = {"HGT", "PRMSL", "MSLMA", "MSLET", "gh", "msl",
                       "Geopotential_height_isobaric", "Pressure_reduced_to_MSL_msl"}
_BARB_SEARCH_TOKENS = {"UGRD", "VGRD", "wind"}


def _classify_vars(var_names, search=""):
    """Return (scalar_vars, u_var, v_var, is_contour_line)."""
    u_var = v_var = None
    scalar_vars = []
    for v in var_names:
        vup = v.upper() if isinstance(v, str) else str(v)
        if "UGRD" in vup or vup in ("U", "U10", "10U", "U-COMPONENT_OF_WIND"):
            u_var = v
        elif "VGRD" in vup or vup in ("V", "V10", "10V", "V-COMPONENT_OF_WIND"):
            v_var = v
        else:
            scalar_vars.append(v)

    is_contour_line = False
    if scalar_vars:
        first = str(scalar_vars[0]).upper()
        if any(tok in first for tok in ("HGT", "PRMSL", "MSLMA", "MSLET")):
            is_contour_line = True
    if "PRMSL" in search.upper() or "HGT" in search.upper():
        is_contour_line = True

    return scalar_vars, u_var, v_var, is_contour_line


def _get_lat_lon(ds):
    """Extract latitude and longitude arrays from a dataset."""
    lat = lon = None
    for name in ("latitude", "lat", "y", "gridlat_0", "XLAT"):
        if name in ds.coords or name in ds.dims:
            lat = ds[name].values
            break
    for name in ("longitude", "lon", "x", "gridlon_0", "XLONG"):
        if name in ds.coords or name in ds.dims:
            lon = ds[name].values
            break
    if lat is None or lon is None:
        raise ValueError(
            "Could not find lat/lon coordinates in the dataset. "
            f"Available coords: {list(ds.coords)}"
        )
    return lat, lon


def _parse_area(area):
    """Convert area specification to (west, east, south, north) or None.

    Accepts a string name (looked up from rustplots named_areas) or a
    tuple of four floats.  Returns None for 'global' / None input.
    """
    if area is None:
        return None
    if isinstance(area, (list, tuple)) and len(area) == 4:
        return tuple(float(x) for x in area)
    if isinstance(area, str):
        try:
            from rustplots.declarative import named_areas
            key = area.strip().lower()
            if key in named_areas:
                val = named_areas[key]
                if val == "global":
                    return None
                return tuple(val)
        except ImportError:
            pass
        # Fallback hard-coded extents
        _fallback = {
            "us": (-130, -60, 20, 55),
            "conus": (-125, -66, 23, 50),
            "ne": (-85, -65, 37, 48),
            "se": (-95, -74, 24, 38),
            "mw": (-105, -82, 35, 50),
            "sp": (-110, -87, 25, 40),
            "np": (-115, -90, 40, 52),
            "sw": (-125, -100, 28, 43),
            "nw": (-130, -108, 38, 52),
        }
        key = area.strip().lower()
        if key in _fallback:
            return _fallback[key]
        if key == "global":
            return None
    return None


def _auto_title(search, var_names, model, fxx):
    """Build a sensible default title."""
    parts = []
    parts.append(model.upper())
    if fxx is not None and fxx > 0:
        parts.append(f"F{fxx:03d}")
    if search:
        parts.append(search)
    elif var_names:
        parts.append(", ".join(str(v) for v in var_names[:3]))
    return " | ".join(parts)


def _default_cmap(var_names, search=""):
    """Pick a sensible default colormap based on the variable."""
    s = (search + " " + " ".join(str(v) for v in var_names)).upper()
    if "TMP" in s or "TEMP" in s or "T2M" in s:
        return "RdYlBu_r"
    if "CAPE" in s:
        return "YlOrRd"
    if "CIN" in s:
        return "BuPu"
    if "REFC" in s or "REFL" in s or "DBZ" in s:
        return "NWSReflectivity"
    if "APCP" in s or "PRECIP" in s or "WEASD" in s:
        return "YlGnBu"
    if "RH" in s or "HUMIDITY" in s:
        return "BrBG"
    if "PWAT" in s:
        return "GnBu"
    if "HGT" in s:
        return "inferno"
    if "ABSV" in s or "VORT" in s:
        return "PiYG_r"
    if "HLCY" in s or "SRH" in s:
        return "Reds"
    if "VIS" in s:
        return "gray_r"
    if "WIND" in s or "UGRD" in s or "WSPD" in s:
        return "plasma"
    return "viridis"


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def auto_plot(ds, search="", area="us", cmap=None, levels=None, title=None,
              barbs=False, save=None, native=False, model="", fxx=None,
              figsize=(12, 8)):
    """Auto-detect and render the right plot type.

    Parameters
    ----------
    ds : xarray.Dataset
        The data to plot.
    search : str
        The original GRIB search string (used for heuristics).
    area : str or tuple
        Map extent.
    cmap : str, optional
        Colormap override.
    levels : array-like, optional
        Contour level override.
    title : str, optional
        Plot title override.
    barbs : bool or str
        Overlay wind barbs.  ``True`` uses UGRD/VGRD from the dataset;
        a string value is used as a search for separate wind data.
    save : str, optional
        Save path instead of showing interactively.
    native : bool
        Use Rust native renderer instead of matplotlib.
    model : str
        Model name for title building.
    fxx : int, optional
        Forecast hour for title building.
    figsize : tuple
        Figure size in inches.

    Returns
    -------
    matplotlib.figure.Figure or PIL.Image.Image or None
    """
    var_names = list(ds.data_vars)
    if not var_names:
        log.warning("Dataset has no data variables -- nothing to plot.")
        return None

    if native:
        return _native_plot(ds, var_names, search, area, cmap, levels,
                            title, barbs, save, model, fxx)

    return _mpl_plot(ds, var_names, search, area, cmap, levels, title,
                     barbs, save, model, fxx, figsize)


def _mpl_plot(ds, var_names, search, area, cmap, levels, title, barbs,
              save, model, fxx, figsize):
    """Render with matplotlib + cartopy."""
    import matplotlib
    if save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    scalar_vars, u_var, v_var, is_contour_line = _classify_vars(var_names, search)

    # Try cartopy projection; fall back to plain axes
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
        projection = ccrs.LambertConformal(central_longitude=-96, central_latitude=39)
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(1, 1, 1, projection=projection)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
        ax.add_feature(cfeature.BORDERS, linewidth=0.3)
        ax.add_feature(cfeature.STATES, linewidth=0.3)
        use_cartopy = True
    except ImportError:
        fig, ax = plt.subplots(figsize=figsize)
        use_cartopy = False

    # Set map extent
    extent = _parse_area(area)
    if extent and use_cartopy:
        import cartopy.crs as ccrs
        ax.set_extent(extent, crs=ccrs.PlateCarree())

    # Get coordinates
    try:
        lat, lon = _get_lat_lon(ds)
    except ValueError:
        log.warning("No lat/lon found; plotting raw array indices.")
        lat = lon = None

    data_crs = None
    if use_cartopy:
        import cartopy.crs as ccrs
        data_crs = ccrs.PlateCarree()

    # Plot scalar fields
    for vname in scalar_vars:
        da = ds[vname]
        data = da.values
        # Squeeze single-element dimensions (time, level)
        while data.ndim > 2:
            data = data[0]

        if lat is not None and lon is not None:
            plot_lon, plot_lat = lon, lat
            if plot_lon.ndim == 1 and plot_lat.ndim == 1:
                plot_lon, plot_lat = np.meshgrid(plot_lon, plot_lat)
        else:
            plot_lat = np.arange(data.shape[0])
            plot_lon = np.arange(data.shape[1])

        chosen_cmap = cmap or _default_cmap([vname], search)

        # For NWS reflectivity, fall back to a standard cmap if the custom
        # one is not registered
        try:
            plt.colormaps[chosen_cmap]
        except (KeyError, ValueError):
            if chosen_cmap == "NWSReflectivity":
                chosen_cmap = "turbo"

        kw = {}
        if data_crs is not None:
            kw["transform"] = data_crs

        if is_contour_line:
            cs = ax.contour(plot_lon, plot_lat, data,
                            levels=levels or 12, colors="k",
                            linewidths=0.8, **kw)
            ax.clabel(cs, inline=True, fontsize=8, fmt="%.0f")
        else:
            cf = ax.contourf(plot_lon, plot_lat, data,
                             levels=levels or 20, cmap=chosen_cmap,
                             extend="both", **kw)
            plt.colorbar(cf, ax=ax, shrink=0.7, pad=0.02)

    # Plot wind barbs if we have both u and v
    if u_var and v_var:
        u_data = ds[u_var].values
        v_data = ds[v_var].values
        while u_data.ndim > 2:
            u_data = u_data[0]
        while v_data.ndim > 2:
            v_data = v_data[0]

        if lat is not None and lon is not None:
            b_lon, b_lat = lon, lat
            if b_lon.ndim == 1 and b_lat.ndim == 1:
                b_lon, b_lat = np.meshgrid(b_lon, b_lat)
        else:
            b_lat = np.arange(u_data.shape[0])
            b_lon = np.arange(u_data.shape[1])

        # Thin barbs so the plot is readable
        skip = max(1, min(u_data.shape) // 30)
        sl = (slice(None, None, skip), slice(None, None, skip))

        kw = {}
        if data_crs is not None:
            kw["transform"] = data_crs

        # If there are no scalar fields, colour the barbs by speed
        if not scalar_vars:
            speed = np.sqrt(u_data ** 2 + v_data ** 2)
            chosen_cmap = cmap or "plasma"
            cf = ax.contourf(b_lon, b_lat, speed, levels=levels or 20,
                             cmap=chosen_cmap, extend="both", **kw)
            plt.colorbar(cf, ax=ax, shrink=0.7, pad=0.02, label="Wind Speed (m/s)")

        ax.barbs(b_lon[sl], b_lat[sl], u_data[sl], v_data[sl],
                 length=5.5, linewidth=0.4, **kw)

    # Overlay additional wind barbs from a separate dataset if requested
    elif barbs and isinstance(barbs, str):
        log.info("Barb overlay from separate search not yet wired up.")

    # Title
    if title is None:
        title = _auto_title(search, var_names, model, fxx)
    ax.set_title(title, fontsize=12, fontweight="bold")

    plt.tight_layout()

    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        log.info("Saved plot to %s", save)
        plt.close(fig)
        return None
    else:
        plt.show()
        return fig


def _native_plot(ds, var_names, search, area, cmap, levels, title, barbs,
                 save, model, fxx):
    """Render with the native Rust engine (no matplotlib)."""
    try:
        from rustplots._rustplots import (
            render_filled_contour, render_wind_barbs,
            composite_layers, encode_png,
        )
    except ImportError:
        raise ImportError(
            "Native rendering requires rustplots compiled with the Rust backend.  "
            "Install with: pip install rustplots[native]"
        )

    from PIL import Image
    import io

    scalar_vars, u_var, v_var, _ = _classify_vars(var_names, search)

    layers = []

    # Render scalar field
    if scalar_vars:
        vname = scalar_vars[0]
        data = ds[vname].values.astype(np.float64)
        while data.ndim > 2:
            data = data[0]
        chosen_cmap = cmap or _default_cmap([vname], search)
        layer = render_filled_contour(
            data, colormap=chosen_cmap, width=1200, height=800,
        )
        layers.append(layer)

    # Render wind barbs
    if u_var and v_var:
        u_data = ds[u_var].values.astype(np.float64)
        v_data = ds[v_var].values.astype(np.float64)
        while u_data.ndim > 2:
            u_data = u_data[0]
        while v_data.ndim > 2:
            v_data = v_data[0]
        layer = render_wind_barbs(u_data, v_data, width=1200, height=800)
        layers.append(layer)

    if not layers:
        log.warning("Nothing to render.")
        return None

    rgba = composite_layers(layers) if len(layers) > 1 else layers[0]
    png_bytes = encode_png(rgba)

    if save:
        with open(save, "wb") as f:
            f.write(png_bytes)
        log.info("Saved native plot to %s", save)
        return None

    img = Image.open(io.BytesIO(png_bytes))
    img.show()
    return img
