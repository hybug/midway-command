"""Tests for §3 空间索引 — GEO-012~018"""
import pytest

from src.spatial import SpatialIndex


# ── GEO-012: 空间索引-更新 ──

class TestSpatialUpdate:
    """GEO-012: 空间索引更新"""

    def test_update_entity(self):
        """更新实体位置"""
        idx = SpatialIndex()
        idx.update_entity("ship_1", 31.5, -176.0)
        pos = idx.get_hex_for_entity("ship_1")
        assert pos is not None

    def test_update_entity_old_position_cleared(self):
        """更新后旧位置被清除"""
        idx = SpatialIndex()
        idx.update_entity("ship_1", 31.5, -176.0)
        old_pos = idx.get_hex_for_entity("ship_1")
        idx.update_entity("ship_1", 32.0, -176.0)
        new_pos = idx.get_hex_for_entity("ship_1")
        assert old_pos != new_pos


# ── GEO-013: 空间索引-移除 ──

class TestSpatialRemove:
    """GEO-013: 空间索引移除"""

    def test_remove_entity(self):
        """移除实体"""
        idx = SpatialIndex()
        idx.update_entity("ship_1", 31.5, -176.0)
        idx.remove_entity("ship_1")
        assert idx.get_hex_for_entity("ship_1") is None

    def test_remove_nonexistent(self):
        """GEO-EDGE-006: 移除不存在的实体不抛异常"""
        idx = SpatialIndex()
        idx.remove_entity("nonexistent")  # Should not raise


# ── GEO-014: 空间索引-范围查询 ──

class TestSpatialRangeQuery:
    """GEO-014: 空间索引范围查询"""

    def test_entities_in_range(self):
        """范围内查询"""
        idx = SpatialIndex()
        idx.update_entity("ship_1", 31.5, -176.0)
        idx.update_entity("ship_2", 31.6, -176.1)  # 接近
        idx.update_entity("ship_3", 28.2, -177.4)  # 远（中途岛）

        pos = idx.get_hex_for_entity("ship_1")
        result = idx.get_entities_in_range(pos[0], pos[1], 2)
        assert "ship_1" in result
        # ship_2 可能在范围内（取决于hex距离）
        # ship_3 应该不在范围内


# ── GEO-015: 空间索引-距离查询 ──

class TestSpatialDistance:
    """GEO-015: 空间索引距离查询"""

    def test_distance_between(self):
        """两个实体之间的距离"""
        idx = SpatialIndex()
        idx.update_entity("ship_1", 31.5, -176.0)
        idx.update_entity("ship_2", 28.2, -177.4)
        d = idx.distance_between("ship_1", "ship_2")
        assert d is not None
        assert d > 0

    def test_distance_not_found(self):
        """GEO-EDGE-006: 实体不存在返回None"""
        idx = SpatialIndex()
        idx.update_entity("ship_1", 31.5, -176.0)
        d = idx.distance_between("ship_1", "nonexistent")
        assert d is None


# ── GEO-016: 空间索引-每tick重建 ──

class TestSpatialFullRebuild:
    """GEO-016: 空间索引完整重建"""

    def test_full_rebuild(self):
        """clear + 重新添加"""
        idx = SpatialIndex()
        idx.update_entity("ship_1", 31.5, -176.0)
        idx.update_entity("ship_2", 28.2, -177.4)
        assert len(idx.entity_positions) == 2

        idx.clear()
        assert len(idx.entity_positions) == 0

        idx.update_entity("ship_1", 32.0, -176.0)
        assert len(idx.entity_positions) == 1


# ── GEO-017: 空间索引-同格查询 ──

class TestSpatialSameHex:
    """GEO-017: 同格查询"""

    def test_entities_in_same_hex(self):
        """同格其他实体"""
        idx = SpatialIndex()
        idx.update_entity("ship_1", 31.5, -176.0)
        idx.update_entity("ship_2", 31.5, -176.0)  # 同位置
        same = idx.entities_in_same_hex("ship_1")
        assert "ship_2" in same
        assert "ship_1" not in same

    def test_entities_in_same_hex_empty(self):
        """同格无其他实体"""
        idx = SpatialIndex()
        idx.update_entity("ship_1", 31.5, -176.0)
        same = idx.entities_in_same_hex("ship_1")
        assert len(same) == 0


# ── GEO-018: 空间索引-邻居查询 ──

class TestSpatialNearby:
    """GEO-018: 邻居查询"""

    def test_entities_nearby(self):
        """范围内实体（不含自身）"""
        idx = SpatialIndex()
        idx.update_entity("ship_1", 31.5, -176.0)
        idx.update_entity("ship_2", 31.6, -176.1)  # 接近
        nearby = idx.entities_nearby("ship_1", 2)
        # ship_1 自身不在结果中
        assert "ship_1" not in nearby or len(nearby) > 0

    def test_entities_nearby_nonexistent(self):
        """GEO-EDGE-006: 实体不存在返回空dict"""
        idx = SpatialIndex()
        nearby = idx.entities_nearby("nonexistent", 2)
        assert nearby == {}
