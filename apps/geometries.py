from dataclasses import dataclass
import datetime
import math
from typing import Dict
from typing import List
from typing import Iterable
from typing import Any

import geojson
import geopandas as gpd
import pandas as pd
import polars as pl
import shapely
from shapely.geometry import LineString
from shapely.geometry import Point
from shapely.geometry import Polygon
from shapely.geometry import MultiPolygon
import simplekml

from apps.projective_transformer import transformer_project
from apps.settings.configs import check_lang_jn_in_df
from apps.settings.configs import DrgGpxConfs
from apps.settings.configs import JnDataCols
from apps.settings.configs import rename_en_to_jn_in_df
from apps.settings.configs import rename_properties_dict
 


def check_nan(dic: Dict[str, Any]):
    """
    JSONではNanが書き込めないのでNoneに変える
    """ 
    new_dict = dict()
    for key, val in dic.items():
        if type(val) == str:
            new_dict[key] = val
        elif val is None:
            new_dict[key] = None
        elif math.isnan(val):
            new_dict[key] = None
        else:
            new_dict[key] = val
    return new_dict


def select_geom_rows(gdf: gpd.GeoDataFrame, poly=True) -> gpd.GeoDataFrame:
    """
    列名を日本語に変更してから
    GeoDataFrameからMultiPolygonとPolygonの行のみ取り出す
    Args:
        gdf(GeoDataFrame): 
    Returns:
        gdf(GeoDataFrame): 
    """
    # 列名の変更
    is_jn = check_lang_jn_in_df(gdf)
    if is_jn == False:
        gdf = rename_en_to_jn_in_df(gdf)
    # Polygonの取り出し
    if poly:
        select = ['MultiPolygon', 'Polygon']
    else:
        select = ['MultiPoint', 'Point']
    is_poly = []
    for gtype in gdf.geometry.type.to_list():
        if gtype in select:
            is_poly.append(True)
        else:
            is_poly.append(False)
    return gdf.loc[is_poly]


def union_geoms(geoms: Iterable[Polygon]) -> MultiPolygon:
    # 複数のGeometryオブジェクトを結合する
    result_geom = None
    for geom in geoms:
        if result_geom is None:
            result_geom = geom
        else:
            result_geom = result_geom.union(geom)
    return result_geom


def check_epsg(gdf: gpd.GeoDataFrame, local_epsg: int) -> gpd.GeoDataFrame:
    # EPSGが平面直角座標系でないならば変更する
    if gdf.crs.to_epsg() != local_epsg:
        gdf = gdf.to_crs(crs=f'EPSG:{local_epsg}')

    return gdf


@dataclass
class GeoDatasets:
    point_gdf: gpd.GeoDataFrame
    poly_gdf: gpd.GeoDataFrame


def merge_poly_gdf(
    main_gdf: gpd.GeoDataFrame | Iterable[gpd.GeoDataFrame], 
    inner_gdf: gpd.GeoDataFrame | Iterable[gpd.GeoDataFrame],
    outer_gdf: gpd.GeoDataFrame | Iterable[gpd.GeoDataFrame],
    local_epsg: int
) -> GeoDatasets:
    """複数のGeoDataFrameを結合する"""
    #----------- MultiPolygonの作成 -----------#
    main_poly_rows = check_epsg(select_geom_rows(main_gdf), local_epsg)
    main_poly_geom = union_geoms(main_poly_rows.geometry.to_list())
    #----------- 外側の区画処理 -----------#
    if not outer_gdf is None:
        outer_poly_rows = check_epsg(select_geom_rows(outer_gdf), local_epsg)
        outer_poly_geom = union_geoms(outer_poly_rows.geometry.to_list())    
        # メインのPolygonに外側のPolygonを結合する
        merged_poly_geom = main_poly_geom.union(outer_poly_geom)
        # 測点を数える
        
    else:
        outer_poly_rows = None
        merged_poly_geom = main_poly_geom
    #----------- 内側の区画処理 -----------#
    if not inner_gdf is None:
        inner_poly_rows = check_epsg(select_geom_rows(inner_gdf), local_epsg)
        inner_poly_geom = union_geoms(inner_poly_rows.geometry.to_list())
        # 結合済みのPolygonから内側のPolygonを差し引く
        result_poly_geom = merged_poly_geom.difference(inner_poly_geom)
    else:
        inner_poly_rows = None
        result_poly_geom = merged_poly_geom
    
    # Pointの属性値を集計する 
    _gdfs = [main_gdf]
    if inner_gdf is None:
        pass
    elif isinstance(inner_gdf, gpd.GeoDataFrame):
        _gdfs.append(inner_gdf)
    else:
        _gdfs += [_gdf for _gdf in inner_gdf]
    if outer_gdf is None:
        pass
    elif isinstance(outer_gdf, gpd.GeoDataFrame):
        _gdfs.append(outer_gdf)
    else:
        _gdfs += [_gdf for _gdf in outer_gdf]
    point_gdf = select_geom_rows(pd.concat(_gdfs), False)
    properties = properties_pt2poly(point_gdf)
    properties['面積(ha)'] = round(result_poly_geom.area / 10_000, 4)
    properties['周囲長(m)'] = round(result_poly_geom.length, 3)
    result_poly_gdf = gpd.GeoDataFrame(
        data=[properties], 
        geometry=[result_poly_geom],
        crs=f'EPSG:{local_epsg}'
    )
    return GeoDatasets(point_gdf=point_gdf, poly_gdf=result_poly_gdf)


@dataclass
class SingleGeometries:
    points: List[Point]
    line: LineString
    poly: Polygon
    epsg: int
    length: float
    area: float = None
    

class EditGeometries(object):
    def __init__(self, xs: List[float], ys: List[float], in_epsg: int):
        self.xs = xs
        self.ys = ys
        self.in_epsg = in_epsg

    def convert_coords_to_points(self, out_epsg: int=None) -> List[Point]:
        if out_epsg is None:
            points = [Point(x, y) for x, y in zip(self.xs, self.ys)]
        else:
            coords = transformer_project(self.xs, self.ys, self.in_epsg, out_epsg)
            points = [Point(c[0], c[1]) for c in zip(coords.lons, coords.lats)]
        return points

    def convert_coords_to_linestring(self, out_epsg: int=None, close: bool = False) -> LineString: 
        points = self.convert_coords_to_points(out_epsg)
        if close:
            points.append(points[0])
        return LineString(points)

    def convert_coords_to_polygon(self, out_epsg: int=None) -> Polygon:
        points = self.convert_coords_to_points(out_epsg)
        points.append(points[0])
        poly = Polygon([[p.x, p.y] for p in points])
        return poly
    

def to_poly(points: List[Point]) -> Polygon:
    points = points + [points[0]]
    return Polygon([[p.x, p.y] for p in points])



def edit_single_geom_datasets(
    df: pl.DataFrame, 
    out_epsg: int=None,
    close: bool=True,
    positioning_correction: bool=False,
    local_epsg: int=6678,
) -> SingleGeometries:
    jn_confs = JnDataCols()
    # 座標データからGeometriesObjectを作成する
    if positioning_correction:
        # 地殻変動補正しているならばEPSGコードをDataFrameから取り出す
        in_epsg = df[jn_confs.epsg_col].to_list()[0]
        editor = EditGeometries(
            xs=df[jn_confs.y_col].to_list(),
            ys=df[jn_confs.x_col].to_list(),
            in_epsg=in_epsg
        )
    else:
        in_epsg = 4326
        editor = EditGeometries(
            xs=df[jn_confs.lon_col].to_list(),
            ys=df[jn_confs.lat_col].to_list(),
            in_epsg=4326
        )
    # GeomrtriesObjectの作成
    area = None
    poly = None
    if in_epsg == out_epsg:
        #----- 地殻変動補正済みかつ平面直角座標系で出力するならば -----#
        points = editor.convert_coords_to_points()
        if close:
            line = editor.convert_coords_to_linestring()
            poly = to_poly(points)
            area = round(poly.area / 10000, 5)
            length = round(poly.length, 3)
            if (in_epsg == 4326) | (in_epsg == 3857):
                # 正しい面積計算の為に一度平面直角座標計で計算する
                __temp_pts = editor.convert_coords_to_points(local_epsg)
                area = round(to_poly(__temp_pts).area / 10000, 5)
                length = round(editor.convert_coords_to_linestring(local_epsg, close=True).length, 3)                
        else:
            line = editor.convert_coords_to_linestring()
            length = round(line.length, 3)
            if (in_epsg == 4326) | (in_epsg == 3857):
                # 正しい面積計算の為に一度平面直角座標計で計算する
                __temp_pts = editor.convert_coords_to_points(local_epsg)
                length = round(editor.convert_coords_to_linestring(local_epsg, close=True).length, 3)
    elif (positioning_correction == True) & (in_epsg != out_epsg):
        #----- 地殻変動補正しているが、別な座標系で出力する -----#
        points = editor.convert_coords_to_points(out_epsg)
        if close:
            line = editor.convert_coords_to_linestring(out_epsg)
            poly = editor.convert_coords_to_polygon(out_epsg)
            # 正しい面積計算の為に一度平面直角座標計で計算する
            __temp_pts = editor.convert_coords_to_points(local_epsg)
            area = round(to_poly(__temp_pts).area / 10000, 5)
            length = round(editor.convert_coords_to_linestring(local_epsg, close=True).length, 3)
        else:
            line = editor.convert_coords_to_linestring(out_epsg)
            length = round(editor.convert_coords_to_linestring(local_epsg).length, 3)
    elif positioning_correction == False:
        in_epsg = 4326
        if in_epsg == out_epsg:
            #----- 地殻変動補正していないのでWGS84で出力する -----#
            points = editor.convert_coords_to_points()
            if close:
                line = editor.convert_coords_to_linestring()
                poly = to_poly(points)
                # 正しい面積計算の為に一度平面直角座標計で計算する
                __temp_pts = editor.convert_coords_to_points(local_epsg)
                area = round(to_poly(__temp_pts).area / 10000, 5)
                length = round(editor.convert_coords_to_linestring(local_epsg, close=True).length, 3)
            else:
                line = editor.convert_coords_to_linestring()
                length = round(editor.convert_coords_to_linestring(local_epsg).length, 3)
        else:
            #----- 地殻変動補正していないが別な座標系で出力する -----#
            points = editor.convert_coords_to_points(out_epsg)
            if close:
                line = editor.convert_coords_to_linestring(out_epsg)
                poly = to_poly(points)
                # 正しい面積計算の為に一度平面直角座標計で計算する
                __temp_pts = editor.convert_coords_to_points(local_epsg)
                area = round(to_poly(__temp_pts).area / 10000, 5)
                length = round(editor.convert_coords_to_linestring(local_epsg, close=True).length, 3)
            else:
                line = editor.convert_coords_to_linestring(out_epsg)
                length = round(editor.convert_coords_to_linestring(local_epsg).length, 3)
    return SingleGeometries(points, line, poly, out_epsg, length, area)


#------------------------------- geopackage関連 -------------------------------#


#------------------------------- geojson関連 -------------------------------#


def properties_pt2poly(df: pl.DataFrame | gpd.GeoDataFrame) -> Dict[str, Any]:
    jn_confs = JnDataCols()
    fmt = '%Y-%m-%d %H:%M:%S'
    if isinstance(df, pl.DataFrame):
        start = df[jn_confs.start_datetime_col].min().strftime(fmt)
        end = df[jn_confs.datetime_col].max().strftime(fmt)
    else:
        start = (
            pd.to_datetime(df[jn_confs.start_datetime_col])
            .min()
            .to_pydatetime()
            .strftime(fmt)
        )
        end = (
            pd.to_datetime(df[jn_confs.start_datetime_col])
            .max()
            .to_pydatetime()
            .strftime(fmt)
        )

    properties = {
        jn_confs.start_datetime_col: start,
        jn_confs.datetime_col: end,
        '測点数': len(df),
        'PDOPの最大値': df[jn_confs.pdop_col].max(),
        '衛星数の最小値': df[jn_confs.satellites_col].min(),
        '信号周波数の最小値': df[jn_confs.signal_frec_col].min(),
        jn_confs.office_col: df[jn_confs.office_col].min(),
        jn_confs.branch_office_col: df[jn_confs.branch_office_col].min(),
        jn_confs.lcoal_area_col: df[jn_confs.lcoal_area_col].min(),
        jn_confs.address_col: df[jn_confs.address_col].min(),
    }
    return properties


@dataclass
class GeoJsons:
    pnp_geojson: str = None
    pnl_geojson: str = None
    poly_geojson: str = None
    line_geojson: str = None
    point_geojson: str = None


class GeoJ(JnDataCols):
    def __init__(self, df: pl.DataFrame, geometries: SingleGeometries, is_en: bool):
        super().__init__()
        self.df = self._str_to_datetime(df)
        self.geometries = geometries
        self.is_en = is_en
    
    @property
    def write_poly_geojson(self) -> geojson.Feature:
        properties = properties_pt2poly(self.df)
        properties['面積(ha)'] = self.geometries.area
        properties['周囲長(m)'] = self.geometries.length
        properties = rename_properties_dict(properties, self.is_en)
        start = self.df[self.start_datetime_col].min()
        end = self.df[self.datetime_col].max()
        properties['work_time'] = self._timedelta_to_str(end - start)
        feats = geojson.Feature(
            geometry=self.geometries.poly, properties=properties)
        return feats
        
    @property
    def write_points_geojson(self) -> List[geojson.Feature]:
        df = self._datetime_to_str(self.df)
        properties_lst =[]
        for _, row in df.to_pandas().iterrows():
            row = rename_properties_dict(row.to_dict(), self.is_en)
            row = check_nan(row)
            properties_lst.append(row)
        features = []
        for i, point in enumerate(self.geometries.points):
            feat = geojson.Feature(geometry=point, properties=properties_lst[i])
            features.append(feat)
        return features
    
    @property
    def write_line_geojson(self) -> List[geojson.Feature]:
        properties = properties_pt2poly(self.df)
        properties['面積(ha)'] = self.geometries.area
        properties['周囲長(m)'] = self.geometries.length
        properties = rename_properties_dict(properties, self.is_en)
        start = self.df[self.start_datetime_col].min()
        end = self.df[self.datetime_col].max()
        properties['work_time'] = self._timedelta_to_str(end - start)
        feats = geojson.Feature(
            geometry=self.geometries.line, properties=properties)
        return feats
        
    def collections(self, poly: bool) -> GeoJsons:
        poly_feat = self.write_poly_geojson
        line_feat = self.write_line_geojson
        point_feat = self.write_points_geojson
        # FeatureCollectionの作成とCRSの設定
        pnp_collection = geojson.FeatureCollection([poly_feat] + point_feat)
        pnl_collection = geojson.FeatureCollection([line_feat] + point_feat)
        poly_collection = geojson.FeatureCollection([poly_feat])
        line_collection = geojson.FeatureCollection([line_feat])
        point_collection = geojson.FeatureCollection(point_feat)
        pnp_collection['crs'] = self.__crs
        pnl_collection['crs'] = self.__crs
        poly_collection['crs'] = self.__crs
        line_collection['crs'] = self.__crs
        point_collection['crs'] = self.__crs
        if poly:
            gjsons = GeoJsons(
                pnp_geojson=geojson.dumps(pnp_collection, indent=2),
                poly_geojson=geojson.dumps(poly_collection, indent=2),
                point_geojson=geojson.dumps(point_collection, indent=2)
            )
        else:
            gjsons = GeoJsons(
                pnl_geojson=geojson.dumps(pnl_collection, indent=2),
                line_geojson=geojson.dumps(line_collection, indent=2),
                point_geojson=geojson.dumps(point_collection, indent=2)
            )
        return gjsons

    @property
    def __crs(self) -> Dict[str, Any]:
        crs = {
            "type": "name", 
            "properties": {
                "name": f"urn:ogc:def:crs:EPSG::{self.geometries.epsg}"
            }
        }
        return crs

    def _str_to_datetime(self, df: pl.DataFrame) -> pl.DataFrame:
        fmt = '%Y-%m-%d %H:%M:%S'
        if df[self.start_datetime_col].dtype != pl.Datetime:
            df = df.with_columns([
                pl.col(self.start_datetime_col).str.strptime(pl.Datetime, fmt)
            ])
        if df[self.datetime_col].dtype != pl.Datetime:
            df = df.with_columns([
                pl.col(self.datetime_col).str.strptime(pl.Datetime, fmt)
            ])
        return df

    def _datetime_to_str(self, df: pl.DataFrame) -> pl.DataFrame:
        fmt = '%Y-%m-%d %H:%M:%S'
        if df[self.start_datetime_col].dtype == pl.Datetime:
            df = df.with_columns([
                pl.col(self.start_datetime_col).dt.strftime(fmt)
            ])
        if df[self.datetime_col].dtype == pl.Datetime:
            df = df.with_columns([
                pl.col(self.datetime_col).dt.strftime(fmt)
            ])
        return df

    def _timedelta_to_str(self, delta: datetime.timedelta) -> str:
        days = delta.days
        hours = delta.seconds // 3600
        if 0 < hours:
            minutes = int(round((delta.seconds - hours * 3600) / 60, 0))
        else:
            minutes = int(round(delta.seconds / 60, 0))
        if days == 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{days}d {hours}h {minutes}m"

    def _labels(self, poly: bool) -> List[str]:
        if poly:
            labels = [
                "ポイント&ポリゴン.geojson ファイルのダウンロード",
                "ポイント.geojson ファイルのダウンロード",
                "ポリゴン.geojson ファイルのダウンロード",
            ]
        else:
            labels = [
                "ポイント&ライン.geojson ファイルのダウンロード",
                "ポイント.geojson ファイルのダウンロード",
                "ライン.geojson ファイルのダウンロード",
            ]
        return labels



#------------------------------- kml関連 -------------------------------#


def create_poly_style(
    normal_color: str=simplekml.Color.red,
    normal_line_width: int=1,
    highlight_color: str=simplekml.Color.red,
    highlight_line_width: int=3,
) -> simplekml.StyleMap:
        """
        Args:
            normal_color(str): 通常時に見えるPolygonの外枠の色
            normal_line_width: 通常時に見えるPolygonの外枠の太さ
            highlight_color(str): カーソルを置いた時に見えるPolygonの外枠の色
            highlight_line_width: カーソルを置いた時に見えるPolygonの外枠の太さ
        Returns:
            (simplekml.StyleMap): simplekml.featgeom.Polygon.stylemap などに渡して色を設定する
        Example:
            >>> style_map = create_poly_style(normal_color=simplekml.Color.black,
                                              normal_line_width=1,
                                              highlight_color=simplekml.Color.yellowgreen,
                                              highlight_line_width=3)
            >>> kml = simplekml.Kml()
            >>> poly = kml.newpolygon(name='ポップアップのタイトル',
                                      outerboundaryis=outer_coors,
                                      innerboundaryis=inner_coors)
            >>> poly.stylemap = style_map
            >>> kml.save(out_fp)
        """
        # 通常時の色設定
        normal_style = simplekml.Style()
        normal_style.linestyle.color = normal_color
        normal_style.polystyle.fill = 0
        normal_style.linestyle.width = normal_line_width

        # カーソルを近づけた時の色設定
        highlight_style = simplekml.Style()
        highlight_style.linestyle.color = highlight_color
        highlight_style.polystyle.fill = 0
        highlight_style.linestyle.width = highlight_line_width

        return simplekml.StyleMap(normal_style, highlight_style)


def create_extended_data_kml(properties: Dict[str, Any]) -> simplekml.ExtendedData:
    """
    Args:
        properties(Dict): 
    Retuens:
        (simplekml.ExtendedData): 
    Example:
        >>> with open('sample.geojson', mode='r') as f:
        >>>     data = json.load()
        >>>
        >>> kml = simplekml.Kml()
        >>>
        >>> for row in data.get('features'):
        >>>     --------------------------------------------
        >>>     --------------------------------------------
        >>>     extendeddata = create_extended_data(row.get('properties'))
        >>>     poly = kml.newpolygon(name='ポップアップのタイトル',
                                    outerboundaryis=outer_coors,
                                    innerboundaryis=inner_coors)
        >>>     poly.extendeddata = style_map
        >>>
        >>> kml.save(out_fp)
    
    """
    data = simplekml.ExtendedData()
    for key, value in properties.items():
        data.newdata(name=key, value=value)
    return data


def edit_points_kml(
    df: pl.DataFrame, 
    geometries: SingleGeometries,
    is_en: bool
) -> str:
    jn_confs = JnDataCols()
    drg_confs = DrgGpxConfs()
    # kmlオブジェクトの作成
    kml = simplekml.Kml()
    for iterr, point in zip(df.to_pandas().iterrows(), geometries.points):
        _, row = iterr
        properties = rename_properties_dict(row.to_dict(), is_en)
        if is_en:
            name = properties[drg_confs.pt_name_col]
        else:
            name = row[jn_confs.pt_name_col]

        extended = create_extended_data_kml(properties)
        coords = [(point.x, point.y)]
        kml.newpoint(
            name=name, 
            extendeddata=extended,
            coords=coords
        )
    return kml


def edit_poly_kml(
    df: pl.DataFrame,
    geometries: SingleGeometries,
    is_en: bool
) -> str:
    # PolygonのPropertiesを作成する
    properties = properties_pt2poly(df)
    properties['面積(ha)'] = geometries.area
    properties['周囲長(m)'] = geometries.length
    properties = rename_properties_dict(properties, is_en)
    # polygonのオブジェクト作成
    poly_coords = []
    for coor in geometries.poly.exterior.coords:
        poly_coords.append(coor)
    # kmlオブジェクトの作成
    kml = simplekml.Kml()
    poly = kml.newpolygon(
        name='Polygon', 
        extendeddata=create_extended_data_kml(properties),
        outerboundaryis=poly_coords
    )
    poly.stylemap = create_poly_style()
    return kml


def edit_line_kml(
    df: pl.DataFrame,
    geometries: SingleGeometries,
    is_en: bool
) -> str:
    # PolygonのPropertiesを作成する
    properties = properties_pt2poly(df)
    properties['周囲長(m)'] = geometries.length
    properties = rename_properties_dict(properties, is_en)
    # polygonのオブジェクト作成
    line_coords = []
    for coor in geometries.line.coords:
        line_coords.append(coor)
    # kmlオブジェクトの作成
    kml = simplekml.Kml()
    line = kml.newlinestring(name='LineString')
    line.extendeddata = create_extended_data_kml(properties)
    line.coords = line_coords
    line.stylemap = create_poly_style()
    return kml
    

def edit_multipoly_kml(gdf: gpd.GeoDataFrame) -> str:
    """GeoDataFrameからMultiPolygonのKMLを作成する"""
    # kmlはwgs84に強制
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(crs='EPSG:4326')
    # Porpertiesの取り出し
    proper = gdf.drop('geometry', axis=1).iloc[0].to_dict()
    properties = create_extended_data_kml(proper)
    # KMLの作成
    kml = simplekml.Kml()
    multi_kml = (
        kml
        .newmultigeometry(
            name='MultiPolygon',
            extendeddata=properties
        )
    )
    # Geometryの作成
    multi_poly = gdf.geometry.to_list()[0]
    generate = lambda poly_geom: [xy for xy in poly_geom.exterior.coords]
    for i in range(shapely.get_num_geometries(multi_poly)):
        _poly = shapely.get_geometry(multi_poly, i)
        ring = shapely.get_exterior_ring(_poly)
        main_poly = generate(Polygon(ring))
        inner_polys = []
        if 1 <= shapely.get_num_interior_rings(_poly):
            for j in range(shapely.get_num_interior_rings(_poly)):
                in_ring = shapely.get_interior_ring(_poly, j)
                inner_polys.append(generate(Polygon(in_ring)))
        multi_kml.newpolygon(
            name=f'NewName{i}',
            outerboundaryis=main_poly,
            innerboundaryis=inner_polys
        )
    
    multi_kml.stylemap = create_poly_style() 
    return kml.kml()


if __name__ == '__main__':
    import rich
    df = pl.read_csv(r'./yokohama.csv')
    geometries = edit_single_geom_datasets(df, out_epsg=3857, positioning_correction=True)
    edit = edit_poly_kml(df, geometries)
    a = 10