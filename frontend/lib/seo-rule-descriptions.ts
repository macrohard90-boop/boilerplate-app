/**
 * Educational descriptions for all 29 SEO scoring rules.
 * Used by the Optimize page to explain each rule in plain English.
 */

export interface RuleDescription {
  /** What this rule checks — 1-2 sentences, no jargon */
  whatItChecks: string;
  /** Why it matters for SEO, in real terms */
  whyItMatters: string;
  /** What a "passing" state looks like — concrete criteria */
  passingLooks: string;
  /** For non-editable rules: where/how to fix it. Null for admin-editable rules. */
  howToFix: string | null;
}

export const RULE_DESCRIPTIONS: Record<string, RuleDescription> = {
  // ── Content (13 rules) ──────────────────────────────────────────────

  title_present: {
    whatItChecks:
      "Checks whether your page has a title tag. The title is the clickable blue headline that appears in Google search results — it is the first thing people see.",
    whyItMatters:
      "Without a title, search engines have to guess what your page is about, and the result in Google will show something ugly or irrelevant. People are much less likely to click on a result with no clear title.",
    passingLooks:
      "Your page has a non-empty <title> tag in the <head> section.",
    howToFix: null,
  },

  title_length: {
    whatItChecks:
      "Checks that your page title is between 30 and 60 characters long. You can see the exact character count next to the title input when editing.",
    whyItMatters:
      'Titles shorter than 30 characters waste valuable space in search results where you could be selling your page to searchers. Titles longer than 60 characters get cut off with "..." so visitors cannot read the full title.',
    passingLooks: "Title is between 30 and 60 characters.",
    howToFix: null,
  },

  desc_present: {
    whatItChecks:
      "Checks whether your page has a meta description. This is the 1-2 sentence summary that appears below the title in Google search results — your elevator pitch to searchers.",
    whyItMatters:
      "Without a meta description, Google will grab a random snippet from your page, which often looks bad and does not sell your content. A well-written description can significantly increase your click-through rate.",
    passingLooks: 'Your page has a non-empty <meta name="description"> tag.',
    howToFix: null,
  },

  desc_length: {
    whatItChecks:
      "Checks that your meta description is between 120 and 160 characters. You can see the exact character count next to the description input when editing.",
    whyItMatters:
      "Descriptions under 120 characters leave empty space in search results and miss the chance to persuade people to click. Descriptions over 160 characters get cut off mid-sentence, which looks unprofessional.",
    passingLooks: "Description is between 120 and 160 characters.",
    howToFix: null,
  },

  content_length: {
    whatItChecks:
      "Checks that the page has enough visible text content. Product pages need at least 300 characters, and other pages need at least 500 characters of body text.",
    whyItMatters:
      'Search engines need enough text to understand what a page is about. Pages with very little text (called "thin content") rank poorly because Google views them as not providing enough value to visitors.',
    passingLooks:
      "Product pages have 300+ characters of body text; other pages have 500+ characters.",
    howToFix:
      "Add more written content to the page. Edit the page component file (e.g., frontend/app/about/page.tsx) to include more descriptive text, paragraphs, or sections.",
  },

  images_alt_text: {
    whatItChecks:
      'Checks that every image on the page has an "alt" attribute — a short text description of what the image shows (e.g., alt="Red leather handbag on white background").',
    whyItMatters:
      'Alt text serves two purposes: screen readers read it aloud for visually impaired visitors (accessibility), and search engines use it to understand images since they cannot "see." Pages with missing alt text rank worse in image search and fail accessibility standards.',
    passingLooks: "All <img> tags on the page have non-empty alt attributes.",
    howToFix:
      'Add alt="..." to every <img> tag in your page component or template. Describe what the image shows in a few words.',
  },

  internal_links: {
    whatItChecks:
      "Checks that the page has at least 2 links pointing to other pages on your own site (e.g., links to /products, /about, /contact).",
    whyItMatters:
      'Internal links help search engines discover and crawl your other pages. They also spread "ranking power" (called link equity) across your site and help visitors navigate to related content, which reduces bounce rate.',
    passingLooks:
      "Page contains 2 or more links to other pages on the same domain.",
    howToFix:
      'Add links to related pages within your content or navigation. For example, add a "See our products" link or "Learn more about us" link in the page body.',
  },

  keyword_in_content: {
    whatItChecks:
      "Checks if your target keyword appears in at least 2 of these three key locations: the page title, the meta description, and the main heading (H1). You assign target keywords in the Discover tab.",
    whyItMatters:
      "When someone searches for a term, Google looks for it in key locations on your page. If your target keyword is not in the title, description, or main heading, Google is less confident your page is a good match for that search query.",
    passingLooks:
      "Target keyword found in 2+ of: title, description, H1. Auto-passes if no target keyword is assigned.",
    howToFix:
      "First, assign a target keyword in the Discover tab. Then edit your title and description (in the Meta editor) and your H1 heading (in the page component) to naturally include that keyword.",
  },

  readability_score: {
    whatItChecks:
      "Measures how easy your page content is to read, using the Flesch Reading Ease formula. This is a standard readability test used by schools and publishers. Scores range from 0 (very hard) to 100 (very easy).",
    whyItMatters:
      "Content that is hard to read drives visitors away quickly. Google tracks engagement signals like time-on-page and bounce rate. Simpler, clearer writing keeps people on your page longer, which indirectly helps rankings. Aim for 8th-9th grade reading level.",
    passingLooks:
      "Flesch Reading Ease score of 60 or higher (approximately 8th-9th grade reading level). Auto-passes if the page has less than 100 characters of body text.",
    howToFix:
      "Edit the page content to use shorter sentences, simpler words, and fewer multi-syllable words. Break long paragraphs into smaller ones. Use bullet points. Avoid jargon.",
  },

  keyword_density: {
    whatItChecks:
      'Measures how frequently your target keyword appears in the page content, expressed as a percentage. For example, if "leather shoes" appears 5 times in 500 words, that is a 1% density.',
    whyItMatters:
      'If your keyword appears too rarely (under 0.5%), Google may not associate the page with that term. If it appears too often (over 3%), Google may flag it as "keyword stuffing" — an old spam technique — and penalize your page.',
    passingLooks:
      "Target keyword density between 0.5% and 3.0%. Auto-passes if no target keyword is assigned or if page content is too short to measure.",
    howToFix:
      "If density is too low, naturally weave your target keyword into the content a few more times. If too high, replace some instances with synonyms or related terms.",
  },

  external_links_present: {
    whatItChecks:
      "Checks that your page has at least one link pointing to another website (an outbound link). For example, a link to a supplier, industry body, or authoritative source.",
    whyItMatters:
      "Linking to relevant, authoritative external sources signals that your content is well-researched and trustworthy. Pages that never link out can appear isolated or low-quality to search engines. It also helps visitors find related information.",
    passingLooks:
      "At least 1 outbound link to an external domain (e.g., https://example.com).",
    howToFix:
      "Add at least one link to a relevant external resource in your page content. For example, link to a technology you use, an industry association, or a cited source.",
  },

  title_h1_differentiated: {
    whatItChecks:
      "Checks that the page title tag (shown in Google results) and the H1 heading (shown on the actual page) are not identical text.",
    whyItMatters:
      'The title tag appears in search results while the H1 appears on the actual page. Having them slightly different lets you target more keyword variations. For example, the title could be "Buy Italian Leather Shoes Online" while the H1 says "Handcrafted Italian Leather Shoes."',
    passingLooks:
      'Title and H1 contain different text. The comparison ignores the site name suffix (e.g., " | My Site").',
    howToFix:
      "Edit either the page title (via the Meta editor in admin) or the H1 heading (in the page component file) so they are not identical. Keep both relevant to the page topic but use different wording.",
  },

  meta_desc_complete: {
    whatItChecks:
      "Checks that the meta description ends with proper punctuation — a period (.), exclamation mark (!), or question mark (?).",
    whyItMatters:
      "A description that ends mid-sentence looks like it was auto-generated or cut off accidentally. Complete, well-punctuated descriptions look professional and build trust in search results.",
    passingLooks: 'Description ends with ".", "!", "?", or "..."',
    howToFix:
      "Edit your meta description (via the Meta editor or inline editor) and make sure it ends with a period, exclamation mark, or question mark.",
  },

  // ── Technical (10 rules) ────────────────────────────────────────────

  canonical_set: {
    whatItChecks:
      'Checks whether a canonical URL is set for the page. A canonical URL is a special tag that tells search engines "this is the official version of this page."',
    whyItMatters:
      "Websites often have multiple URLs that show the same content (with/without www, with tracking parameters, HTTP vs HTTPS, etc.). Without a canonical tag, search engines may split your ranking power across these duplicate URLs, weakening all of them.",
    passingLooks: 'A <link rel="canonical"> tag is present in the page head.',
    howToFix: null,
  },

  canonical_self_ref: {
    whatItChecks:
      'Checks that the canonical URL points back to this page itself (called "self-referencing"), not to a different page.',
    whyItMatters:
      "If your canonical accidentally points to a different page, you are telling Google to ignore THIS page and rank the other one instead. This is a common misconfiguration that can silently remove pages from search results.",
    passingLooks: "The canonical URL path matches the current page path.",
    howToFix: null,
  },

  robots_indexable: {
    whatItChecks:
      'Checks that the page is not blocked from appearing in search results by a "noindex" robots directive. The robots tag tells search engines whether they are allowed to show this page.',
    whyItMatters:
      'If a page has "noindex" set, search engines will completely exclude it from search results. This is intentional for pages like login or cart, but accidental noindex on important pages means they are invisible to anyone searching.',
    passingLooks: 'The robots meta tag does not contain "noindex".',
    howToFix: null,
  },

  h1_present: {
    whatItChecks:
      "Checks that the page has a main heading — an H1 tag. This is the biggest, most prominent heading on the page, like a chapter title in a book.",
    whyItMatters:
      "The H1 is one of the strongest signals to search engines about the page topic. A page without an H1 is like a chapter without a title — search engines and visitors alike struggle to understand what the page is about.",
    passingLooks: "Page contains at least one <h1> tag.",
    howToFix:
      "Add an <h1> tag to your page component. Most pages should have exactly one H1 that clearly states what the page is about.",
  },

  heading_hierarchy: {
    whatItChecks:
      "Checks that headings follow a logical order: H1 first (main heading), then H2 (sub-headings), then H3 (sub-sub-headings) — without skipping levels (e.g., jumping from H1 straight to H3 without an H2).",
    whyItMatters:
      "A proper heading hierarchy acts like a table of contents for both screen readers and search engines. Skipped heading levels confuse the document structure and hurt accessibility scores. Google uses heading structure to understand page organization.",
    passingLooks:
      "Page has at least one H2, and no heading levels are skipped (e.g., H1 followed by H2 followed by H3, not H1 followed by H3).",
    howToFix:
      "Restructure your headings in the page component. Use H2 for main sections, H3 for sub-sections within those. Never skip from H1 to H3.",
  },

  url_quality: {
    whatItChecks:
      "Checks the page URL for common problems: excessive length (over 100 characters), underscores instead of hyphens, special characters, or double slashes.",
    whyItMatters:
      "Clean, readable URLs perform better in search. Messy URLs with special characters or random strings look untrustworthy to users and can cause crawling issues. Google officially recommends hyphens over underscores in URLs.",
    passingLooks:
      "URL is under 100 characters, uses hyphens (not underscores), no special characters, no double slashes.",
    howToFix:
      'Rename the page URL/slug. In Next.js, this means renaming the folder under app/ (e.g., rename "my_page" to "my-page"). Use short, descriptive, hyphenated paths.',
  },

  https_enforced: {
    whatItChecks:
      "Checks that the page canonical URL uses HTTPS (encrypted connection) rather than plain HTTP.",
    whyItMatters:
      'Google has explicitly stated that HTTPS is a ranking signal. Beyond SEO, browsers show "Not Secure" warnings on HTTP pages, which drives visitors away. HTTPS is essentially mandatory for any professional website.',
    passingLooks:
      'Canonical URL starts with "https://". This rule auto-passes in localhost development environments.',
    howToFix:
      "Configure HTTPS in your deployment. Set up SSL/TLS certificates in your reverse proxy (nginx). Ensure the FRONTEND_URL in .env uses https://.",
  },

  viewport_present: {
    whatItChecks:
      "Checks for a viewport meta tag, which tells mobile browsers how to scale and display the page.",
    whyItMatters:
      'Without a viewport tag, mobile browsers render the page at desktop width and then shrink it down — making text unreadable without zooming. Google uses "mobile-first indexing" which means it primarily uses the mobile version of your page for ranking. Missing the viewport tag is the most basic mobile failure.',
    passingLooks:
      'Page has a <meta name="viewport"> tag in the <head> section.',
    howToFix:
      'This is usually set in your root layout (frontend/app/layout.tsx). Next.js adds it automatically in most cases. If missing, add: <meta name="viewport" content="width=device-width, initial-scale=1">',
  },

  lang_attribute: {
    whatItChecks:
      'Checks that the HTML document declares its language — for example, <html lang="en"> for English.',
    whyItMatters:
      "The lang attribute helps search engines serve your page to the right audience (English speakers get English results, Spanish speakers get Spanish results). It also enables screen readers to use the correct pronunciation, which is an accessibility requirement.",
    passingLooks: 'The <html> element has a lang attribute (e.g., lang="en").',
    howToFix:
      'Add the lang attribute to the <html> tag in your root layout (frontend/app/layout.tsx). Example: <html lang="en">',
  },

  favicon_present: {
    whatItChecks:
      "Checks that the page has a favicon — the small icon that appears in the browser tab next to the page title, in bookmarks, and sometimes in search results.",
    whyItMatters:
      "Google sometimes shows favicons in mobile search results next to your page listing. A missing favicon makes your result look incomplete. In browser tabs, it helps users identify your site among many open tabs, which improves return visits.",
    passingLooks:
      'A <link rel="icon"> or <link rel="shortcut icon"> tag is present in the <head>.',
    howToFix:
      'Add a favicon file (favicon.ico or favicon.png) to the public/ directory and add a <link rel="icon" href="/favicon.ico"> tag in your root layout head.',
  },

  // ── Social (4 rules) ───────────────────────────────────────────────

  og_complete: {
    whatItChecks:
      "Checks that the page has the three essential Open Graph (OG) meta tags: og:title, og:description, and og:image. Open Graph is a standard created by Facebook that controls how your page looks when someone shares it on social media.",
    whyItMatters:
      "When someone shares a link to your page on Facebook, LinkedIn, Slack, iMessage, Discord, or many other platforms, these platforms read the OG tags to generate a rich preview card with an image, title, and description. Without them, the shared link looks like a bare URL or shows a random snippet, which gets far fewer clicks.",
    passingLooks:
      "All three tags present in the <head>: og:title, og:description, og:image.",
    howToFix:
      "OG tags are auto-generated by the backend. If they are missing, check the OG service in modules/seo/services/og_service.py. For custom values, add a meta override with the appropriate title and description.",
  },

  twitter_complete: {
    whatItChecks:
      "Checks for Twitter/X-specific card tags: twitter:card (the card format), twitter:title, and twitter:description. These control how the page appears when shared on Twitter/X.",
    whyItMatters:
      'Twitter/X can use Open Graph tags as a fallback, but dedicated Twitter Card tags give you more control over how your content appears in the Twitter feed. The twitter:card tag specifically controls the card format — "summary" shows a small thumbnail, "summary_large_image" shows a big image preview.',
    passingLooks:
      "All three tags present: twitter:card, twitter:title, twitter:description.",
    howToFix:
      "Twitter tags are auto-generated by the backend alongside OG tags. If missing, check modules/seo/services/og_service.py.",
  },

  og_image_custom: {
    whatItChecks:
      "Checks that the page uses a unique, page-specific image for social sharing — not the site-wide default fallback image that every page gets.",
    whyItMatters:
      "When every page on your site shares the same generic image, all your social shares look identical and unremarkable. A page-specific image (like the product photo, a team photo for the About page, or a custom graphic) dramatically increases click-through rates on social platforms.",
    passingLooks:
      "The og:image URL is different from the default OG image path (currently /images/og-default.png).",
    howToFix:
      "Create a unique image for this page and place it in the public/images/ directory. Then update the OG service or meta override to reference the page-specific image instead of the default.",
  },

  og_url_valid: {
    whatItChecks:
      "Checks that the og:image URL is structurally valid — it should start with http://, https://, or / (an absolute path).",
    whyItMatters:
      "A broken or malformed image URL means social platforms cannot load your preview image. The shared link will show a blank space or a broken image icon, which looks unprofessional and reduces engagement.",
    passingLooks: "og:image URL is a valid absolute URL or absolute path.",
    howToFix:
      "Fix the og:image URL in the OG service or meta override to use a valid path. Use an absolute URL (https://yoursite.com/images/page.jpg) or an absolute path (/images/page.jpg).",
  },

  // ── Performance (3 rules) ──────────────────────────────────────────

  structured_data: {
    whatItChecks:
      'Checks for page-specific structured data (also called Schema.org or JSON-LD). This is machine-readable metadata embedded in a <script type="application/ld+json"> tag that tells search engines exactly what kind of content is on the page — a product, a recipe, an article, a FAQ, etc.',
    whyItMatters:
      'Structured data enables "rich results" in Google — those enhanced listings with star ratings, prices, availability badges, recipe cooking times, FAQ accordions, and more. Pages with rich results get significantly higher click-through rates because they stand out visually in search results. Without structured data, you only get the basic blue-link listing.',
    passingLooks:
      "Page has at least one JSON-LD block with a specific type beyond the generic Organization and WebSite schemas (e.g., Product, BreadcrumbList, Article, FAQPage, AboutPage).",
    howToFix:
      'Add a JSON-LD structured data block to the page. For the About page, add an "AboutPage" type. For products, a "Product" type is auto-generated. Edit the page component or meta_service.py to include page-specific schema.',
  },

  schema_complete: {
    whatItChecks:
      'Checks that your structured data includes all the required fields for its type. For example, a Product schema needs "name" and "offers" (with price and currency), and a BreadcrumbList needs "itemListElement".',
    whyItMatters:
      "Incomplete structured data will not generate rich results. Google validates these schemas and will simply ignore structured data that is missing required fields — wasting the effort of adding it in the first place.",
    passingLooks:
      "All structured data schemas have their required fields populated. For Product: name, offers, priceCurrency, price. For BreadcrumbList: itemListElement.",
    howToFix:
      "Review your JSON-LD blocks and add any missing required fields. Use Google's Rich Results Test (search.google.com/test/rich-results) to validate your structured data.",
  },

  img_dimensions: {
    whatItChecks:
      'Checks that images in the HTML have explicit width and height attributes (e.g., <img width="800" height="600">), not just CSS-based sizing.',
    whyItMatters:
      "When images lack width/height attributes, the browser does not know how much space to reserve for them while loading. As images load, the page jumps around — a problem called Cumulative Layout Shift (CLS). CLS is one of Google's Core Web Vitals and is used as a ranking signal. High CLS means a worse user experience and lower rankings.",
    passingLooks:
      "80% or more of images on the page have explicit width and height attributes.",
    howToFix:
      "Add width and height attributes to <img> tags in your page components. In Next.js, using the <Image> component from next/image automatically handles this.",
  },
};
