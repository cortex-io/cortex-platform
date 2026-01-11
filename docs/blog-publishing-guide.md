# Cortex Blog Publishing System

Automated blog post creation and publishing for the ry-ops/blog repository.

## Overview

The Cortex Blog Publishing System provides tools to automate blog post creation, validation, and publishing. It's integrated into Cortex's coordination system and can be used standalone or as part of automated workflows.

## Quick Start

### Create a Blog Post

```bash
./scripts/lib/blog-publisher.sh create \
  "My Amazing Post Title" \
  "A compelling description of the post" \
  "  - AI\n  - Machine Learning\n  - Cortex"
```

This creates a new blog post in `/Users/ryandahlberg/Projects/blog/src/content/posts/` with:
- Proper frontmatter (title, date, author, tags, etc.)
- Auto-generated filename based on date and title
- Ready-to-edit template

### Validate a Blog Post

```bash
./scripts/lib/blog-publisher.sh validate \
  /Users/ryandahlberg/Projects/blog/src/content/posts/2025-12-04-my-post.md
```

Checks that all required frontmatter fields are present.

### Check Hero Image

```bash
./scripts/lib/blog-publisher.sh check-image \
  /Users/ryandahlberg/Projects/blog/src/content/posts/2025-12-04-my-post.md
```

Verifies that the hero image specified in frontmatter exists in the blog repository.

### Publish a Blog Post

```bash
./scripts/lib/blog-publisher.sh publish \
  /Users/ryandahlberg/Projects/blog/src/content/posts/2025-12-04-my-post.md \
  "docs: Add blog post about autonomous development"
```

This will:
1. Validate the blog post frontmatter
2. Check hero image exists (warning only)
3. Git add the file
4. Git commit with the provided message
5. Git push to main branch

### List Recent Blog Posts

```bash
./scripts/lib/blog-publisher.sh list 10
```

Shows the 10 most recent blog posts.

## Blog Post Format

All blog posts must include this frontmatter:

```yaml
---
title: "Your Post Title"
category: AI & ML  # or other category
description: "SEO-friendly description"
date: 2025-12-04T22:30:00.000Z
author:
  name: Ryan Dahlberg
  avatar: /logo-avatar.svg
featured: true  # or false
tags:
  - Tag 1
  - Tag 2
  - Tag 3
series: Cortex  # optional
seriesOrder: 5  # optional
hero:
  image: /images/posts/your-post-hero.svg
  generated: false
---
```

## Integration with Cortex Coordination

### Blog Post Worker

Create a blog post task in Cortex:

```json
{
  "task_id": "blog-post-inception-mode",
  "type": "documentation:blog",
  "priority": "medium",
  "title": "Create blog post about inception mode",
  "description": "Document the EUI dashboard autonomous build",
  "deliverables": [
    "Blog post in /Users/ryandahlberg/Projects/blog/src/content/posts/",
    "Frontmatter validation passed",
    "Published to main branch"
  ]
}
```

### Automated Blog Publishing

The blog publisher can be triggered by:
1. Manual execution
2. Cortex worker tasks
3. GitHub Actions (future)
4. Scheduled publishing (future)

## Directory Structure

```
cortex/
├── scripts/lib/blog-publisher.sh   # Main blog publishing script
├── docs/blog-publishing-guide.md   # This guide
└── blog-posts/                      # Draft blog posts (not published)

blog/ (separate repository)
└── src/content/posts/               # Published blog posts
```

## Workflow

1. **Draft** - Write blog post in `cortex/blog-posts/` or create directly in blog repo
2. **Validate** - Use `blog-publisher.sh validate` to check frontmatter
3. **Publish** - Use `blog-publisher.sh publish` to commit and push
4. **Deploy** - Blog automatically rebuilds and deploys (Astro)

## Common Tasks

### Create and Publish in One Go

```bash
# Create blog post
BLOG_FILE=$(./scripts/lib/blog-publisher.sh create \
  "Cortex Achievement" \
  "How we built X using Y" \
  "  - Achievement\n  - Technical")

# Edit the file (manually or via script)
# ... edit content ...

# Validate
./scripts/lib/blog-publisher.sh validate "$BLOG_FILE"

# Publish
./scripts/lib/blog-publisher.sh publish "$BLOG_FILE" "docs: Add Cortex achievement post"
```

### Check Recent Posts

```bash
# List last 5 posts
./scripts/lib/blog-publisher.sh list 5

# Find specific post
ls -la /Users/ryandahlberg/Projects/blog/src/content/posts/ | grep "inception"
```

## Best Practices

1. **Always validate before publishing** - Catch frontmatter errors early
2. **Check hero images exist** - Use `check-image` command to verify hero images
3. **Use descriptive commit messages** - `docs: Add post about X` format
4. **Include relevant tags** - Helps with SEO and categorization
5. **Set appropriate series** - Groups related posts together
6. **Write compelling descriptions** - Used for SEO and social sharing
7. **Create hero images** - Place SVG/image files in `/public/images/posts/`

## Future Enhancements

- [ ] AI-powered blog post generation from Cortex events
- [x] Hero image validation (implemented!)
- [ ] Automatic hero image generation from blog content
- [ ] SEO optimization suggestions
- [ ] Social media post generation
- [ ] Scheduled publishing queue
- [ ] Draft management system
- [ ] Blog analytics integration

## Troubleshooting

### Permission Denied

```bash
chmod +x ./scripts/lib/blog-publisher.sh
```

### Blog Repository Not Found

Update `BLOG_ROOT` in `blog-publisher.sh`:
```bash
BLOG_ROOT="/Users/ryandahlberg/Projects/blog"
```

### Git Push Failed

Ensure you have push access to the blog repository:
```bash
cd /Users/ryandahlberg/Projects/blog
git remote -v
```

## Examples

See `blog-posts/eui-dashboard-inception-mode.md` for a complete example of a Cortex blog post documenting an autonomous development achievement.

## Support

For issues or questions:
- Check existing blog posts for format examples
- Review validation errors carefully
- Ensure blog repository is accessible
- Verify git credentials are configured

---

*This blogging system was built by Cortex to automate one of the most common tasks: celebrating achievements and sharing knowledge.*
