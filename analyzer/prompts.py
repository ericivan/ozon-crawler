ANALYZE_PRODUCTS_SYSTEM = """你是一位专业的 Ozon 俄罗斯电商选品分析师。收到原始商品数据后进行结构化分析。
分析维度：竞争强度（低/中/高）、缺口机会、价格带、关键词建议、入场建议。
竞争强度判断标准：
- 低：搜索结果 <200 且头部评价 <100
- 中：搜索结果 200-1000 或评价数 100-500
- 高：搜索结果 >1000 且头部评价 >500
只返回 JSON，不含任何解释文字和 markdown 代码块，文字用中文，关键词保留俄语。"""

ANALYZE_PRODUCTS_USER = """分析关键词：{keyword_ru}（中文：{keyword_cn}）
抓取商品数量：{total_count}
原始数据：{json_data}

输出 JSON schema（严格遵循，不要添加额外字段）：
{{
  "competition_level": "低|中|高",
  "opportunity_score": 1-10的整数,
  "summary": "综合分析摘要（中文）",
  "price_analysis": {{
    "min": 最低价格数字,
    "max": 最高价格数字,
    "sweet_spot": "主流价格区间描述",
    "weak_zone": "价格竞争薄弱区间描述"
  }},
  "gap_opportunities": [
    {{"direction": "机会方向", "reason": "原因", "entry_difficulty": "低|中|高"}}
  ],
  "keywords_recommend": [
    {{"ru": "俄语关键词", "cn": "中文翻译", "type": "核心词|长尾词|场景词", "reason": "推荐原因"}}
  ],
  "action": {{
    "conclusion": "入场|观望|放弃",
    "reason": "入场建议原因",
    "next_step": "建议下一步行动"
  }}
}}"""

SUGGEST_KEYWORDS_SYSTEM = """你是精通俄语的 Ozon 关键词专家。生成符合俄罗斯用户真实搜索习惯的关键词。
分类：核心词3个（高搜索量）、长尾词4个（带属性/场景）、场景词3个。
只返回 JSON 数组，避免机器翻译腔。"""

SUGGEST_KEYWORDS_USER = """产品：{product_name_cn}
属性：{attributes}
目标用户：{target_user}
价格区间：{price_range}

输出 JSON 数组（严格遵循，共10个关键词）：
[
  {{
    "ru": "俄语关键词",
    "cn": "中文翻译",
    "type": "核心词|长尾词|场景词",
    "difficulty": "低|中|高",
    "reason": "推荐理由"
  }}
]"""

ANALYZE_REVIEWS_SYSTEM = """你是消费者洞察分析师。分析 Ozon 俄语评价，提取痛点和需求。
只返回 JSON，文字用中文。"""

ANALYZE_REVIEWS_USER = """关键词：{keyword_ru}
评价样本：{reviews_json}

输出 JSON schema：
{{
  "pain_points": [
    {{"issue": "问题描述", "frequency": "高|中|低", "quote_hint": "原文提示"}}
  ],
  "unmet_needs": [
    {{"need": "未满足需求", "opportunity": "对应机会"}}
  ],
  "positive_points": [
    {{"point": "好评点", "frequency": "高|中|低"}}
  ],
  "opportunity_signal": "综合机会信号描述"
}}"""

BATCH_RANK_SYSTEM = """你是 Ozon 选品策略顾问。横向比较多个关键词数据，按综合得分排序。
权重：opportunity_score×0.4 + 竞争强度(低3分/中2分/高1分)×0.3 + 价格区间宽度×0.2 + 缺口数量×0.1
只返回 JSON。"""

BATCH_RANK_USER = """共 {total} 个关键词汇总数据：
{batch_summary_json}

输出 JSON schema：
{{
  "ranked_list": [
    {{
      "rank": 排名数字,
      "keyword_ru": "俄语关键词",
      "keyword_cn": "中文关键词",
      "composite_score": 综合得分数字,
      "conclusion": "入场|观望|放弃",
      "one_line_reason": "一句话理由"
    }}
  ],
  "top_pick": "最推荐关键词的俄语",
  "weekly_insight": "本周选品洞察摘要"
}}"""
