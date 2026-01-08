/**
 * HTML sanitization utilities using DOMPurify.
 *
 * Use these functions to sanitize any user-generated or external HTML
 * before rendering with dangerouslySetInnerHTML.
 */

import DOMPurify from 'dompurify';

/**
 * Sanitize HTML content with a safe set of allowed tags.
 * Use this for rich text content like reports, notes, etc.
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'b', 'i', 'u',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'blockquote', 'pre', 'code', 'table', 'thead', 'tbody',
      'tr', 'th', 'td', 'a', 'span', 'div', 'mark', 'sub', 'sup',
    ],
    ALLOWED_ATTR: ['class', 'href', 'target', 'rel'],
    // Force safe link behavior
    ADD_ATTR: ['target'],
    FORCE_BODY: true,
  });
}

/**
 * Sanitize HTML for search result highlighting.
 * Only allows basic formatting tags used for highlighting matches.
 */
export function sanitizeHighlight(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['mark', 'em', 'strong', 'b', 'span'],
    ALLOWED_ATTR: ['class'],
  });
}

/**
 * Sanitize HTML for markdown-rendered content.
 * Allows a broader set of tags typically produced by markdown renderers.
 */
export function sanitizeMarkdown(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'b', 'i', 'u', 's', 'del',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'blockquote', 'pre', 'code', 'table', 'thead', 'tbody',
      'tr', 'th', 'td', 'a', 'span', 'div', 'mark', 'hr',
      'img', 'figure', 'figcaption', 'sub', 'sup',
    ],
    ALLOWED_ATTR: ['class', 'href', 'target', 'rel', 'src', 'alt', 'title', 'width', 'height'],
    ADD_ATTR: ['target'],
  });
}

/**
 * Strip all HTML tags and return plain text.
 * Use this when you need text-only content.
 */
export function stripHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [],
    ALLOWED_ATTR: [],
  });
}
