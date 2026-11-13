"""Data cubes (time, latitude, longitude) for one polygon, from openEO and Earth Engine.

Both backends return the same raw dataset (one variable per logical band, see
config.yaml); `ndvi_dataset` and `lst_dataset` turn it into the final variables.
"""
from pathlib import Path

import numpy as np
import shapely
import xarray as xr
import yaml


def load_config(path="config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def read_polygon(cfg):
    return shapely.from_wkt(cfg["polygon"])


# openEO ----------------------------------------------------------------------

def openeo_connect(cfg):
    """Connect to the openEO backend. The first call opens a browser login;
    the refresh token is then cached by the openeo library."""
    import openeo
    return openeo.connect(cfg["openeo"]["url"]).authenticate_oidc()


def openeo_cube(con, source, geom, cfg, batch=True):
    """Raw cube for `source` ('sentinel2' or 'landsat') over the polygon bounding box.

    batch=True runs a batch job (robust, a few minutes); batch=False is a
    synchronous request, only suitable for short periods."""
    src, bands = cfg[source], cfg[source]["openeo"]["bands"]
    west, south, east, north = geom.bounds
    args = dict(
        spatial_extent=dict(west=west, south=south, east=east, north=north),
        temporal_extent=cfg["time"],
        bands=list(bands.values()),
    )
    if "stac" in src["openeo"]:
        cube = con.load_stac(src["openeo"]["stac"], **args)
    else:
        cube = con.load_collection(src["openeo"]["collection"], **args)
    cube = cube.resample_spatial(resolution=src["resolution"], projection=4326, method="near")

    path = Path(cfg["output_dir"]) / f"openeo_{source}_raw.nc"
    path.parent.mkdir(exist_ok=True)
    if batch:
        cube.execute_batch(path, out_format="netCDF", title=f"eo-polygon {source}")
    else:
        cube.download(path, format="netCDF")

    ds = xr.open_dataset(path).drop_vars("crs", errors="ignore")
    ds = ds.rename({"t": "time", "x": "longitude", "y": "latitude"})
    return ds.rename({v: k for k, v in bands.items()})


# Earth Engine ----------------------------------------------------------------

def gee_init(cfg):
    """Initialise Earth Engine. The first call opens a browser login;
    credentials are then cached by the earthengine library."""
    import ee
    kw = dict(project=cfg["gee"]["project"], opt_url=cfg["gee"]["url"])
    try:
        ee.Initialize(**kw)
    except Exception:
        ee.Authenticate()
        ee.Initialize(**kw)


def gee_cube(source, geom, cfg):
    """Raw cube for `source` ('sentinel2' or 'landsat') over the polygon bounding box."""
    import ee
    from xee.helpers import fit_geometry
    src, bands = cfg[source], cfg[source]["gee"]["bands"]
    ic = ee.ImageCollection(ee.FeatureCollection(
        [ee.ImageCollection(c) for c in src["gee"]["collection"]]).flatten())
    ic = (ic.filterBounds(ee.Geometry(shapely.geometry.mapping(geom)))
            .filterDate(*cfg["time"])
            .sort("system:time_start")
            .select(list(bands.values()), list(bands)))
    res = src["resolution"]
    grid = fit_geometry(geom, grid_scale=(res, -res))
    ds = xr.open_dataset(ic, engine="ee", mask_and_scale=False, **grid)
    return ds.rename({"x": "longitude", "y": "latitude"}).transpose("time", "latitude", "longitude")


# Shared post-processing --------------------------------------------------------

def inside(ds, geom):
    """Boolean (latitude, longitude) mask of the pixel centres inside the polygon."""
    lon, lat = np.meshgrid(ds.longitude, ds.latitude)
    return xr.DataArray(shapely.contains_xy(geom, lon, lat),
                        coords=dict(latitude=ds.latitude, longitude=ds.longitude))


def ndvi_dataset(raw, geom, cfg):
    """NDVI, scene classification and cloud mask from a raw Sentinel-2 cube."""
    red, nir = raw.red.astype("float32"), raw.nir.astype("float32")
    valid = (red > 0) & (nir > 0)
    return xr.Dataset(dict(
        ndvi=((nir - red) / (nir + red)).where(valid),
        scl=raw.scl,
        cloud=raw.scl.isin(cfg["sentinel2"]["scl_cloud"]) | ~valid,
        farm=inside(raw, geom),
    ))


def lst_dataset(raw, geom, cfg):
    """Land surface temperature (kelvin) and cloud mask from a raw Landsat cube."""
    src = cfg["landsat"]
    valid = raw.st > 0
    qa = raw.qa.fillna(0).astype("uint16")
    bits = sum(1 << b for b in src["qa_cloud_bits"])
    ds = xr.Dataset(dict(
        lst=(raw.st * src["scale"] + src["offset"]).where(valid).astype("float32"),
        cloud=((qa & bits) > 0) | ~valid,
        farm=inside(raw, geom),
    ))
    return ds.isel(time=valid.any(["latitude", "longitude"]).values)  # drop empty scenes
