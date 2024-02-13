# GNSS測量の後処理アプリ

## はじめに
このアプリケーションは`DroggerGPS`を使用し、GNSS測量を行った後のデータ処理アプリケーションです。


## 注意
exe化せずに`streamlit cloud`で動作させたところ、`arcgis`のPythonAPIがインストール出来ず、2つのアプリに分けて管理する事になりました。

その為こちらのアプリでは`ArcGIS Online`にデータを同期する機能を使えなくしています。

データを同期したい場合は「GNSS_App_Desktop」の方をexe化して使用して下さい。


## exe化コマンド
#### 1度目のPyInstallerを実行
```py: command
pyinstaller --onefile --additional-hooks-dir=./hooks run.py --clean
```

#### .specファイルを編集する
`_run.spec`を参考に`run.spec`を編集する。`datas`と`hiddenimports`を編集する。`datas`には`streamlit`のindexファイルや`st_aggrid`、`streamlit_folium`が必要なので注意する事。コピペでも大丈夫なはず。

#### 2度目のPyInstallerを実行
```python: command
pyinstaller run.spec --clean
```
`dist`ディレクトリーにexeファイルがあるので上位のディレクトリーに移動
