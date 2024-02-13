"""
.DTAファイル作成の為のPythonモジュール

"""
from dataclasses import dataclass
from io import BytesIO
from typing import List
import zipfile

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import pyproj
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from apps.documents import Summary
from apps.exception import confirmation_existence_points
from apps.merge_page import convert_lang
from apps.geometries import GeoDatasets
from apps.geometries import select_geom_rows
from apps.merge_page import uploder
from apps.projective_transformer import create_tramsformer
from apps.projective_transformer import transformer_project
from apps.settings.configs import JnDataCols
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


def multiple_dta_sentence(
    pt_names: List[str | float],
    azimuth_lst: List[float],
    distance_lst: List[float],
    main_conns: List[str | float],
    conn_azimuth_lst: List[float],
    conn_distance_lst: List[float],
    sub_conns: List[str | float],
    sub_file_paths: List[str],
) -> str:
    """
    区画が複数あるDTAファイルに書き込む文字列の作成
    Args:
        pt_names(List[str | float]): 測点名
        azimuth_lst(List[float]): 方位角（真北）
        distance_lst(List[float]): 水平距離
        main_conns(List[str | float]): 従属区画と接続するmain区画の測点名
        azimuth_lst(List[float]): 従属区画と接続するmain区画の測点からの方位角
        distance_lst(List[float]): 従属区画と接続するmain区画の測点からの水平距離
        sub_conns(List[str | float]): main区画と接続する従属区画の測点名
        sub_file_paths(List[str]): 従属区画のファイル名
    Returns:
        str: DTAファイルの文字列、このまま書き込み出来る
    """
    indent = ' ' * 297
    header = ' 0  0  0  0\n'
    for i, (name, azimuth, distance) in \
            enumerate(zip(pt_names, azimuth_lst, distance_lst)):
        # Indexの作成 [' 1(D-1.0)', ' 2(D-2.0)', ...]
        idx = f"{i + 1}({name})"
        sentence = f" {idx}  {azimuth}  0  {distance}"
        if name in main_conns:
            i = main_conns.index(name)
            # 従属ファイルまでの方位角と距離を入力
            sentence += f'  {conn_azimuth_lst[i]}  0  {conn_distance_lst[i]}'
            sentence += f"{indent}{sub_conns[i]}  {sub_file_paths[i]}"
        sentence += '\n'
        header += sentence
    return header


def write_dta_sentence(
    pt_names: List[str | float],
    lons: List[float], 
    lats: List[float], 
    epsg: int,
    closed: bool=True,
    main_conns: List[str | float]=None,
    sub_conns: List[str | float]=None,
    sub_lons: List[float]=None,
    sub_lats: List[float]=None,
    sub_file_paths: List[str]=None,
    sub_epsg: int=None
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
        main_conns(List[str | float]): 従属区画と接続するmain区画の測点名
        sub_conns(List[str | float]): main区画と接続する従属区画の測点名
        sub_lons(List[float]): main区画と接続する従属区画測点の経度のリスト
        sub_lats(List[float]): main区画と接続する従属区画測点の緯度のリスト
        sub_file_paths(List[str]): 従属区画のファイル名
        sub_epsg(int): 従属区画のEPSGコード
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
    # 複数の区画を結合するならば　
    if not main_conns is None:
        if sub_epsg != 4326:
            # 結合先座標の投影変換
            coords = (
                transformer_project(
                    lon=sub_lons, 
                    lat=sub_lats, 
                    in_epsg=sub_epsg,
                    out_epsg=4326
                )
            )
            sub_lons = coords.lons
            sub_lats = coords.lats
        # メイン区画経緯度から結合区画測点の経緯度までの相対座標を計算
        conn_azimuth_lst = []
        conn_distance_lst = []
        for m_name, s_lon, s_lat in zip(main_conns, sub_lons, sub_lats):
            # 従属測点と結合するメイン区画の座標を取得
            m_idx = pt_names.index(m_name)
            m_lon = lons[m_idx]
            m_lat = lats[m_idx]
            # メイン区画測点から従属区画測点までの方位角と水平距離を計算
            _relative = (
                azimuth_and_distance(
                    behind_lon=m_lon,
                    behind_lat=m_lat,
                    forward_lon=s_lon,
                    forward_lat=s_lat,
                    epsg=4326
                )
            )
            conn_azimuth_lst.append(_relative.azimuth)
            conn_distance_lst.append(_relative.distance)
        # DTAセンテンスの作成（複数区画）
        sentence = multiple_dta_sentence(
            pt_names=pt_names,
            azimuth_lst=relative_coords.azimuth_lst,
            distance_lst=relative_coords.distance_lst,
            main_conns=main_conns,
            conn_azimuth_lst=conn_azimuth_lst,
            conn_distance_lst=conn_distance_lst,
            sub_conns=sub_conns,
            sub_file_paths=sub_file_paths
        )
    else:
        # DTAセンテンスの作成（単独区画）
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
        coords_sets: MultiDtaCoords,
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
        calc = st.toggle('計算させる')
        if calc:
            coords = dta_tools.multi_azimuth_and_distance(datasets, main_data)
            dtas , file_names = dta_tools.write_dta_sentence(main_data, datasets, coords)
            dta_tools.download_zipfile(dtas, file_names)



if __name__ == '__main__':
    import geopandas as gpd
    # outer = gpd.read_file(r"D:\マイドライブ\DEL\test_multiple_jsons\OuterPoly.geojson")
    # island = gpd.read_file(r"D:\マイドライブ\DEL\test_multiple_jsons\Island.geojson")
    # d = dict(
    #     pt_names=outer['測点名'].to_list(),
    #     lons=outer.geometry.x.to_list(),
    #     lats=outer.geometry.y.to_list(),
    #     epsg=6678,
    #     main_conns=['4.0',],
    #     sub_conns=['D-5.0', ],
    #     sub_lons=[39765.294807053214754,],
    #     sub_lats=[126928.37512831465574, ],
    #     sub_file_paths=['island.dta', ],
    #     sub_epsg=6678
    # )
    # sentence = write_dta_sentence(**d)
    gdf = gpd.read_file(r"Y:\OWLを利用した立木調査\geometries.gpkg", layer='対象地')
    xs, ys = [], []
    for coords in gdf.geometry[3].__geo_interface__.get('coordinates')[0][0]:
        xs.append(coords[0])
        ys.append(coords[1])
    d = dict(
        pt_names=[i + 1 for i in  range(len(xs))],
        lons=xs,
        lats=ys,
        epsg=6678
    )   
    sentence = write_dta_sentence(**d)

    outfp= r"Y:\OWLを利用した立木調査\2023_大鰐_586は1_586い5\コンパス\仮想コンパス測量成果_586結合.dta"
    with open(outfp, mode='w', encoding='cp932') as f:
        f.write(sentence)
