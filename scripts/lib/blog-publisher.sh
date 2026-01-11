#!/usr/bin/env bash
#
# Cortex Blog Publisher
# Automated blog post creation and publishing system
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BLOG_ROOT="/Users/ryandahlberg/Projects/blog"
BLOG_POSTS_DIR="$BLOG_ROOT/src/content/posts"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to generate blog post filename
generate_filename() {
    local title="$1"
    local date=$(date +%Y-%m-%d)
    local slug=$(echo "$title" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
    echo "${date}-${slug}.md"
}

# Function to validate blog post frontmatter
validate_frontmatter() {
    local file="$1"

    # Check required fields
    if ! grep -q "^title:" "$file"; then
        print_error "Missing 'title' in frontmatter"
        return 1
    fi

    if ! grep -q "^category:" "$file"; then
        print_error "Missing 'category' in frontmatter"
        return 1
    fi

    if ! grep -q "^description:" "$file"; then
        print_error "Missing 'description' in frontmatter"
        return 1
    fi

    if ! grep -q "^date:" "$file"; then
        print_error "Missing 'date' in frontmatter"
        return 1
    fi

    print_success "Frontmatter validation passed"
    return 0
}

# Function to validate hero image exists
validate_hero_image() {
    local file="$1"

    # Extract hero image path from frontmatter
    local hero_path=$(grep "image:" "$file" | head -1 | awk '{print $2}')

    if [ -z "$hero_path" ]; then
        print_warning "No hero image specified in frontmatter"
        return 1
    fi

    # Convert /images/posts/ to actual file path
    local full_path="$BLOG_ROOT/public${hero_path}"

    if [ ! -f "$full_path" ]; then
        print_warning "Hero image not found: $full_path"
        print_info "You may need to create the hero image before publishing"
        return 1
    fi

    print_success "Hero image found: $(basename "$full_path")"
    return 0
}

# Function to create blog post from template
create_blog_post() {
    local title="$1"
    local category="${2:-AI & ML}"
    local description="$3"
    local tags="$4"
    local series="${5:-Cortex}"

    local filename=$(generate_filename "$title")
    local filepath="$BLOG_POSTS_DIR/$filename"

    if [ -f "$filepath" ]; then
        print_warning "Blog post already exists: $filename"
        echo "$filepath"
        return 0
    fi

    local date=$(date -u +%Y-%m-%dT%H:%M:%S.000Z)

    # Create frontmatter
    cat > "$filepath" << EOF
---
title: "$title"
category: $category
description: "$description"
date: $date
author:
  name: Ryan Dahlberg
  avatar: /logo-avatar.svg
featured: true
tags:
$tags
series: $series
seriesOrder: 999
hero:
  image: /images/posts/${filename%.md}-hero.svg
  generated: false
---

# $title

[Content goes here]

EOF

    print_success "Created blog post: $filename"
    echo "$filepath"
}

# Function to publish blog post (commit and push)
publish_blog_post() {
    local filepath="$1"
    local commit_msg="${2:-docs: Add new blog post}"

    cd "$BLOG_ROOT"

    # Check if file exists
    if [ ! -f "$filepath" ]; then
        print_error "Blog post not found: $filepath"
        return 1
    fi

    # Validate before publishing
    if ! validate_frontmatter "$filepath"; then
        print_error "Validation failed, cannot publish"
        return 1
    fi

    # Validate hero image (warning only, non-blocking)
    validate_hero_image "$filepath" || print_warning "Consider adding a hero image for better SEO"

    print_info "Publishing blog post to repository..."

    # Add file
    git add "$filepath"

    # Commit
    git commit -m "$commit_msg"

    # Push
    git push origin main

    print_success "Blog post published!"
    print_info "Live at: https://ry-ops.dev/posts/$(basename "$filepath" .md)"
}

# Function to list recent blog posts
list_blog_posts() {
    local limit="${1:-10}"
    print_info "Recent blog posts:"
    ls -lt "$BLOG_POSTS_DIR" | head -n $((limit + 1)) | tail -n $limit | awk '{print $NF}'
}

# Main function
main() {
    local command="${1:-help}"

    case "$command" in
        create)
            if [ $# -lt 4 ]; then
                print_error "Usage: blog-publisher.sh create <title> <description> <tags>"
                exit 1
            fi
            create_blog_post "$2" "AI & ML" "$3" "$4"
            ;;
        validate)
            if [ $# -lt 2 ]; then
                print_error "Usage: blog-publisher.sh validate <filepath>"
                exit 1
            fi
            validate_frontmatter "$2"
            ;;
        check-image)
            if [ $# -lt 2 ]; then
                print_error "Usage: blog-publisher.sh check-image <filepath>"
                exit 1
            fi
            validate_hero_image "$2"
            ;;
        publish)
            if [ $# -lt 2 ]; then
                print_error "Usage: blog-publisher.sh publish <filepath> [commit_message]"
                exit 1
            fi
            publish_blog_post "$2" "${3:-docs: Add new blog post}"
            ;;
        list)
            list_blog_posts "${2:-10}"
            ;;
        help)
            cat << 'HELP'
Cortex Blog Publisher

Usage: blog-publisher.sh <command> [options]

Commands:
  create <title> <description> <tags>  Create new blog post
  validate <filepath>                   Validate blog post frontmatter
  check-image <filepath>                Check if hero image exists
  publish <filepath> [message]          Commit and push blog post
  list [n]                              List n recent blog posts
  help                                  Show this help

Examples:
  # Create a new blog post
  blog-publisher.sh create "My Amazing Post" "Description" "  - AI\n  - ML"

  # Validate a blog post
  blog-publisher.sh validate /path/to/blog/post.md

  # Check hero image
  blog-publisher.sh check-image /path/to/blog/post.md

  # Publish a blog post
  blog-publisher.sh publish /path/to/blog/post.md "docs: Add inception mode post"

  # List recent blog posts
  blog-publisher.sh list 5
HELP
            ;;
        *)
            print_error "Unknown command: $command"
            $0 help
            exit 1
            ;;
    esac
}

# Run main if executed directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
