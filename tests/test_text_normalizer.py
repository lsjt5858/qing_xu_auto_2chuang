"""
Chinese text normalization tests.
"""
from __future__ import annotations

import unittest

from src.utils.text_normalizer import normalize_chinese_text


class TestTextNormalizer(unittest.TestCase):
    def test_normalize_common_traditional_text_to_simplified(self):
        text = "我們都沒有上帝視角 愛和委屈都要大聲說出來 只有從失敗了再絕望請求希望"
        self.assertEqual(
            normalize_chinese_text(text),
            "我们都没有上帝视角 爱和委屈都要大声说出来 只有从失败了再绝望请求希望",
        )


if __name__ == "__main__":
    unittest.main()
