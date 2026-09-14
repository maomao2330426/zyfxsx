"""限域、遵循 robots、带溯源的 Scrapy 单页采集与句子清洗。"""
import argparse
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse
import scrapy
from scrapy.crawler import CrawlerProcess
from .common import *


class WasteSpider(scrapy.Spider):
    name = 'waste'
    custom_settings = {'ROBOTSTXT_OBEY': True, 'DOWNLOAD_DELAY': 1.5, 'CONCURRENT_REQUESTS': 2,
                       'DOWNLOAD_TIMEOUT': 25, 'RETRY_TIMES': 1, 'COOKIES_ENABLED': False,
                       'USER_AGENT': 'WasteKG-Educational/1.0 (+local course project)',
                       'TELNETCONSOLE_ENABLED': False,
                       'LOG_LEVEL': 'INFO', 'FEED_EXPORT_ENCODING': 'utf-8'}

    def __init__(self, urls, output, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = urls
        self.allowed_domains = list({urlparse(u).hostname for u in urls})
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.audit = []

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, errback=self.failed)

    def failed(self, failure):
        self.audit.append({'url': failure.request.url, 'status': 'failed', 'error': str(failure.value)})

    def parse(self, response):
        digest = hashlib.sha256(response.body).hexdigest()
        (self.output / (digest[:16] + '.html')).write_bytes(response.body)
        title = clean_text(' '.join(response.css('title::text').getall()))
        self.audit.append({'url': response.url, 'status': response.status, 'sha256': digest, 'title': title})
        # 排除脚本、样式、导航、页脚；跨内联标签聚合完整段落。
        blocks = response.xpath('//p[not(ancestor::nav or ancestor::footer)] | //li[not(ancestor::nav or ancestor::footer)] | //tr')
        seen = set()
        for block in blocks:
            raw = ''.join(block.xpath('.//text()[not(ancestor::script or ancestor::style)]').getall())
            for sentence in re.split(r'(?<=[。！？；])', clean_text(raw)):
                sentence = clean_text(sentence)
                if not 8 <= len(sentence) <= 500 or not any(w in sentence for w in ['垃圾', '回收', '投放']):
                    continue
                key = hashlib.sha256(sentence.encode()).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                yield {'id': key[:20], 'text': sentence, 'source_url': response.url, 'title': title,
                       'retrieved_at': datetime.now(timezone.utc).isoformat(), 'sha256': digest,
                       'provenance': 'web_crawl', 'review_status': 'unreviewed'}

    def closed(self, reason):
        write_json(self.output / 'crawl_audit.json', {'reason': reason, 'pages': self.audit})


def clean(input_path, output_path):
    unique = {}
    total = 0
    noisy = 0
    for record in read_jsonl(input_path):
        total += 1
        text = clean_text(record['text'])
        if text.startswith('^') or re.match(r'^\d+(?:\.\d+)*\.?[\u4e00-\u9fff]{2,8}$',text) or '原始内容存档于' in text:
            noisy += 1
            continue
        if len(text) >= 8:
            key = hashlib.sha256(text.encode()).hexdigest()
            if key not in unique:
                unique[key] = {**record, 'text': text, 'source_urls': [record['source_url']]}
            elif record['source_url'] not in unique[key]['source_urls']:
                unique[key]['source_urls'].append(record['source_url'])
    write_jsonl(output_path, unique.values())
    write_json(Path(output_path).with_suffix('.audit.json'), {'input': total, 'retained': len(unique), 'removed': total-len(unique), 'noise_removed':noisy})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--urls', default=str(DATA/'seed_urls.txt'))
    parser.add_argument('--output', default=str(DATA/'raw'))
    parser.add_argument('--clean', nargs=2, metavar=('INPUT', 'OUTPUT'))
    args = parser.parse_args()
    if args.clean:
        clean(*args.clean)
        return
    urls = [s.strip() for s in Path(args.urls).read_text(encoding='utf-8').splitlines() if s.strip() and not s.startswith('#')]
    if any(urlparse(u).scheme not in ('http', 'https') for u in urls):
        raise ValueError('仅接受 HTTP(S) 来源')
    target = Path(args.output)/'pages.jsonl'
    process = CrawlerProcess({'FEEDS': {str(target): {'format': 'jsonlines', 'overwrite': True}}})
    process.crawl(WasteSpider, urls=urls, output=args.output)
    process.start()


if __name__ == '__main__':
    main()
