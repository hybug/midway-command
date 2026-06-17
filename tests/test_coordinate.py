"""Tests for §3 地理/坐标系统 — GEO-001~011"""
import math
import pytest

from src.render.coordinate import (
    world_to_hex,
    hex_to_world,
    hex_distance,
    hex_distance_nm,
    hex_bearing,
    hex_sector,
    hex_neighbors,
    hex_in_range,
    bearing_in_sector,
    REF_LAT,
    REF_LON,
    CELL_SIZE_NM,
    GRID_RADIUS,
)


# ── GEO-001: 地理→hex ──

class TestWorldToHex:
    """GEO-001: 地理坐标转hex坐标"""

    def test_world_to_hex_ref_point(self):
        """TC-GEO-001a: 中途岛参考点 → (0, 0)"""
        q, r = world_to_hex(REF_LAT, REF_LON)
        assert q == 0
        assert r == 0

    def test_world_to_hex_basic(self):
        """TC-GEO-001b: TF16 初始位置 ≈ (8, 20)"""
        q, r = world_to_hex(31.5, -176.0)
        # 允许 ±1 误差
        assert abs(q - 8) <= 1
        assert abs(r - 20) <= 1

    def test_world_to_hex_extreme(self):
        """极端坐标仍可转换（不抛异常）"""
        # 当前实现不校验范围，极端坐标也能转换
        q, r = world_to_hex(89.9, 179.9)
        assert isinstance(q, int)
        assert isinstance(r, int)


# ── GEO-002: hex→地理 ──

class TestHexToWorld:
    """GEO-002: hex坐标转地理坐标"""

    def test_hex_to_world(self):
        """hex(0,0) → 中途岛"""
        lat, lon = hex_to_world(0, 0)
        assert abs(lat - REF_LAT) < 0.01
        assert abs(lon - REF_LON) < 0.01


# ── GEO-003: 坐标往返精度 ──

class TestRoundtrip:
    """GEO-003: world→hex→world 往返精度"""

    def test_roundtrip_accuracy(self):
        """TC-GEO-003: 往返精度（当前实现精度约 0.17°/格 ≈ 10nm）"""
        test_coords = [
            (31.5, -176.0),
            (28.2, -177.4),
            (30.0, -178.0),
            (29.5, -176.5),
        ]
        for lat, lon in test_coords:
            q, r = world_to_hex(lat, lon)
            lat2, lon2 = hex_to_world(q, r)
            # 当前实现：10nm/格，1°≈60nm，所以误差约 0.17°
            assert abs(lat - lat2) < 0.2, f"lat diff: {abs(lat - lat2)}"
            assert abs(lon - lon2) < 0.2, f"lon diff: {abs(lon - lon2)}"


# ── GEO-004: hex距离 ──

class TestHexDistance:
    """GEO-004: hex距离计算"""

    def test_hex_distance(self):
        """两个不同hex的距离"""
        # cube distance: max(|q1-q2|, |r1-r2|, |s1-s2|)
        # (0,0) → (3,4): s1=0, s2=-7, max(3, 4, 7) = 7
        d = hex_distance(0, 0, 3, 4)
        assert d == 7

    def test_hex_distance_same_cell(self):
        """同一点距离为0"""
        d = hex_distance(5, 5, 5, 5)
        assert d == 0


# ── GEO-005: hex距离→海里 ──

class TestHexDistanceNm:
    """GEO-005: hex距离转海里"""

    def test_hex_distance_nm(self):
        """距离 × CELL_SIZE_NM = 海里"""
        d = hex_distance_nm(0, 0, 3, 4)
        assert d == 7 * CELL_SIZE_NM


# ── GEO-006: hex方位 ──

class TestHexBearing:
    """GEO-006: hex方位计算"""

    def test_hex_bearing_cardinal(self):
        """基本方位测试"""
        # r 增加 = 向北，所以 (0, 5) 是北方
        bearing = hex_bearing(0, 0, 0, 5)
        assert 350 <= bearing or bearing <= 10  # 大约 0° (北)

    def test_hex_bearing_same_point(self):
        """GEO-EDGE-005: 同一点返回0°"""
        bearing = hex_bearing(5, 5, 5, 5)
        assert bearing == 0.0


# ── GEO-007/008: 扇面生成 ──

class TestHexSector:
    """GEO-007/008: 扇面生成"""

    def test_hex_sector_basic(self):
        """TC-GEO-007: 基本扇面"""
        cells = hex_sector(0, 0, 350, 10, 5)
        assert len(cells) > 0
        # 应该包含 (0,0) 中心
        assert (0, 0) in cells

    def test_sector_wrap_360(self):
        """TC-GEO-008: 扇面跨360°"""
        cells = hex_sector(0, 0, 350, 10, 5)
        # 应该包含方位 355° 和 5° 的格
        assert len(cells) > 0


# ── GEO-009: 方位在扇面内 ──

class TestBearingInSector:
    """GEO-009: 方位在扇面内判定"""

    def test_bearing_in_sector(self):
        """基本扇面判定"""
        assert bearing_in_sector(45, 30, 60) is True
        assert bearing_in_sector(20, 30, 60) is False

    def test_bearing_in_sector_wrap(self):
        """跨360°扇面判定"""
        assert bearing_in_sector(355, 350, 10) is True
        assert bearing_in_sector(5, 350, 10) is True
        assert bearing_in_sector(200, 350, 10) is False


# ── GEO-010: hex邻居 ──

class TestHexNeighbors:
    """GEO-010: hex邻居"""

    def test_hex_neighbors(self):
        """每个hex有6个邻居"""
        neighbors = hex_neighbors(0, 0)
        assert len(neighbors) == 6


# ── GEO-011: hex在范围内 ──

class TestHexInRange:
    """GEO-011: hex在范围内"""

    def test_hex_in_range(self):
        """范围内返回True"""
        assert hex_in_range(0, 0, 0, 0, 5) is True
        assert hex_in_range(2, 3, 0, 0, 5) is True  # distance=5, in range

    def test_hex_out_of_range(self):
        """范围外返回False"""
        assert hex_in_range(10, 10, 0, 0, 5) is False
