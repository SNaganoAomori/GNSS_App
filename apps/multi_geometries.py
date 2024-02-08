from typing import Any
from typing import Dict
from typing import Iterable
from typing import List

import geopandas as gpd
import simplekml
from shapely import MultiPolygon
from shapely import Point
from shapely import Polygon

from apps.geometries import create_extended_data_kml
from apps.geometries import create_poly_style


class MultiGeoms(object):
    def __init__(self, geo_col: str='geometry'):
        self.geo_col = geo_col

    def select_points_gdf(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        geopandas.GeoDataFrameからPointデータの行のみ抽出する
        """
        selected = []
        for _, row in gdf.iterrows():
            if type(row[self.geo_col]) == Point:
                selected.append(row.to_dict())
        
        gdf = gpd.GeoDataFrame(selected)
        return gdf
    
    def generate_poly(self, points_gdf: gpd.GeoDataFrame) -> Polygon:
        """
        Pointのみのgeopandas.GeoDataFrameからPolygonを作成する
        """
        return Polygon(points_gdf[self.geo_col].to_list())
        
    def convert_poly_to_list(self, poly: Polygon) -> List[List[float]]:
        return [xy for xy in poly.exterior.coords]
    
    def generate_multipoly(
        self, 
        main_poly: Polygon, 
        outer_polys: Iterable[Polygon], 
        inner_polys: Iterable[Polygon],
    ) -> MultiPolygon:
        for inner in inner_polys:
            main_poly = main_poly.difference(inner)

        return MultiPolygon([main_poly] + outer_polys)
    
    def generate_multipoly_kml(
        self, 
        main_poly: Polygon, 
        outer_polys: Iterable[Polygon], 
        inner_polys: Iterable[Polygon],
        name: str,
        properties: Dict[str, Any]
    ) -> simplekml.Kml.kml:
        kml = simplekml.Kml()
        multi_kml = (
            kml
            .newmultigeometry(
                name='dff', 
                extendeddata=create_extended_data_kml(properties)
            )
        )
        multi_kml.newpolygon(
            name=name,
            outerboundaryis=main_poly,
            innerboundaryis=outer_polys + inner_polys
        )
        multi_kml.stylemap = create_poly_style() 
        return kml.kml()