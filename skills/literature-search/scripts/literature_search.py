#!/usr/bin/env python3
"""
学术文献检索工具 v2 - 三引擎版
=============================
引擎1: OpenAlex (主力) - 免费API，覆盖广，支持引用链追踪、摘要提取
引擎2: Semantic Scholar (辅助) - 搜索精准，有TLDR，需API key避免限流
引擎3: Google Scholar (补充) - 通过联网搜索，被引数最全，适合验证和补充

核心功能:
    search   - 关键词搜索论文（按被引排序）
    author   - 搜索作者及其代表作
    detail   - 获取论文详情（含完整摘要）
    cite     - 引用链追踪（谁引用了它/它引用了谁）
    verify   - 验证参考文献真伪
    trend    - 某主题的发表趋势
    google   - Google Scholar联网搜索（需外部调用internet_search）
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

# ========== 配置 ==========
OPENALEX_EMAIL = os.environ.get('OPENALEX_EMAIL', '')
S2_API_KEY = os.environ.get('S2_API_KEY', '')
REQUEST_DELAY = 0.3

# ========== 学科预设 ==========
FIELDS = {
    'econ': '20',       # Economics, Econometrics and Finance
    'biz': '14',        # Business, Management and Accounting
    'soc': '33',        # Social Sciences
    'psych': '32',      # Psychology
    'cs': '7',          # Computer Science
    'all': None,        # 不过滤
}

# ========== 工具函数 ==========
def http_get(url, headers=None, timeout=15):
    """发送HTTP GET请求，返回JSON"""
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0 (LitSearch/2.0)'}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {'_error': str(e)}

def rebuild_abstract(inverted_index):
    """从OpenAlex的abstract_inverted_index重建完整摘要
    注意：某些论文的inverted_index包含网页垃圾，限制最大2000字符
    """
    if not inverted_index:
        return ''
    wp = []
    for word, positions in inverted_index.items():
        for pos in positions:
            wp.append((pos, word))
    wp.sort()
    text = ' '.join([w for _, w in wp])
    # 正常摘要不超过2000字符，超过说明是脏数据
    if len(text) > 2000:
        # 尝试截取到Abstract:之后的内容
        idx = text.find('Abstract:')
        if idx >= 0:
            text = text[idx + 9:].strip()
        # 如果还是太长，取前2000字符
        if len(text) > 2000:
            text = text[:2000]
    return text

def trunc(text, n=200):
    """截断文本"""
    if not text:
        return ''
    return text[:n] + '...' if len(text) > n else text


# ============================================================
#  OpenAlex API - 主力引擎
# ============================================================
class OpenAlexAPI:
    BASE = 'https://api.openalex.org'
    SELECT = ('id,title,publication_year,cited_by_count,doi,'
              'authorships,primary_location,open_access,'
              'abstract_inverted_index,type,referenced_works')

    def __init__(self, email=''):
        self.email = email or OPENALEX_EMAIL

    def _url(self, endpoint, params=None):
        url = f'{self.BASE}/{endpoint}'
        if params is None:
            params = {}
        if self.email:
            params['mailto'] = self.email
        if params:
            url += '?' + urllib.parse.urlencode(params, safe=':,|/')
        return url

    # --- 搜索 ---
    def search(self, query, n=10, year_from=None, year_to=None,
               min_citations=None, sort='cited_by_count:desc', field=None):
        """field: OpenAlex field ID, 如 '20'=Economics, '14'=Business, '20|14'=两者"""
        filters = []
        if year_from:
            filters.append(f'from_publication_date:{year_from}-01-01')
        if year_to:
            filters.append(f'to_publication_date:{year_to}-12-31')
        if min_citations:
            filters.append(f'cited_by_count:>{min_citations}')
        if field:
            filters.append(f'primary_topic.field.id:{field}')
        params = {
            'search': query,
            'per_page': str(min(n, 50)),
            'sort': sort,
            'select': self.SELECT
        }
        if filters:
            params['filter'] = ','.join(filters)
        return http_get(self._url('works', params))

    def search_title(self, title, n=3):
        """精确标题搜索（验证用）"""
        params = {
            'search': title,
            'per_page': str(n),
            'sort': 'relevance_score:desc',
            'select': self.SELECT
        }
        return http_get(self._url('works', params))

    # --- 单篇详情 ---
    def get_work(self, work_id):
        if work_id.startswith('10.'):
            work_id = f'https://doi.org/{work_id}'
        params = {'select': self.SELECT}
        return http_get(self._url(f'works/{work_id}', params))

    # --- 作者 ---
    def search_authors(self, name, n=5):
        params = {
            'search': name, 'per_page': str(n),
            'select': 'id,display_name,works_count,cited_by_count,summary_stats,last_known_institutions'
        }
        return http_get(self._url('authors', params))

    def get_author_works(self, author_id, n=10, sort='cited_by_count:desc'):
        params = {
            'filter': f'author.id:{author_id}',
            'per_page': str(min(n, 50)),
            'sort': sort,
            'select': self.SELECT
        }
        return http_get(self._url('works', params))

    # --- 引用链 ---
    def get_citing(self, work_id, n=15, year_from=None, min_citations=None):
        """谁引用了这篇"""
        filters = [f'cites:{work_id}']
        if year_from:
            filters.append(f'from_publication_date:{year_from}-01-01')
        if min_citations:
            filters.append(f'cited_by_count:>{min_citations}')
        params = {
            'filter': ','.join(filters),
            'per_page': str(min(n, 50)),
            'sort': 'cited_by_count:desc',
            'select': self.SELECT
        }
        return http_get(self._url('works', params))

    def get_references(self, work_id, n=30):
        """这篇引用了谁"""
        work = self.get_work(work_id)
        if not work or '_error' in work:
            return work
        ref_ids = work.get('referenced_works', [])
        if not ref_ids:
            return {'results': [], 'meta': {'count': 0}}
        ids_str = '|'.join([r.split('/')[-1] for r in ref_ids[:n]])
        params = {
            'filter': f'openalex:{ids_str}',
            'per_page': str(min(len(ref_ids), 50)),
            'sort': 'cited_by_count:desc',
            'select': self.SELECT
        }
        return http_get(self._url('works', params))

    # --- 趋势 ---
    def trend(self, query, year_from=2010, year_to=2024):
        params = {
            'search': query,
            'filter': f'from_publication_date:{year_from}-01-01,to_publication_date:{year_to}-12-31',
            'group_by': 'publication_year'
        }
        return http_get(self._url('works', params))


# ============================================================
#  Semantic Scholar API - 辅助引擎
# ============================================================
class SemanticScholarAPI:
    BASE = 'https://api.semanticscholar.org/graph/v1'
    FIELDS = 'title,authors,year,venue,citationCount,abstract,externalIds,journal,tldr'

    def __init__(self, api_key=''):
        self.api_key = api_key or S2_API_KEY

    def _headers(self):
        h = {'User-Agent': 'Mozilla/5.0 (LitSearch/2.0)'}
        if self.api_key:
            h['x-api-key'] = self.api_key
        return h

    def _get(self, url):
        return http_get(url, headers=self._headers())

    def search(self, query, n=10, year=None, fields_of_study=None):
        params = {'query': query, 'limit': str(n), 'fields': self.FIELDS}
        if year:
            params['year'] = year
        if fields_of_study:
            params['fieldsOfStudy'] = fields_of_study
        url = f'{self.BASE}/paper/search?{urllib.parse.urlencode(params)}'
        return self._get(url)

    def get_paper(self, paper_id):
        if paper_id.startswith('10.'):
            paper_id = f'DOI:{paper_id}'
        encoded = urllib.parse.quote(paper_id, safe=':')
        fields = self.FIELDS + ',referenceCount,fieldsOfStudy'
        url = f'{self.BASE}/paper/{encoded}?fields={fields}'
        return self._get(url)

    def get_citations(self, paper_id, n=20):
        encoded = urllib.parse.quote(paper_id, safe=':')
        fields = 'title,authors,year,venue,citationCount,abstract'
        url = f'{self.BASE}/paper/{encoded}/citations?fields={fields}&limit={n}'
        return self._get(url)

    def get_references(self, paper_id, n=20):
        encoded = urllib.parse.quote(paper_id, safe=':')
        fields = 'title,authors,year,venue,citationCount,abstract'
        url = f'{self.BASE}/paper/{encoded}/references?fields={fields}&limit={n}'
        return self._get(url)

    def search_author(self, name, n=3):
        params = {'query': name, 'limit': str(n),
                  'fields': 'name,hIndex,citationCount,paperCount'}
        url = f'{self.BASE}/author/search?{urllib.parse.urlencode(params)}'
        return self._get(url)

    def recommend(self, paper_id, n=10):
        fields = 'title,authors,year,venue,citationCount,abstract'
        url = (f'https://api.semanticscholar.org/recommendations/v1'
               f'/papers/forpaper/{paper_id}?fields={fields}&limit={n}')
        return self._get(url)


# ============================================================
#  格式化输出
# ============================================================
def fmt_oa(w, idx=None):
    """格式化OpenAlex论文（含完整摘要重建）"""
    prefix = f'[{idx}] ' if idx is not None else ''
    title = w.get('title', 'N/A') or 'N/A'
    year = w.get('publication_year', '')
    cited = w.get('cited_by_count', 0)
    doi = w.get('doi', '') or ''

    auths = w.get('authorships', [])
    names = [a['author']['display_name'] for a in auths[:4]]
    if len(auths) > 4:
        names.append('et al.')
    authors = ', '.join(names)

    loc = w.get('primary_location') or {}
    src = loc.get('source') or {}
    journal = src.get('display_name', '')

    oa = w.get('open_access') or {}
    oa_tag = ' 🔓OA' if oa.get('is_oa') else ''

    abstract = rebuild_abstract(w.get('abstract_inverted_index'))

    lines = [f'{prefix}{title}']
    lines.append(f'  作者: {authors}')
    lines.append(f'  {journal} | {year} | 被引:{cited}{oa_tag}')
    if doi:
        lines.append(f'  DOI: {doi}')
    if abstract:
        lines.append(f'  摘要: {abstract}')
    return '\n'.join(lines)


def fmt_s2(p, idx=None):
    """格式化Semantic Scholar论文"""
    prefix = f'[{idx}] ' if idx is not None else ''
    title = p.get('title', 'N/A') or 'N/A'
    year = p.get('year', '')
    cited = p.get('citationCount', 0)
    venue = p.get('venue', '') or (p.get('journal') or {}).get('name', '')

    names = [a.get('name', '') for a in p.get('authors', [])[:4]]
    if len(p.get('authors', [])) > 4:
        names.append('et al.')
    authors = ', '.join(names)

    doi = (p.get('externalIds') or {}).get('DOI', '')
    tldr = (p.get('tldr') or {}).get('text', '')
    abstract = p.get('abstract', '') or ''

    lines = [f'{prefix}{title}']
    lines.append(f'  作者: {authors}')
    lines.append(f'  {venue} | {year} | 被引:{cited}')
    if doi:
        lines.append(f'  DOI: {doi}')
    if tldr:
        lines.append(f'  TLDR: {tldr}')
    elif abstract:
        lines.append(f'  摘要: {abstract}')
    return '\n'.join(lines)


# ============================================================
#  主类 - 三引擎组合
# ============================================================
class LiteratureSearch:
    """文献检索主类"""

    def __init__(self, s2_key='', oa_email=''):
        self.oa = OpenAlexAPI(email=oa_email)
        self.s2 = SemanticScholarAPI(api_key=s2_key)

    # ------ 1. 关键词搜索 ------
    def search(self, query, n=10, year_from=None, year_to=None,
               min_citations=None, engine='openalex', field='econ'):
        """搜索论文（含摘要）
        engine: 'openalex' | 's2' | 'both'
        field: 学科过滤预设
               'econ' = Economics (默认)
               'biz'  = Business/Management
               'all'  = 不过滤
               也可直接传OpenAlex field ID如'20|14'
        """
        results = []
        # 解析学科预设
        field_id = FIELDS.get(field, field) if field else None
        if engine in ('openalex', 'both'):
            data = self.oa.search(query, n=n, year_from=year_from,
                                  year_to=year_to, min_citations=min_citations,
                                  field=field_id)
            if data and '_error' not in data:
                total = data.get('meta', {}).get('count', 0)
                print(f'[OpenAlex] 共 {total} 篇\n')
                for i, w in enumerate(data.get('results', [])[:n], 1):
                    print(fmt_oa(w, i))
                    print()
                    results.append(('oa', w))
        if engine in ('s2', 'both'):
            year_str = None
            if year_from and year_to:
                year_str = f'{year_from}-{year_to}'
            elif year_from:
                year_str = f'{year_from}-'
            elif year_to:
                year_str = f'-{year_to}'
            time.sleep(REQUEST_DELAY)
            data = self.s2.search(query, n=n, year=year_str)
            if data and '_error' not in data:
                total = data.get('total', 0)
                print(f'[Semantic Scholar] 共 {total} 篇\n')
                for i, p in enumerate(data.get('data', [])[:n], 1):
                    print(fmt_s2(p, i))
                    print()
                    results.append(('s2', p))
        return results

    # ------ 2. 作者搜索 ------
    def author(self, name, n=10):
        """搜索作者及其代表作（含摘要）"""
        data = self.oa.search_authors(name, n=3)
        if not data or '_error' in data or not data.get('results'):
            print(f'未找到作者: {name}')
            return
        for a in data['results'][:2]:
            aid = a['id'].split('/')[-1]
            inst = ''
            insts = a.get('last_known_institutions') or []
            if insts:
                inst = f" | {insts[0].get('display_name', '')}"
            h = a.get('summary_stats', {}).get('h_index', 'N/A')
            print(f"{'='*50}")
            print(f"作者: {a['display_name']}")
            print(f"  ID: {aid} | 论文:{a.get('works_count',0)} | "
                  f"被引:{a.get('cited_by_count',0)} | h-index:{h}{inst}")
            print()
            works = self.oa.get_author_works(aid, n=n)
            if works and '_error' not in works:
                print(f"代表作（按被引排序）:")
                for i, w in enumerate(works.get('results', [])[:n], 1):
                    print(fmt_oa(w, i))
                    print()

    # ------ 3. 论文详情 ------
    def detail(self, identifier):
        """获取论文详情（含完整摘要）
        identifier: DOI / OpenAlex ID (W开头) / S2 ID
        """
        if identifier.startswith('W') or identifier.startswith('10.'):
            work = self.oa.get_work(identifier)
            if work and '_error' not in work:
                print('[OpenAlex]\n')
                print(fmt_oa(work))
                abstract = rebuild_abstract(work.get('abstract_inverted_index'))
                if abstract:
                    print(f'\n完整摘要:\n{abstract}')
                ref_count = len(work.get('referenced_works', []))
                print(f'\n参考文献数: {ref_count}')
                print()
        time.sleep(REQUEST_DELAY)
        paper = self.s2.get_paper(identifier)
        if paper and '_error' not in paper and paper.get('title'):
            print('[Semantic Scholar]\n')
            print(fmt_s2(paper))
            if paper.get('abstract'):
                print(f'\n完整摘要:\n{paper["abstract"]}')
            tldr = (paper.get('tldr') or {}).get('text', '')
            if tldr:
                print(f'\nTLDR: {tldr}')
            print()

    # ------ 4. 引用链追踪 ------
    def cite_trace(self, work_id, direction='both', n=15,
                   year_from=None, min_citations=None):
        """引用链追踪
        work_id: OpenAlex ID (W开头)
        direction: 'citing' | 'refs' | 'both'
        """
        if direction in ('citing', 'both'):
            print(f'=== 引用了此论文的文献 ===\n')
            data = self.oa.get_citing(work_id, n=n,
                                      year_from=year_from,
                                      min_citations=min_citations)
            if data and '_error' not in data:
                total = data.get('meta', {}).get('count', 0)
                print(f'共 {total} 篇引用\n')
                for i, w in enumerate(data.get('results', [])[:n], 1):
                    print(fmt_oa(w, i))
                    print()
        if direction in ('refs', 'both'):
            print(f'=== 此论文的参考文献 ===\n')
            data = self.oa.get_references(work_id, n=n)
            if data and '_error' not in data:
                results = data.get('results', [])
                print(f'共 {len(results)} 篇\n')
                for i, w in enumerate(results[:n], 1):
                    print(fmt_oa(w, i))
                    print()

    # ------ 5. 验证参考文献 ------
    def verify(self, ref_text):
        """验证单条参考文献的真伪（双引擎交叉验证）"""
        # 提取标题：先找[J]/[M]/[C]前的内容，再去掉作者部分
        m_bracket = re.search(r'\[([JMCR])\]', ref_text)
        before = ref_text[:m_bracket.start()].strip() if m_bracket else ref_text

        # 作者格式 "姓, X." 结束后接标题，标题以长单词开头
        m_title = re.search(r'[A-Z]\.[\s]+([A-Z][a-z]{2,}.+)$', before)
        if m_title:
            title = m_title.group(1).strip().rstrip('.')
        else:
            # fallback: 取". "分割后最长的部分
            parts = before.split('. ')
            title = before
            if len(parts) > 1:
                for p in reversed(parts):
                    if len(p) > 15:
                        title = p.strip().rstrip('.')
                        break

        print(f'验证: {trunc(ref_text, 80)}')
        print(f'提取标题: {title}\n')

        found_oa = False
        data = self.oa.search_title(title, n=3)
        if data and '_error' not in data and data.get('results'):
            for w in data['results'][:3]:
                wt = (w.get('title') or '').lower()
                if wt and wt[:30] == title.lower()[:30]:
                    found_oa = True
                    abstract = rebuild_abstract(w.get('abstract_inverted_index'))
                    loc = w.get('primary_location') or {}
                    src = loc.get('source') or {}
                    j = src.get('display_name', '')
                    print(f'  ✅ OpenAlex: {w["title"]}')
                    print(f'     {j} | {w.get("publication_year","")} | 被引:{w.get("cited_by_count",0)}')
                    if abstract:
                        print(f'     摘要: {abstract}')
                    break
        if not found_oa:
            print(f'  ⚠️ OpenAlex未精确匹配')

        time.sleep(REQUEST_DELAY)
        found_s2 = False
        data2 = self.s2.search(title, n=3)
        if data2 and '_error' not in data2 and data2.get('data'):
            for p in data2['data'][:3]:
                pt = (p.get('title') or '').lower()
                if pt and pt[:30] == title.lower()[:30]:
                    found_s2 = True
                    print(f'  ✅ S2: {p["title"]}')
                    print(f'     {p.get("venue","")} | {p.get("year","")} | 被引:{p.get("citationCount",0)}')
                    tldr = (p.get('tldr') or {}).get('text', '')
                    abstract = p.get('abstract', '')
                    if tldr:
                        print(f'     TLDR: {tldr}')
                    elif abstract:
                        print(f'     摘要: {abstract}')
                    break
        if not found_s2:
            print(f'  ⚠️ S2未精确匹配')

        verdict = '✅ 文献真实存在' if (found_oa or found_s2) else '❌ 未能验证'
        print(f'\n  结论: {verdict}\n')
        return found_oa or found_s2

    # ------ 6. 发表趋势 ------
    def trend(self, query, year_from=2010, year_to=2024):
        """某主题的发表趋势"""
        data = self.oa.trend(query, year_from, year_to)
        if not data or '_error' in data:
            print('趋势数据获取失败')
            return
        groups = data.get('group_by', [])
        year_counts = {}
        for g in groups:
            k = g.get('key') or g.get('key_display_name')
            if k:
                year_counts[int(k)] = g['count']
        if not year_counts:
            print('无趋势数据')
            return
        mx = max(year_counts.values())
        print(f'主题: {query} ({year_from}-{year_to})\n')
        print(f'{"年份":>6} | {"数量":>7} | 趋势')
        print('-' * 55)
        for y in range(year_from, year_to + 1):
            c = year_counts.get(y, 0)
            bar = '█' * int(c / mx * 30) if mx > 0 else ''
            print(f'{y:>6} | {c:>7} | {bar}')
        print(f'\n总计: {sum(year_counts.values())} 篇')

    # ------ 7. 推荐相关论文 ------
    def recommend(self, paper_id, n=10):
        """基于某篇论文推荐相关文献（S2引擎）"""
        data = self.s2.recommend(paper_id, n=n)
        if data and '_error' not in data:
            papers = data.get('recommendedPapers', [])
            print(f'推荐 {len(papers)} 篇相关文献:\n')
            for i, p in enumerate(papers[:n], 1):
                print(fmt_s2(p, i))
                print()

    # ------ 8. Google Scholar搜索提示 ------
    @staticmethod
    def google_query(query, author=None, year=None):
        """生成Google Scholar搜索语句（供internet_search使用）
        返回优化后的搜索字符串
        """
        parts = [f'site:scholar.google.com {query}']
        if author:
            parts.append(f'author:"{author}"')
        if year:
            parts.append(str(year))
        q = ' '.join(parts)
        print(f'Google Scholar搜索语句:\n  {q}')
        print(f'\n请将此语句传入 internet_search 工具执行搜索')
        return q


# ============================================================
#  CLI入口
# ============================================================
def main():
    ls = LiteratureSearch(s2_key=S2_API_KEY, oa_email=OPENALEX_EMAIL)
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == 'search':
        query = sys.argv[2] if len(sys.argv) > 2 else ''
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        engine = sys.argv[4] if len(sys.argv) > 4 else 'openalex'
        ls.search(query, n=n, engine=engine)
    elif cmd == 'author':
        ls.author(sys.argv[2] if len(sys.argv) > 2 else '')
    elif cmd == 'detail':
        ls.detail(sys.argv[2] if len(sys.argv) > 2 else '')
    elif cmd == 'cite':
        wid = sys.argv[2] if len(sys.argv) > 2 else ''
        d = sys.argv[3] if len(sys.argv) > 3 else 'both'
        ls.cite_trace(wid, direction=d)
    elif cmd == 'verify':
        ls.verify(' '.join(sys.argv[2:]))
    elif cmd == 'trend':
        ls.trend(sys.argv[2] if len(sys.argv) > 2 else '')
    elif cmd == 'recommend':
        ls.recommend(sys.argv[2] if len(sys.argv) > 2 else '')
    else:
        print(f'未知命令: {cmd}\n')
        print(__doc__)

if __name__ == '__main__':
    main()
