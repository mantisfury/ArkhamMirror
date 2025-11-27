nch# 🚀 ArkhamMirror: Public Release Strategy (v0.1)

This document outlines the roadmap to a clean, secure, and impactful public launch.

## ✅ Phase 1: Security & Code Hygiene (The "Clean Sweep")

*Before showing the world, ensure the house is clean.*

- [ ] **Secret Scanning**:
  - Run `trufflehog` or `git-secrets` to ensure no API keys, passwords, or `.env` files are in the git history.
  - **Action**: Add `.env` to `.gitignore` (already done, but verify).
  - **Action**: Check `config.yaml` for any hardcoded paths or keys.
- [ ] **PII Removal**:
  - Ensure no personal names, emails, or IP addresses are in the code comments or sample data (except the fictional "Phantom Shipping" case).
- [ ] **Dependency Audit**:
  - Run `pip audit` to check for known vulnerabilities in `requirements.txt`.
  - Lock versions in `requirements.txt` to ensure reproducibility.
- [ ] **License File**:
  - Ensure `LICENSE` (MIT) is present and correct.
- [ ] **"Works on My Machine" Check**:
  - Test the install process on a fresh VM or a friend's computer to ensure no hidden dependencies exist.

## 🎨 Phase 2: Assets & Documentation (The "Polish")

*Make it look professional and easy to use.*

- [ ] **Brand Identity**:
  - **Logo**: Create a logo (Square for GitHub avatar, Banner for README).
    - *Concept*: A magnifying glass over a shattered mirror, or a digital eye.
  - **Social Preview**: Create an `og:image` for social media sharing.
- [ ] **Documentation Upgrade**:
  - **README.md**: Needs a "Hero Image" and a 30-second "Hook" (Why use this?).
  - **User Guide**: A PDF or Wiki page for non-technical users (Journalists).
  - **Developer Guide**: How to write a new Worker or Strategy.
- [ ] **Demo Content**:
  - Record a 60-second GIF/Video of the "Phantom Shipping" case ingestion and search.
  - *Why*: People don't read; they watch.

## 🤝 Phase 3: Community & Sustainability (The "Foundation")

*Set up the channels for help and funding.*

- [ ] **Funding Setup**:
  - Create a `.github/FUNDING.yml` file.
  - **Options**: GitHub Sponsors (best for code), Open Collective (best for transparency), Ko-fi (casual).
- [ ] **Communication Channels**:
  - **Discord/Matrix**: Create a community server for support.
  - **GitHub Discussions**: Enable this repo feature for Q&A.
- [ ] **Contribution Guidelines**:
  - Update `CONTRIBUTING.md` with a "Good First Issue" tag policy to attract newbies.

## 📢 Phase 4: The Launch (Outreach)

*Get it in front of the right people.*

### **Who to Contact (The Target Audience)**

1. **Investigative Journalism Tech**:
    - **Bellingcat**: They love open-source investigative tools.
    - **GIJN (Global Investigative Journalism Network)**: They have a "Tools" section.
    - **ICIJ (Panama Papers team)**: The gold standard.
2. **Open Source Intelligence (OSINT)**:
    - **r/OSINT** (Reddit).
    - **OSINTCurious**.
3. **Tech Community**:
    - **Hacker News**: Post with title "Show HN: ArkhamMirror – Local-first AI for investigative journalists".
    - **r/SelfHosted**: They love local-first tools.

### **The Pitch (Draft)**
>
> "Investigative journalists are drowning in documents, but existing AI tools require uploading sensitive leaks to the cloud. ArkhamMirror is a local-first, air-gapped alternative. It uses local LLMs (Qwen-VL) and OCR to index, analyze, and connect entities across PDFs, emails, and images—without a single byte leaving your laptop. Open source and available now."

## 🗓️ Launch Checklist

- [ ] Codebase audited & cleaned.
- [ ] Logo & Banner added to README.
- [ ] `FUNDING.yml` created.
- [ ] Demo GIF recorded.
- [ ] "Phantom Shipping" tutorial verified.
- [ ] Release v0.1 tag on GitHub.
- [ ] Post to Hacker News / Reddit.
- [ ] Email/DM key contacts.
