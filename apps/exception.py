"""
: 例外処理の作成 :

1. 「Side Bar」のfile_uploaderで
    ・".gpx"以外のフォーマットが入力された場合

2. 「メインページ」でPolygonの境界線がクロスしている場合

3. 「ファイル出力」の「データ保存」タブでセミダイナミック補正されていない場合

4. 「ファイル出力」の「実測図作成」タブで
    ・".geojson"以外が入力された場合
    ・複数のPolygonが含まれたデータが与えられた場合
    ・Polygonだけが与えられた場合
    ・Pointだけが与えられた場合
    ・Polygonの頂点とPointが一致していない場合

5. 「データ結合」の「GeoJ to GIS」タブで
    ・".geojson"以外が入力された場合
    ・Polygonだけが与えられた場合
    ・Pointだけが与えられた場合
    ・Polygonの頂点とPointが一致していない場合

6. 「データ結合」の「GeoJ to DTA」タブで
    ・".geojson"以外が入力された場合
    ・Polygonだけが与えられた場合
    ・Pointだけが与えられた場合
    ・Polygonの頂点とPointが一致していない場合

7. 「アップロード」にgeojsonデータを入力した際に
    ・".geojson"以外が入力された場合
    ・複数行あった場合
    ・PolygonかLineString、MultiPolygon、MultiLineString以外のデータが入力された場合
"""
from typing import Dict
from typing import List

import geopandas as gpd
import polars as pl
import shapely
from shapely.geometry import LineString
from shapely.geometry import MultiLineString
from shapely.geometry import MultiPolygon
from shapely.geometry import Point
from shapely.geometry import Polygon
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from streamlit.runtime.uploaded_file_manager import UploadedFile

from apps.disassembly import geom_disassembly
from apps.settings.configs import JnDataCols



def _single_file_format_checker(fmt: str | List[str], file: UploadedFile):
    """
    単一ファイルのフォーマットが、処理できるフォーマットかを確かめる
    Returns:
        bool: Trueならば処理可能、Falseならば処理不可能
    """
    file_name = file.name
    input_fmt = file_name[file_name.rfind('.'): ]
    message = """
    Error message:   
    入力ファイルのフォーマットを間違えています。  
    {correct} を入力して下さい。  
    現在は {uncorrect} が読み込まれています。
    """
    if isinstance(fmt, str):
        if fmt != input_fmt:
            st.error(message.format(correct=fmt, uncorrect=input_fmt))
            return False
        else:
            return True
    else:
        if not input_fmt in fmt:
            st.error(message.format(correct=fmt, uncorrect=input_fmt))
            return False
        else:
            return True
    

def _multi_file_format_checker(fmt: str | List[str], files: List[UploadedFile]):
    """
    複数ファイルのフォーマットが、処理できるフォーマットかを確かめる
    Returns:
        bool: Trueならば処理可能、Falseならば処理不可能
    """
    file_names = [file.name for file in files]
    input_fmts = [fn[fn.rfind('.'): ] for fn in file_names]
    message = """
    Error message:   
    入力ファイルのフォーマットを間違えています。  
    {correct} を入力して下さい。  
    現在は {uncorrect} が読み込まれています。
    """
    if isinstance(fmt, str):
        for ifmt in input_fmts:
            if ifmt != fmt:
                st.error(message.format(correct=fmt, uncorrect=ifmt))
                return False
    else:
        for ifmt in input_fmts:
            if not ifmt in fmt:
                st.error(message.format(correct=fmt, uncorrect=ifmt))
                return False
        return True


def format_checker(
    fmt: str | List[str], 
    file: UploadedFile | List[UploadedFile]
):
    """
    入力したファイルが指定したフォーマットと一致しているかを確かめる
    Returns:
        bool: Trueならば処理可能、Falseならば処理不可能
    """
    if isinstance(file, List):
        res = _multi_file_format_checker(fmt, file)
    else:
        res = _single_file_format_checker(fmt, file)
    return res


def poly_cross_checker(geom: Polygon | MultiPolygon):
    """
    # Polygonの境界線がクロスしていないかを確かめる
    Returns:
        bool: Trueならば処理可能、Falseならば処理不可能
    """
    e_message = """
    Error message:  
    測量結果を閉合しようとしていますが、境界線が交差しています。  
    測点を並び替えて交差しないように調整して下さい。
    """
    s_message = """境界線は交差していません。"""
    if isinstance(geom, Polygon) | isinstance(geom, MultiPolygon):
        if geom.is_valid:
            st.success(s_message)
            return True
        else:
            st.error(e_message)
            return False


def collection_checker(df: pl.DataFrame) -> bool:
    # DataFrame内の全ての行が、セミダイナミック補正済みかを確かめる
    jn_confs = JnDataCols()
    message = """
    Warning message:  
    セミダイナミック補正されていない測点があります。  
    補正しない限り測量野帳は出力する事が出来ません。  
    """
    placeholder  = st.empty()
    if None in df[jn_confs.epsg_col].to_list():
        # 補正されていない測点が1つでもあるならば、補正を実行させる
        st.warning(message, icon='😭')
        return False
    else:
        # セミダイナミック補正済みの場合は補正させない
        st.session_state['dataframe'] = df
        st.success("""セミダイナミック補正済みです""", icon='😃')
        return True


def count_poly_in_gdf(gdf: gpd.GeoDataFrame):
    # GeoDataFrame内にある`Polygon`または`MultiPolgon`の行が1行かを確かめる
    if 1 < gdf.shape[0]:
        message = """
        Error message:  
        データ内のPolygonの数が多い。  
        Polygonは1つしか受け付けません。
        """
        st.error(message)
        return False
    elif gdf.shape[0] < 1:
        message = """
        Error message:  
        データ内にポリゴンが存在しません。  
        Polygonのファイルを入力して下さい。
        """
        st.error(message)
        return False
    return True


def confirmation_existence_poly(gdf: gpd.GeoDataFrame) -> bool:
    # GeoDataFrame内に`Polygon`または`MultiPolgon`の行があるかを確かめる
    geom = gdf.geometry.iloc[0]
    geom_types = {3: 'Polygon', 6: 'MultiPolygon'}
    if geom_types.get(shapely.get_type_id(geom)) is None:
        message = """
        Error message:  
        データ内にポリゴンのオブジェクトが存在しません。  
        "xxx_Poly.geojson" も入力して下さい。
        """
        st.error(message)
        return False
    return True


def confirmation_existence_points(gdf: gpd.GeoDataFrame) -> bool:
    # GeoDataFrame内に`Point`のデータがあるかを確かめる
    if gdf.shape[0] == 0:
        message = """
        Error message:  
        データ内にポイントのオブジェクトが存在しません。  
        "xxx_Point.geojson" も入力して下さい。
        """
        st.error(message)
        return False
    return True


def vertex_matching(poly: Polygon | MultiPolygon, points: List[Point]) -> bool:
    # `Polygon`の頂点と`Point`の頂点が一致していて、数も同数なのを確かめる
    # まずは頂点数を確かめる
    count_message = """
    Error message:  
    ポリゴンの頂点数とポイントの数が一致していません。
    """
    poly_id = shapely.get_type_id(poly)
    poly_vertex = []
    if poly_id == 3:
        # Single geometry
        poly_vertex = geom_disassembly(poly, 'point')[: -1]
    elif poly_id == 6:
        # Multi geometry
        polys = geom_disassembly(poly, 'point')
        for _poly in polys:
            vertex = _poly[: -1]
            poly_vertex += vertex
    if len(poly_vertex) != len(points):
            st.error(count_message)
    # 頂点の位置が一致しているかを確かめる
    not_exists = []
    for point in points:
        if not point in poly_vertex:
            not_exists.append(point)
    if not_exists:
        message = f"""
        Warning message:  
        ポリゴンとポイントの頂点位置が一致していません。  
        端数の可能性もあるので処理は可能にしていますが、注意して下さい。  
        一致しない測点数は {len(not_exists)} 点です。
        """
        st.warning(message)


def confirmation_existence_pnp(gdf: gpd.GeoDataFrame) -> bool:
    poly_types = [3, 6]
    poly_count = 0
    point_type = 0
    point_count = 0
    geom_ids = [shapely.get_type_id(geom) for geom in gdf.geometry.to_list()]
    for _id in geom_ids:
        if _id in poly_types:
            poly_count += 1
        elif _id == point_type:
            point_count += 1
    if poly_count < 1:
        message = f"""
        Error message: 
        ポリゴンのデータが存在しません。
        このアプリで出力した "xxx_PnP.geojson" のデータを入力して下さい。
        """
        st.error(message)
    elif 1 < poly_count:
        message = f"""
        Error message: 
        ポリゴンが多すぎます。
        このアプリで出力した "xxx_PnP.geojson" のデータを入力して下さい。
        """
        st.error(message)
    elif poly_count + point_count != gdf.shape[0]:
        message = f"""
        Error message: 
        データ行数 != (ポリゴン数 + ポイント数)  
        データ数が一致しません。LineStringのデータなどを入れていませんか?
        """
        st.error(message)


def count_data_rows(gdf: gpd.GeoDataFrame):
    # `GeoDataFrame`が複数行ないかを確かめる
    if 1 < gdf.shape[0]:
        message = f"""
        Error message:  
        データの行数は1行だけアップロードが可能です。  
        このデータは {gdf.shape[0]} 行あります。
        """
        st.error(message)