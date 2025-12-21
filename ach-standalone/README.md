# ArkhamMirror ACH

A privacy-first Analysis of Competing Hypotheses (ACH) tool based on Richard Heuer's structured analytic methodology.

**Part of the [ArkhamMirror](https://github.com/mantisfury/ArkhamMirror) investigation platform.**

[![Support on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/arkhammirror)

![ACH Infographic](AHC_infograph.png)

## What is ACH?

Analysis of Competing Hypotheses (ACH) is a structured analytic technique developed by Richards J. Heuer Jr. at the CIA. It counteracts confirmation bias by systematically trying to **disprove** all possible theories, rather than prove one.

**Watch this video for a complete explanation of ACH:**

[![ACH Explained](https://img.youtube.com/vi/oYoUh6ttW8A/0.jpg)](https://youtu.be/oYoUh6ttW8A)

[Watch on YouTube: What is ACH and How to Use It](https://youtu.be/oYoUh6ttW8A)

## Features

- **8-Step ACH Methodology**: Complete implementation of Heuer's ACH process
- **Privacy First**: All data stored locally in your browser's localStorage
- **Zero Network Calls**: Works completely offline after initial load
- **Export Options**: Save analyses as JSON, Markdown, or PDF reports
- **Sensitivity Analysis**: Test how robust your conclusions are
- **Version History**: Create snapshots to track analysis evolution
- **Optional AI Assistance**: Connect to local or cloud LLM providers for AI-powered suggestions

## Quick Start

### Run from GitHub Pages

**[Launch ACH Tool](https://mantisfury.github.io/ArkhamMirror/ach/)** - Zero installation required. Your data stays in your browser.

> **Note**: When running from GitHub Pages, only cloud LLM providers will work (see [LLM Integration](#llm-integration) below).

### Run Locally (Maximum Privacy + Full Features)

1. Download this folder
2. Install dependencies: `npm install`
3. Start dev server: `npm run dev`
4. Open http://localhost:5173

Or build for production:
```bash
npm run build
# Serve the dist/ folder with any static file server
```

## The 8 Steps of ACH

1. **Identify Hypotheses** - List all possible explanations, including unlikely ones
2. **Gather Evidence** - Collect facts, testimony, documents, assumptions, and arguments
3. **Create Matrix** - Rate how consistent each evidence item is with each hypothesis
4. **Analyze Diagnosticity** - Identify which evidence distinguishes between hypotheses
5. **Refine Matrix** - Review and update ratings based on diagnosticity analysis
6. **Draw Conclusions** - Identify the hypothesis with the fewest inconsistencies
7. **Sensitivity Analysis** - Test if removing any single evidence would change the conclusion
8. **Report & Milestones** - Set future indicators and export your analysis

## Rating Scale

- **CC** (Very Consistent) - Strong support for the hypothesis
- **C** (Consistent) - Supports the hypothesis
- **N** (Neutral) - Neither supports nor contradicts
- **I** (Inconsistent) - Contradicts the hypothesis
- **II** (Very Inconsistent) - Strongly contradicts the hypothesis

## LLM Integration

The app supports optional LLM integration for AI-assisted analysis. AI can help with:
- Suggesting alternative hypotheses
- Recommending evidence items
- Rating evidence consistency with hypotheses
- Providing analysis insights
- Suggesting future milestones to watch

### Cloud Providers (Work Everywhere)

Cloud LLM providers work both on GitHub Pages and when running locally:

| Provider | Endpoint | API Key Required |
|----------|----------|------------------|
| OpenAI | `https://api.openai.com/v1` | Yes |
| Groq | `https://api.groq.com/openai/v1` | Yes (free tier available) |
| OpenRouter | `https://openrouter.ai/api/v1` | Yes |
| Anthropic | `https://api.anthropic.com/v1` | Yes |
| Any OpenAI-compatible API | Your endpoint URL | Varies |

**To configure:**
1. Click the gear icon in the top right
2. Enable LLM Integration
3. Select your provider or enter a custom endpoint
4. Enter your API key
5. Select a model (e.g., `gpt-4o-mini`, `llama-3.1-70b-versatile`)

> **Privacy Note**: Your API key is stored only in your browser's localStorage and is sent only to your selected provider.

### Local Providers (Maximum Privacy)

Local LLM providers keep everything on your machine - no data leaves your computer.

| Provider | Default Endpoint | Notes |
|----------|------------------|-------|
| LM Studio | `http://localhost:1234/v1` | OpenAI-compatible API |
| Ollama | `http://localhost:11434/v1` | OpenAI-compatible mode |

#### Requirements for Local LLM

**Important**: Local LLM integration has specific requirements:

1. **Must run ACH locally** - Due to browser security (mixed content blocking), HTTPS pages (like GitHub Pages) cannot make requests to HTTP localhost endpoints. You must:
   - Clone/download this repository
   - Run `npm install` then `npm run dev`
   - Access via `http://localhost:5173`

2. **CORS must be enabled** - Your local LLM server must allow cross-origin requests:
   - **LM Studio**: CORS is enabled by default when you start the local server
   - **Ollama**: Run with `OLLAMA_ORIGINS="*" ollama serve` or set the environment variable

3. **Server must be running** - Start your LLM server before using AI features:
   - **LM Studio**: Load a model and click "Start Server" (default port 1234)
   - **Ollama**: Run `ollama serve` and ensure you've pulled a model (e.g., `ollama pull llama3.1`)

#### Recommended Local Models

For best results with ACH analysis, use instruction-tuned models:
- **LM Studio**: Qwen 2.5 7B/14B, Llama 3.1 8B, Mistral 7B
- **Ollama**: `llama3.1`, `qwen2.5`, `mistral`

### Troubleshooting LLM Issues

| Issue | Solution |
|-------|----------|
| "CORS error" | Enable CORS on your local server, or run ACH locally |
| "Failed to fetch" | Check that your LLM server is running |
| "Connection refused" | Verify the endpoint URL and port |
| "Unauthorized" | Check your API key (cloud providers) |
| No AI suggestions appear | Verify model name matches what's loaded/available |

## Export Options

- **JSON** - Full analysis data for backup/import
- **Markdown** - Human-readable report
- **PDF** - Professional printable report with matrix, rankings, and conclusions

## About ArkhamMirror

This ACH tool is part of the **ArkhamMirror** project - an air-gapped, AI-powered investigation platform for journalists and researchers.

ArkhamMirror provides:
- Local AI chat with your documents (Offline RAG)
- Semantic search across document collections
- Knowledge graph visualization
- Automatic timeline extraction
- Contradiction detection
- And much more...

**Learn more**: [ArkhamMirror on GitHub](https://github.com/mantisfury/ArkhamMirror)

## Support the Project

If this tool helps you in your investigations, consider supporting the project:

[![Support on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/arkhammirror)

## Tech Stack

- React 18 + TypeScript
- Vite (build tool)
- Zustand (state management with localStorage persistence)
- TailwindCSS (styling)
- Lucide React (icons)
- jsPDF + jspdf-autotable (PDF generation)

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Type check
npm run build

# Preview production build
npm run preview
```

## License

Open source - use freely for personal, educational, or commercial purposes.

---

Based on Richard Heuer's Analysis of Competing Hypotheses methodology as described in "Psychology of Intelligence Analysis" (CIA, 1999).
