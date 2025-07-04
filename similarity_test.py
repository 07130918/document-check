#!/usr/bin/env python3
"""
類似度ベースでの検証スクリプト
p34/p35問題やiOS版バージョン問題を実際に計算して検証
"""

from difflib import SequenceMatcher

def calculate_similarity(text1: str, text2: str) -> float:
    """SequenceMatcherで類似度を計算"""
    return SequenceMatcher(None, text1, text2).ratio()

def test_similarity_cases():
    """問題となっているケースの類似度を実際に計算"""
    test_cases = [
        # ページ番号の変更
        ("p34", "p35"),
        ("p34", "p36"),
        ("p10", "p11"),
        
        # iOS版バージョンの変更
        ("iOS 11/12/13/14/15/16", "iOS 11/12/13/14/15/16/17"),
        ("iOS 11/12/13/14/15/16", "iOS 11/12/13/14/15/16/17/18"),
        
        # 日付の変更
        ("令和5年度", "令和6年度"),
        ("令和5年10月25日", "令和6年10月23日"),
        ("令和5年10月25日午後4時", "令和6年10月23日午後4時"),
        
        # 人数の変更
        ("約1.8万人", "約1.6万人"),
        ("約2.5万人", "約2.4万人"),
        
        # 表紙の変更
        ("裏表紙", "背表紙"),
        ("表紙", "裏表紙"),
        
        # 全く異なるテキスト
        ("完全に異なるテキスト", "totally different text"),
        
        # 同じテキスト
        ("同じテキスト", "同じテキスト"),
    ]
    
    print("=== 類似度計算結果 ===")
    print(f"{'変更前':<20} {'変更後':<20} {'類似度':<8} {'60%以上':<8}")
    print("-" * 60)
    
    for text1, text2 in test_cases:
        similarity = calculate_similarity(text1, text2)
        above_threshold = "✓" if similarity >= 0.6 else "✗"
        print(f"{text1:<20} {text2:<20} {similarity:.3f}    {above_threshold}")
    
    return test_cases

def test_dynamic_threshold():
    """動的閾値のテスト"""
    print("\n=== 動的閾値の効果 ===")
    
    def calculate_dynamic_threshold(text1: str, text2: str) -> float:
        """SequenceMatcherベースの動的閾値計算"""
        min_length = min(len(text1), len(text2))
        
        if min_length <= 20:
            return 0.6  # 短いテキストは低い閾値
        elif min_length <= 50:
            return 0.7  # 中程度のテキスト
        else:
            return 0.8  # 長いテキストは高い閾値
    
    test_cases = [
        ("p34", "p35"),
        ("iOS 11/12/13/14/15/16", "iOS 11/12/13/14/15/16/17"),
        ("令和5年10月25日午後4時", "令和6年10月23日午後4時"),
        ("約1.8万人", "約1.6万人"),
    ]
    
    print(f"{'変更前':<25} {'変更後':<25} {'類似度':<8} {'固定60%':<8} {'動的閾値':<8} {'動的判定':<8}")
    print("-" * 90)
    
    for text1, text2 in test_cases:
        similarity = calculate_similarity(text1, text2)
        fixed_threshold = similarity >= 0.6
        dynamic_threshold = calculate_dynamic_threshold(text1, text2)
        dynamic_result = similarity >= dynamic_threshold
        
        fixed_mark = "✓" if fixed_threshold else "✗"
        dynamic_mark = "✓" if dynamic_result else "✗"
        
        print(f"{text1:<25} {text2:<25} {similarity:.3f}    {fixed_mark:<8} {dynamic_threshold:.1f}      {dynamic_mark}")

def analyze_levenshtein_distance():
    """レーベンシュタイン距離での分析"""
    print("\n=== レーベンシュタイン距離分析 ===")
    
    def levenshtein_distance(s1: str, s2: str) -> int:
        """レーベンシュタイン距離計算"""
        if len(s1) > len(s2):
            s1, s2 = s2, s1
        
        distances = list(range(len(s1) + 1))
        for i2, c2 in enumerate(s2):
            distances_ = [i2 + 1]
            for i1, c1 in enumerate(s1):
                if c1 == c2:
                    distances_.append(distances[i1])
                else:
                    distances_.append(1 + min(distances[i1], distances[i1 + 1], distances_[-1]))
            distances = distances_
        
        return distances[-1]
    
    def levenshtein_ratio(s1: str, s2: str) -> float:
        """レーベンシュタイン比率計算"""
        distance = levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))
        return (max_len - distance) / max_len if max_len > 0 else 1.0
    
    test_cases = [
        ("p34", "p35"),
        ("iOS 11/12/13/14/15/16", "iOS 11/12/13/14/15/16/17"),
        ("令和5年度", "令和6年度"),
        ("約1.8万人", "約1.6万人"),
    ]
    
    print(f"{'変更前':<25} {'変更後':<25} {'SequenceMatcher':<15} {'Levenshtein':<15}")
    print("-" * 80)
    
    for text1, text2 in test_cases:
        seq_similarity = calculate_similarity(text1, text2)
        lev_similarity = levenshtein_ratio(text1, text2)
        
        print(f"{text1:<25} {text2:<25} {seq_similarity:.3f}           {lev_similarity:.3f}")

def test_character_level_analysis():
    """文字レベルの分析"""
    print("\n=== 文字レベル分析 ===")
    
    def analyze_character_changes(text1: str, text2: str):
        """文字レベルの変更を分析"""
        matcher = SequenceMatcher(None, text1, text2)
        changes = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                changes.append(f"変更: '{text1[i1:i2]}' → '{text2[j1:j2]}'")
            elif tag == 'delete':
                changes.append(f"削除: '{text1[i1:i2]}'")
            elif tag == 'insert':
                changes.append(f"挿入: '{text2[j1:j2]}'")
        
        return changes
    
    test_cases = [
        ("p34", "p35"),
        ("iOS 11/12/13/14/15/16", "iOS 11/12/13/14/15/16/17"),
        ("令和5年度", "令和6年度"),
    ]
    
    for text1, text2 in test_cases:
        print(f"\n'{text1}' → '{text2}':")
        changes = analyze_character_changes(text1, text2)
        for change in changes:
            print(f"  {change}")
        similarity = calculate_similarity(text1, text2)
        print(f"  類似度: {similarity:.3f}")

def main():
    """メイン実行"""
    print("類似度ベース検証スクリプト実行開始")
    print("=" * 60)
    
    test_similarity_cases()
    test_dynamic_threshold()
    analyze_levenshtein_distance()
    test_character_level_analysis()
    
    print("\n=== 結論 ===")
    print("1. p34→p35の類似度は約67%で、60%閾値をわずかに上回る")
    print("2. iOS版バージョンの類似度は約96%で、60%閾値を大幅に上回る")
    print("3. 動的閾値により短いテキストの検出精度が向上する可能性")
    print("4. 文字レベル分析により、具体的な変更箇所が明確になる")

if __name__ == "__main__":
    main()