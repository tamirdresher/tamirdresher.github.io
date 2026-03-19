---
title: Products
---

<style>
.products-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
  margin-top: 1.5rem;
}

.product-card {
  border: 1px solid var(--card-border-color, #dee2e6);
  border-radius: 0.75rem;
  padding: 1.5rem;
  background: var(--card-bg, #fff);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.product-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
}

.product-card h3 {
  margin-top: 0;
  font-size: 1.15rem;
}

.product-card .price {
  font-weight: 700;
  color: var(--link-color, #007bff);
  font-size: 1.1rem;
  margin-bottom: 0.5rem;
}

.product-card .description {
  font-size: 0.95rem;
  color: var(--text-muted-color, #6c757d);
  margin-bottom: 1rem;
  line-height: 1.5;
}

.cta-button {
  display: inline-block;
  padding: 0.5rem 1.25rem;
  background: var(--link-color, #007bff);
  color: #fff !important;
  border-radius: 0.4rem;
  text-decoration: none !important;
  font-weight: 600;
  font-size: 0.9rem;
  transition: opacity 0.2s;
}

.cta-button:hover {
  opacity: 0.85;
}

.products-intro {
  font-size: 1.05rem;
  line-height: 1.7;
  margin-bottom: 0.5rem;
}
</style>

<p class="products-intro">
Developer tools, cheatsheets, and starter kits built by <strong>TDSquad DevTools</strong> to help you ship faster and level up your engineering skills.
</p>

<div class="products-grid">

  <div class="product-card">
    <h3>🧪 Rx.NET Cheatsheet</h3>
    <div class="price">$9.99+</div>
    <div class="description">
      The essential quick-reference for Reactive Extensions in .NET. Covers operators, schedulers, error handling patterns, and real-world usage examples — all in a print-friendly format.
    </div>
    <a href="https://tdsquad.gumroad.com/l/gtscax" target="_blank" rel="noopener" class="cta-button">Get It Now →</a>
  </div>

  <div class="product-card">
    <h3>🚀 DevTools Pro Bundle</h3>
    <div class="price">$23</div>
    <div class="description">
      The complete developer productivity pack. Includes the Rx.NET Cheatsheet, .NET Productivity Kit, and Squad Config Templates — everything you need at a bundled discount.
    </div>
    <a href="https://tdsquad.gumroad.com/l/fonqxn" target="_blank" rel="noopener" class="cta-button">Get It Now →</a>
  </div>

  <div class="product-card">
    <h3>⚙️ Squad Config Templates</h3>
    <div class="price">$9</div>
    <div class="description">
      Production-ready configuration templates for CI/CD pipelines, Docker, Kubernetes, and cloud deployments. Stop writing boilerplate — start shipping.
    </div>
    <a href="https://tdsquad.gumroad.com/l/hocwhh" target="_blank" rel="noopener" class="cta-button">Get It Now →</a>
  </div>

  <div class="product-card">
    <h3>🛠️ .NET Productivity Kit</h3>
    <div class="price">$9</div>
    <div class="description">
      Curated collection of snippets, project templates, and workflow automations for .NET developers. Boost your daily productivity with battle-tested patterns.
    </div>
    <a href="https://tdsquad.gumroad.com/l/hzqbj" target="_blank" rel="noopener" class="cta-button">Get It Now →</a>
  </div>

  <div class="product-card">
    <h3>🤖 MCP Server Starter Kit</h3>
    <div class="price">$9</div>
    <div class="description">
      Everything you need to build and deploy your own MCP (Model Context Protocol) server. Includes boilerplate code, configuration guides, and deployment scripts.
    </div>
    <a href="https://tdsquad.gumroad.com/l/nlplel" target="_blank" rel="noopener" class="cta-button">Get It Now →</a>
  </div>

  <div class="product-card">
    <h3>⚡ Build Your AI Squad in 30 Minutes</h3>
    <div class="price">$12</div>
    <div class="description">
      Step-by-step guide to assembling a team of AI agents that work together. Learn multi-agent architecture, orchestration patterns, and practical implementation strategies.
    </div>
    <a href="https://tdsquad.gumroad.com/l/ekoljw" target="_blank" rel="noopener" class="cta-button">Get It Now →</a>
  </div>

  <div class="product-card">
    <h3>🧠 AI Agent Architecture Cheatsheet</h3>
    <div class="price">$9</div>
    <div class="description">
      Visual reference guide covering AI agent design patterns, tool-calling architectures, memory strategies, and multi-agent communication topologies.
    </div>
    <a href="https://tdsquad.gumroad.com/l/crxym" target="_blank" rel="noopener" class="cta-button">Get It Now →</a>
  </div>

</div>

<br>

<p style="text-align: center; margin-top: 1rem;">
  <a href="https://tdsquad.gumroad.com" target="_blank" rel="noopener" class="cta-button" style="padding: 0.75rem 2rem; font-size: 1rem;">
    Browse All Products on Gumroad →
  </a>
</p>
