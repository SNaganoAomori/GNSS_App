"""
.DTAファイル作成の為のPythonモジュール

"""
from dataclasses import dataclass
import datetime
from io import BytesIO
from typing import List
import zipfile

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import pyproj
import shapely
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from apps.convert_coords import CoordinatesFormatter
from apps.documents import Summary
from apps.exception import confirmation_existence_points
from apps.merge_page import convert_lang
from apps.geometries import GeoDatasets
from apps.geometries import select_geom_rows
from apps.merge_page import uploder
from apps.projective_transformer import create_tramsformer
from apps.projective_transformer import transformer_project
from apps.settings.configs import JnDataCols
from apps.settings.configs import mag_csv_file
summary = Summary()


@dataclass
class RelativeCoordinate:
    # 相対座標のデータクラス
    azimuth: float=None
    distance: float=None
    azimuth_lst: List[float]=None
    distance_lst: List[float]=None


class CoordsToCompass(object):
    def __init__(
        self, 
        xs: List[float]=None, 
        ys: List[float]=None, 
        epsg: int=None
    ):
        self.xs = xs
        self.ys = ys
        self.in_epsg = epsg
        self.ellipsoid = 'GRS80'
        self.round_int = 1
        if epsg is None:
            pass
        elif epsg != 4326:
            # WGS84以外ならば投影変換
            transformer = create_tramsformer(self.in_epsg, 4326)
            abs_coords = transformer_project(xs, ys, transformer=transformer)
            self.xs = abs_coords.lons
            self.ys = abs_coords.lats


    def calc_azimuth_and_distance(
        self,
        behind_lon: float, 
        behind_lat: float, 
        forward_lon: float, 
        forward_lat: float,
    ) -> RelativeCoordinate:
        """経緯度から方位角と水平距離を計算します
        Args:
            behind_lon(float): n番目の経度
            behind_lat(float): n番目の緯度
            forward_lon(float): n+1番目の経度
            forward_lat(float): n+1番目の緯度
        Returns:
            RelativeCoordinate:
                azimuth(float): 方位角（真北）
                distance(float): 水平距離
        """
        g = pyproj.Geod(ellps=self.ellipsoid)
        result = g.inv(behind_lon, behind_lat, forward_lon, forward_lat)
        azimuth = result[0]
        if azimuth < 0:
            azimuth += 360
        distance = result[2] 
        return RelativeCoordinate(azimuth=round(azimuth, self.round_int), 
                                  distance=round(distance, self.round_int)
        )
    
    def calc_azimuth_and_distance_all(
        self, 
        lons: List[float]=None,
        lats: List[float]=None,
        closed: bool=True,
    ) -> RelativeCoordinate:
        """
        経緯度のリストから真北の方位角と水平距離を計算します。
        Args:
            lons(float): 経度のリスト
            lats(float): 緯度のリスト
            closed(bool): 閉合するか、閉合する場合は0番目の経緯度を最後にも追加する
        Returns:
            RelativeCoordinate:
                azimuth_lst(List[float]): 方位角（真北）
                distance_lst(List[float]): 水平距離
        """
        if lons is None:
            lons = self.xs
            lats = self.ys
        if closed:
            # 閉合の場合、最初の座標を最後にも追加する
            xs = lons + [lons[0]]
            ys = lats + [lats[0]]
        else:
            # 閉合しない場合
            xs = lons
            ys = lats
        # 方位角と水平距離を計算
        azimuth_lst = []
        distance_lst = []
        for i in range(1, len(xs)):
            behind_lon = xs[i - 1]
            behind_lat = ys[i - 1]
            forward_lon = xs[i]
            forward_lat = ys[i]
            relative_coords = (
                self
                .calc_azimuth_and_distance(
                    behind_lon, 
                    behind_lat, 
                    forward_lon, 
                    forward_lat
                )
            )
            azimuth_lst.append(relative_coords.azimuth)
            distance_lst.append(relative_coords.distance)
        return RelativeCoordinate(azimuth_lst=azimuth_lst, 
                                  distance_lst=distance_lst
        )


def azimuth_and_distance(
    behind_lon: float, 
    behind_lat: float, 
    forward_lon: float, 
    forward_lat: float,
    epsg: int,
) -> RelativeCoordinate:
    """
    経緯度から方位角と水平距離を計算します
    Args:
        behind_lon(float): n番目の経度
        behind_lat(float): n番目の緯度
        forward_lon(float): n+1番目の経度
        forward_lat(float): n+1番目の緯度
        epsg(int): 投影法のEPSGコード
    Returns:
        RelativeCoordinate:
            azimuth(float): 方位角（真北）
            distance(float): 水平距離
    """
    compass = CoordsToCompass()
    if epsg != 4326:
        # WGS84以外ならば投影変換
        transformer = create_tramsformer(epsg, 4326)
        behind_coords = transformer_project(
            behind_lon, 
            behind_lat, 
            transformer=transformer
        )
        behind_lon = behind_coords.lon
        behind_lat = behind_coords.lat
        forward_coords = transformer_project(
            forward_lon, 
            forward_lat,
            transformer=transformer
        )
        forward_lon = forward_coords.lon
        forward_lat = forward_coords.lat
    # 方位角と水平距離を計算
    relative_coords = (
        compass
        .calc_azimuth_and_distance(
            behind_lon,
            behind_lat,
            forward_lon,
            forward_lat
        )
    )
    return relative_coords


def azimuth_and_distance_all(
    lons: List[float], 
    lats: List[float], 
    closed: bool,
    epsg: int
) -> RelativeCoordinate:
    """
    経緯度のリストから真北の方位角と水平距離を計算します。
    Args:
        lons(float): 経度のリスト（WGS84以外も可）
        lats(float): 緯度のリスト（WGS84以外も可）
        closed(bool): 閉合するか、閉合する場合は0番目の経緯度を最後にも追加する
        epsg(int): 投影法のEPSGコード
    Returns:
        RelativeCoordinate:
            azimuth_lst(List[float]): 方位角（真北）
            distance_lst(List[float]): 水平距離
    """
    if epsg != 4326:
        # WGS84以外ならば投影変換
        coords = transformer_project(lons, lats, epsg, 4326)
        lons = coords.lons
        lats = coords.lats
    # 方位角と水平距離を計算
    compass = CoordsToCompass()
    relative_coords = compass.calc_azimuth_and_distance_all(lons, lats, closed)
    return relative_coords

def true_north_to_mag_north(
    azimuth_lst: List[float], 
    points: List[shapely.Point]
) -> List[float]:
    # UTMに投影変換
    point_gdf = gpd.GeoDataFrame(geometry=points, crs='EPSG:4326')
    point_gdf_utm = point_gdf.to_crs(point_gdf.estimate_utm_crs())
    # 偏角のファイルを読み込む
    mag_df = pd.read_csv(mag_csv_file)
    mag_points = gpd.points_from_xy(mag_df['lon'], mag_df['lat'])
    mag_gdf = gpd.GeoDataFrame(mag_df, geometry=mag_points, crs='EPSG:4326')
    mag_gdf_utm = mag_gdf.to_crs(point_gdf_utm.crs)
    delta_lst = []
    for point in point_gdf_utm.geometry:
        mag_gdf_utm['distance'] = mag_gdf_utm.distance(point)
        mag_gdf_utm = mag_gdf_utm.sort_values('distance').copy()
        dms =  mag_gdf_utm.iloc[0]['delta']
        cf = CoordinatesFormatter(dms)
        now = datetime.datetime.now()
        delta = cf.degree + 0.05 * (now.year - 2020)
        delta_lst.append(delta)
    new_azimuth_lst = []
    for azimuth, delta_lst in zip(azimuth_lst, delta_lst):
        azimuth -= delta
        if azimuth < 0:
            new_azimuth_lst.append(azimuth + 360)
        else:
            new_azimuth_lst.append(azimuth)
    return [round(azimuth, 1) for azimuth in new_azimuth_lst]


def single_dta_sentence(
    pt_names: List[str | float],
    azimuth_lst: List[float],
    distance_lst: List[float]
) -> str:
    """
    シンプルなDTAファイルに書き込む文字列を作成
    Args:
        pt_names(List[str | float]): 測点名
        azimuth_lst(List[float]): 方位角（真北）
        distance_lst(List[float]): 水平距離
    Returns:
        str: DTAファイルの文字列、このまま書き込み出来る
    """
    # Indexの作成 [' 1(D-1.0)', ' 2(D-2.0)', ...]
    idx = [f"{i + 1}({name})" for i, name in enumerate(pt_names)]
    header = ' 0  0  0  0\n'
    for name, azimuth, distance in zip(idx, azimuth_lst, distance_lst):
        header += f" {name}  {azimuth}  0  {distance}\n"
    return header



def write_dta_sentence(
    pt_names: List[str | float],
    lons: List[float], 
    lats: List[float], 
    epsg: int,
    closed: bool=True,
    mag_corr: bool=False
) -> str:
    """
    DTAファイルに書き込む文字列の作成。単一区画でも複数でも可。複数の場合は全て
    の引数に変数を渡す必要あり。
    Args:
        pt_names(List[str | float]): 測点名
        lons(List[float]): 経度のリスト
        lats(List[float]): 緯度のリスト
        epsg(int): main区画のEPSGコード
        closed(bool): 閉合するか、Trueの場合は0番目の経緯度を最後にも追加する
    Returns:
        str: DTAファイルの文字列、このまま書き込み出来る
    """
    if epsg != 4326:
        # main座標の投影変換
        coords = (
            transformer_project(
                lon=lons, 
                lat=lats, 
                in_epsg=epsg,
                out_epsg=4326
            )
        )
        lons = coords.lons
        lats = coords.lats
    
    # メイン区画の方位角と水平距離を計算
    relative_coords = azimuth_and_distance_all(lons, lats, closed, 4326)
    if mag_corr:
        mag_azimuth_lst = true_north_to_mag_north(
            relative_coords.azimuth_lst, 
            points=[shapely.Point(x, y) for x, y in zip(lons, lats)]
        )
        relative_coords.azimuth_lst = mag_azimuth_lst
    sentence = single_dta_sentence(
        pt_names=pt_names,
        azimuth_lst=relative_coords.azimuth_lst,
        distance_lst=relative_coords.distance_lst
    )
    return sentence


def write_csv_sentence(
    pt_names: List[str | float],
    lons: List[float], 
    lats: List[float], 
    epsg: int,
    closed: bool=True
) -> str:
    coords = azimuth_and_distance_all(lons, lats, closed, epsg)
    zipper = zip(pt_names, coords.azimuth_lst, coords.distance_lst)
    sentence = ''
    for i, (name, azimuth, distance) in enumerate(zipper):
        sentence += f"{i},{name},{azimuth},0,{distance}\n"
    return sentence


def plot_polys(dfs: List[gpd.GeoDataFrame], fps: List[str]) -> go.Figure:
    jn_confs = JnDataCols()
    # 最初の測点を最後にも追加
    dfs = [
        pd.concat([df.copy(), df[: 1].copy()])
        for df in dfs
    ]
    layout = go.Layout(
        yaxis=dict(scaleanchor='x'),
        scene=dict(aspectratio=dict(x=1, y=1))
    )
    fig = go.Figure(layout=layout)
    for df, name in zip(dfs, fps):
        name = name.replace('.geojson', '')
        x = df.geometry.x.to_list()
        y = df.geometry.y.to_list()
        t = df[jn_confs.pt_name_col].to_list()
        scatter = go.Scatter(
            x=x, y=y, text=t, mode='lines+markers+text',
            textposition='middle left', textfont=dict(size=13, color='black')
            ,name=name
        )
        fig.add_trace(scatter)
    fig.update_layout(
        hovermode=False,
        legend=dict(x=-0.1, y=0, xanchor='left', yanchor='top', orientation='h')
    )
    return fig


def plot_add_line(datasets: List[GeoDatasets], fig: go.Figure) -> go.Figure:
    name_col = JnDataCols().pt_name_col
    main_gdf = datasets[0].gdf
    for data in datasets[1: ]:
        sub_gdf = data.gdf
        main_coor = (
            main_gdf[main_gdf[name_col] == data.conn_main_pt_name]
            .geometry.to_list()[0]
        )
        sub_coor = (
            sub_gdf[sub_gdf[name_col] == data.conn_sub_pt_name]
            .geometry.to_list()[0]
        )
        xs = [main_coor.x, sub_coor.x] 
        ys = [main_coor.y, sub_coor.y]
        scatter = go.Scatter(
            x=xs, y=ys,
            marker=dict(color='black'),
            showlegend=False
        )
        fig.add_trace(scatter)
    return fig
        


@dataclass
class CombinationSettings:
    name: str
    gdf: gpd.GeoDataFrame
    pt_names: List[str]
    option: str=None
    conn_main_pt_name: str=None
    conn_sub_pt_name: str=None


@dataclass
class MultiDtaCoords:
    main_coords: List[RelativeCoordinate]
    sub_coords: List[RelativeCoordinate]
    conn_coords: List[RelativeCoordinate]


class MultiDtaTools(object):
    def __init__(self):
        self._confs = JnDataCols()
        self._pt_name_col = self._confs.pt_name_col

    def create_point_datasets(
        self, 
        files: List[UploadedFile]
    ) -> List[CombinationSettings]:
        """
        ファイルからGeoDataFrameを作成し、GeometryがPointだけになるように絞り込む
        """
        datasets = []
        for file in files:
            _fname = file.name
            _gdf = (
                convert_lang(
                    select_geom_rows(
                        gpd.read_file(file), 
                        False
                    )
                )
            )
            confirmation_existence_points(_gdf)
            _pt_names = _gdf[self._pt_name_col].astype(str).to_list()
            _dic = {
                'name': _fname,
                'gdf': _gdf,
                'pt_names': _pt_names
            }
            datasets.append(CombinationSettings(**_dic))
        return datasets

    def check_main_file(self, datasets: List[CombinationSettings]) -> List[bool]:
        """
        メインファイルにチェックを入れさせる
        """
        st.markdown('<br>', True)
        st.markdown('### メインファイルとサブファイルに分ける')
        st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
        expander = st.expander('メイン区画のファイルにチェックを入れて下さい')
        checks = []
        for data in datasets:
            # メインファイルにチェックを入れさせる
            check = expander.checkbox(label=data.name)
            checks.append(check)
        return checks

    def select_connect_points(
        self, 
        datasets: List[CombinationSettings], 
        main_data: CombinationSettings
    ):
        st.markdown('<br>', True)
        st.markdown('### 連結する測点を選択する')
        st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
        expander = st.expander(label='連結させる測点を選択する')
        for i, data in enumerate(datasets):
            expander.markdown('---')
            expander.markdown(data.name.replace('.geojson', ''))
            left, right = expander.columns(2)
            data.conn_main_pt_name = left.selectbox(
                'メインの測点番号' + ' ' * i, 
                options=main_data.pt_names
            )
            data.conn_sub_pt_name = right.selectbox(
                'サブの測点番号' + ' ' * i, 
                options=data.pt_names
            )
        used = []
        continued = True
        for data in datasets:
            if data.conn_main_pt_name in used:
                continued = False
                expander.markdown(':red[選択しているメイン区画の測点が重複しています]:')
            else:
                used.append(data.conn_main_pt_name)
        return datasets, continued

    def multi_azimuth_and_distance(
        self,
        datasets: List[CombinationSettings], 
        main_data: CombinationSettings
    ) -> MultiDtaCoords:
        """
        方位角と水平距離を計算する
        """
        main_gdf = main_data.gdf
        main_coords = (
            azimuth_and_distance_all(
                lons=main_gdf.geometry.x.to_list(), 
                lats=main_gdf.geometry.y.to_list(), 
                closed=True, 
                epsg=main_gdf.crs.to_epsg()
            )
        )
        sub_coords = []
        conn_coords = []
        for data in datasets:
            sub_gdf = data.gdf
            sub_coords += [
                azimuth_and_distance_all(
                    lons=sub_gdf.geometry.x.to_list(),
                    lats=sub_gdf.geometry.y.to_list(),
                    closed=True,
                    epsg=sub_gdf.crs.to_epsg()
                )
            ]
            main_conn_geom = main_gdf[
                main_gdf[self._pt_name_col] == data.conn_main_pt_name
            ].geometry.to_list()[0]
            sub_conn_geom = sub_gdf[
                sub_gdf[self._pt_name_col] == data.conn_sub_pt_name
            ].geometry.to_list()[0]
            conn_coords += [
                azimuth_and_distance(
                    behind_lon=main_conn_geom.x,
                    behind_lat=main_conn_geom.y,
                    forward_lon=sub_conn_geom.x,
                    forward_lat=sub_conn_geom.y,
                    epsg=sub_gdf.crs.to_epsg()
                )
            ]
        return MultiDtaCoords(main_coords, sub_coords, conn_coords)

    def create_file_names(self, datasets: List[CombinationSettings]) -> List[str]:
        file_names = []
        for data in datasets:
            fp = data.name.replace('geojson', 'DTA')
            file_names.append(fp)
        return file_names

    def write_dta_sentence(
        self,
        main_data: CombinationSettings,
        datasets: List[CombinationSettings],
        coords_sets: MultiDtaCoords
    ):
        conn_main_pt_names = []
        conn_sub_pt_names = []
        sub_dtas = []
        # サブ区画のdta作成
        for data, coords in zip(datasets, coords_sets.sub_coords):
            pt_names = data.gdf[self._pt_name_col].to_list()
            dta = single_dta_sentence(
                pt_names=pt_names,
                azimuth_lst=coords.azimuth_lst,
                distance_lst=coords.distance_lst
            )
            sub_dtas.append(dta)
            conn_main_pt_names.append(data.conn_main_pt_name)
            conn_sub_pt_names.append(data.conn_sub_pt_name)
        # メインDTAの作成
        main_pt_names = main_data.gdf[self._pt_name_col].to_list()
        indent = ' ' * 297
        main_dta = ' 0  0  0  0\n'
        loop = zip(
            main_pt_names,
            coords_sets.main_coords.azimuth_lst,
            coords_sets.main_coords.distance_lst
        )
        sub_fps = []
        sorted_sub_dtas = []
        for i, (name, azimuth, distance) in enumerate(loop):
            idx = f"{i + 1}({name})"
            sentence = f" {idx}  {azimuth}  0  {distance}"
            if name in conn_main_pt_names:
                get_idx = conn_main_pt_names.index(name)
                # 連結線の作成
                conn_coords = coords_sets.conn_coords[get_idx]
                sentence += f"  {conn_coords.azimuth}  0  {conn_coords.distance}"
                # 連結点の取得とファイル名の取得
                sub_fp = datasets[get_idx].name.replace('geojson', 'DTA')
                sub_fps.append(sub_fp)
                sentence += f"{indent}{conn_sub_pt_names[get_idx]}  {sub_fp}"
                # sub DTAの並び替え
                sorted_sub_dtas.append(sub_dtas[get_idx])
            sentence += '\n'
            main_dta += sentence
        dtas = [main_dta, ] + sorted_sub_dtas
        file_names = [main_data.name.replace('geojson', 'DTA'), ] + sub_fps
        return dtas, file_names

    def download_zipfile(self, dtas: List[str], file_names: List[str]):
        # BytesIOオブジェクトを作成する
        buffer = BytesIO()

        # ZipFileオブジェクトを作成する
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # JSON文字列をZipFileオブジェクトに書き込む
            for sentence, fp in zip(dtas, file_names):
                zip_file.writestr(fp, sentence.encode('cp932'))

        # 圧縮されたファイルのバイト列を取得する
        compressed_file = buffer.getvalue()

        # ダウンロードボタンを作成する
        expander = st.expander('DTAファイルが入った圧縮ファイル')
        expander.download_button(
            label='Download',
            data=compressed_file,
            file_name=f"{file_names[0].replace('.DTA', '')}.zip",
            mime='application/zip',
            type='primary'
        )


def multi_file_to_magnetic_correction(
    coords: MultiDtaCoords, 
    gdfs: List[gpd.GeoDataFrame]
) -> MultiDtaCoords:
    """複数ファイルの真北から磁北への変換"""
    base = shapely.MultiPoint(pd.concat(gdfs).geometry.to_list()).centroid
    coords.main_coords.azimuth_lst = true_north_to_mag_north(
        coords.main_coords.azimuth_lst,
        points=[base for _ in range(len(coords.main_coords.azimuth_lst))]
    )
    sub_coords = []
    for coord in coords.sub_coords:
        coord.azimuth_lst = true_north_to_mag_north(
            coord.azimuth_lst,
            points=[base for _ in range(len(coord.azimuth_lst))]
        )
        sub_coords.append(coord)
    conn_coords = []
    for coord in coords.conn_coords:
        coord.azimuth = true_north_to_mag_north([coord.azimuth], [base])[0]
        conn_coords.append(coord)
    return MultiDtaCoords(coords.main_coords, sub_coords, conn_coords)
    

    

def merge_page_dta():
    """GeoJSONファイルを結合してDTAファイルが入った圧縮フォルダを作成するページ"""
    summary.show_marge_dta_summary
    # ファイルの入力
    files = uploder(' ')
    # PointのGeometryが入った行のみに絞り込む、列名を日本語に変換
    dta_tools = MultiDtaTools()
    datasets = dta_tools.create_point_datasets(files)
    # メインファイルとサブファイルに分ける
    checks = dta_tools.check_main_file(datasets)
    preprod = False
    if sum([1 for check in checks if check]) == 1:
        # メインファイルが一つだけの場合は処理する
        main_data = [data for check, data in zip(checks, datasets) if check][0]
        datasets.remove(main_data)
        gdfs, names = [main_data.gdf], ['メイン区画']
        for data in datasets:
            gdfs.append(data.gdf)
            names.append(data.name)
        datasets, continued = dta_tools.select_connect_points(datasets, main_data)
        # 確認用にPlotする
        fig = plot_polys(gdfs, names)
        if continued:
            fig = plot_add_line([main_data] + datasets, fig)
            preprod = True
        st.plotly_chart(fig, config={'modeBarButtonsToRemove': ["lasso2d", "select2d"]})
    
    if preprod:
        # 前処理が終わったら
        st.markdown('<br>', True)
        st.markdown('### 圧縮ファイルのダウンロード')
        st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
        sentence = "国土地理院で公開されている2020年時点での地域ごとの偏角一覧を使用。  "
        sentence += "https://www.gsi.go.jp/buturisokuchi/menu03_magnetic_chart.html"
        mag_corr = st.toggle('磁北への変換 ', help=sentence)
        calc = st.toggle('計算させる')
        if calc:
            coords = dta_tools.multi_azimuth_and_distance(datasets, main_data)
            if mag_corr:
                coords = multi_file_to_magnetic_correction(coords, gdfs)
            dtas , file_names = dta_tools.write_dta_sentence(main_data, datasets, coords)
            dta_tools.download_zipfile(dtas, file_names)
