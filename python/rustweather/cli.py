"""Command-line interface for rustweather.

Usage:
    wx plot hrrr "TMP:2 m"
    wx plot hrrr temp --area conus --save output.png
    wx sounding hrrr OKC
    wx hodograph gfs DEN --fxx 24
    wx surface hrrr --area mw
    wx upperair gfs --level 500
    wx severe hrrr --area sp
    wx forecast hrrr "TMP:2 m" --hours 0,3,6,9,12,15,18
    wx get hrrr "TMP:2 m" --output temp.nc
    wx cross hrrr TMP OKC DFW
"""

import argparse
import sys


def _parse_hours(s):
    """Parse comma-separated hours or a range like '0-18:3'."""
    if "-" in s and ":" in s:
        # range format: start-end:step
        parts = s.split(":")
        rng = parts[0].split("-")
        start, end = int(rng[0]), int(rng[1])
        step = int(parts[1]) if len(parts) > 1 else 1
        return list(range(start, end + 1, step))
    elif "," in s:
        return [int(x.strip()) for x in s.split(",")]
    elif "-" in s:
        parts = s.split("-")
        return list(range(int(parts[0]), int(parts[1]) + 1))
    else:
        return [int(s)]


def _parse_location(s):
    """Parse a location string: station ID or 'lat,lon'."""
    if "," in s:
        parts = s.split(",")
        return (float(parts[0].strip()), float(parts[1].strip()))
    return s


def main():
    parser = argparse.ArgumentParser(
        prog="wx",
        description="rustweather -- One command. Every weather workflow.",
        epilog="Examples:\n"
               "  wx plot hrrr temp\n"
               "  wx sounding hrrr OKC\n"
               "  wx surface gfs --area conus\n"
               "  wx get hrrr 'TMP:2 m' --output temp.nc\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- wx plot ---
    p_plot = subparsers.add_parser("plot", help="Plot any field from any model")
    p_plot.add_argument("model", help="Model name (hrrr, gfs, nam, ...)")
    p_plot.add_argument("search", help="GRIB search string or alias (temp, cape, refl, ...)")
    p_plot.add_argument("--date", "-d", default=None, help="Init date (YYYY-MM-DD HH:MM)")
    p_plot.add_argument("--fxx", "-f", type=int, default=0, help="Forecast hour")
    p_plot.add_argument("--area", "-a", default="us", help="Map area (us, conus, ne, se, ...)")
    p_plot.add_argument("--save", "-s", default=None, help="Save to file instead of showing")
    p_plot.add_argument("--cmap", default=None, help="Colormap name")
    p_plot.add_argument("--native", action="store_true", help="Use Rust native renderer")
    p_plot.add_argument("--title", default=None, help="Custom title")
    p_plot.add_argument("--barbs", action="store_true", help="Overlay wind barbs")

    # --- wx sounding ---
    p_snd = subparsers.add_parser("sounding", help="Plot a SkewT sounding")
    p_snd.add_argument("model", help="Model name")
    p_snd.add_argument("location", help="Station ID (OKC) or lat,lon (35.2,-97.5)")
    p_snd.add_argument("--date", "-d", default=None, help="Init date")
    p_snd.add_argument("--fxx", "-f", type=int, default=0, help="Forecast hour")
    p_snd.add_argument("--save", "-s", default=None, help="Save to file")
    p_snd.add_argument("--title", default=None, help="Custom title")

    # --- wx hodograph ---
    p_hodo = subparsers.add_parser("hodograph", help="Plot a hodograph")
    p_hodo.add_argument("model", help="Model name")
    p_hodo.add_argument("location", help="Station ID or lat,lon")
    p_hodo.add_argument("--date", "-d", default=None, help="Init date")
    p_hodo.add_argument("--fxx", "-f", type=int, default=0, help="Forecast hour")
    p_hodo.add_argument("--save", "-s", default=None, help="Save to file")
    p_hodo.add_argument("--title", default=None, help="Custom title")

    # --- wx surface ---
    p_sfc = subparsers.add_parser("surface", help="Surface analysis map")
    p_sfc.add_argument("model", help="Model name")
    p_sfc.add_argument("--date", "-d", default=None, help="Init date")
    p_sfc.add_argument("--fxx", "-f", type=int, default=0, help="Forecast hour")
    p_sfc.add_argument("--area", "-a", default="us", help="Map area")
    p_sfc.add_argument("--save", "-s", default=None, help="Save to file")
    p_sfc.add_argument("--title", default=None, help="Custom title")

    # --- wx upperair ---
    p_ua = subparsers.add_parser("upperair", help="Upper air analysis")
    p_ua.add_argument("model", help="Model name")
    p_ua.add_argument("--level", "-l", type=int, default=500, help="Pressure level (mb)")
    p_ua.add_argument("--date", "-d", default=None, help="Init date")
    p_ua.add_argument("--fxx", "-f", type=int, default=0, help="Forecast hour")
    p_ua.add_argument("--area", "-a", default="us", help="Map area")
    p_ua.add_argument("--save", "-s", default=None, help="Save to file")
    p_ua.add_argument("--title", default=None, help="Custom title")

    # --- wx severe ---
    p_sev = subparsers.add_parser("severe", help="Severe weather parameters")
    p_sev.add_argument("model", help="Model name")
    p_sev.add_argument("--params", "-p", default=None,
                       help="Comma-separated params (CAPE,SRH,SHEAR,UH,STP)")
    p_sev.add_argument("--date", "-d", default=None, help="Init date")
    p_sev.add_argument("--fxx", "-f", type=int, default=0, help="Forecast hour")
    p_sev.add_argument("--area", "-a", default="us", help="Map area")
    p_sev.add_argument("--save", "-s", default=None, help="Save to file")
    p_sev.add_argument("--title", default=None, help="Custom title")

    # --- wx forecast ---
    p_fc = subparsers.add_parser("forecast", help="Multi-hour forecast panels")
    p_fc.add_argument("model", help="Model name")
    p_fc.add_argument("search", help="GRIB search string or alias")
    p_fc.add_argument("--hours", default=None,
                      help="Forecast hours: 0,3,6,9 or 0-18:3")
    p_fc.add_argument("--date", "-d", default=None, help="Init date")
    p_fc.add_argument("--area", "-a", default="us", help="Map area")
    p_fc.add_argument("--save", "-s", default=None, help="Save to file")
    p_fc.add_argument("--cmap", default=None, help="Colormap name")
    p_fc.add_argument("--title", default=None, help="Custom title")

    # --- wx get ---
    p_get = subparsers.add_parser("get", help="Download data (no plot)")
    p_get.add_argument("model", help="Model name")
    p_get.add_argument("search", help="GRIB search string or alias")
    p_get.add_argument("--date", "-d", default=None, help="Init date")
    p_get.add_argument("--fxx", "-f", type=int, default=0, help="Forecast hour")
    p_get.add_argument("--output", "-o", default=None, help="Save as netCDF")

    # --- wx calc ---
    p_calc = subparsers.add_parser("calc", help="Download + calculate")
    p_calc.add_argument("model", help="Model name")
    p_calc.add_argument("function", help="metrust.calc function name")
    p_calc.add_argument("--location", default=None,
                        help="Station ID or lat,lon for point calculation")
    p_calc.add_argument("--date", "-d", default=None, help="Init date")
    p_calc.add_argument("--fxx", "-f", type=int, default=0, help="Forecast hour")

    # --- wx cross ---
    p_xs = subparsers.add_parser("cross", help="Vertical cross-section")
    p_xs.add_argument("model", help="Model name")
    p_xs.add_argument("search", help="GRIB search string or alias")
    p_xs.add_argument("start", help="Start point (station ID or lat,lon)")
    p_xs.add_argument("end", help="End point (station ID or lat,lon)")
    p_xs.add_argument("--date", "-d", default=None, help="Init date")
    p_xs.add_argument("--fxx", "-f", type=int, default=0, help="Forecast hour")
    p_xs.add_argument("--save", "-s", default=None, help="Save to file")
    p_xs.add_argument("--title", default=None, help="Custom title")

    # --- Parse ---
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    # Lazy-import core to keep CLI startup fast
    from rustweather import core

    try:
        if args.command == "plot":
            core.plot(
                args.model, args.search,
                date=args.date, fxx=args.fxx, area=args.area,
                save=args.save, cmap=args.cmap, native=args.native,
                title=args.title, barbs=args.barbs,
            )

        elif args.command == "sounding":
            loc = _parse_location(args.location)
            core.sounding(
                args.model, loc,
                date=args.date, fxx=args.fxx, save=args.save,
                title=args.title,
            )

        elif args.command == "hodograph":
            loc = _parse_location(args.location)
            core.hodograph(
                args.model, loc,
                date=args.date, fxx=args.fxx, save=args.save,
                title=args.title,
            )

        elif args.command == "surface":
            core.surface(
                args.model,
                date=args.date, fxx=args.fxx, area=args.area,
                save=args.save, title=args.title,
            )

        elif args.command == "upperair":
            core.upperair(
                args.model, level=args.level,
                date=args.date, fxx=args.fxx, area=args.area,
                save=args.save, title=args.title,
            )

        elif args.command == "severe":
            params = None
            if args.params:
                params = [p.strip() for p in args.params.split(",")]
            core.severe(
                args.model,
                params=params, date=args.date, fxx=args.fxx,
                area=args.area, save=args.save, title=args.title,
            )

        elif args.command == "forecast":
            hours = None
            if args.hours:
                hours = _parse_hours(args.hours)
            core.forecast(
                args.model, args.search,
                hours=hours, date=args.date, area=args.area,
                save=args.save, cmap=args.cmap, title=args.title,
            )

        elif args.command == "get":
            ds = core.get(
                args.model, args.search,
                date=args.date, fxx=args.fxx,
            )
            if args.output:
                ds.to_netcdf(args.output)
                print(f"Saved to {args.output}")
            else:
                print(ds)

        elif args.command == "calc":
            loc = _parse_location(args.location) if args.location else None
            result = core.calc(
                args.model, args.function,
                location=loc, date=args.date, fxx=args.fxx,
            )
            print(result)

        elif args.command == "cross":
            start = _parse_location(args.start)
            end = _parse_location(args.end)
            core.cross_section(
                args.model, args.search, start, end,
                date=args.date, fxx=args.fxx, save=args.save,
                title=args.title,
            )

    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
