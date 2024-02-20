from dataclasses import dataclass
import decimal
import math
from typing import Any
from typing import Iterable
from typing import List

import geopandas as gpd
import pandas as pd


@dataclass
class DegreeMinuteSecond:
    degree: float=None
    minute: float=None
    second: float=None
    dms: str=None


class CoordinatesFormatter(object):
    def __init__(self, value: float | str, NorE: str=None):
        self.value = self._set_value(value)
        self.fmt = self._search_format(self.value)
        if NorE is None:
            self.NorE = ''
        else:
            self.NorE = NorE

    def _set_value(self, value: Any):
        if isinstance(value, float):
            return  value
        elif isinstance(value, str):
            return self._convert_zen_symbols(value)
        elif isinstance(value, Iterable):
            if (2 <= len(value)) & (len(value) <= 3):
                return self._d_m_s_to_degree(*value)

    def _search_format(self, value: float | str):
        if isinstance(value, float):
            return 'Degree'
        elif isinstance(value, str):
            fmt = self._format_check_dms(value)
            if not fmt is None:
                return fmt
        return None
            
    @property
    def _normal_symbols(self) -> List[str]:
        return ['°', "'", '"']
    
    @property
    def _zen_symbols(self) -> List[str]:
        return ['°', '′', '″']
    
    @property
    def _jn_zen_symbols(self) -> List[str]:
        return ['度', '分', '秒']

    def _convert_zen_symbols(self, dms: str) -> str:
        for sym, zsym in zip(self._normal_symbols, self._zen_symbols):
            dms = dms.replace(sym, zsym)
        for sym, zsym in zip(self._jn_zen_symbols, self._zen_symbols):
            dms = dms.replace(sym, zsym)
        return dms    

    def _dose_second_exist(self, dms: str) -> bool:
        """DMSの中に秒単位のデータが存在するか"""
        if self._zen_symbols[-1] in dms:
            return True
        else:
            return False

    def _format_check_dms(self, dms: str) -> str:
        """度分秒のフォーマットチェック"""
        syms = self._zen_symbols
        if (syms[0] in dms) & (syms[1] in dms):
            if self._dose_second_exist(dms):
                return 'DMS'
            else:
                return 'DM'
        return None

    def _find_numeric(self, string: str, start: int, end: int) -> int | float:
        """DMSフォーマットから数値を探して型変換する"""
        if (0 <= start) & (0 <= end):
            item = string[start: end]
        else:
            item = None
        try:
            if item is None:
                numeric = None
            elif '.' in item:
                numeric = float(item)
            else:
                numeric = int(item)
        except ValueError as e:
            return None
        else:
            return numeric
    
    def _d_m_s_to_dms_string(
        self,
        degree: int, 
        minute: int, 
        second: float=None, 
    ) -> str:
        """D,M,SからDSMフォーマットの文字列を作成する。"""
        sentence = f"{degree}{self._zen_symbols[0]}"
        sentence += f"{minute}{self._zen_symbols[1]}"
        if not second is None:
            sentence += f"{second}{self._zen_symbols[2]}"
        sentence += self.NorE
        return sentence

    def _degree_to_dms(self, degree: float) -> DegreeMinuteSecond:
        """
        Degreeフォーマットの座標をDMSフォーマットに変換する。\n
        Args
            degree(float): 10進法表記の経度や緯度
            NorE(str): 'N': lat | 'E': lon
        Returns:
            DegreeMinuteSecond:
                degree(int): 度
                minute(int): 分
                second(float): 秒
                dms(str): DMSフォーマットの文字列
        Doctest:
            >>> lon = 141.3071
            >>> lat = 41.1427
            >>> degree_to_dms(lon)
            DegreeMinuteSecond(degree=141, minute=18, second=25.56, dms='141°18′25.56″')
            >>> degree_to_dms(lon, NorE='E')
            DegreeMinuteSecond(degree=141, minute=18, second=25.56, dms='141°18′25.56″E')
            >>> degree_to_dms(lat)
            DegreeMinuteSecond(degree=41, minute=8, second=33.72, dms='41°8′33.72″')
            >>> degree_to_dms(lat, NorE='N')
            DegreeMinuteSecond(degree=41, minute=8, second=33.72, dms='41°8′33.72″N')
        """
        deg = int(math.modf(degree)[1])
        _minute = (degree - deg) * 60
        minute = int(_minute)
        second = round((_minute - minute) * 60, 4)
        dms = self._d_m_s_to_dms_string(deg, minute, second)
        return DegreeMinuteSecond(deg, minute, second, dms)

    def _d_m_s_to_degree(self, degree, minute, second=None):
        if second is None:
            second = 0
        degree = degree + ((minute / 60) + (second / 3600))
        return degree

    def _dms_to_d_m_s(self, dms: str) -> DegreeMinuteSecond:
        """DMSフォーマットの文字列を[d,s,m]の数値に分解する。"""
        symbols = self._zen_symbols
        if symbols[0] in dms:
            d = self._find_numeric(dms, 0, dms.find(symbols[0]))
            m = self._find_numeric(dms, dms.find(symbols[0]) + 1, dms.find(symbols[1]))
            s = self._find_numeric(dms, dms.find(symbols[1]) + 1, dms.find(symbols[2]))
            return DegreeMinuteSecond(d, m, s)
        else:
            raise ValueError('The DMS format is an unintended format.')

    @property
    def dms(self):
        if (self.fmt == 'DMS') or (self.fmt == 'DM'):
            return self.value
        elif self.fmt == 'Degree':
            return self._degree_to_dms(self.value).dms
    
    @property
    def d_m_s(self):
        if (self.fmt == 'DMS') or (self.fmt == 'DM'):
            dms_data = self._dms_to_d_m_s(self.value)
            if dms_data.second is None:
                return (dms_data.degree, dms_data.minute)
            else:
                return (dms_data.degree, dms_data.minute, dms_data.second)
        elif self.fmt == 'Degree':
            dms_data = self._degree_to_dms(self.value)
            return (dms_data.degree, dms_data.minute, dms_data.second)
    
    @property
    def degree(self):
        if (self.fmt == 'DMS') or (self.fmt == 'DM'):
            dms_data = self._dms_to_d_m_s(self.value)
            args = None
            if dms_data.second is None:
                args = (dms_data.degree, dms_data.minute)
            else:
                args = (dms_data.degree, dms_data.minute, dms_data.second)
            if not args is None:
                return self._d_m_s_to_degree(*args)
        elif self.fmt == 'Degree':
            return self.value


class NorthToMagneticNorth(object):
    def __init__(points, mag_df: pd.DataFrame):
        pass

    def approximate_formula_2020(lon, lat):
        # D2020.0 = 8°15.822′ + 18.462′Δφ -	7.726′Δλ + 0.007′(Δφ)2 - 0.007′ΔφΔλ	- 0.655′(Δλ)2
        # D2020 = 8.2637 + 0.3077 * Δφ - 0.12876 * Δλ + 0.0001166 * Δφ**2 - 0.0001166 * Δφ * Δλ - 0.010917 * Δλ**2
        cf = CoordinatesFormatter(lon)
        phi_v = lat
        lambda_v = lon
        delta_phi = phi_v - 37
        delta_lambda = lambda_v - 138
        declination_deg = (
            cf._d_m_s_to_degree(8, 15.822)
            + cf._d_m_s_to_degree(0, 18.462) * delta_phi
            - cf._d_m_s_to_degree(0, 7.726) * delta_lambda
            + cf._d_m_s_to_degree(0, 0.007) * (delta_phi * 2) # 2乗だと思うがこちらの方が計算が合う?
            - cf._d_m_s_to_degree(0, 0.007) * delta_phi * delta_lambda
            - cf._d_m_s_to_degree(0, 0.655) * (delta_lambda * 2) # 2乗だと思うがこちらの方が計算が合う?
        )
        dms = cf._degree_to_dms(declination_deg)
        declination_dms = f"{dms[0]}°{dms[1]}′{dms[2]}″"
        return {'degree': declination_deg, 'dms': declination_dms}



if __name__ == '__main__':
    pass
    # test_data = [
    #     141.3071,
    #     41.1427,
    #     [41, 8, 33.72],
    #     [141, 18, 25.56],
    #     "41°8′33.72″N",
    #     "141°18′25.56″E",
    #     "41度8分N",
    #     "141度18分25.56秒E"
    # ]
    # for coords in test_data:
    #     cf = CoordinatesFormatter(coords)
    #     print(cf.degree)
    #     print(cf.dms)
    #     print(cf.d_m_s)
    #     print('_____________')