"""rustweather -- One install. One line. Every weather workflow.

Wraps rusbie (download), cfrust (GRIB decode), metrust (calculations),
and rustplots (plotting) into dead-simple one-liner commands.

    from rustweather import plot, sounding, get
    plot("hrrr", "temp")
    sounding("hrrr", "OKC")
    ds = get("gfs", "HGT:500 mb")
"""

from rustweather.core import (
    plot,
    sounding,
    hodograph,
    surface,
    upperair,
    severe,
    forecast,
    obs,
    cross_section,
    get,
    calc,
)
from rustweather.models import models, latest

__version__ = "0.1.0"

__all__ = [
    "plot",
    "sounding",
    "hodograph",
    "surface",
    "upperair",
    "severe",
    "forecast",
    "obs",
    "cross_section",
    "get",
    "calc",
    "models",
    "latest",
]
