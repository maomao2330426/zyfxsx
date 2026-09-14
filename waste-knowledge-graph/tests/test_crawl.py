import json
import pytest
scrapy=pytest.importorskip('scrapy')
from scrapy.http import HtmlResponse
from wastekg.crawl import WasteSpider,clean
from wastekg.common import read_jsonl,write_jsonl


def test_html_extraction_joins_inline_nodes_and_skips_scripts(tmp_path):
    html='<html><title>示例</title><script>垃圾垃圾垃圾垃圾</script><p>香蕉皮属于<strong>湿垃圾</strong>。</p><p>香蕉皮属于湿垃圾。</p></html>'
    spider=WasteSpider(urls=['https://example.org'],output=tmp_path)
    response=HtmlResponse(url='https://example.org',body=html.encode(),encoding='utf-8')
    rows=list(spider.parse(response))
    assert len(rows)==1
    assert rows[0]['text']=='香蕉皮属于湿垃圾。'
    assert rows[0]['provenance']=='web_crawl'


def test_clean_deduplicates_and_retains_all_sources(tmp_path):
    source=tmp_path/'raw.jsonl';out=tmp_path/'clean.jsonl'
    write_jsonl(source,[{'text':'香蕉皮属于湿垃圾。','source_url':'https://a.org'},{'text':' 香蕉皮属于湿垃圾。 ','source_url':'https://b.org'}])
    clean(source,out)
    rows=read_jsonl(out)
    assert len(rows)==1 and len(rows[0]['source_urls'])==2
