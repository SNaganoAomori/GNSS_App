from dataclasses import asdict
import re
import subprocess
import sys
import time
from typing import List

import pandas as pd
import polars as pl
import streamlit as st
from shapely.geometry import Point, Polygon

from apps.check_password import check_password
from apps.create_pdf import page_of_mapping_pdf
from apps.documents import Summary
from apps.documents import CheatSheet
from apps.dta import merge_page_dta
from apps.exception import poly_cross_checker
from apps.mapper import mapping_in_streamlit
from apps.merge_page import merge_page
from apps.output_file_page import check_internet_connection
from apps.output_file_page import output_page
from apps.sidebar import run_sidebar
from apps.sidebar import SideBarResponse
from apps.settings.configs import DrgGpxConfs
from apps.settings.configs import JnDataCols
from apps.settings.configs import WebAppConfs
from apps.table_loader import files_to_datasets
from apps.table_loader import show_editing_table
from apps.table_loader import DataFrames
summary = Summary()


def page_config():
    # ページの設定
    st.set_page_config(
        page_title='JFF Aomori', 
        page_icon='🛰', 
        # layout='centered',
        layout='wide',
        initial_sidebar_state="expanded",
    )


def check_input_sidebar(sidebar_resps: SideBarResponse) -> bool:
    # Sidebarにデータが入力されたかをチェックする
    check_list = WebAppConfs().add_details_list
    data = asdict(sidebar_resps)
    for c in check_list:
        value = data.get(c)
        if value == '':
            return False
    return True


def to_pandas(dataframe_sets: DataFrames) -> pd.DataFrame:
    jn_confs = JnDataCols()
    # 精度確認用のDataFrameを作成する
    df = (
        dataframe_sets
        .show_table
        .with_columns([
            pl.col(jn_confs.datetime_col).dt.strftime("%Y/%m/%d %H:%M:%S")
        ])
        .to_pandas()
    )
    return df


def _points_to_poly(df: pl.DataFrame) -> Polygon:
    jn_confs = JnDataCols()
    lons = df[jn_confs.lon_col].to_list()
    lats = df[jn_confs.lat_col].to_list()
    poly = Polygon([
        Point(lon, lat)
        for lon, lat in zip(lons, lats)
    ])
    return poly

def get_result_table(dataframe: pl.DataFrame, poly_close: bool) -> pl.DataFrame:
    # 編集が完了したDataFrameを取得
    drg_confs = DrgGpxConfs()
    result = (
        dataframe.join(dataframe, on='ori_idx')
        .sort(pl.col('idx'))
        .drop('ori_idx')
        .with_columns([
            pl.col(drg_confs.pt_name_col_jn).map_elements(
                lambda s: re.sub(r"[^A-Za-z]", '', s)
            ).alias('group')
        ])
    )
    if poly_close:
        poly = _points_to_poly(result)
        poly_cross_checker(poly)
    return result


def run():
    drg_confs = DrgGpxConfs()
    jn_confs = JnDataCols()
    page_config()
    # 編集タブの他にDocumentsを見れるタブなどを用意する
    tab_names = [
        'メインページ', 
        'ファイル出力', 
        'データ結合',
        '説明書',
        'アップロード',
    ]

    if check_internet_connection() == False:
        tab_names.remove('アップロード')
    tabs = st.tabs(tab_names)
    # Sidebarの起動
    sidebar_resps = run_sidebar()
    with tabs[0]:
        # メインページ
        _ = summary.show_main_page_summary
        show = check_input_sidebar(sidebar_resps[0]) if sidebar_resps else False
        if show:
            # 編集用dataframeと表示用dataframeの取得
            dataframe_sets = files_to_datasets(sidebar_resps)
            show_df = to_pandas(dataframe_sets)
            # 編集用テーブルの表示
            selected_rows = show_editing_table(show_df, sidebar_resps[0])
            # 編集後データの取得
            result = get_result_table(selected_rows, sidebar_resps[0].poly_close)
            # mapping.
            mapping_in_streamlit(result, sidebar_resps)
        else:
            st.markdown(':red[追加情報が全て入力されるまで計算出来ません。]')
            
    with tabs[1]:
        # ファイル出力ページ
        output_tabs = st.tabs(['データの保存', '実測図作成'])
        with output_tabs[0]:
            if show:
                output_page(result, sidebar_resps)
        with output_tabs[1]:
            page_of_mapping_pdf()

    with tabs[2]:
        # データ結合（GIS to GIS）
        merge_tabs = st.tabs([
            '（複数のGeoJSONからGISデータへ）',
            '（複数のGeoJSONからDTAへ）',
        ])
        with merge_tabs[0]:
            merge_page()
        with merge_tabs[1]:
            merge_page_dta()

    with tabs[3]:
        # Documents page.
        cheat_sheet = CheatSheet()
        
    if check_internet_connection():
        with tabs[4]:
            pass
            # sync_cloud_page()



if __name__ == '__main__':
    if check_password():
        run()