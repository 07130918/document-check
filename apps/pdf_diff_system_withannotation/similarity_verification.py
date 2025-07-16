#!/usr/bin/env python3
"""
類似度ベースの検証スクリプト
実際の問題ケースでの類似度計算とアルゴリズムの検証
"""

from difflib import SequenceMatcher
import sys
import os

# プロジェクトのルートディレクトリをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import Levenshtein
    HAS_LEVENSHTEIN = True
    print("Levenshteinライブラリが利用可能です")
except ImportError:
    HAS_LEVENSHTEIN = False
    print("Levenshteinライブラリが利用できません（SequenceMatcherのみ使用）")


def calculate_similarity_sequencematcher(text1: str, text2: str) -> float:
    """SequenceMatcherによる類似度計算"""
    return SequenceMatcher(None, text1, text2).ratio()


def calculate_similarity_levenshtein(text1: str, text2: str) -> float:
    """Levenshtein距離による類似度計算"""
    if HAS_LEVENSHTEIN:
        return Levenshtein.ratio(text1, text2)
    else:
        return calculate_similarity_sequencematcher(text1, text2)


def calculate_dynamic_threshold(text1: str, text2: str) -> float:
    """動的閾値の計算（SequenceMatcherDetectorの実装と同じ）"""
    min_length = min(len(text1), len(text2))
    
    if min_length <= 20:
        return 0.6  # 短いテキストは低い閾値
    elif min_length <= 50:
        return 0.7  # 中程度のテキスト
    else:
        return 0.8  # 長いテキストは高い閾値


def test_similarity_cases():
    """問題のあるケースでの類似度検証"""
    test_cases = [
        # 問題のあるケース
        ("p34", "p35", "ページ番号の変更"),
        ("iOS 11/12/13/14/15/16", "iOS 11/12/13/14/15/16/17", "iOSバージョンの追加"),
        ("令和5年度", "令和6年度", "年度の変更"),
        ("約1.8万人", "約1.6万人", "数値の変更"),
        ("令和5年10月25日", "令和6年10月25日", "年の変更"),
        ("午後4時", "午後5時", "時間の変更"),
        
        # 比較用のケース
        ("裏表紙", "背表紙", "完全に異なる語"),
        ("テスト", "テストケース", "部分的な追加"),
        ("完全に異なる文章", "全く関係のない内容", "無関係な文章"),
        ("同じ文章", "同じ文章", "同一文章"),
        ("", "", "空文字列"),
    ]
    
    print("=== 類似度検証結果 ===\n")
    
    for text1, text2, description in test_cases:
        print(f"【{description}】")
        print(f"  文1: '{text1}' ({len(text1)}文字)")
        print(f"  文2: '{text2}' ({len(text2)}文字)")
        
        # 類似度計算
        seq_similarity = calculate_similarity_sequencematcher(text1, text2)
        lev_similarity = calculate_similarity_levenshtein(text1, text2)
        
        # 動的閾値
        dynamic_threshold = calculate_dynamic_threshold(text1, text2)
        
        print(f"  SequenceMatcher類似度: {seq_similarity:.3f}")
        if HAS_LEVENSHTEIN:
            print(f"  Levenshtein類似度: {lev_similarity:.3f}")
        print(f"  動的閾値: {dynamic_threshold:.3f}")
        
        # 判定結果
        print(f"  現在の固定閾値(0.6)による判定: {'修正' if seq_similarity >= 0.6 else '削除+追加'}")
        print(f"  動的閾値による判定: {'修正' if seq_similarity >= dynamic_threshold else '削除+追加'}")
        print(f"  SequenceMatcher(0.7)による判定: {'修正' if seq_similarity >= 0.7 else '削除+追加'}")
        
        # 問題の分析
        if seq_similarity < 0.6 and description in ["ページ番号の変更", "年度の変更", "数値の変更", "年の変更", "時間の変更"]:
            print(f"  ⚠️  問題: 明らかな修正が削除+追加として判定される")
        elif seq_similarity >= 0.6 and description in ["完全に異なる語", "無関係な文章"]:
            print(f"  ⚠️  問題: 無関係な文章が修正として判定される")
        
        print()


def analyze_threshold_effectiveness():
    """閾値の効果分析"""
    # 実際の問題ケース
    problem_cases = [
        ("p34", "p35"),
        ("iOS 11/12/13/14/15/16", "iOS 11/12/13/14/15/16/17"),
        ("令和5年度", "令和6年度"),
        ("約1.8万人", "約1.6万人"),
    ]
    
    # 各種閾値での検証
    thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    
    print("=== 閾値効果分析 ===\n")
    
    for text1, text2 in problem_cases:
        similarity = calculate_similarity_sequencematcher(text1, text2)
        print(f"'{text1}' → '{text2}' (類似度: {similarity:.3f})")
        
        for threshold in thresholds:
            result = "修正" if similarity >= threshold else "削除+追加"
            status = "✓" if result == "修正" else "✗"
            print(f"  閾値 {threshold:.1f}: {result} {status}")
        
        print()


def test_sequence_matcher_logic():
    """SequenceMatcherの詳細な動作検証"""
    test_cases = [
        ("p34", "p35"),
        ("iOS 11/12/13/14/15/16", "iOS 11/12/13/14/15/16/17"),
    ]
    
    print("=== SequenceMatcher詳細分析 ===\n")
    
    for text1, text2 in test_cases:
        print(f"分析対象: '{text1}' → '{text2}'")
        
        matcher = SequenceMatcher(None, text1, text2)
        
        # 詳細な分析
        print(f"  全体類似度: {matcher.ratio():.3f}")
        print(f"  実際の類似度: {matcher.real_quick_ratio():.3f}")
        print(f"  高速類似度: {matcher.quick_ratio():.3f}")
        
        # マッチングブロックの詳細
        print("  マッチングブロック:")
        for block in matcher.get_matching_blocks():
            if block.size > 0:
                common_part = text1[block.a:block.a + block.size]
                print(f"    '{common_part}' (位置: {block.a}-{block.a + block.size}, サイズ: {block.size})")
        
        # 操作の詳細
        print("  必要な操作:")
        for op in matcher.get_opcodes():
            tag, i1, i2, j1, j2 = op
            if tag == 'equal':
                print(f"    保持: '{text1[i1:i2]}'")
            elif tag == 'replace':
                print(f"    置換: '{text1[i1:i2]}' → '{text2[j1:j2]}'")
            elif tag == 'delete':
                print(f"    削除: '{text1[i1:i2]}'")
            elif tag == 'insert':
                print(f"    挿入: '{text2[j1:j2]}'")
        
        print()


if __name__ == "__main__":
    print("類似度ベース検証開始\n")
    
    # 1. 基本的な類似度検証
    test_similarity_cases()
    
    # 2. 閾値効果の分析
    analyze_threshold_effectiveness()
    
    # 3. SequenceMatcherの詳細分析
    test_sequence_matcher_logic()
    
    print("類似度ベース検証完了")