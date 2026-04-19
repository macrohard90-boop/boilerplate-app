/**
 * Educational descriptions for all 15 GEO scoring rules.
 * Displayed in the GEO dashboard when a user clicks the (?) info button.
 */

export interface GEORuleDescription {
  whatItChecks: string;
  whyItMatters: string;
  passingLooks: string;
  howToFix: string;
}

export const GEO_RULE_DESCRIPTIONS: Record<string, GEORuleDescription> = {
  // ── Extractability ──────────────────────────────────────────

  direct_answer_opening: {
    whatItChecks:
      "Whether your opening paragraph directly answers the page's topic in 60 words or fewer, without filler phrases like 'Welcome to...' or 'In this article...'.",
    whyItMatters:
      "AI engines (ChatGPT, Perplexity, Google AI Overviews) extract and cite content that front-loads the answer. Pages that start with a direct statement get cited 67% more often than those with generic intros.",
    passingLooks:
      "First paragraph is 60 words or fewer and starts with a direct factual statement. Example: 'SEO (Search Engine Optimization) is the practice of improving a website to increase its visibility in search engine results.' Not: 'Welcome to our comprehensive guide about SEO.'",
    howToFix:
      "Rewrite your opening paragraph to directly answer the page's main topic. Remove filler phrases. Lead with the definition, answer, or key point. Keep it under 60 words.",
  },

  h2_question_format: {
    whatItChecks:
      "Whether at least 50% of your H2 headings are phrased as questions (e.g., 'What is SEO?' instead of 'SEO Overview').",
    whyItMatters:
      "AI engines map user queries to content sections. When your H2 headings match how people ask questions, AI systems can directly extract and cite that section as an answer. Question-format headings align with natural language queries.",
    passingLooks:
      "At least half of H2 headings start with question words (What, How, Why, When, Where, Which, Can, Does, Is) or contain a question mark.",
    howToFix:
      "Rephrase your H2 headings as questions that match how users search. Change 'Pricing Overview' to 'How much does it cost?', 'Features' to 'What features are included?', 'Getting Started' to 'How do I get started?'.",
  },

  sections_self_contained: {
    whatItChecks:
      "Whether at least 60% of your H2 sections provide a direct answer within the first 1-2 sentences after the heading — readable without needing context from earlier in the page.",
    whyItMatters:
      "AI engines extract individual sections, not full pages. Each section must make sense on its own. If a section starts with 'As mentioned above...' or requires the reader to have read previous sections, AI engines skip it.",
    passingLooks:
      "Each H2 section's first 1-2 sentences directly address the heading's topic with at least 10 words of substantive content.",
    howToFix:
      "Ensure each H2 section begins with a direct answer to the heading's question. Avoid references to other sections. Treat each section as a standalone mini-article that an AI engine could quote independently.",
  },

  // ── Fact Density ────────────────────────────────────────────

  stat_density: {
    whatItChecks:
      "Whether your content includes at least 1 statistic or data point per 200 words. Detected patterns include percentages (42%), dollar amounts ($1,000), multipliers (3x, 4-fold), and comparative figures (increased by 30%).",
    whyItMatters:
      "AI engines strongly prefer content with verifiable, concrete data. Including unique statistics increases AI visibility by up to 30%. Content with data points is synthesized into AI-generated answers far more often than narrative-only content.",
    passingLooks:
      "An 800-word article has at least 4 statistics or data points, each linked to a credible source.",
    howToFix:
      "Add concrete numbers throughout your content. Replace vague claims ('significantly improved') with specific data ('improved by 42%'). Link statistics to their original sources. Include comparison data, percentages, and measurements.",
  },

  data_tables_present: {
    whatItChecks:
      "Whether the page contains at least one HTML data table with header cells (<th> elements).",
    whyItMatters:
      "Original data tables earn 4.1x more AI citations than narrative-only content. Tables present structured, scannable data that AI engines can easily parse and reference in their answers. They signal data authority.",
    passingLooks:
      "At least one <table> element with <th> header cells containing structured data (comparisons, pricing, specifications, timelines, etc.).",
    howToFix:
      "Add a comparison table, specifications table, pricing breakdown, or feature matrix relevant to your page's topic. Use proper HTML table markup with <th> header cells so AI engines can parse the structure.",
  },

  source_citations: {
    whatItChecks:
      "Whether at least 50% of your outbound links point to authoritative domains — .edu, .gov, .org, Wikipedia, academic journals (Nature, PubMed, arXiv), and recognized research institutions.",
    whyItMatters:
      "AI engines assess content trustworthiness by checking what sources it references. Pages that link to credible, authoritative sources are weighted higher in AI-generated answers. It signals that your claims are backed by verified research.",
    passingLooks:
      "More than half of outbound links go to educational institutions, government sites, Wikipedia, or peer-reviewed journals.",
    howToFix:
      "When making claims, link to the original research source rather than secondary blog posts. Prefer .edu, .gov, Wikipedia, and academic publisher links. Replace links to commercial blogs with links to the underlying studies they reference.",
  },

  // ── Authority ───────────────────────────────────────────────

  authority_outbound_links: {
    whatItChecks:
      "Whether the page has at least 3 outbound links to authority domains (.edu, .gov, .org, Wikipedia, academic publishers, recognized research organizations).",
    whyItMatters:
      "AI engines cite pages that reference credible sources 40% more often. Having multiple authority links establishes your content as well-researched and trustworthy. Wikipedia alone appears in 47.9% of top ChatGPT sources.",
    passingLooks:
      "3 or more unique outbound links to .edu, .gov, Wikipedia, or academic/institutional domains.",
    howToFix:
      "Add references to authoritative sources that support your content. Link to relevant Wikipedia articles, government data sources, university research, or peer-reviewed publications. Aim for 5-8 authority links per article.",
  },

  expert_quotes: {
    whatItChecks:
      "Whether the page contains expert quotations — either HTML <blockquote> elements or text patterns like 'According to [Name]...', 'says [Name]', 'noted [Name]'.",
    whyItMatters:
      "Expert quotations with attribution boost AI citation likelihood by up to 41%. Named, credentialed sources signal expertise and trustworthiness (E-E-A-T), which AI engines use to assess content reliability.",
    passingLooks:
      "At least one direct quote attributed to a named expert, either in a <blockquote> element or with an attribution phrase.",
    howToFix:
      "Add expert commentary to your content. Include direct quotes from industry experts, researchers, or practitioners with their name and credentials. Use <blockquote> tags or attribution phrases like 'According to Dr. Smith, a professor at MIT...'.",
  },

  content_depth: {
    whatItChecks:
      "Whether the page has enough content depth — at least 800 words for standard pages or 300 words for product/shop pages.",
    whyItMatters:
      "AI engines prefer substantial, in-depth content that comprehensively covers a topic. Thin pages are rarely cited because they lack the detail needed for AI synthesis. Depth signals authority on the subject.",
    passingLooks:
      "Standard pages have 800+ words of body text. Product pages have 300+ words.",
    howToFix:
      "Expand your content with more details, examples, data points, and explanations. Add sections covering related subtopics, use cases, comparisons, or frequently asked questions.",
  },

  // ── Freshness ───────────────────────────────────────────────

  date_modified_present: {
    whatItChecks:
      "Whether the page's Article or BlogPosting schema markup includes a dateModified field.",
    whyItMatters:
      "50% of content cited by AI engines is less than 13 weeks old. AI systems use dateModified to determine content freshness. Without this signal, your content appears undated and is less likely to be cited for current information.",
    passingLooks:
      "Article or BlogPosting JSON-LD schema includes a dateModified field in ISO 8601 format.",
    howToFix:
      "Add Article or BlogPosting schema to your page with a dateModified field. Update this field whenever you make meaningful content changes. Example: 'dateModified': '2026-04-15T10:00:00Z'.",
  },

  content_recency: {
    whatItChecks:
      "Whether the content was updated within the last 90 days, based on dateModified in schema markup or the last meta override update in the admin.",
    whyItMatters:
      "Content updated within 30 days gets 3.2x more AI citations. Pages not refreshed quarterly are 3x more likely to lose existing citations. AI engines actively prefer recently verified information.",
    passingLooks:
      "dateModified or last admin update is within the past 90 days.",
    howToFix:
      "Review and update your content at least quarterly. Refresh statistics with current data, update examples, verify links still work, and bump the dateModified field. Even minor factual additions help maintain freshness signals.",
  },

  no_stale_references: {
    whatItChecks:
      "Whether the body text contains year references more than 2 years old (e.g., 'in 2023' appearing in 2026 content) without historical context.",
    whyItMatters:
      "Stale year references signal outdated content to AI engines. If your page says 'in 2023' without framing it historically, AI systems may skip citing it for current information, even if the underlying advice is still valid.",
    passingLooks:
      "No standalone references to years more than 2 years in the past, or such references are framed with historical context (e.g., 'historically', 'since 2023', 'as of').",
    howToFix:
      "Search your content for old year references. Update them with current data, remove them, or add context (e.g., change 'In 2023, 42% of...' to 'As of 2026, approximately 55% of...'). Keep examples and case studies current.",
  },

  // ── Structural Metadata ─────────────────────────────────────

  faq_schema: {
    whatItChecks:
      "Whether the page has FAQPage schema markup (JSON-LD) with at least 2 questions and answers.",
    whyItMatters:
      "FAQPage schema directly maps to how users query AI engines. Pages with FAQ schema see 28% more AI citations. It tells AI systems exactly what questions your page answers, making extraction trivial.",
    passingLooks:
      "JSON-LD FAQPage with 2+ mainEntity items, each containing a Question with an acceptedAnswer.",
    howToFix:
      "Add FAQPage JSON-LD schema to your page. Identify the 3-5 most common questions about your topic and add them as structured FAQ data. Each question needs an acceptedAnswer with a substantive text response.",
  },

  article_schema_complete: {
    whatItChecks:
      "Whether the page has Article or BlogPosting schema with all three required fields: author, datePublished, and dateModified.",
    whyItMatters:
      "Complete Article schema helps AI engines attribute content to a specific author and verify when it was created and last updated. This builds E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) signals that AI systems use for source selection.",
    passingLooks:
      "Article or BlogPosting JSON-LD with author (name), datePublished (ISO date), and dateModified (ISO date) all present.",
    howToFix:
      "Add or complete your Article/BlogPosting schema. Include: author with name and credentials, datePublished when first created, dateModified when last updated. All dates should be ISO 8601 format.",
  },

  schema_stack_depth: {
    whatItChecks:
      "Whether the page has 2 or more distinct schema types from: FAQPage, Article/BlogPosting, HowTo, BreadcrumbList, ItemList.",
    whyItMatters:
      "Pages with a 'schema stack' (multiple schema types) receive 1.8x more AI citations than pages with just one schema type. Multiple schema types give AI engines richer structured data to work with and more entry points for citation.",
    passingLooks:
      "At least 2 distinct schema types present. Common winning combinations: Article + FAQPage, Article + BreadcrumbList + FAQPage, or Article + HowTo.",
    howToFix:
      "Add a second schema type to complement your existing markup. If you have Article schema, add FAQPage with common questions. If you have BreadcrumbList, add Article schema. The more schema types that accurately describe your content, the better.",
  },
};

/** GEO dimension display configuration. */
export const GEO_DIMENSIONS: Record<
  string,
  { label: string; color: string; bgColor: string; description: string }
> = {
  extractability: {
    label: "Extractability",
    color: "text-accent-purple",
    bgColor: "bg-accent-purple/20",
    description:
      "How easily AI engines can extract citable sentences from your content",
  },
  fact_density: {
    label: "Fact Density",
    color: "text-accent-blue",
    bgColor: "bg-accent-blue/20",
    description: "Statistical and data richness for AI synthesis",
  },
  authority: {
    label: "Authority",
    color: "text-accent-green",
    bgColor: "bg-accent-green/20",
    description: "Outbound citations to credible sources and expert quotations",
  },
  freshness: {
    label: "Freshness",
    color: "text-amber-400",
    bgColor: "bg-amber-400/20",
    description:
      "Content recency signals — AI engines strongly prefer recent content",
  },
  metadata: {
    label: "Metadata",
    color: "text-accent-pink",
    bgColor: "bg-accent-pink/20",
    description: "Structured data stack depth (FAQ, Article, HowTo, etc.)",
  },
};
