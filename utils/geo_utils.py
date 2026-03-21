import geopandas as gpd
from shapely.geometry import Point
import pandas as pd

def load_world_polygons(source: str | None = None) -> gpd.GeoDataFrame:
    """
    If source is None, load GeoPandas' naturalearth_lowres.
    Otherwise, read a local Natural Earth admin_0 countries shapefile.
    """
    if source is None:
        world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
    else:
        world = gpd.read_file(source)
    # Normalize country name column
    if 'name' not in world.columns:
        # Natural Earth 'admin' column often holds the country names
        if 'admin' in world.columns:
            world = world.rename(columns={'admin': 'name'})
    return world.to_crs(epsg=4326)

def add_geometry_from_latlon(df: pd.DataFrame, lat_col: str, lon_col: str) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=[Point(xy) for xy in zip(df[lon_col], df[lat_col])],
        crs="EPSG:4326",
    )
    return gdf

def reverse_geocode_country(points_gdf: gpd.GeoDataFrame, world_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # Spatial join to assign country to each point
    joined = gpd.sjoin(points_gdf, world_gdf[['name', 'geometry']], how='left', predicate='within')
    joined = joined.rename(columns={'name': 'country'}).drop(columns=['index_right'])
    return joined

def count_by_country(points_with_country: gpd.GeoDataFrame, country_col="country") -> pd.DataFrame:
    counts = points_with_country.groupby(country_col, dropna=False).size().reset_index(name='n')
    counts = counts.sort_values('n', ascending=False).reset_index(drop=True)
    return counts