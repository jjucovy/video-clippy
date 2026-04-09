# Video CMS Frontend Architecture Refactor Plan

## Current Architecture Issues

### The SSR Trap
**Current Setup:**
- Astro SSR mode (`output: 'server'`) on Vercel serverless
- Every page request triggers:
  1. Vercel serverless function execution
  2. Server-side fetch to Django API
  3. HTML rendering with data baked in
  4. Client-side JS hydration for interactivity

**Why This Is Suboptimal:**
- 💰 **Cost**: Serverless invocations on every page view
- 🐌 **Latency**: User → Vercel → Django → Vercel → User (double hop)
- 🔄 **No Client Caching**: Can't leverage browser/CDN caching for API responses
- 🏗️ **Complexity**: Requires two servers (Vercel + Django) instead of one
- 🔀 **State Management**: Data exists in both HTML (SSR) and client state
- 🎭 **Component Limitations**: Can't use reactive components properly (hence the WETness we just fixed)

**Why It Was Done:**
- ✅ **SEO**: Video metadata in HTML for search engine indexing
- ✅ **Rich Snippets**: Performance history, performers, dates discoverable

## Architectural Options

### Option 1: Static Site + Client-Side Fetching (Simplest)
**Architecture:**
```
Static HTML (CDN) → Client JS → Django REST API
```

**Implementation:**
- Switch Astro to `output: 'static'`
- Build static pages at deploy time (or on-demand ISR)
- Client-side JS fetches data from Django API
- Use Web Components or lightweight framework (Lit, Svelte, etc.)

**Pros:**
- ✅ Cheapest (CDN only, no serverless)
- ✅ Fastest (no server-side processing)
- ✅ Simplest (one server: Django)
- ✅ Better client caching
- ✅ Reactive components work naturally

**Cons:**
- ❌ No SEO for dynamic content
- ❌ Search engines won't see video metadata
- ❌ Not viable for a public archive that needs discoverability

**Verdict:** ❌ **Not suitable** - SEO is critical for dance archive

---

### Option 2: Hybrid Static + ISR (Incremental Static Regeneration)
**Architecture:**
```
Static HTML (pre-rendered) → CDN → Revalidate on-demand
Client JS hydrates for interactivity
```

**Implementation:**
- Pre-render all pages at build time
- Serve from CDN
- Revalidate/rebuild pages when content changes (webhook from Django)
- Client-side hydration for interactive features

**Pros:**
- ✅ Full SEO (static HTML)
- ✅ CDN performance
- ✅ Lower serverless costs (only on content changes)
- ✅ Reactive components possible

**Cons:**
- ⚠️ Build time increases with content (hundreds of pieces × clips)
- ⚠️ Stale data between rebuilds (acceptable for archival content)
- ⚠️ Requires webhook integration Django → Vercel

**Verdict:** ✅ **Good option** - Best of both worlds for mostly-static archives

---

### Option 3: Islands Architecture (Astro's Sweet Spot)
**Architecture:**
```
Static HTML (SEO) + Interactive Islands (client components)
```

**Implementation:**
- Astro pages with static content rendering
- Interactive components (carousel, video player) as "islands"
- Use `client:load`, `client:visible`, `client:idle` directives
- Islands can be Svelte/React/Vue components
- Fetch data client-side within islands

**Example:**
```astro
---
// Server-side: fetch for SEO
const piece = await get('pieces', id);
const clips = await list(`clips?piece=${id}`);
---

<Layout title={piece.title}>
  <!-- Static content for SEO -->
  <h1>{piece.title}</h1>
  <p>{piece.choreographer?.name}</p>

  <!-- Interactive island: loads/hydrates client-side -->
  <ClipCarousel
    client:load
    initialData={clips}
    pieceId={id}
  />
</Layout>
```

**Pros:**
- ✅ Full SEO (initial HTML has all metadata)
- ✅ Reactive components work properly
- ✅ Partial hydration (only interactive parts load JS)
- ✅ Can mix static/dynamic content
- ✅ Component composition works naturally

**Cons:**
- ⚠️ Still requires serverless for initial render (but cached better)
- ⚠️ More complex than pure static

**Verdict:** ✅ **Excellent option** - Leverages Astro's strengths

---

### Option 4: Django Templates + Web Components
**Architecture:**
```
Django (templates + REST API) → Web Components for interactivity
```

**Implementation:**
- Django renders HTML templates (like old-school server rendering)
- Embed data in HTML via JSON scripts or data attributes
- Web Components (custom elements) for interactive features
- No frontend build step (or minimal one)

**Example:**
```html
<!-- Django template -->
<h1>{{ piece.title }}</h1>
<clip-carousel data-piece-id="{{ piece.id }}">
  <!-- Pre-rendered clips for SEO -->
  {% for clip in clips %}
    <div class="clip" data-clip-id="{{ clip.id }}">...</div>
  {% endfor %}
</clip-carousel>

<script type="module">
  // Web Component definition
  import { ClipCarousel } from '/static/components/clip-carousel.js';
</script>
```

**Pros:**
- ✅ Full SEO (Django templates)
- ✅ One server (Django only)
- ✅ No serverless costs
- ✅ Web Components are framework-agnostic
- ✅ Progressive enhancement friendly

**Cons:**
- ⚠️ Django templates less pleasant than Astro/React
- ⚠️ Less tooling than modern frameworks
- ⚠️ Two paradigms (Django templates + JS)

**Verdict:** ✅ **Pragmatic option** - Simplifies infrastructure significantly

---

### Option 5: Full Framework SPA + SSR (Next.js/SvelteKit/Nuxt)
**Architecture:**
```
Framework SSR → Serverless → Client hydration
```

**Implementation:**
- Replace Astro with Next.js/SvelteKit/Nuxt
- Server-side render on serverless
- Client-side hydration and routing
- Full reactive components

**Pros:**
- ✅ Full SEO
- ✅ Rich ecosystem
- ✅ Best DX for complex apps
- ✅ Component composition works perfectly

**Cons:**
- ❌ Most expensive (serverless on every page)
- ❌ Heaviest JS bundle
- ❌ Overkill for a content site
- ❌ Still requires two servers (Vercel + Django)

**Verdict:** ❌ **Overkill** - Current Astro SSR problems but worse

---

## Recommended Path Forward

### Phase 1: Islands Architecture (Quick Win)
**Timeline:** 1-2 weeks

1. **Keep Astro, switch to Islands**
   - Maintain current SSR for SEO
   - Convert interactive components to islands:
     - `<ClipCarousel client:load>`
     - `<VideoPlayer client:visible>`
   - Use Svelte or Lit for islands (lightweight)

2. **Benefits:**
   - ✅ Fixes component composition issues properly
   - ✅ Reduces JS bundle (only load what's needed)
   - ✅ Maintains SEO
   - ✅ Minimal migration effort

### Phase 2: Evaluate Static + ISR (Medium-term)
**Timeline:** 1-2 months

1. **Measure content velocity**
   - How often do clips/performances change?
   - Can you tolerate 5-15 min staleness?

2. **If content is mostly stable:**
   - Switch to `output: 'static'` with ISR
   - Set up webhooks: Django → Vercel rebuild
   - Cache static pages on CDN
   - Use client-side fetching for real-time needs

3. **Benefits:**
   - ✅ Massive cost savings (CDN only)
   - ✅ Better performance (no cold starts)
   - ✅ Still maintains SEO

### Phase 3: Consider Django Templates + Web Components (Long-term)
**Timeline:** 3-6 months

1. **If Vercel costs become prohibitive:**
   - Migrate frontend to Django templates
   - Build Web Components for interactivity
   - Deploy Django on single server (DigitalOcean, Fly.io, Railway)
   - Use standard web hosting (cheaper than serverless)

2. **Benefits:**
   - ✅ Simplest infrastructure (one server)
   - ✅ Lowest cost (no serverless, no CDN)
   - ✅ Full control
   - ✅ Standards-based (no framework lock-in)

---

## Decision Matrix

| Option | SEO | Cost | Performance | DX | Complexity |
|--------|-----|------|-------------|-----|------------|
| **Current SSR** | ✅ | 💰💰 | 🐌🐌 | ⚠️ | 🔧🔧 |
| **Static + Client** | ❌ | 💰 | ⚡⚡⚡ | ✅ | 🔧 |
| **Static + ISR** | ✅ | 💰 | ⚡⚡⚡ | ✅ | 🔧🔧 |
| **Islands** | ✅ | 💰💰 | ⚡⚡ | ✅ | 🔧 |
| **Django + WC** | ✅ | 💰 | ⚡⚡ | ⚠️ | 🔧 |
| **Full SPA** | ✅ | 💰💰💰 | 🐌🐌 | ✅ | 🔧🔧🔧 |

---

## Technical Implementation Notes

### Islands Architecture Migration

**Step 1: Create island components**
```typescript
// src/components/ClipCarousel.svelte (or .tsx, .vue)
<script lang="ts">
  import { onMount } from 'svelte';
  import { initializeVideoJsPlayer } from '@/utils/videojs-player';

  export let clips: Clip[];
  export let pieceTitle: string;

  let currentIndex = 0;
  let players = new Map();

  onMount(async () => {
    // Initialize players client-side
    for (let i = 0; i < clips.length; i++) {
      const player = await initializeVideoJsPlayer({...});
      players.set(i, player);
    }
  });
</script>

<div class="carousel">
  {#each clips as clip, i}
    <div class:hidden={i !== currentIndex}>
      <video id="player-{i}" ...>
    </div>
  {/each}
</div>
```

**Step 2: Use in Astro page**
```astro
---
import ClipCarousel from '@/components/ClipCarousel.svelte';
const clips = await list(`clips?piece=${id}`);
---

<Layout title={piece.title}>
  <!-- SEO content rendered server-side -->
  <h1>{piece.title}</h1>

  <!-- Interactive island -->
  <ClipCarousel
    client:load
    clips={clips}
    pieceTitle={piece.title}
  />
</Layout>
```

### Static + ISR Migration

**Step 1: Astro config**
```javascript
export default defineConfig({
  output: 'hybrid', // Mix static and SSR
  adapter: vercel({
    isr: {
      expiration: 60 * 15, // 15 minutes
    }
  })
});
```

**Step 2: Page config**
```astro
---
export const prerender = true; // Static generation
export const revalidate = 900; // Revalidate every 15 min

const piece = await get('pieces', id);
const clips = await list(`clips?piece=${id}`);
---
```

**Step 3: Django webhook**
```python
# archive/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
import requests

@receiver(post_save, sender=Clip)
def revalidate_vercel(sender, instance, **kwargs):
    # Trigger Vercel revalidation
    webhook_url = f"https://api.vercel.com/v1/integrations/deploy/{HOOK_ID}"
    requests.post(webhook_url)
```

### Web Components Migration

**Step 1: Create web component**
```typescript
// static/components/clip-carousel.ts
class ClipCarousel extends HTMLElement {
  connectedCallback() {
    const clips = JSON.parse(this.dataset.clips);
    this.render(clips);
    this.initPlayers();
  }

  async initPlayers() {
    const videos = this.querySelectorAll('video');
    // Use shared videojs utility
  }
}

customElements.define('clip-carousel', ClipCarousel);
```

**Step 2: Django template**
```html
<!-- archive/templates/piece_detail.html -->
<h1>{{ piece.title }}</h1>

<clip-carousel data-clips='{{ clips_json|safe }}'>
  {% for clip in clips %}
    <div class="clip-wrapper" data-clip-id="{{ clip.id }}">
      <video id="player-{{ clip.id }}"...>
  {% endfor %}
</clip-carousel>

<script type="module" src="{% static 'components/clip-carousel.js' %}"></script>
```

---

## Migration Risks & Mitigation

### Risk 1: SEO Regression
**Mitigation:**
- Test with Google Search Console before/after
- Validate structured data markup
- Monitor search rankings during transition

### Risk 2: Performance Regression
**Mitigation:**
- Measure Core Web Vitals before/after
- Use Lighthouse CI in deployment pipeline
- A/B test with portion of traffic

### Risk 3: Feature Breakage
**Mitigation:**
- Comprehensive integration tests
- Visual regression testing (Percy, Chromatic)
- Gradual rollout (feature flags)

---

## Cloudflare Stream Clips API Investigation

### Future Enhancement: Real Clips vs. Timeline Hacks

**Current Implementation:**
- Clips are client-side only (JavaScript enforces start/end times)
- Full source video loaded, timeline shows full duration
- User sees they're watching a segment, not a standalone clip

**Cloudflare Stream Clips API:**
- Creates reference-based clips (not full copies)
- Each clip gets its own UID and playback URL
- Timeline shows only clip duration
- Appears as completely standalone video

**Storage Cost Question (NEEDS VERIFICATION):**
- **Expected behavior:** Clips are reference-based, no storage duplication
  - 60min source + 10min clip = 60min total storage (not 70min)
  - Similar to YouTube clips (pointer to original bytes)
- **Need to verify:**
  1. Check Cloudflare docs: https://developers.cloudflare.com/stream/edit-videos/create-clips/
  2. Create test clip and monitor dashboard storage metrics
  3. Contact Cloudflare support for billing confirmation
- **Risk:** If clips DO duplicate storage, costs could double with heavy clipping

**API Example:**
```python
# archive/utils/cloudflare.py
def create_cloudflare_clip(video_uid, start_seconds, end_seconds, clip_name):
    """Create a real clip using Cloudflare Stream's clip API"""
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/stream/clip"

    payload = {
        "uid": video_uid,
        "startTimeSeconds": start_seconds,
        "endTimeSeconds": end_seconds,
        "creator": clip_name,
        "allowedOrigins": ["*"]
    }

    response = requests.post(url, headers=headers, json=payload)
    # Returns a NEW clip with its own UID and playback URL
    clip_data = response.json()
    return clip_data['result']['uid'], clip_data['result']['playback']
```

**Migration Plan:**
1. Add `cloudflare_clip_uid` field to Clip model (nullable for backward compat)
2. Add `cloudflare_clip_playback_url` field
3. Create management command to generate clips for existing Clip records
4. Update admin to call API when creating new clips
5. Frontend: Use clip playback URL if available, fall back to timestamp hack

**TODO BEFORE IMPLEMENTING:**
- ✅ Verify storage billing behavior with test clip
- ✅ Confirm cost model with Cloudflare support
- ⚠️ Current workaround: Frontend timeline hack (implemented below)

---

## Conclusion

**Immediate Action (Now):**
- ✅ Already fixed WETness with shared utilities
- Continue using current SSR architecture

**Next Steps (1-2 months):**
1. Evaluate Islands architecture
2. Measure content update frequency
3. Prototype ISR approach

**Long-term (6-12 months):**
- If costs are manageable: stick with Islands
- If costs are high: migrate to Django templates + Web Components
- Continuously monitor SEO impact

**Key Principle:**
> SEO is non-negotiable for a public archive. Choose the simplest architecture that maintains search visibility while minimizing operational costs.
