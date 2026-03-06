# 学术文献检索 Skill v2 (Literature Search)

三引擎学术文献检索：OpenAlex（主力）+ Semantic Scholar（辅助）+ Google Scholar（补充）

## 脚本位置

`/skills/literature-search/scripts/literature_search.py`

## 核心能力

| 功能 | 方法 | 说明 | 摘要 |
|------|------|------|------|
| 关键词搜索 | `ls.search()` | 按被引排序，支持年份/被引过滤 | ✅ |
| 作者搜索 | `ls.author()` | 作者信息+代表作列表 | ✅ |
| 论文详情 | `ls.detail()` | 完整摘要+TLDR+参考文献数 | ✅完整 |
| 引用链追踪 | `ls.cite_trace()` | 谁引用了它/它引用了谁 | ✅ |
| 验证文献 | `ls.verify()` | 双引擎交叉验证真伪 | ✅ |
| 发表趋势 | `ls.trend()` | 按年份统计论文数量 | - |
| 论文推荐 | `ls.recommend()` | 基于某篇推荐相关文献(S2) | ✅ |
| Google搜索 | `ls.google_query()` | 生成搜索语句供internet_search使用 | - |

## 快速开始

```python
import sys
sys.path.insert(0, '/skills/literature-search/scripts')
from literature_search import LiteratureSearch
ls = LiteratureSearch()
```

## 各功能用法

### 1. 关键词搜索
```python
# 默认搜经济学文献（field='econ'）
ls.search('competition innovation firms', n=10)

# 搜管理学/商学文献
ls.search('dynamic capabilities', n=10, field='biz')

# 不限学科
ls.search('machine learning prediction', n=10, field='all')

# 限定年份+最低被引
ls.search('market power markup', n=10, year_from=2018, min_citations=50)

# 用Semantic Scholar搜（有TLDR）
ls.search('inverted-U competition', n=5, engine='s2')

# 学科预设: 'econ'=经济学(默认) | 'biz'=商学 | 'all'=不限
#           也可直接传OpenAlex field ID如'20|14'
```

### 2. 作者搜索
```python
ls.author('Philippe Aghion', n=10)
```

### 3. 论文详情（完整摘要）
```python
ls.detail('10.1162/0033553053970214')  # DOI
ls.detail('W4293020912')               # OpenAlex ID
```

### 4. 引用链追踪
```python
ls.cite_trace('W4293020912', direction='citing', n=15)
ls.cite_trace('W4293020912', direction='refs', n=15)
ls.cite_trace('W4293020912', direction='both', n=10)
ls.cite_trace('W4293020912', direction='citing', year_from=2020, min_citations=50)
```

### 5. 验证参考文献
```python
ls.verify('Aghion, P. A Model of Growth[J]. Econometrica, 1992.')
```

### 6. 发表趋势
```python
ls.trend('machine learning economics', year_from=2015, year_to=2024)
```

### 7. Google Scholar
```python
q = ls.google_query('competition innovation', author='Aghion', year=2005)
# 将q传入internet_search工具
```

## 标准工作流

```
1. ls.search('主题关键词', n=20, min_citations=50) → 找经典
2. 选核心论文，记OpenAlex ID
3. ls.cite_trace('W...', direction='both') → 引用链展开
4. ls.author('核心作者') → 找其他相关论文
5. ls.verify(每条参考文献) → 确认真伪+摘要匹配
```

## 搜索技巧

- 英文关键词效果远好于中文
- 加 `min_citations=50` 过滤低质量
- 引用链追踪是最高效的文献发现方式
- 摘要可判断论文是否真正相关

## 配置

```python
ls = LiteratureSearch(s2_key='你的key', oa_email='你的邮箱')
```
S2 API Key申请：https://www.semanticscholar.org/product/api#api-key

## ⚠️ 摘要使用规则（极其重要）

脚本返回的摘要是从API获取的原文摘要（英文），在任何场景下：

1. **禁止总结/压缩摘要** — 必须完整保留原文，一个词都不能少
2. **禁止翻译摘要** — 除非用户明确要求翻译，否则保持英文原文
3. **禁止改写摘要** — 不得用自己的话重新表述
4. **subagent返回时同样适用** — 如果用subagent批量获取文献，返回结果中的摘要必须是API原文，不得总结

正确做法：直接输出脚本print的内容，不做任何加工。
