import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import polars as pl

from apps.settings.configs import JnDataCols


def visualize_data(df: pl.DataFrame, time_series: bool=False) -> go.Figure:
    jn_confs = JnDataCols()
    fig = make_subplots(
        rows=2, cols=2, 
        subplot_titles=[
            '測定回数', 'PDOP', '衛星数', '水平標準偏差（m）'
        ],
        vertical_spacing=0.4
    )
    if time_series:
        df = df.sort(jn_confs.datetime_col)
        #------------------ epochs ------------------#
        fig.add_trace(
            go.Scatter(
                x=df[jn_confs.datetime_col], y=df[jn_confs.epochs_col],
                mode='markers'
            ), row=1, col=1
        )
        #------------------ pdop ------------------#
        fig.add_trace(
            go.Scatter(
                x=df[jn_confs.datetime_col], y=df[jn_confs.pdop_col],
                mode='markers'
            ), row=1, col=2
        )
        #------------------ n-satellites ------------------#
        fig.add_trace(
            go.Scatter(
                x=df[jn_confs.datetime_col], y=df[jn_confs.satellites_col],
                mode='markers'
            ), row=2, col=1
        )
        #------------------ holizontal std ------------------#
        fig.add_trace(
            go.Scatter(
                x=df[jn_confs.datetime_col], y=df[jn_confs.hstd_col],
                mode='markers+lines'
            ), row=2, col=2
        )
            
    else:
        #------------------ epochs ------------------#
        epochs = df[jn_confs.epochs_col].to_numpy()
        epochs_dict = {name: len(epochs[name == epochs]) for name in np.unique(epochs)}
        x = list(epochs_dict.keys())
        y = list(epochs_dict.values())
        fig.add_trace(go.Bar(x=x, y=y), row=1, col=1)
        #------------------ pdop ------------------#
        pdop = df[jn_confs.pdop_col].to_list()
        fig.add_trace(go.Histogram(x=pdop), row=1, col=2)
        #------------------ n-satellites ------------------#
        n_sats = df[jn_confs.satellites_col].to_numpy()
        n_sats_dict = {name: len(n_sats[name == n_sats]) for name in np.unique(n_sats)}
        x = list(n_sats_dict.keys())
        y = list(n_sats_dict.values())
        fig.add_trace(go.Bar(x=x, y=y), row=2, col=1)
        #------------------ holizontal std ------------------#
        h_std = df[jn_confs.hstd_col].to_list()
        fig.add_trace(go.Histogram(x=h_std), row=2, col=2)
    fig.update_layout( 
        bargap=0.2,
        showlegend=False,
        margin=dict(l=22, r=22, t=22, b=22)
    )
    fig.update_traces(
        marker_color='#008899',
        marker_line_color='black',
        marker_line_width=2,
        opacity=0.75,
    )
    return fig

