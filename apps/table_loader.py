from dataclasses import asdict
from dataclasses import dataclass
import string
from typing import Dict
from typing import List

import geopandas as gpd
from pandas.core.series import Series
import polars as pl
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile
from st_aggrid import AgGrid, GridUpdateMode
from st_aggrid.grid_options_builder import GridOptionsBuilder

from apps.documents import Summary
from apps.read_files import read_drggpx_useing_jn
from apps.sidebar import SideBarResponse
from apps.settings.configs import DrgGpxConfs
from apps.settings.configs import JnDataCols
from apps.settings.configs import WebAppConfs
summary = Summary()


@dataclass
class DataFrames:
    dataframe: pl.DataFrame
    show_table: pl.DataFrame

class WaypointFileLoader(DrgGpxConfs):
    def __init__(self, sidebar_response: SideBarResponse):
        super().__init__()
        self.sidebar_response = sidebar_response
        self.file_idx = sidebar_response.file_idx * 1000 # indexが被らない様に、流石に1000点も測量しないだろうと
        self.sort_col = sidebar_response.sort_col
        self.sort_type = sidebar_response.sort_type
        self.group_name = sidebar_response.group_name

    def sidebar_response_to_df(self) -> pl.DataFrame:
        web_confs = WebAppConfs()
        resps = asdict(self.sidebar_response)
        adds = {
            key: val 
            for key, val in resps.items() 
            if key in web_confs.add_details_list
        }
        investigated = read_drggpx_useing_jn(resps.get('uploaded_file'))
        # originalのIndexを作成
        ori_idx = pl.Series(name='ori_idx', values=list(range(len(investigated))))
        df = (
            pl.DataFrame(investigated)
            .with_columns([
                pl.lit(value).alias(key)
                for key, value in adds.items()
            ])
            .sort(pl.col(self.sort_col), descending=self.sort_type)
            .with_columns([
                pl.col(self.pt_name_col_jn).cast(str)
            ])
            .with_columns([
                ori_idx + self.file_idx,
                pl.when(self.group_name != '')
                    .then(f'{self.group_name} - ' + pl.col(self.pt_name_col_jn))
                    .otherwise(pl.col(self.pt_name_col_jn).cast(str))
                    .alias(self.pt_name_col_jn),
            ])
        )
        df = df.drop([col for col in df.columns if df[col].is_null().all()])
        return df

    def get_rename_columns(self, df: pl.DataFrame) -> Dict[str, str]:
        df_cols = df.columns
        rename_dict = {}
        for key, val in WebAppConfs().add_details_dict.items():
            if key in df_cols:
                rename_dict[key] = val
        return rename_dict


@st.cache_data
def _to_dataframe(sidebar_response: SideBarResponse) -> pl.DataFrame:
    """file_uploaderで入力した.gpxファイルをpolarsのDataFrameに変換する"""
    wpfl = WaypointFileLoader(sidebar_response)
    df = wpfl.sidebar_response_to_df()
    # 変更する列名を取得する
    df = ( 
        df
        .with_columns([
            pl.col(col).cast(pl.Int64)
            for tp, col in zip(df.dtypes, df.columns) if tp == pl.Null
        ])
        .rename(wpfl.get_rename_columns(df))
    )
    return df


def _select_columns(df: pl.DataFrame) -> pl.DataFrame:
    # 表示用のDataFrameに絞り込む
    web_confs = WebAppConfs()
    return df.select(web_confs.show_cols_in_table)


def files_to_datasets(files: List[UploadedFile]):
    """複数ファイルをDataFrameに変換し結合する"""
    dfs = []
    for file in files:
        _df = _to_dataframe(file)
        dfs.append(_df)
    dataframe = (
        pl.concat(dfs)
        .sort('ori_idx')
    )
    show_table = _select_columns(dataframe)
    return DataFrames(dataframe, show_table)


def heiglight(series: Series, thres, upward=True) -> List[str]:
    # データフレーム内のセル色Listの作成
    hc = 'background-color: lightcoral;'
    default = ''
    if upward:
        return [hc if thres < v else default for v in series]
    else:
        return [hc if v < thres else default for v in series]


def show_editing_table(df, sidebar_resps: SideBarResponse):
    """アプリのMainPageにDataFrameを表示する。"""
    # 設定ファイルの読み込み
    drg_confs = DrgGpxConfs()
    jn_confs = JnDataCols()

    ######## 編集用テーブル ######## 
    # Optionの設定
    gd = GridOptionsBuilder.from_dataframe(df)
    gd.configure_selection(selection_mode='multiple', use_checkbox=True)
    gd.configure_grid_options(
        rowDragEntireRow=True, 
        rowDrag=True, 
        rowDragManaged=True, 
        rowDragMultiRow=True
    )
    # 測点名のみ編集可能にする
    gd.configure_column(drg_confs.pt_name_col_jn, 
        filterable=False, 
        sortable=False,
        editable=True
    )
    grid_options = gd.build()
    summary.show_edit_table_summary
    expander = st.expander('編集用テーブルを見て見る')
    expander.markdown('※テーブル左上の "Update" ボタンを押さなければ、編集が適用されません。')
    with expander.container():
        grid_response = AgGrid(
            df, 
            gridOptions=grid_options,
            update_mode=GridUpdateMode.MANUAL
        )
    
    ######## 出力テーブルの確認 ######## 
    st.markdown('<br><br>', True)
    st.markdown('### 確認用テーブル')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    st.markdown('精度が保証できない測点は赤くハイライトされます。')
    # 編集用テーブルからpd.DataFrameを取得
    df_res = grid_response.data.set_index(drg_confs.pt_datetime_col_jn)
    
    # チェックが入っている行を削除
    drop_idx = []
    if grid_response.selected_rows is not None:
        for _, row in grid_response.selected_rows.iterrows():
            drop_idx.append(row.get(drg_confs.pt_datetime_col_jn))
    _df = df_res.loc[~df_res.index.isin(drop_idx)].copy()
    
    # DataFrameのハイライト（規定を満たさないセルを強調する）
    heiglight_df = _df.copy()
    expander = st.expander('テーブルを表示')
    expander.dataframe(
        heiglight_df
        .style
        .format({
            jn_confs.pt_number_col: '{:.1f}', jn_confs.epochs_col:  '{:.0f}',
            jn_confs.pdop_col: '{:.2f}', jn_confs.satellites_col:  '{:.0f}',
        })
        .apply(
            heiglight, subset=[jn_confs.epochs_col], axis=0, 
            thres=sidebar_resps.thres_epochs, upward=False)
        .apply(heiglight, subset=[jn_confs.pdop_col], axis=0, 
               thres=sidebar_resps.thres_pdop)
        .apply(heiglight, subset=[jn_confs.satellites_col], axis=0, 
               thres=sidebar_resps.thres_sats, upward=False)
        .apply(heiglight, subset=[jn_confs.signal_frec_col], axis=0, 
               thres=1.99, upward=False)
    )

    # 精度保証に関する警告
    if _df[jn_confs.epochs_col].min() < sidebar_resps.thres_epochs:
        # 平均化測点数が足りているか
        st.markdown(
            "<font color=#ff3333>測定回数が規定を満たさない測点が含まれています。</font>", 
            unsafe_allow_html=True
        )

    if sidebar_resps.thres_pdop < _df[jn_confs.pdop_col].max():
        # PDOPが大きくないか
        values = _df[jn_confs.pdop_col].to_numpy()
        values = values[sidebar_resps.thres_pdop < values]
        if len(_df) / 2 <= len(values):
            st.markdown(
                "<font color=#ff3333>計測した測点の半数以上がPDOPの規定を満たしていません。</font>", 
                unsafe_allow_html=True
            )

    if _df[jn_confs.satellites_col].min() < sidebar_resps.thres_sats:
        # 衛星数が足りているか
        st.markdown(
            "<font color=#ff3333>使用衛星数が規定を満たさない測点が含まれています。</font>", 
            unsafe_allow_html=True
        )

    if _df[jn_confs.signal_frec_col].min() < 2:
        # 信号の種類が2周波か
        st.markdown(
            "<font color=#ff3333>1周波の測点が含まれているので、測点間距離が20m以上で面積が1.0ha以上でなければなりません。</font>", 
            unsafe_allow_html=True
        )

    result_df = pl.DataFrame(_df.reset_index())
    idx = pl.Series(name='idx', values=list(range(len(result_df))))
    result_df = (
        result_df
        .with_columns([
            idx
        ])
        .select(['ori_idx', 'idx'])
    )
    return result_df
    



