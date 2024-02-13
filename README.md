# GNSS測量の後処理アプリ

## はじめに
このアプリケーションは`DroggerGPS`を使用し、GNSS測量を行った後のデータ処理アプリケーションです。


## 注意
exe化せずに`streamlit cloud`で動作させたところ、`arcgis`のPythonAPIがインストール出来ず、2つのアプリに分けて管理する事になりました。

その為こちらのアプリでは`ArcGIS Online`にデータを同期する機能を使えなくしています。

データを同期したい場合は「GNSS_App_Desktop」の方をexe化して使用して下さい。
