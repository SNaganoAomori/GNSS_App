from dataclasses import dataclass
from typing import Dict
from typing import List

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import polars as pl
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from apps.documents import Summary
from apps.exception import format_checker
from apps.exception import confirmation_existence_pnp
from apps.exception import confirmation_existence_points
from apps.exception import confirmation_existence_poly
from apps.settings.configs import check_lang_jn_in_df
from apps.settings.configs import rename_en_to_jn_in_df
from apps.settings.configs import rename_jn_to_en_in_df
from apps.geometries import select_geom_rows
from apps.geometries import GeoDatasets
from apps.geometries import SingleGeometries
from apps.geometries import merge_poly_gdf
from apps.geometries import edit_multipoly_kml
from apps.geometries import edit_points_kml
from apps.settings.configs import JnDataCols
from apps.settings.configs import rename_jn_to_en_in_df
from apps.settings.configs import rename_en_to_jn_in_df
from apps.sidebar import survey_area_confs
summary = Summary()



def uploder(_add: str='') -> List[UploadedFile]:
    st.markdown('<br>', True)
    st.markdown('### GeoJSONデータの入力')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    expander = st.expander(
        'GeoJSONファイルのアップロード' + _add,
        expanded=True
    )
    expander = summary.show_input_geoj2(expander)
    files = expander.file_uploader(
        label='ファイル' + _add, 
        accept_multiple_files=True,
        help='GeoJSONファイルを入力して下さい。'
    )
    format_checker('.geojson', files)
    return files


def select_dependency_files(file_names: List[str]) -> Dict[str, str]:
    st.markdown('<br>', True)
    st.markdown('### 区画の重ね方を選択')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    clus_expander = st.expander(
        'ファイル毎に区画の従属性を選択して下さい', 
        expanded=True
    )
    clus = {
        'メインの区画': 0,
        '外側の区画': 1,
        '内側の区画': 2
    }
    selected = {
        0: None,
        1: [],
        2: []
    }
    for file_name in file_names:
        if not selected.get(0) is None:
            select = clus_expander.selectbox(
                f'メインの区画に対する従属性: {file_name}', 
                options=list(clus.keys())[1: ]
            )
        else:
            select = clus_expander.selectbox(
                f'メインの区画に対する従属性: {file_name}', 
                options=list(clus.keys())
            )
        if clus.get(select) == 0:
            selected[0] = file_name
        else:
            selected[clus.get(select)].append(file_name)
    return selected


def generate_file_base() -> str:
    st.markdown('<br>', True)
    st.markdown('### 出力データ名を設定')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    out_name = st.text_input('ファイル名を入力して下さい')
    return out_name


def plot_polys(
    outer_gdfs: List[gpd.GeoDataFrame], 
    inner_gdfs: List[gpd.GeoDataFrame],
    area: float,
    length: float
) -> go.Figure:
    jn_confs = JnDataCols()
    # 最初の測点を最後にも追加
    outer_gdfs = [select_geom_rows(_df, False) for _df in outer_gdfs]
    inner_gdfs = [select_geom_rows(_df, False) for _df in inner_gdfs]
    outers = [
        pd.concat([df.copy(), df[: 1].copy()])
        for df in outer_gdfs
    ]
    inners = [
        pd.concat([df.copy(), df[: 1].copy()])
        for df in inner_gdfs
    ]
    # Layout設定
    layout = go.Layout(
        yaxis=dict(scaleanchor='x'),
        scene=dict(aspectratio=dict(x=1, y=1))
    )
    fig = go.Figure(layout=layout)
    for i, rows in enumerate(outers):
        if i == 0:
            fig.add_trace(
                go.Scatter(
                    x=rows.geometry.x, y=rows.geometry.y,
                    mode='lines', line_color='#2a83a2', fill='tonexty',
                    fillcolor='#00a3af', name='対象区域'
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=rows.geometry.x, y=rows.geometry.y,
                    mode='lines', showlegend=False, line_color='#2a83a2', fill='tonexty',
                    fillcolor='#00a3af'
                )
            )
    for rows in inners:
        fig.add_trace(
            go.Scatter(
                x=rows.geometry.x, y=rows.geometry.y,
                mode='lines',
                line_color='#008899', showlegend=False,
                fill='toself', fillcolor='white'
            )
        )
    fig.update_layout(
        title=f'面積(ha): {area},  周囲長(m): {length}',
        hovermode=False,
        legend=dict(x=-0.1, y=0, xanchor='left', yanchor='top', orientation='h')
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    return fig


@dataclass
class OutputSettings:
    local_epsg: int
    output_epsg: int
    is_en: bool


def select_data_properties() -> OutputSettings:
    st.markdown('<br>', True)
    st.markdown('### データ設定')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    expander = st.expander('開いて設定して下さい', False)
    local_epsg = survey_area_confs(1, expander).get('epsg')
    epsg_codes = {
        '平面直角座標系': local_epsg,
        '経緯度（WGS84）': 4326,
        'Webメルカトル': 3857,
    }
    selected = expander.radio(
        '出力座標系の選択', 
        options=list(epsg_codes.keys())
    )
    is_en = expander.toggle('列名を英語で出力する  ')
    output_epsg = epsg_codes.get(selected)
    return OutputSettings(local_epsg, output_epsg, is_en)


def convert_lang(gdf: gpd.GeoDataFrame):
    if JnDataCols().datetime_col in gdf.columns:
        return gdf
    else:
        return rename_en_to_jn_in_df(gdf)


def check_gdf(gdf: gpd.GeoDataFrame):
    poly_gdf = select_geom_rows(gdf)
    point_gdf = select_geom_rows(gdf, False)
    confirmation_existence_points(point_gdf)
    confirmation_existence_poly(poly_gdf)


def create_geodataframes(
        main_file: UploadedFile, 
        inner_files: List[UploadedFile],
        outer_files: List[UploadedFile],
        output_settings: OutputSettings
) -> GeoDatasets:
    # -------------------- GeoDataFrameの作成 --------------------#
    jn_confs = JnDataCols()
    plot_outers_gdf = []
    plot_inners_gdf = []
    main_gdf = convert_lang(gpd.read_file(main_file))
    check_gdf(main_gdf)
    plot_outers_gdf.append(main_gdf)
    outer_gdf = [convert_lang(gpd.read_file(outer)) for outer in outer_files]
    plot_outers_gdf += outer_gdf
    if outer_gdf:
        outer_gdf = pd.concat(outer_gdf)
        check_gdf(outer_gdf)
    else:
        outer_gdf = None
    inner_gdf = [convert_lang(gpd.read_file(inner)) for inner in inner_files]
    plot_inners_gdf += inner_gdf
    if inner_gdf:
        inner_gdf = pd.concat(inner_gdf)
        check_gdf(inner_gdf)
    else:
        inner_gdf = None
    # MultiPolygonとPointのGeoDataFrameを作成  
    geodatasets = merge_poly_gdf(
        main_gdf=main_gdf, 
        inner_gdf=inner_gdf,
        outer_gdf=outer_gdf,
        local_epsg=output_settings.local_epsg
    )
    #-------------------- 投影変換 --------------------# 
    if geodatasets.poly_gdf.crs.to_epsg != output_settings.output_epsg:
        geodatasets.poly_gdf = (
            geodatasets
            .poly_gdf
            .to_crs(crs=f'EPSG:{output_settings.output_epsg}')
        )
    if geodatasets.point_gdf.crs.to_epsg != output_settings.output_epsg:
        geodatasets.point_gdf = (
            geodatasets
            .point_gdf
            .to_crs(crs=f'EPSG:{output_settings.output_epsg}')
        )
    # 不要な列を削除する
    del_cols = [
        '測点数', 'PDOPの最大値', '衛星数の最小値', 
        '信号周波数の最小値', '面積(ha)', '周囲長(m)'
    ]
    # Plot
    geom = geodatasets.poly_gdf.geometry.to_list()[0]
    area = round(geom.area / 10_000, 4)
    length = round(geom.length, 3)
    fig = plot_polys(plot_outers_gdf, plot_inners_gdf, area, length)
    st.plotly_chart(fig, config={'modeBarButtonsToRemove': ["lasso2d", "select2d"]})
    geodatasets.point_gdf.drop(del_cols, axis=1, inplace=True)
    # 日時文字列の列が日時として読まれている場合がある
    start_col = jn_confs.start_datetime_col
    stop_col = jn_confs.datetime_col
    geodatasets.point_gdf[start_col] = geodatasets.point_gdf[start_col].astype(str)
    geodatasets.point_gdf[stop_col] = geodatasets.point_gdf[stop_col].astype(str)
    geodatasets.poly_gdf[start_col] = geodatasets.poly_gdf[start_col].astype(str)
    geodatasets.poly_gdf[stop_col] = geodatasets.poly_gdf[stop_col].astype(str)
    if output_settings.is_en:
        # 列名を変更する
        geodatasets.point_gdf = rename_jn_to_en_in_df(geodatasets.point_gdf)
        geodatasets.poly_gdf = rename_jn_to_en_in_df(geodatasets.poly_gdf)
    return geodatasets


def download_geojson(geodatasets: GeoDatasets, file_name: str):
    """GeoJSONファイルのダウンロード"""
    st.markdown('<br>', True)
    st.markdown('### 📝 GeoJSONファイルのダウンロード')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    # GeoJSONの作成とDownload
    expander = st.expander('geojsonデータセットを開く', False)
    multi_gjson = (
        pd.concat([geodatasets.poly_gdf, geodatasets.point_gdf])
        .to_json(ensure_ascii=False, indent=2)
    )
    expander.download_button(
        label='ポイント&ポリゴンのgeojsonファイルをダウンロード',
        data=multi_gjson,
        file_name=f'{file_name}_PnP.geojson',
        mime='application/json',
        type='primary' 
    )
    point_gjson = geodatasets.point_gdf.to_json(ensure_ascii=False, indent=2)
    expander.download_button(
        label='ポイントのgeojsonファイルをダウンロード',
        data=point_gjson,
        file_name=f'{file_name}_Points.geojson',
        mime='application/json',
        type='primary' 
    )
    poly_gjson = geodatasets.poly_gdf.to_json(ensure_ascii=False, indent=2)
    expander.download_button(
        label='ポリゴンのgeojsonファイルをダウンロード',
        data=poly_gjson,
        file_name=f'{file_name}_Polygon.geojson',
        mime='application/json',
        type='primary' 
    )


def download_kml(geodatasets: GeoDatasets, file_name: str, is_en: bool):
    """
    KMLファイルのダウンロード
    """
    st.markdown('<br>', True)
    st.markdown('### 📝 KMLファイルのダウンロード')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    expander = st.expander('kmlデータセットを開く', False)
    # PointのKML作成とダウンロード
    point_gdf = geodatasets.point_gdf
    # 強制的にWGS84へ
    if point_gdf.crs.to_epsg() != 4326:
        point_gdf = point_gdf.to_crs(crs='EPSG:4326')
    df = pl.DataFrame(point_gdf.drop('geometry', axis=1))
    sg = SingleGeometries(point_gdf.geometry.to_list(), None, None, None, None)
    point_kml = edit_points_kml(df, sg, is_en).kml()
    expander.download_button(
        label="ポイント.kml ファイルのダウンロード ",
        data=point_kml,
        file_name=f"{file_name}_point.kml",
        mime='application/octet-stream',
        type='primary'
    )
    # MultiPolygonのKML作成とダウンロード
    poly_kml = edit_multipoly_kml(geodatasets.poly_gdf)
    expander.download_button(
        label="ポリゴン.kml ファイルのダウンロード ",
        data=poly_kml,
        file_name=f"{file_name}_poly.kml",
        mime='application/octet-stream',
        type='primary'
    )


def download_csv(geodatasets: GeoDatasets, file_name: str, is_en: bool):
    """
    csvファイルのダウンロード
    """
    st.markdown('<br>', True)
    st.markdown('### 📝 CSVファイルのダウンロード')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    expander = st.expander('csvデータセットを開く', False)
    expander.markdown(
    """
    csvは文字コードをUTF-8で出力します。Excelなどで見たい場合は
    1. Excelを開く
    2. 「データ」タブを開く
    3. 「テキストファイル」ウィジェットを開き、csvを読み込む
    4. 「テキストファイルウィザード - 1/3」そのまま次へ
    5. 「テキストファイルウィザード - 2/3」コンマにチェックを入れて完了
    """, unsafe_allow_html=True)
    # PointデータのDataFrameを作成する
    if check_lang_jn_in_df(geodatasets.point_gdf) & is_en:
        point_df = (
            rename_jn_to_en_in_df(geodatasets.point_gdf)
            .drop('geometry', axis=1)
            .copy()
        )
    else:
        point_df = geodatasets.point_gdf.drop('geometry', axis=1).copy()
    # PolygonデータのDataFrameを作成する
    if check_lang_jn_in_df(geodatasets.poly_gdf) & is_en:
        poly_df = (
            rename_jn_to_en_in_df(geodatasets.poly_gdf)
            .drop('geometry', axis=1)
            .copy()
        )
    else:
        poly_df = geodatasets.poly_gdf.drop('geometry', axis=1).copy()
    expander.download_button(
        label="ポイント.csv ファイルのダウンロード ",
        data=point_df.to_csv().encode('utf-8'),
        file_name=f"{file_name}_point.csv",
        mime='text/csv',
        type='primary'
    )
    expander.download_button(
        label="ポリゴン.csv ファイルのダウンロード ",
        data=poly_df.to_csv().encode('utf-8'),
        file_name=f"{file_name}_poly.csv",
        mime='text/csv',
        type='primary'
    )


def merge_page():
    summary.show_marge_geojson_summary
    # ファイルのアップロード
    files = uploder()
    if files:
        file_dict = {file.name.replace('.geojson', ''): file for file in files}
        # 座標系の選択
        output_project = select_data_properties()

        # 区画の種類を選択
        selected = select_dependency_files(list(file_dict.keys()))
        main_file = file_dict.get(selected.get(0))
        outer_files = [file_dict.get(file) for file in selected.get(1)]
        inner_files = [file_dict.get(file) for file in selected.get(2)]
        
        # MultiPolygonとPointのGeoDataFrameを作成する
        geodatasets = create_geodataframes(
            main_file, 
            inner_files, 
            outer_files, 
            output_project
        )

        # -------------------- File名の設定 --------------------#
        file_name = generate_file_base()
        # -------------------- Download GeoJSON --------------------#
        download_csv(geodatasets, file_name, output_project.is_en)
        # -------------------- Download GeoJSON --------------------#
        download_geojson(geodatasets, file_name)
        # -------------------- Download KML --------------------#
        download_kml(geodatasets, file_name, output_project.is_en)
        
