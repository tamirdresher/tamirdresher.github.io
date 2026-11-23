"""Focused archive-generation checks; --render also runs real safe-mode Jekyll."""

import argparse
from html.parser import HTMLParser
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
import unittest
from urllib.parse import unquote, urlsplit
import uuid

import yaml

from generate_tag_pages import ROOT, archive_pages, frontmatter, generate, parse_page, tag_slug
from urllib.parse import quote_plus


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links = []
        self.post_tags = []
        self.canonical = None
        self.post_tag_depth = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            if self.post_tag_depth:
                self.post_tag_depth += 1
            elif "post-tags" in attrs.get("class", "").split():
                self.post_tag_depth = 1
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
            if self.post_tag_depth:
                self.post_tags.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "div" and self.post_tag_depth:
            self.post_tag_depth -= 1


class TagNavigationTests(unittest.TestCase):
    def setUp(self):
        self.work = ROOT / "_site" / "tag-navigation-checks"
        if self.work.exists():
            raise RuntimeError(f"Existing check directory must not be overwritten: {self.work}")
        (self.work / "_posts").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.work)

    def post(self, name, tags, **extra):
        data = {"title": name, "date": "2020-01-01", "tags": tags, **extra}
        path = self.work / "_posts" / f"2020-01-01-{name}.md"
        path.write_text("---\n" + yaml.safe_dump(data) + "---\nBody.\n", encoding="utf-8")
        return path

    def test_exact_taxonomy_and_encoded_collision_archive(self):
        self.post("one", ["workflows", "distributed systems", "C# & APIs"])
        self.post("two", ["distributed-systems", "distributed systems"])
        self.post("windows", ["workflows"]).write_bytes(
            b"---\r\ntitle: Windows\r\ntags: [workflows]\r\n---\r\nBody.\r\n")
        self.post("hidden", ["hidden-tag"], published=False)
        self.assertEqual(generate(self.work), 3)
        archive = frontmatter(self.work / "tags" / "distributed-systems.md")
        self.assertEqual(archive["tag_keys"], ["distributed systems", "distributed-systems"])
        self.assertEqual(archive["permalink"], "/tags/distributed-systems/")
        special = frontmatter(self.work / "tags" / "c%23-%26-apis.md")
        self.assertEqual(special["tag"], "C# & APIs")
        self.assertEqual(special["permalink"], "/tags/c%23-%26-apis/")
        self.assertFalse((self.work / "tags" / "hidden-tag.md").exists())

    def test_regeneration_preserves_editorial_metadata_and_removes_only_generated_pages(self):
        self.post("one", ["workflows"])
        generate(self.work)
        custom = self.work / "tags" / "editorial.md"
        custom.write_text("---\nlayout: tag\ntitle: Editorial title\ntag: editorial\n---\nArchive introduction.\n",
                          encoding="utf-8")
        self.post("two", ["editorial"])
        generate(self.work)
        self.assertEqual(frontmatter(custom)["title"], "Editorial title")
        self.assertEqual(frontmatter(custom)["permalink"], "/tags/editorial/")
        self.assertTrue(custom.read_text(encoding="utf-8").endswith("Archive introduction.\n"))
        (self.work / "_posts" / "2020-01-01-one.md").unlink()
        with self.assertRaises(ValueError):
            generate(self.work, check=True)
        generate(self.work)
        self.assertFalse((self.work / "tags" / "workflows.md").exists())
        self.assertTrue(custom.exists())
        generate(self.work, check=True)

    def test_committed_archives_cover_exact_source_tag_keys(self):
        generate(ROOT, check=True)
        for path, content in archive_pages(ROOT).items():
            expected = parse_page(content)[0]
            actual = frontmatter(path)
            self.assertEqual(actual["permalink"], expected["permalink"])
            self.assertEqual(actual.get("tag_keys", [actual["tag"]]),
                             expected.get("tag_keys", [expected["tag"]]))


def revision_posts(ref):
    archive = subprocess.check_output(["git", "archive", ref, "--", "_posts"], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source:
            if member.isfile() and Path(member.name).suffix in (".md", ".html", ".markdown"):
                text = source.extractfile(member).read().decode("utf-8-sig")
                yield member.name, parse_page(text)[0]


def check_master_coverage(ref):
    keys = set()
    for _, data in revision_posts(ref):
        if data.get("published") is False:
            continue
        tags = data.get("tags") or []
        keys.update(tags.split() if isinstance(tags, str) else tags)
    for tag in keys:
        slug = quote_plus(tag_slug(tag), safe="")
        path = ROOT / "tags" / f"{slug}.md"
        if not path.is_file():
            raise AssertionError(f"{ref} tag {tag!r} has no committed archive source")
        data = frontmatter(path)
        if data["permalink"] != f"/tags/{slug}/" or tag not in data.get("tag_keys", [data["tag"]]):
            raise AssertionError(f"{ref} tag {tag!r} has a mismatching archive")
    sha = subprocess.check_output(["git", "rev-parse", ref], cwd=ROOT, text=True).strip()
    print(f"Master coverage passed: {sha}, {len(keys)} exact tag keys")


def effective_source(work, ref, additional_ref=None):
    effective = work / "effective-source"
    effective.mkdir()
    process = subprocess.Popen(["git", "archive", ref], cwd=ROOT, stdout=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        archive.extractall(effective, filter="data")
    if process.wait() != 0:
        raise RuntimeError(f"Could not read source tree at {ref}")
    base = subprocess.check_output(["git", "merge-base", "HEAD", ref], cwd=ROOT, text=True).strip()
    branch_paths = set(subprocess.check_output(
        ["git", "diff", "--name-only", base, "HEAD"], cwd=ROOT, text=True).splitlines())
    master_paths = set(subprocess.check_output(
        ["git", "diff", "--name-only", base, ref], cwd=ROOT, text=True).splitlines())
    for path in branch_paths & master_paths:
        branch = subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=ROOT)
        master = subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT)
        if branch != master:
            raise RuntimeError(f"Conflicting source-composition input: {path}")
    local_paths = set(subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True).splitlines())
    new_paths = set(subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines())
    for path in branch_paths | local_paths | new_paths:
        if "__pycache__" in Path(path).parts:
            continue
        target = effective / path
        current = ROOT / path
        if current.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current, target)
        elif target.exists():
            target.unlink()
    if additional_ref:
        extra_paths = set(subprocess.check_output(
            ["git", "diff", "--name-only", f"{ref}...{additional_ref}"],
            cwd=ROOT, text=True).splitlines())
        overlap = extra_paths & (branch_paths | local_paths | new_paths)
        if overlap:
            raise RuntimeError(f"Independent slices overlap: {sorted(overlap)}")
        archive = subprocess.check_output(
            ["git", "archive", additional_ref, "--", *sorted(extra_paths)], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(effective, filter="data")
    generate(effective, check=True)
    return effective


def build(source, destination, baseurl="", docker_image=None, work=None):
    if docker_image:
        def container_path(path):
            path = path.resolve()
            if path.is_relative_to(work):
                return "/validation/" + path.relative_to(work).as_posix()
            return "/blog/" + path.relative_to(ROOT).as_posix()

        ruby = """
require 'github-pages'
require 'fileutils'
$stdout.sync = true
FileUtils.mkdir_p('render-work/source')
source = File.expand_path('render-work/source')
destination = File.expand_path('render-work/output')
puts 'Copying public source into owned ephemeral container filesystem'
Dir.children(ARGV[0]).reject { |name| ['.git', '_site', '.jekyll-cache', '.sass-cache'].include?(name) }.each do |name|
  FileUtils.cp_r(File.join(ARGV[0], name), source)
end
config = Jekyll.configuration('source' => source, 'destination' => destination, 'baseurl' => ARGV[2])
config = GitHubPages::Configuration.effective_config(config)
raise 'Not a safe-mode Pages build' unless config['safe']
puts "Actual Pages render: Jekyll #{Jekyll::VERSION}, github-pages #{GitHubPages::VERSION}, safe=#{config['safe']}, future=#{config['future']}, baseurl=#{config['baseurl']}"
Jekyll::Site.new(config).process
html = Dir.glob(File.join(destination, '**', '*.html'))
html.each do |path|
  target = File.join(ARGV[1], path.delete_prefix(destination + '/'))
  FileUtils.mkdir_p(File.dirname(target))
  FileUtils.cp(path, target)
end
puts "Pages build complete; captured #{html.size} actual HTML outputs for navigation checks"
"""
        subprocess.run([
            "docker", "run", "--rm", "--name", f"data-tag-render-{uuid.uuid4().hex[:12]}",
            "--network", "none", "--mount", f"type=bind,source={ROOT},target=/blog,readonly",
            "--mount", f"type=bind,source={work},target=/validation",
            "--env", "JEKYLL_ENV=production", "--env", "BUNDLE_GEMFILE=/Gemfile",
            "--entrypoint", "bundle", docker_image, "exec", "ruby", "-e", ruby,
            container_path(source), container_path(destination), baseurl,
        ], cwd=ROOT, check=True)
        return
    bundle = shutil.which("bundle")
    if not bundle:
        raise RuntimeError("Real Jekyll render unavailable: Ruby/Bundler is not installed")
    subprocess.run(
        [bundle, "exec", "jekyll", "build", "--safe",
         "--source", str(source), "--destination", str(destination), "--baseurl", baseurl],
        cwd=ROOT, check=True,
    )


def tag_targets(site, html, baseurl=""):
    targets = []
    for href in Links(html).links:
        path = urlsplit(href).path
        prefix = baseurl + "/tags/"
        if not path.startswith(prefix) or path == prefix:
            continue
        relative = unquote(path[len(baseurl):]).strip("/")
        target = site / relative / "index.html"
        if not target.is_file():
            raise AssertionError(f"{href} has no rendered archive: {target}")
        targets.append((href, target))
    return targets


def page_html(site, path):
    index = site / path.strip("/") / "index.html"
    if index.exists():
        return index.read_text(encoding="utf-8")
    return (site / (path.strip("/") + ".html")).read_text(encoding="utf-8")


def check_rendered_membership(site, baseurl=""):
    checks = 0
    for path in site.rglob("*.html"):
        html = path.read_text(encoding="utf-8")
        tag_targets(site, html, baseurl)
        links = Links(html)
        if not links.post_tags:
            continue
        if not links.canonical:
            raise AssertionError(f"Tagged post lacks its canonical URL: {path}")
        post_url = urlsplit(links.canonical).path
        for href in links.post_tags:
            targets = tag_targets(site, f'<a href="{href}"></a>', baseurl)
            if not targets:
                raise AssertionError(f"Post tag is not an archive link: {href}")
            for _, archive in targets:
                if post_url not in Links(archive.read_text(encoding="utf-8")).links:
                    raise AssertionError(f"{post_url} missing from matching archive {href}")
                checks += 1
    if not checks:
        raise AssertionError("No actual tagged-post archive membership was checked")
    print(f"Actual tagged-post/archive membership checks passed: {checks}")


def render_checks(docker_image=None, master_ref=None, additional_ref=None, expected_posts=()):
    work = ROOT / "_site" / "tag-navigation-render"
    if work.exists():
        raise RuntimeError(f"Existing render directory must not be overwritten: {work}")
    work.mkdir(parents=True)
    try:
        source = effective_source(work, master_ref, additional_ref) if master_ref else ROOT
        site = work / "site"
        build(source, site, docker_image=docker_image, work=work)
        home = (site / "index.html").read_text(encoding="utf-8")
        if not tag_targets(site, home):
            raise AssertionError("Homepage did not emit tag links")
        tag_targets(site, page_html(site, "/tabs/tags"))
        check_rendered_membership(site)
        for post_url in expected_posts:
            if not Links(page_html(site, post_url)).post_tags:
                raise AssertionError(f"Expected post has no rendered tag links: {post_url}")
            print(f"Expected post rendered and membership checked: {post_url}")

        fixture = work / "fixture"
        fixture.mkdir()
        for directory in ("_layouts", "_includes", "_data", "tabs"):
            shutil.copytree(ROOT / directory, fixture / directory)
        shutil.copy2(ROOT / "index.html", fixture / "index.html")
        shutil.copy2(ROOT / "_config.yml", fixture / "_config.yml")
        (fixture / "_posts").mkdir()
        for i in range(3):
            tags = ["workflows"]
            if i == 0:
                tags += ["distributed systems", "distributed-systems", "C# & APIs"]
            data = {"layout": "post", "title": f"Fixture {i}", "date": f"2020-01-{i + 1:02}",
                    "tags": tags}
            (fixture / "_posts" / f"2020-01-{i + 1:02}-fixture-{i}.md").write_text(
                "---\n" + yaml.safe_dump(data) + "---\nBody.\n", encoding="utf-8")
        (fixture / "_posts" / "2999-01-01-scheduled.md").write_text(
            "---\nlayout: post\ntitle: Scheduled\n"
            "date: 2999-01-01\ntags: ['distributed SYSTEMS']\n---\nFuture.\n",
            encoding="utf-8")
        generate(fixture)
        for baseurl in ("", "/preview"):
            output = work / ("fixture-site" + ("-preview" if baseurl else ""))
            build(fixture, output, baseurl, docker_image=docker_image, work=work)
            home = (output / "index.html").read_text(encoding="utf-8")
            tag_targets(output, home, baseurl)
            multi = output / "tags" / "distributed-systems" / "index.html"
            multi_html = multi.read_text(encoding="utf-8")
            expected = baseurl + "/blog/2020/01/01/fixture-0"
            if Links(multi_html).links.count(expected) != 1:
                raise AssertionError("Colliding multi-word tags must show their matching post once")
            if any("/2999/" in href for href in Links(multi_html).links):
                raise AssertionError("Tag archive bypassed future: false")
            special = output / "tags" / "c#-&-apis" / "index.html"
            special_html = special.read_text(encoding="utf-8")
            if "C# &amp; APIs" not in special_html or expected not in Links(special_html).links:
                raise AssertionError("Punctuation archive lost its escaped label or matching post")
            check_rendered_membership(output, baseurl)
            workflow_links = [
                href for href in Links((output / "tags" / "workflows" / "index.html").read_text(encoding="utf-8")).links
                if href.startswith(baseurl + "/blog/")
            ]
            if workflow_links[0] != baseurl + "/blog/2020/01/03/fixture-2":
                raise AssertionError("Tag archive posts are not newest first")
        print("Real safe-mode Jekyll navigation checks passed (site + two fixture baseurls)")
    finally:
        shutil.rmtree(work)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--docker-image", help="Use an installed GitHub Pages image for rendering")
    parser.add_argument("--master-ref", help="Check and render the effective master + PR source tree")
    parser.add_argument("--additional-ref", help="Include a disjoint independent PR in the rendered source")
    parser.add_argument("--expected-post", action="append", default=[],
                        help="Require a specific post URL only for an explicit integration check")
    args = parser.parse_args()
    if args.additional_ref and not args.master_ref:
        parser.error("--additional-ref requires --master-ref")
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TagNavigationTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.master_ref:
        check_master_coverage(args.master_ref)
    if args.render:
        render_checks(args.docker_image, args.master_ref, args.additional_ref, args.expected_post)
