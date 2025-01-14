from typing import Any
from typing import Dict
from typing import List

import folium
from folium.plugins import BeautifyIcon
import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import polars as pl
import streamlit as st
from streamlit_folium import st_folium
import shapely

from apps.geometries import edit_single_geom_datasets
from apps.sidebar import SideBarResponse
from apps.visualization import visualize_data
from apps.settings.configs import check_lang_jn_in_df
from apps.settings.configs import JnDataCols
from apps.settings.configs import rename_en_to_jn_in_df
from apps.settings.configs import Tiles


class Mapping(object):
    def cmap(self, plot_num: int) -> str:
        """使用するRGBの文字列を取得"""
        colors = ['#ff0000', # 赤
                '#0000cc', # 青
                '#00cc00', # 緑
                '#cc00ff', # 紫
                '#00947a', # ターコイズ
                '#cc6600', # 茶
                '#ff0099', # ピンク
                '#00a1e9', # シアン
                '#5f6527', # オリーブ
                ] 
        return colors[plot_num]

    def size_list(self, values: List[int], normal_size=6) -> List[int]:
        '''最初の測点と5点ごとにサイズを大きく設定する'''
        size_lst = []
        for i, _ in enumerate(values):
            i += 1
            if i == 1:
                size_lst.append(int(normal_size * 2.2))
            elif i % 5 == 0:
                size_lst.append(int(normal_size * 1.8))
            else:
                size_lst.append(normal_size)
        return size_lst

    def create_fig(self) -> go.Figure:
        """FigureObjectの作成と設定"""
        layout = go.Layout(
            yaxis=dict(scaleanchor='x'),
            scene=dict(aspectratio=dict(x=1, y=1)),
            hoverlabel=dict(font=dict(size=15))
        )
        
        fig = go.Figure(layout=layout)
        return fig
    
    def create_hover_data(self, df: [pl.DataFrame | pd.DataFrame]) -> Dict[str, List[Any]]:
        """plotlyでhover_dataに渡すDictの作成"""
        confs = JnDataCols()
        # Hoverdata
        if type(df) == pl.DataFrame:
            data = {
                '日時': df[confs.datetime_col].cast(str).to_list(),
                confs.pt_name_col: df[confs.pt_name_col].cast(str).to_list(),
                confs.epochs_col: df[confs.epochs_col].cast(str).to_list(),
                confs.pdop_col: df[confs.pdop_col].cast(str).to_list(),
                confs.satellites_col: df[confs.satellites_col].cast(str).to_list(),
                confs.signal_frec_col: df[confs.signal_frec_col].cast(str).to_list()
            }
        else:
            data = {
                '日時': df[confs.datetime_col].astype(str).to_list(),
                confs.pt_name_col: df[confs.pt_name_col].astype(str).to_list(),
                confs.epochs_col: df[confs.epochs_col].astype(str).to_list(),
                confs.pdop_col: df[confs.pdop_col].astype(str).to_list(),
                confs.satellites_col: df[confs.satellites_col].astype(str).to_list(),
                confs.signal_frec_col: df[confs.signal_frec_col].astype(str).to_list()
            }
        hover_data = []
        for i, _ in enumerate(data.get(list(data.keys())[0])):
            txt = ""
            for key in data.keys():
                txt += f"{key}: {data.get(key)[i]}<br>"
            hover_data.append(txt)
        return hover_data
    
    def create_display_label(self, labels: List[str | Any]) -> List[str | float]:
        """plotlyで表示する為のラベル作成(5点毎)"""
        # Labelを5点ごとに作成
        new_labels = []
        for i, label in enumerate(labels):
            if i == 0:
                new_labels.append(label)
            elif (i + 1) % 5 == 0:
                new_labels.append(label)
            else:
                new_labels.append(None)
        return new_labels

    def select_cmaps(self, groups: List[Any]) -> List[str]:
        """グループ別の色設定を測点分作成する"""
        behind = groups[0]
        colors = []
        get_idx = 0
        for group in groups:
            if behind != group:
                get_idx += 1
                behind = group
                colors.append(self.cmap(get_idx))
            else:
                colors.append(self.cmap(get_idx))
        return colors
    
    @property
    def plotly_item_confs(self) -> Dict[str, Any]:
        return {'modeBarButtonsToRemove': ["lasso2d", "select2d"]}
    
    def create_report(self, df: pl.DataFrame, sidebar_resps: SideBarResponse) -> pd.DataFrame:
        """計測結果の入力されたpandas.DataFrameを作成する"""
        confs = JnDataCols()
        geoms = edit_single_geom_datasets(
            df=df,
            close=sidebar_resps.poly_close,
            local_epsg=sidebar_resps.epsg,
        )
        report = {
            '距離(m)': str(geoms.length),
            '面積(ha )': str(geoms.area),
            '測点数': str(len(geoms.points)),
            '最低測定回数': str(df[confs.epochs_col].min()),
            '最大PDOP': str(df[confs.pdop_col].max()),
            '最低衛星数': str(df[confs.satellites_col].min()),
            '最大水平方向標準偏差(m)': str(df[confs.hstd_col].max()),
        }
        report = pl.DataFrame({
            '名称': list(report.keys()),
            '値': list(report.values())
        })
        return report.to_pandas()

    def single_scatter(self, df: [pl.DataFrame | pd.DataFrame], closed: bool) -> go.Scatter:
        """単一区画の描画オブジェクト作成"""
        confs = JnDataCols()
        if not check_lang_jn_in_df(df):
            df = rename_en_to_jn_in_df(df)
        # 座標と測点名の取得
        lons = df[confs.lon_col].to_list()
        lats = df[confs.lat_col].to_list()
        labels = df[confs.pt_name_col].to_list()
        # 閉合
        if closed:
            lons.append(lons[0])
            lats.append(lats[0])
            labels.append('')

        # mapping
        hover_data = self.create_hover_data(df)
        # 散布図の色設定
        mk_prop = dict(
            color=self.cmap(0), 
            symbol='circle-open-dot', 
            size=self.size_list(lons)
        )
        # Objectの作成
        scatter = (
            go
            .Scatter( 
                x=lons, 
                y=lats,
                hovertext=hover_data,
                mode='lines+markers+text',
                marker=mk_prop,
                line=dict(color='#666666'),
                text=self.create_display_label(labels),
                textposition='middle left',
                textfont=dict(size=17, color='black'),
                showlegend=False
            )
        )
        return scatter

    def multi_file_signel_scatter(
        self, 
        df: [pl.DataFrame | pd.DataFrame], 
        closed: bool,
        groups: List[Any]=None,
    ) -> go.Scatter:
        """単一区画の描画オブジェクト作成"""
        confs = JnDataCols()
        if not check_lang_jn_in_df(df):
            df = rename_en_to_jn_in_df(df)
        # 座標と測点名の取得
        lons = df[confs.lon_col].to_list()
        lats = df[confs.lat_col].to_list()
        labels = df[confs.pt_name_col].to_list()
        # 描画に使用するグループを取得
        if (groups is None) & ('group' not in df.columns):
            groups = [0 for _ in range(len(df))]
        elif 'group' in df.columns:
            groups = df['group'].to_list()
        # 閉合
        if closed:
            lons.append(lons[0])
            lats.append(lats[0])
            labels.append('')
            groups.append(groups[-1])
        # mapping
        mapping = Mapping()
        hover_data = mapping.create_hover_data(df)
        colors = mapping.select_cmaps(groups)
        # 散布図の色設定
        mk_prop = dict(
            color=colors, 
            symbol='circle-open-dot', 
            size=self.size_list(lons)
        )
        # 測点のPlot
        scatter = (
            go.Scatter(
                x=lons, 
                y=lats,
                hovertext=hover_data,
                mode='lines+markers+text',
                line=dict(color='#666666'),
                marker=mk_prop,
                text=self.create_display_label(labels),
                textposition='middle left',
                textfont=dict(size=17, color='black'),
                showlegend=False
            )
        )
        return scatter


    

def create_multiple_file_single_poly_figure(
    df: [pl.DataFrame | pd.DataFrame],
    closed: bool,
    groups: List[Any]=None
):
    mapping = Mapping()
   
    fig = mapping.create_fig()
    scatter = mapping.multi_file_signel_scatter(df, closed, groups)
    fig.add_trace(scatter)
    fig.update_layout(width=600, height=600)
    return fig


def create_single_poly_figure(
    df: pl.DataFrame,
    closed: bool=True,
):  
    mapping = Mapping()
    fig = mapping.create_fig()
    scatter = mapping.single_scatter(df, closed)
    fig.add_trace(scatter)
    fig.update_layout(width=600, height=600)
    return fig


def write_html(feature: Dict[str, Any]) -> str:
    confs = JnDataCols()
    properties = feature['properties']
    data = {
        confs.datetime_col: properties[confs.datetime_col],
        confs.pt_name_col: properties[confs.pt_name_col],
        confs.epochs_col: properties[confs.epochs_col],
        confs.pdop_col: properties[confs.pdop_col],
        confs.satellites_col: properties[confs.satellites_col],
        confs.signal_frec_col: properties[confs.signal_frec_col],
    }
    _df = (
        pd
        .DataFrame
        .from_dict(data, orient='index')
    )
    _df.columns = ['']
    table = _df.to_html(classes="table table-striped", border=2)
    html_style = """
    <style>
        .table {
            font-size: 10px;
        }
    </style>
    """
    return html_style + table

def create_map(df: pl.DataFrame, tile: dict, closed: bool=True):
    confs = JnDataCols()
    mapper = Mapping()
    df = df.to_pandas()
    df['測定開始日時'] = df['測定開始日時'].dt.strftime("%Y/%m/%d %H:%M:%S")
    df['測定終了日時'] = df['測定終了日時'].dt.strftime("%Y/%m/%d %H:%M:%S")
    gdf = gpd.GeoDataFrame(
        df, 
        geometry=gpd.points_from_xy(df[confs.lon_col], df[confs.lat_col]),
        crs="EPSG:4326"
    )
    m = folium.Map(
        location=[gdf.geometry.y.mean(), gdf.geometry.x.mean()], 
        zoom_start=17,
        max_zoom=25,
        min_zoom=5,
        tiles="OpenStreetMap"
    )
    # タイルの追加
    folium.WmsTileLayer(
        transparent=True,
        overlay=False,
        control=True,
        maxNativeZoom=18,  # Set the maximum native zoom level
        maxZoom=25, # Set the maximum zoom level
        **tile
    ).add_to(m)

    icon_circle = BeautifyIcon(
        icon="plane", border_color="#b3334f", text_color="#b3334f", icon_shape="triangle"
    )
    poly_cds = [[geom.y, geom.x] for geom in gdf['geometry']]
    if closed:
        poly_cds += [poly_cds[0]]
        folium.Polygon(
            locations=poly_cds,
            color="red",
            weight=3,
        ).add_to(m)
    else:
        folium.PolyLine(
            locations=poly_cds,
            color="red",
            weight=3,
        ).add_to(m)

    # 測点をマップに追加
    labels = mapper.create_display_label(gdf[confs.pt_name_col].to_list())
    geojson = gdf.to_geo_dict()
    for feature, label in zip(geojson['features'], labels):
        icon_circle = folium.plugins.BeautifyIcon(
            icon="regular:circle", 
            border_color="none", 
            text_color="red", 
            background_color='none', 
            icon_shape="circle",
            icon_size=[15, 15],
            icon_anchor=[7.5, 7.5],
        )
        table = write_html(feature)
        popup = folium.Popup(table, max_width=1000)
        # 測点マーカーとラベルの追加
        coords = feature['geometry']['coordinates'][::-1]
        if label is None:
            label = ""
        folium.Marker(
            location=coords,
            icon=icon_circle
        ).add_to(m)
        folium.map.Marker(
            location=coords,
            popup=popup,
            icon=folium.DivIcon(
                html=f'<div style="white-space: nowrap; font-size: 12px; color: black; text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff;">{label}</div>'
            )
        ).add_to(m)
    
    folium.LayerControl().add_to(m)
    return m


            

def mapping_in_streamlit(
    df: pl.DataFrame,
    sidebar_resps_list: List[SideBarResponse]
):
    st.markdown("<br><br>", True)
    st.markdown('### GNSSの計測結果をMapで表示する')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    mapping = Mapping()
    # 計測レポートの作成
    repo_expander = st.expander('計測レポート')
    report = mapping.create_report(df, sidebar_resps_list[0])
    repo_expander.data_editor(report, hide_index=True, disabled=True, )
    # Mapping
    container = st.container()
    map_list = [
        
    ]
    map_list = {
        'ノーマル': None,
        '標準地図に投影（国土地理院）': Tiles.chiriin_base_map(),
        '空中写真に投影（国土地理院）': Tiles.chiriin_aerial_imagery(),
        '衛星画像に投影（Google）': Tiles.google_satellites(),
        '衛星画像に投影（Esri）': Tiles.esri_world_imagery(),
    }
    radio = container.radio('表示するデータ', map_list, horizontal=True)
    closed = sidebar_resps_list[0].poly_close
    if radio == 'ノーマル':
        # ノーマルのMapping
        if len(sidebar_resps_list) == 1:
            # データが1つの場合のMapping.
            fig = create_single_poly_figure(df, closed)
            st.plotly_chart(fig, config=mapping.plotly_item_confs)

        elif 1 < len(sidebar_resps_list):
            # データが複数の場合のMapping.
            fig = create_multiple_file_single_poly_figure(df, closed)
            st.plotly_chart(fig, config=mapping.plotly_item_confs)
    else:
        # 地図上に投影
        tile = map_list[radio]
        m = create_map(df, tile, closed)
        st_data = st_folium(m, width=1300)
            
    time_series = st.toggle('時系列で表示')
    fig = visualize_data(df, time_series)
    st.plotly_chart(fig, config= {'staticPlot': True})



