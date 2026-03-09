---
name: htmx-components
description: "HTMX + Tailwind + Alpine.js patterns for ColabMusic frontend. Use this skill when creating templates, views that return partials, HTMX interactions, Tailwind styling, or any frontend work. Also use when the user mentions UI, templates, pages, components, or frontend."
---

# HTMX Components — ColabMusic

## Core Principles

- Server-Side Rendering first — Django templates render everything
- HTMX for dynamic updates — NO React, Vue, or other JS frameworks
- Alpine.js ONLY for small client-side state (dropdowns, modals, tabs)
- Tailwind CSS for all styling — no custom CSS files unless absolutely necessary

## Base Template Pattern

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}ColabMusic{% endblock %}</title>
  <link href="{% static 'css/output.css' %}" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@2.0.4"></script>
  <script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
</head>
<body class="bg-gray-50 text-gray-900" hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
  {% include "components/navbar.html" %}
  <main class="max-w-7xl mx-auto px-4 py-8">
    {% block content %}{% endblock %}
  </main>
  {% block scripts %}{% endblock %}
</body>
</html>
```

## HTMX Partial View Pattern

```python
# views.py
def project_vote(request, project_id):
    """HTMX endpoint — returns only the vote count fragment."""
    project = get_object_or_404(Project, id=project_id)
    # ... handle vote logic ...
    return render(request, "components/vote_button.html", {"project": project})
```

```html
<!-- templates/components/vote_button.html -->
<div id="vote-{{ project.id }}" class="flex items-center gap-2">
  <button
    hx-post="{% url 'rankings:vote' project.id %}"
    hx-target="#vote-{{ project.id }}"
    hx-swap="outerHTML"
    class="text-red-500 hover:text-red-700 transition"
  >
    ♥ {{ project.vote_count }}
  </button>
</div>
```

## IMPORTANT: CSRF with HTMX

ALWAYS include the CSRF token header on the body tag:
```html
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

This ensures ALL HTMX POST/PUT/DELETE requests include the token automatically.

## Common HTMX Patterns

### Infinite Scroll (Feed)
```html
<div id="project-feed">
  {% for project in projects %}
    {% include "components/project_card.html" %}
  {% endfor %}
  
  {% if has_next %}
  <div hx-get="{% url 'projects:feed' %}?page={{ next_page }}"
       hx-trigger="revealed"
       hx-swap="afterend"
       hx-target="this">
    <span class="loading loading-spinner"></span>
  </div>
  {% endif %}
</div>
```

### Audio Player Status Polling
```html
<!-- Poll until audio processing is complete -->
<div id="audio-status-{{ beat.id }}"
     {% if beat.processing_status != 'ready' %}
     hx-get="{% url 'audio:status' beat.id %}"
     hx-trigger="every 3s"
     hx-swap="outerHTML"
     {% endif %}>
  {% if beat.processing_status == 'ready' %}
    {% include "components/audio_player.html" with track=beat %}
  {% elif beat.processing_status == 'processing' %}
    <div class="animate-pulse flex gap-2 items-center text-gray-500">
      <svg class="animate-spin h-5 w-5">...</svg>
      Procesando audio...
    </div>
  {% elif beat.processing_status == 'failed' %}
    <p class="text-red-500">Error al procesar el audio. Intenta de nuevo.</p>
  {% endif %}
</div>
```

### Search with Debounce
```html
<input type="search"
       name="q"
       placeholder="Buscar canciones, artistas, géneros..."
       hx-get="{% url 'search:results' %}"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#search-results"
       class="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-red-500">

<div id="search-results"></div>
```

### Tab Navigation
```html
<div x-data="{ tab: 'lyrics' }" class="space-y-4">
  <nav class="flex gap-4 border-b">
    <button @click="tab = 'lyrics'" :class="tab === 'lyrics' ? 'border-b-2 border-red-500 text-red-500' : 'text-gray-500'"
            class="pb-2 font-medium">Letras</button>
    <button @click="tab = 'beats'" :class="tab === 'beats' ? 'border-b-2 border-red-500 text-red-500' : 'text-gray-500'"
            class="pb-2 font-medium">Beats</button>
    <button @click="tab = 'vocals'" :class="tab === 'vocals' ? 'border-b-2 border-red-500 text-red-500' : 'text-gray-500'"
            class="pb-2 font-medium">Voces</button>
  </nav>
  
  <div x-show="tab === 'lyrics'" hx-get="{% url 'projects:lyrics-list' project.slug %}" hx-trigger="intersect once">
    Cargando...
  </div>
  <!-- ... more tabs -->
</div>
```

## Component Library

Reusable components go in `templates/components/`. Each is a standalone partial:

| Component | File | Description |
|-----------|------|-------------|
| Project Card | `project_card.html` | Card for feed/search results |
| Audio Player | `audio_player.html` | Wavesurfer player with controls |
| Vote Button | `vote_button.html` | HTMX upvote/downvote |
| User Badge | `user_badge.html` | Avatar + name + role icons |
| Role Tag | `role_tag.html` | Colored tag per role |
| Status Badge | `status_badge.html` | Project status indicator |
| Empty State | `empty_state.html` | Friendly empty state message |

## Tailwind Color Scheme

```
Primary (dark):   #1A1A2E  → text, headers
Accent (red):     #E94560  → CTAs, active states, waveform
Secondary (blue): #0F3460  → links, secondary actions
Background:       #F5F5F5  → page background
Surface:          #FFFFFF  → cards, modals
```

## Responsive Rules

- Mobile-first: start with `sm:` breakpoints
- Feed: single column on mobile, 2 columns on `md:`, 3 on `lg:`
- Audio player: full width always
- Navigation: hamburger menu on mobile with Alpine.js toggle
