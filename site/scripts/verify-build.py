#!/usr/bin/env python3
"""Check the static build and preserved Hexo posts using only Python's stdlib.

Run after `npm run build`: python3 scripts/verify-build.py
An alternate output directory can be supplied with --dist PATH.
"""

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urljoin, urlsplit
from xml.etree import ElementTree as ET


VOID_TAGS = set("area base br col embed hr img input link meta param source track wbr".split())
SHANGHAI = timezone(timedelta(hours=8))


class Page(HTMLParser):
    """Read code, metadata and references without requiring a browser or DOM library."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.canonicals = []
        self.times = []
        self.ids = []
        self.refs = []
        self.code = []
        self.h1 = 0
        self.math_svg = 0
        self.math_errors = 0
        self._stack = []
        self._pre = None
        self._time = None
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            self.meta[attrs.get("property", attrs.get("name"))] = attrs.get("content")
        if tag == "link" and "canonical" in attrs.get("rel", "").split():
            self.canonicals.append(attrs.get("href", ""))
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("name"):
            self.ids.append(attrs["name"])
        if tag == "h1":
            self.h1 += 1
        if tag == "time":
            self._time = {"datetime": attrs.get("datetime"), "text": ""}
            self.times.append(self._time)
        if tag == "pre":
            # Hexo emits a separate <pre> for line numbers; those are not code.
            gutter = any("gutter" in a.get("class", "").split() for _, a in self._stack)
            if not gutter:
                self._pre = len(self.code)
                self.code.append("")
        if tag == "br" and self._pre is not None:
            self.code[self._pre] += "\n"
        if tag == "svg" and any(t == "mjx-container" for t, _ in self._stack):
            self.math_svg += 1
        if (tag == "merror" or attrs.get("data-mml-node") == "merror"
                or "data-mjx-error" in attrs
                or {"MathJax_Error", "mathjax-error"}.intersection(attrs.get("class", "").split())):
            self.math_errors += 1
        for name in ("href", "src", "poster", "xlink:href"):
            if attrs.get(name):
                self.refs.append(attrs[name])
        if tag == "object" and attrs.get("data"):
            self.refs.append(attrs["data"])
        for name in ("srcset", "imagesrcset"):
            value = attrs.get(name, "")
            if value and not value.startswith("data:"):
                self.refs.extend(part.strip().split()[0] for part in value.split(",") if part.strip())
        if tag not in VOID_TAGS:
            self._stack.append((tag, attrs))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "pre":
            self._pre = None
        if tag == "time":
            self._time = None
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                break

    def handle_data(self, data):
        if self._pre is not None:
            self.code[self._pre] += data
        if self._time is not None:
            self._time["text"] += data


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone: " + value)
    return parsed


def code_hash(value):
    # Renderers differ in the final newline; spaces, tabs and internal blank lines matter.
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    return sha256(normalized.encode("utf-8")).hexdigest()


class Verification:
    def __init__(self, dist, fixture):
        self.dist = dist.resolve()
        self.fixture = fixture
        self.origin = fixture["origin"].rstrip("/")
        self.host = urlsplit(self.origin).netloc.lower()
        self.pages = {}
        self.errors = []
        self.checks = 0

    def check(self, condition, message):
        self.checks += 1
        if not condition:
            self.errors.append(message)

    def local_target(self, ref, source_url):
        """Return the local file and decoded fragment, or None for external URLs."""
        url = urlsplit(urljoin(source_url, ref))
        if url.scheme not in ("http", "https") or url.netloc.lower() != self.host:
            return None
        path = unquote(url.path).lstrip("/")
        target = (self.dist / path).resolve()
        if target != self.dist and self.dist not in target.parents:
            return (target, unquote(url.fragment))
        if url.path.endswith("/") or target.is_dir():
            target = target / "index.html"
        return (target, unquote(url.fragment))

    def page_url(self, path):
        relative = path.relative_to(self.dist).as_posix()
        if relative == "index.html":
            relative = ""
        elif relative.endswith("/index.html"):
            relative = relative[:-len("index.html")]
        return self.origin + "/" + relative

    def load_pages(self):
        self.check(self.dist.is_dir(), "Build directory is missing: " + str(self.dist))
        for path in sorted(self.dist.rglob("*.html")):
            self.pages[path] = Page(path.read_text(encoding="utf-8"))
        self.check(bool(self.pages), "No generated HTML pages found")

    def legacy_posts(self):
        blocks = 0
        for post in self.fixture["posts"]:
            label = post["path"]
            path = self.dist / label.strip("/") / "index.html"
            page = self.pages.get(path)
            self.check(page is not None, label + ": original URL is missing")
            if page is None:
                continue
            canonical = self.origin + label
            self.check([unquote(u) for u in page.canonicals] == [canonical], label + ": canonical changed")
            self.check(page.h1 == 1, label + ": expected exactly one H1")
            self.check(page.ids.count("more") == 1, label + ": expected exactly one #more anchor")
            for heading in post.get("headings", []):
                self.check(page.ids.count(heading["id"]) == 1, label + ": legacy heading anchor changed: " + heading["id"])
            for index, (key, metadata_key) in enumerate([
                ("published", "article:published_time"),
                ("updated", "article:modified_time"),
            ]):
                expected = instant(post[key])
                try:
                    actual = page.times[index]
                    self.check(instant(actual["datetime"]) == expected, label + ": " + key + " time changed")
                    local_day = expected.astimezone(SHANGHAI).strftime("%Y/%m/%d")
                    self.check(local_day in actual["text"], label + ": " + key + " display is not the Shanghai date")
                    self.check(instant(page.meta[metadata_key]) == expected, label + ": " + key + " metadata changed")
                except (KeyError, IndexError, TypeError, ValueError) as error:
                    self.check(False, label + ": missing or invalid " + key + " timestamp (" + str(error) + ")")
            hashes = [code_hash(block) for block in page.code]
            self.check(hashes == post["code_sha256"], label + ": code blocks changed, reordered or missing")
            blocks += len(hashes)
            if post["math"]:
                self.check(page.math_svg > 0, label + ": expected static MathJax SVG output")
            self.check(page.math_errors == 0, label + ": MathJax contains an merror")
        self.check(blocks == self.fixture["code_block_count"], "Expected all 27 legacy code blocks to be preserved")

    def internal_links(self):
        for path, page in self.pages.items():
            source_url = self.page_url(path)
            label = path.relative_to(self.dist).as_posix()
            for ref in sorted(set(page.refs)):
                result = self.local_target(ref, source_url)
                if result is None:
                    continue
                target, fragment = result
                inside = target == self.dist or self.dist in target.parents
                self.check(inside and target.is_file(), label + ": missing local target " + ref)
                if not inside or not target.is_file() or not fragment or target.suffix != ".html":
                    continue
                # Browser text fragments may follow a regular element fragment.
                fragment = fragment.split(":~:text=", 1)[0]
                if fragment:
                    target_page = self.pages.get(target)
                    self.check(target_page is not None and fragment in target_page.ids,
                               label + ": missing anchor " + ref)

    def rss(self):
        path = self.dist / "rss.xml"
        self.check(path.is_file(), "rss.xml is missing")
        if not path.is_file():
            return
        items = ET.parse(path).findall("./channel/item")
        by_url = {}
        for item in items:
            link = unquote(item.findtext("link", ""))
            by_url.setdefault(link, []).append(item)
            target = self.local_target(link, self.origin + "/rss.xml")
            self.check(target is not None and target[0].is_file(), "RSS links to a missing local article: " + link)
        for post in self.fixture["posts"]:
            matches = by_url.get(self.origin + post["path"], [])
            self.check(len(matches) == 1, "RSS must include each legacy article exactly once: " + post["path"])
            if matches:
                actual = parsedate_to_datetime(matches[0].findtext("pubDate", ""))
                self.check(actual == instant(post["published"]).replace(microsecond=0),
                           "RSS publication date changed: " + post["path"])

    def sitemap(self):
        pending = [self.dist / "sitemap-index.xml"]
        visited = set()
        locations = []
        while pending:
            path = pending.pop()
            if path in visited:
                continue
            visited.add(path)
            self.check(path.is_file(), "Missing sitemap: " + str(path.relative_to(self.dist)))
            if not path.is_file():
                continue
            root = ET.parse(path).getroot()
            urls = [element.text for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "loc"]
            for url in urls:
                if not url:
                    continue
                result = self.local_target(url, self.page_url(path))
                self.check(result is not None and result[0].is_file(), "Sitemap points to a missing local target: " + url)
                if root.tag.rsplit("}", 1)[-1] == "sitemapindex":
                    if result is not None and result[0].is_file():
                        pending.append(result[0])
                else:
                    locations.append(unquote(url))
        for post in self.fixture["posts"]:
            self.check(locations.count(self.origin + post["path"]) == 1,
                       "Sitemap must include each legacy article exactly once: " + post["path"])

    def search_index(self):
        path = self.dist / "search-index.json"
        self.check(path.is_file(), "search-index.json is missing")
        if not path.is_file():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self.check(isinstance(data, list), "Search index must be a JSON array")
        if not isinstance(data, list):
            return
        counts = Counter()
        legacy = {post["path"]: post for post in self.fixture["posts"]}
        for item in data:
            self.check(isinstance(item, dict), "Search index contains a non-object entry")
            if not isinstance(item, dict):
                continue
            url = item.get("url", "")
            result = self.local_target(url, self.origin + "/search-index.json") if isinstance(url, str) and url else None
            self.check(result is not None and result[0].is_file(), "Search index has a missing article URL: " + str(url))
            self.check(bool(item.get("title")) and bool(item.get("content")), "Search entry lacks title/content: " + str(url))
            self.check(isinstance(item.get("tags"), list), "Search entry tags must be an array: " + str(url))
            if result:
                article_path = unquote(urlsplit(urljoin(self.origin, url)).path)
                counts[article_path] += 1
                if article_path in legacy:
                    post = legacy[article_path]
                    self.check(item.get("title") == post["title"], "Search title changed: " + article_path)
                    try:
                        self.check(instant(item["pubDate"]) == instant(post["published"]),
                                   "Search publication date changed: " + article_path)
                    except (KeyError, TypeError, ValueError):
                        self.check(False, "Search entry lacks a valid publication date: " + article_path)
        for post in self.fixture["posts"]:
            self.check(counts[post["path"]] == 1,
                       "Search index must include each legacy article exactly once: " + post["path"])

    def run(self):
        for name, method in [
            ("HTML loading", self.load_pages),
            ("legacy URLs, dates, code and math", self.legacy_posts),
            ("internal links, anchors and assets", self.internal_links),
            ("RSS", self.rss), ("sitemap", self.sitemap), ("search index", self.search_index),
        ]:
            before = len(self.errors)
            try:
                method()
            except (OSError, ValueError, TypeError, ET.ParseError) as error:
                self.errors.append(name + ": " + str(error))
            print(("PASS " if len(self.errors) == before else "FAIL ") + name)
        if self.errors:
            for error in self.errors:
                print("  - " + error, file=sys.stderr)
            print("FAILED: {} issue(s), {} checks.".format(len(self.errors), self.checks), file=sys.stderr)
            return 1
        print("Verified {} HTML pages, {} legacy posts and {} preserved code blocks ({} checks).".format(
            len(self.pages), len(self.fixture["posts"]), self.fixture["code_block_count"], self.checks))
        return 0


def main():
    script = Path(__file__).resolve()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=script.parent.parent / "dist")
    args = parser.parse_args()
    fixture = json.loads((script.parent / "fixtures" / "legacy-posts.json").read_text(encoding="utf-8"))
    return Verification(args.dist, fixture).run()


if __name__ == "__main__":
    sys.exit(main())
