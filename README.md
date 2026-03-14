# rustweather

**One install. One line. Every weather workflow. Powered by Rust.**

```python
from rustweather import plot, sounding, get

plot("hrrr", "temp")                    # 2m temperature map
plot("gfs", "cape", area="conus")       # CAPE from GFS
sounding("hrrr", "OKC")                # SkewT at Oklahoma City
ds = get("hrrr", "TMP:2 m")           # just the data as xarray
```

Or from the command line:
```bash
wx plot hrrr temp
wx sounding hrrr OKC
wx severe hrrr --area conus
wx upperair gfs --level 500
```

## What it does

rustweather is a single package that wraps the entire Rust meteorology pipeline into one-liner commands. No configuration, no boilerplate — just say what you want.

Under the hood:
- **[rusbie](https://github.com/FahrenheitResearch/rusbie)** downloads the data (parallel HTTP, 45 models)
- **[cfrust](https://github.com/FahrenheitResearch/cfrust)** decodes the GRIB (pure Rust, no eccodes)
- **[metrust](https://github.com/FahrenheitResearch/metrust-py)** runs the calculations (150+ functions, 6-30x faster)
- **[rustplots](https://github.com/FahrenheitResearch/rustplots)** renders the plots (MetPy-compatible)

## Installation

```bash
pip install rustweather
```

No conda. No eccodes. No Fortran. No C libraries.

## One-liners

```python
from rustweather import plot, sounding, hodograph, surface, upperair, severe, get

# Surface fields
plot("hrrr", "temp")              # 2m temperature
plot("hrrr", "dewpoint")          # 2m dewpoint
plot("hrrr", "wind")              # 10m wind barbs
plot("hrrr", "mslp")              # mean sea level pressure
plot("hrrr", "refl")              # composite reflectivity
plot("hrrr", "visibility")        # visibility

# Severe weather
plot("hrrr", "cape")              # CAPE
plot("hrrr", "srh")               # storm-relative helicity
severe("hrrr")                    # multi-panel severe analysis

# Upper air
plot("gfs", "heights_500")        # 500mb geopotential height
plot("gfs", "jet")                # 250mb jet stream
upperair("gfs", level=500)        # 500mb heights + vorticity

# Soundings
sounding("hrrr", "OKC")          # SkewT at Oklahoma City
sounding("gfs", "DEN", fxx=24)   # Denver, 24hr forecast
hodograph("hrrr", "OKC")         # wind hodograph

# Composites
surface("hrrr")                   # temp + MSLP + wind barbs

# Data only (no plotting)
ds = get("hrrr", "temp")         # returns xarray.Dataset

# Any model
plot("gfs", "temp")
plot("nam", "cape")
plot("rap", "refl")
plot("ifs", "temp")               # ECMWF IFS
```

## 36 Supported Models

HRRR, GFS, NAM, RAP, GEFS, NBM, RRFS, RTMA, URMA, HREF, HiResW, CFS, IFS, AIFS, GraphCast, AIGFS, NEXRAD, and more.

## 50+ Field Aliases

Type natural names instead of GRIB search strings:

| Alias | GRIB Search |
|-------|-------------|
| `temp` | `TMP:2 m above ground` |
| `dewpoint` | `DPT:2 m above ground` |
| `wind` | `UGRD:10 m\|VGRD:10 m` |
| `cape` | `CAPE:surface` |
| `refl` | `REFC:entire atmosphere` |
| `mslp` | `PRMSL:mean sea level` |
| `srh` | `HLCY:3000-0 m above ground` |
| `heights_500` | `HGT:500 mb` |
| `jet` | `UGRD:250 mb\|VGRD:250 mb` |

## License

MIT
