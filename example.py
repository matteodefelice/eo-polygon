# %% Setup
import matplotlib.pyplot as plt
import eo_cube as eo

cfg = eo.load_config()
geom = eo.read_polygon(cfg)

# %% openEO: Sentinel-2 NDVI + cloud mask, Landsat land surface temperature
con = eo.openeo_connect(cfg)
s2 = eo.ndvi_dataset(eo.openeo_cube(con, "sentinel2", geom, cfg), geom, cfg)
ls = eo.lst_dataset(eo.openeo_cube(con, "landsat", geom, cfg), geom, cfg)
print(s2, ls, sep="\n\n")

# %% Earth Engine: same variables (needs gee.project in config.yaml)
# eo.gee_init(cfg)
# s2 = eo.ndvi_dataset(eo.gee_cube("sentinel2", geom, cfg), geom, cfg).load()
# ls = eo.lst_dataset(eo.gee_cube("landsat", geom, cfg), geom, cfg).load()

# %% Farm-mean time series of clear pixels
ndvi = s2.ndvi.where(s2.farm & ~s2.cloud).mean(["latitude", "longitude"]).dropna("time")
lst = ls.lst.where(ls.farm & ~ls.cloud).mean(["latitude", "longitude"]).dropna("time") - 273.15

fig, ax = plt.subplots(2, 1, sharex=True, figsize=(8, 5))
ndvi.plot(ax=ax[0], marker="o"); ax[0].set(title="", xlabel="", ylabel="NDVI")
lst.plot(ax=ax[1], marker="o", color="C3"); ax[1].set(title="", xlabel="", ylabel="LST (°C)")
fig.savefig(f"{cfg['output_dir']}/timeseries.png", dpi=150, bbox_inches="tight")
