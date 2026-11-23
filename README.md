# IBlogger — Tamir Dresher's Technical Blog

> Tips, tools, and insights from a Principal Engineer.

**Live site:** [tamirdresher.com](https://www.tamirdresher.com)

---

## About the Blog

IBlogger is the personal technical blog of **Tamir Dresher** — Principal Engineer, author, and speaker. The blog covers the cutting edge of software engineering with a focus on building real, production-grade systems.

### Topics Covered

- 🤖 **AI & Agent Systems** — Building multi-agent AI squads, LLM orchestration, autonomous developer workflows, and production AI patterns
- ☁️ **.NET & Cloud-Native** — .NET Aspire, microservices, distributed application design, and Azure platform engineering
- ⚙️ **Kubernetes & DevOps** — AKS, Helm, ArgoCD, KEDA, CI/CD pipelines, and platform engineering at scale
- 🔄 **Reactive Programming** — Rx.NET, event-driven architectures, and real-time data processing
- 🔐 **Security & Architecture** — Workload identity, zero-trust patterns, and AI agent security hardening
- 🧰 **Developer Tools & Productivity** — Copilot, MCP servers, developer sandboxes, and AI-assisted engineering workflows

---

## Featured Series

### 🚀 Scaling AI — Multi-Agent Engineering at Scale
A deep-dive series on building and deploying AI agent squads in production environments:
- Part 1: Forming the first AI team
- Part 7: Enterprise state management for agents
- Part 8: Pathfinder — navigating complex agent graphs
- And more…

### 🌐 .NET Aspire & Polyglot Microservices
Practical guides for building observable, cloud-ready .NET applications with Aspire.

---

## Author

**Tamir Dresher**
Principal Engineer | Author of [Rx.NET in Action](https://www.manning.com/books/rx-dot-net-in-action) | Microsoft MVP

- 🐦 Twitter/X: [@tamir_dresher](https://twitter.com/tamir_dresher)
- 💼 LinkedIn: [tamirdresher](https://www.linkedin.com/in/tamirdresher)
- 🐙 GitHub: [@tamirdresher](https://github.com/tamirdresher)

---

## Built With

This blog is built using:

- **[Jekyll](https://jekyllrb.com/)** — Static site generator
- **[Chirpy Theme](https://github.com/cotes2020/jekyll-theme-chirpy)** — Responsive Jekyll theme with dark/light mode
- **[GitHub Pages](https://pages.github.com/)** — Hosting

### Running Locally

```bash
# Install dependencies
bundle install

# Serve locally
bundle exec jekyll serve
```

Then open `http://localhost:4000` in your browser.

### Tag archives on GitHub Pages

The site uses legacy GitHub Pages (`master:/`), which does not run custom
generators or the old Chirpy `_scripts/sh/create_pages.sh` helper. Tag archives
therefore live in committed `tags/*.md` pages using the existing `tag` layout.
After adding or changing post tags, regenerate and commit these pages:

```bash
# Maintenance tooling uses Python and PyYAML (not a Pages build dependency).
python tools/generate_tag_pages.py
python tools/generate_tag_pages.py --check
python tools/test_tag_navigation.py
python tools/test_tag_navigation.py --render
```

The last command requires the existing bundled Jekyll toolchain and checks actual
rendered archives and links, including a project-site baseurl. Generation includes
scheduled posts, but `future: false` still controls which posts Jekyll displays.
Archive URLs share the theme's space-to-hyphen/lowercase encoding; colliding tag
names share an archive without changing the posts' taxonomy.

To check coverage against a current fetched base branch without merging it, add
`--master-ref origin/master`. For actual legacy Pages rendering, `--render
--docker-image <installed-image-digest> --master-ref origin/master` uses an
installed GitHub Pages toolchain (for example, the image documented by
[`actions/jekyll-build-pages`](https://github.com/actions/jekyll-build-pages)).
Containers have no network access and mount only this checkout read-only and
the owned `_site` validation output. The effective master-plus-PR source and
rendered fixtures are removed when checks finish.

---

## License

Content © Tamir Dresher. All rights reserved.
Theme licensed under [MIT](https://opensource.org/licenses/MIT).
