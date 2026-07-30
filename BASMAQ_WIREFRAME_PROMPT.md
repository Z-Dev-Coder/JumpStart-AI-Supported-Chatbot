# Page-by-Page Basmaq / Balsamiq Prompts for JumpStart

Use this document when you want detailed wireframes that match the implemented frontend UI.

How to use:

1. Copy the **Common UI Rules**.
2. Copy one page prompt.
3. Paste both into Basmaq/Balsamiq.
4. Generate that one page only.
5. Repeat for the next necessary page.

Do not paste all page prompts at once.

## Common UI Rules

Paste this before every page prompt.

```text
Create a colored low-fidelity Balsamiq wireframe for the implemented JumpStart frontend. Do not redesign. Do not create a user-flow diagram. The output must be a screen wireframe that matches the current Django/Tailwind UI.

Use Balsamiq controls: Browser Window, rectangles, labels, buttons, text inputs, dropdowns, tabs, data grids, cards, modals, drawers, accordions, icon placeholders, chat bubbles, badges, skeleton blocks, chart placeholders, and callout notes.

Match these frontend sources: base.html, store/home.html, store/products.html, store/account.html, chat/chat_panel.html, staff/dashboard.html, admin_panel/dashboard.html, partials/auth_modal.html, partials/product_grid.html, partials/product_detail_modal.html, partials/categories.html, partials/category_filters.html.

Style must match JumpStart:
- Inter-style body text and Poppins-style headings.
- Orange #FF6B35 for primary CTAs, active nav states, category accents, customer chat bubbles, chatbot launcher, and orange badges.
- Navy #1A2B4A for hero/footer/staff/admin headers and staff chat bubbles.
- Gold #FFD700 for rating stars.
- Light gray page background, white cards, pale gray borders.
- Dark mode examples can use gray-950 page, gray-900 cards, gray-800 controls.
- Rounded-lg icon buttons, rounded-xl inputs/buttons, rounded-2xl cards/modals/drawers/chat panels.
- Soft card shadows and stronger modal/drawer shadows.
- Use green/amber/red/blue/gray status badges.

Keep the same frontend layout, header order, nav labels, spacing, panel structure, modal placement, drawer placement, and dashboard density. Do not invent pages, nav items, or visual style.
```

## Prompt 1 - Customer Home Page

```text
Create one detailed Balsamiq wireframe for the JumpStart Customer Home Page, matching store/home.html and base.html.

Layout:
- Browser window frame with sticky header at top.
- Header: JS orange square logo, JumpStart wordmark with orange "Start", desktop nav Home, Products, Electronics, Fashion, right controls Search, Dark Mode, Cart with count badge, Account, mobile menu icon.
- Include small callouts or tiny insets for search overlay, guest account dropdown, logged-in account dropdown, and mobile nav.
- Hero: full-width deep navy section, about 90vh feel, orange/gold accent shapes, right-side product image placeholder with dark navy overlay.
- Hero content left: New Season Arrivals pill, headline "Shop Smart, Live Better" with "Live Better" in orange, support text, Shop Now button, Chat with Support secondary button, stats row 50K+ Happy Customers, 2000+ Products, 4.8 Avg Rating, scroll indicator.
- Featured Categories: white section, eyebrow "Browse by Category", heading "What are you looking for?", All products link, six rounded category tiles with icon boxes. Add note "HTMX-loaded categories".
- Trending Products: gray-50 section, "Hot Right Now", "Trending Products", View all link, horizontal carousel of rounded product cards with skeleton state note.
- Promotion banner: orange gradient rounded-3xl panel, "Limited Time Offer", "Up to 40% OFF", Claim Offer, product image placeholder.
- New Arrivals carousel.
- Trust badges row: Free Delivery, Easy Returns, Secure Payment, 24/7 AI Support.
- Why JumpStart navy section: The JumpStart Difference, cards for AI-Powered Support, Human Handover, Instant Resolution.
- Footer: navy footer with brand summary, Shop, Support, Company columns.
- Bottom-right orange chatbot launcher.

Callouts:
- Shop Now opens /products/.
- Chat with Support opens chatbot.
- Product cards open product detail modal.
- Add to cart requires sign-in if guest.
```

## Prompt 2 - Products Listing Page

```text
Create one detailed Balsamiq wireframe for the JumpStart Products Listing Page, matching store/products.html, product_grid.html, categories.html, and category_filters.html.

Layout:
- Use the shared JumpStart header and footer.
- Page background is gray-50.
- Top page header band is white with title "All Products" and product count text like "12 products found" or "Browse our collection".
- Right side controls: mobile Filters button, Sort dropdown, grid/list segmented toggle.
- Active filter chips row under title with category chip, search chip, price chip, and Clear all.
- Main content is max-width container with two columns.

Left filter sidebar:
- Width about 260px, sticky card, title Filters, Reset link.
- Category section loaded through HTMX. Include All Categories and category buttons with icons.
- Price Range section with Min input, Max input, quick chips Under $50, $50-100, $100-250, Over $250.
- Min Rating radio buttons with gold stars and "& up".
- In Stock Only checkbox.
- Featured Only checkbox.

Product results:
- Main state is grid: 3 columns desktop, white rounded-2xl product cards.
- Each product card has large image area, badge area for discount/popular/top rated/featured/out of stock, wishlist heart on hover, quick view overlay on hover, category label in orange, product name, rating stars, review count, price/original price, Add button, optional low-stock warning.
- Include a small inset showing list view: image left, description, rating, in-stock badge, price and Add to Cart right.
- Include loading skeleton cards, "Loading products..." indicator, no-products empty state, and pagination.

Mobile inset:
- Single-column product cards.
- Filters button opens stacked filter panel.

Callouts:
- Product grid is HTMX-loaded.
- Filters update results.
- Product card opens product detail modal.
- Add opens login modal if guest.
```

## Prompt 3 - Product Detail Modal

```text
Create one detailed Balsamiq wireframe for the JumpStart Product Detail Modal, matching partials/product_detail_modal.html.

Layout:
- Show dark translucent page overlay.
- Center rounded-2xl modal, max width about 3xl, scrollable, strong shadow.
- Top image gallery area with 4:3 main product image placeholder.
- Thumbnail strip below image when multiple images exist; active thumbnail has orange ring.
- Details area below/next to image depending on available space.
- Badge row: orange category badge, Featured badge, In Stock badge or Out of Stock red badge.
- Product name as bold Poppins heading.
- Rating row with gold stars, numeric rating, review count.
- Price row: large orange current price, original price strikethrough, Save percent badge.
- Description paragraph.
- Quantity selector: Qty label, minus button, quantity number, plus button.
- Sticky/bottom CTA area: Add to Cart full-width orange button with cart icon, Save to Wishlist secondary button with heart icon.

States to show as small insets:
- Loading skeleton state before HTMX content loads.
- Product not found state with alert icon and "Product not found."
- Out-of-stock state with disabled Add to Cart.

Callouts:
- HTMX-loaded modal content.
- Add to cart requires sign-in if guest.
- Successful add stores cart in localStorage and closes modal.
```

## Prompt 4 - Cart Drawer

```text
Create one detailed Balsamiq wireframe for the JumpStart Cart Drawer, matching base.html.

Layout:
- Fullscreen dim overlay with backdrop blur.
- Drawer slides in from right, max width about 384px, full height, white or gray-900 dark surface.
- Header row: "Shopping Cart" title, close icon button.
- Empty state: centered shopping cart icon, "Your cart is empty".
- Filled state: vertical cart item rows with thumbnail, product name, unit price, quantity stepper minus/plus, quantity number, remove/trash icon.
- Footer fixed at bottom with Total label, orange total amount, orange Checkout button with credit-card icon, note "Demo mode - no real payment processed".
- Mobile: drawer becomes nearly full width.

Callouts:
- Cart stored in localStorage.
- Quantity controls update totals.
- Remove icon deletes item.
- Checkout is demo mode.
```

## Prompt 5 - Sign In Modal

```text
Create one detailed Balsamiq wireframe for the JumpStart Sign In Modal, matching the login state in partials/auth_modal.html.

Layout:
- Dim overlay with centered rounded-2xl modal, max width about 448px.
- Modal header: JS mini logo, JumpStart text, title "Welcome back", close icon.
- Two tabs across modal: Sign In and Create Account.
- Sign In tab is active with orange underline and orange text.
- Title "Welcome back".
- Username input.
- Password input with eye/eye-off show-hide icon.
- Full-width orange Sign In button.
- Loading state text "Signing in..." with spinner.
- Error alert red rounded box.
- Link text "Don't have an account? Sign up".

Protected action inset:
- Guest tries Add to Cart, Open Chatbot, Account, Staff Dashboard, or Admin Panel.
- Show warning toast "Please sign in to continue" and this Sign In modal opening.

Callouts:
- Successful sign-in stores JWT tokens and user profile in localStorage.
- Staff role redirects to /staff/.
- Admin role redirects to /admin-panel/.
- Customer stays in storefront/account flow.
```

## Prompt 6 - Register Modal

```text
Create one detailed Balsamiq wireframe for the JumpStart Register Modal, matching the create-account state in partials/auth_modal.html.

Layout:
- Dim overlay with centered rounded-2xl modal, max width about 448px.
- Modal header: JS mini logo, JumpStart text, title "Create your account", close icon.
- Two tabs across modal: Sign In and Create Account.
- Create Account tab is active with orange underline and orange text.

- Title "Create your account".
- First name and Last name side-by-side.
- Username input.
- Email input.
- Password input with show-hide.
- Confirm password input.
- Full-width orange Create Account button.
- Loading state "Creating account...".
- Error alert red rounded box.
- Link text "Already have an account? Sign in".

Validation/error inset:
- Password mismatch message "Passwords do not match."
- Registration failed error area.

Callouts:
- Successful registration stores JWT tokens and user profile in localStorage.
- Register response includes user object.
- Link to Sign In switches back to the login tab.
```

## Prompt 7 - Customer Account Dashboard

```text
Create one detailed Balsamiq wireframe for the JumpStart Customer Account page, matching store/account.html.

Layout:
- Use shared JumpStart header and footer.
- Page background gray-50, content max width about 5xl, top padding.
- Account header row: orange rounded-2xl avatar initials, customer name, email.
- Main layout: 4-column grid. Left sidebar nav card takes 1 column; content card takes 3 columns.
- Sidebar buttons: Orders active, Profile, Support History, Sign Out in red.

Orders tab:
- Card title "My Orders".
- Status filter dropdown: All Orders, Processing, Dispatched, Delivered, Return Requested.
- Loading skeleton order cards.
- Empty state with package-open icon, "No orders yet", "Start shopping to see your orders here.", Shop Now button.
- Order card: gray header row with Order ID, placed date, status badge, total.
- Item rows: thumbnail, product name, quantity, price.
- Action row: Track Order, Return if eligible, Cancel if eligible.

Profile tab inset:
- Title "Profile Details".
- Inputs: First Name, Last Name, Username readonly, Email, Phone.
- Orange Save Changes button, Saving state, green Saved confirmation.

Support History tab inset:
- Title "Support History".
- Session rows with state badges AI_ACTIVE, WAITING_FOR_STAFF, HUMAN_ACTIVE, RESOLVED.
- Date, last message preview, View button.

Callouts:
- Return pre-fills chatbot with "I'd like to return my order #...".
- View opens chatbot panel.
- Account requires authentication.
```

## Prompt 8 - Customer Chatbot UI

```text
Create one detailed Balsamiq wireframe for the JumpStart Customer Chatbot UI, matching chat/chat_panel.html.

Closed launcher:
- Fixed bottom-right, 56px rounded-2xl orange gradient button.
- White robot/JS icon, unread red badge, tooltip "AI Support Chat".
- Hover note: button scales slightly.

Open chatbot panel:
- Fixed bottom-right panel, about 384px wide and 480px tall, rounded-2xl, white/dark surface, border and strong shadow.
- Header: navy background, JS orange avatar, status dot, title "JumpStart Support", status text "JS Support - Usually instant", minimize and close icon buttons.
- Welcome state: bot icon, "Hi there!", "I'm JumpStart's JS Support. How can I help you today?", quick reply chips Track my order, Return a product, Talk to a human.
- Message list: customer messages right aligned in orange bubbles, AI messages left aligned in white/gray bubbles with JS avatar, staff messages left aligned in navy bubbles with staff avatar/name, system messages centered with divider lines.
- Message status/time row under customer messages.
- Typing indicator with three bouncing dots.
- AI_ACTIVE footer: Talk to a Human Agent action row, textarea "Type a message...", orange send button.

States as insets:
- Loading skeleton messages.
- WAITING_FOR_STAFF: header status "Waiting for agent...", amber dot, Connecting to Human Support card, average wait 2-3 minutes, input hidden/disabled, footer "Chat will resume when an agent joins".
- HUMAN_ACTIVE: staff bubbles and customer input enabled.
- RESOLVED: feedback card "How was your support experience?", Helpful, Not helpful, negative reason choices Incorrect answer, Unclear response, Problem not resolved, Human was not helpful, Other, Skip, thank-you state, Start new chat.
- Mobile: near full-screen panel with safe margins.

Callouts:
- WebSocket live updates; polling fallback.
- Guest opening chatbot triggers login modal.
- Resolved sessions trigger feedback prompt.
```

## Prompt 9 - Staff Support Dashboard

```text
Create one detailed Balsamiq wireframe for the JumpStart Staff Support Dashboard, matching staff/dashboard.html.

Layout:
- Full-height app below header: height calc(100vh - 64px), gray-50 background.
- Three-column operations layout.

Column 1 - Support Queue:
- Width about 320px, white/dark panel, right border.
- Header "Support Queue" with live/offline WebSocket dot.
- Segmented tabs: Waiting with red count, Active with orange count, Resolved.
- Loading skeleton case cards.
- Empty state "No cases waiting".
- Waiting case card: customer name, customer goal/handover reason, wait time badge, sentiment dot/label, AI confidence badge, intent badge, orange Accept Case button.
- Active/resolved cards show state badges.

Column 2 - Chat Workspace:
- No selected case state: orange inbox icon, "Select a Case", "Choose a case from the queue to start helping."
- Selected case header: customer avatar initial, customer name, Case # and session state, Return to AI button, Resolve button.
- Transcript: customer orange right bubble, AI white/gray left bubble with AI avatar, staff navy left bubble with agent name, system divider, internal note amber centered note.
- Show realistic sample chat history in the selected case:
  - System divider: "Customer requested human support."
  - Customer bubble: "Hi, I want to return my wireless headphones. The order number is JS-1048."
  - AI bubble: "I can help with returns. I found your order, but I need a support agent to confirm eligibility."
  - System divider: "AI routed this case to staff because confidence was low."
  - Internal note amber bubble: "Customer may be frustrated. AI confidence 58%. Check return window before replying."
  - Staff bubble from "Maya - Support Agent": "Hi Alex, I can help with that. I found order JS-1048 and I am checking the return policy now."
  - Customer bubble: "Thanks. The item was delivered yesterday and the box is unopened."
  - Staff bubble from "Maya - Support Agent": "Great, that should be eligible. I can start the return request for you."
- Composer: Reply/Internal Note toggle, textarea, orange send button. Internal Note mode has amber styling and placeholder "not visible to customer".

Column 3 - Handover Package:
- Width about 320px, left border.
- Header "Handover Package".
- Empty state when no case selected.
- Customer info: name, email, priority.
- Use sample customer info: Alex Carter, alex.carter@example.com, priority Medium.
- AI Confidence: progress bar, percent badge, High/Medium/Low label.
- Use sample confidence: 58%, LOW - AI struggled to answer.
- Accordions: AI Summary, Detected Intents, Entities Detected, Tools Used, RAG Sources.
- Customer Goal, Handover Reason badge, AI Suggested Action blue panel.
- Use sample handover package values:
  - Customer Goal: Return unopened wireless headphones from order JS-1048.
  - Handover Reason: Low AI Confidence.
  - Detected Intents: return_request, order_lookup.
  - Entities: order_number JS-1048, product wireless headphones.
  - Tools Used: lookup_order, check_return_eligibility.
  - RAG Sources: Returns Policy v3, Warranty FAQ.
  - AI Suggested Action: Confirm delivery date, verify unopened condition, then create return request.

Modal insets:
- Resolve Case confirmation.
- Return to AI confirmation.

Callouts:
- Accept Case moves WAITING_FOR_STAFF to HUMAN_ACTIVE.
- Resolve triggers customer feedback.
- Return to AI sends session back to AI_ACTIVE.
- Internal notes are staff-only.
```

## Prompt 10 - Admin Overview Dashboard

```text
Create one detailed Balsamiq wireframe for the JumpStart Admin Overview page, matching admin_panel/dashboard.html.

Layout:
- Full-height admin shell below header.
- Left sidebar width about 224px, white/dark surface, border-right.
- Sidebar logo: JS orange square and "Admin Panel".
- Sidebar nav items: Overview active, AI Performance, Knowledge Base, Feedback, Cases & Handovers, Audit Log, Sign Out in red.
- Main content scroll area with padding.

Overview content:
- Title "Overview".
- Subtitle "System health and key performance metrics."
- Loading skeleton row of six rounded KPI cards.
- KPI grid: 2 columns medium, 3 columns desktop.
- KPI cards: Total Chats Today, AI Resolution Rate, Avg AI Confidence, Handover Rate, Active Staff, Resolved Today.
- Each KPI card has colored icon square, trend badge, large value, small label.
- Charts row: Handover Rate (7d) line chart placeholder and Sentiment Breakdown donut chart with legend Positive, Neutral, Negative.

Callouts:
- Admin dashboard is dense and analytical, not marketing style.
- Metrics load from admin/staff overview API.
```

## Prompt 11 - Admin AI Performance Page

```text
Create one detailed Balsamiq wireframe for the JumpStart Admin AI Performance page, matching admin_panel/dashboard.html.

Use the same admin shell and left sidebar, with AI Performance active.

Content:
- Page title "AI Performance".
- Subtitle "LLM confidence, intent accuracy, and RAG retrieval metrics."
- Four gauge metric cards in a row/grid: Recall@5, Precision@5, Faithfulness, Answer Relevancy.
- Each gauge card has circular progress indicator, percent value, label, short description.
- Confidence Trend (7d) chart card.
- Per-Intent Breakdown table with columns Intent, Sessions, Avg Confidence, Handover Rate, Avg Turns.
- Example intent rows: order_status, return_request, product_inquiry, complaint.
- Confidence badges use green for high, amber for medium, red for low.

Callouts:
- Confidence is deterministic and system-calculated, not self-reported by the LLM.
- Metrics relate to RAG retrieval and response quality.
```

## Prompt 12 - Admin Knowledge Base Page

```text
Create one detailed Balsamiq wireframe for the JumpStart Admin Knowledge Base page, matching admin_panel/dashboard.html.

Use the same admin shell and left sidebar, with Knowledge Base active.

Content:
- Header row: title "Knowledge Base", subtitle "Upload and manage documents for RAG retrieval.", orange Upload Document button.
- Upload progress card inset: file icon, filename, percent, orange progress bar.
- Drag-and-drop upload zone with cloud-upload icon, "Drop files here or browse", "PDF, DOCX, TXT, CSV - max 10MB".
- Documents table in a rounded card.
- Table columns: Title, Topic, Status, Usage, Actions.
- Document rows: title and upload date, topic badge, status badge pending/approved/disabled/rejected, usage count.
- Actions: preview eye icon, Approve button for pending, Disable button for approved, Re-enable button for disabled.
- Loading skeleton rows.
- Document Preview Modal inset: dim overlay, rounded-2xl modal, title, close icon, scrollable monospace extracted text area.

Callouts:
- Approved docs feed RAG retrieval.
- Disabled docs are excluded from retrieval.
- Upload triggers embedding generation.
```

## Prompt 13 - Admin Feedback and Quality Page

```text
Create one detailed Balsamiq wireframe for the JumpStart Admin Feedback & Quality page, matching admin_panel/dashboard.html.

Use the same admin shell and left sidebar, with Feedback active.

Content:
- Page title "Feedback & Quality".
- Subtitle "Customer satisfaction and AI response quality review."
- Summary cards: Helpful percentage, Not Helpful percentage, Total Reviews.
- Card titled "Flagged for Review" with red unreviewed count badge.
- Negative feedback rows: rating/reason, session/customer context, submitted date, reviewed state, Mark Reviewed button.
- Reviewed rows appear muted/low opacity.
- Empty state: no feedback to review.

Callouts:
- Negative feedback guides prompt and knowledge base improvements.
- Feedback can come from AI-only or AI plus human support sessions.
```

## Prompt 14 - Admin Cases and Handovers Page

```text
Create one detailed Balsamiq wireframe for the JumpStart Admin Cases & Handovers page, matching admin_panel/dashboard.html.

Use the same admin shell and left sidebar, with Cases & Handovers active.

Content:
- Page title "Cases & Handovers".
- Subtitle "Analytics on AI handovers, staff workload, and peak hours."
- Top row with two chart cards:
  - Handover Trend (30d) line chart.
  - Handover Reasons donut chart with legend/list.
- Staff Workload card with bar chart and staff names.
- Peak Chat Hours card with heatmap:
  - Day labels Mon, Tue, Wed, Thu, Fri, Sat, Sun.
  - 24 hourly columns.
  - Cell intensity shows chat volume.

Callouts:
- Handover reason, confidence, sentiment, and workload are support triage signals.
- Keep this as analytics, not a case-table page.
```

## Prompt 15 - Admin Audit Log Page

```text
Create one detailed Balsamiq wireframe for the JumpStart Admin Audit Log page, matching admin_panel/dashboard.html.

Use the same admin shell and left sidebar, with Audit Log active.

Content:
- Page title "Audit Log".
- Subtitle "Complete agent action history for each session."
- Search row: search input with icon and placeholder "Search by session ID, customer...", date input.
- Session accordion list.
- Session row: session icon, short session ID, created date, customer username, session state badge, expand/collapse icon.
- Expanded audit trail: action icon, action type, optional tool name badge, optional tool input summary, confidence-at-action badge, timestamp.
- Loading skeleton rows.
- Empty state: search-x icon and "No sessions found".

Callouts:
- Audit log supports debugging AI decisions and handover routing.
- Highlight low confidence, tool errors, and failed verification if shown.
```

## Recommended Necessary Set

If you have limited credits, generate these first:

1. Customer Home Page.
2. Products Listing Page.
3. Sign In Modal.
4. Register Modal.
5. Customer Account Dashboard.
6. Customer Chatbot UI.
7. Staff Support Dashboard.
8. Admin Overview Dashboard.
9. Admin Knowledge Base Page.

Then generate the remaining admin pages only if your submission needs deeper analytics detail.
