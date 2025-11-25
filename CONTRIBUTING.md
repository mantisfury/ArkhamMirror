# Contributing to ArkhamMirror

First off, thank you for considering contributing to ArkhamMirror! It's people like you that make open source software such an amazing place to learn, inspire, and create.

## 🤝 How Can I Contribute?

### 1. Reporting Bugs

This section guides you through submitting a bug report for ArkhamMirror. Following these guidelines helps maintainers and the community understand your report, reproduce the behavior, and find related reports.

* **Use a clear and descriptive title** for the issue to identify the problem.
* **Describe the exact steps which reproduce the problem** in as many details as possible.
* **Provide specific examples** to demonstrate the steps. Include links to files or GitHub projects, or copy/pasteable snippets, which you use in those examples.

### 2. Suggesting Enhancements

This section guides you through submitting an enhancement suggestion for ArkhamMirror, including completely new features and minor improvements to existing functionality.

* **Use a clear and descriptive title** for the issue to identify the suggestion.
* **Provide a step-by-step description of the suggested enhancement** in as many details as possible.
* **Explain why this enhancement would be useful** to most ArkhamMirror users.

### 3. Pull Requests

The process is straightforward:

1. **Fork** the repo on GitHub.
2. **Clone** the project to your own machine.
3. **Commit** changes to your own branch.
4. **Push** your work back up to your fork.
5. Submit a **Pull Request** so that we can review your changes.

## 💻 Development Setup

1. **Clone the repository**

    ```bash
    git clone https://github.com/YourUsername/ArkhamMirror.git
    cd ArkhamMirror
    ```

2. **Set up the environment**

    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    ```

3. **Configure Environment Variables**
    Copy `.env.example` to `.env` and update the values.

4. **Run the Stack**

    ```bash
    docker compose up -d  # Starts DB and Qdrant
    streamlit run streamlit_app/Search.py
    ```

## 🎨 Coding Style

* We use **Python** for the backend.
* Please try to follow **PEP 8** guidelines.
* Add comments to your code where necessary.
* If you add a new feature, please add a test case if possible.

## ❓ Questions?

Feel free to open a Discussion or an Issue on GitHub if you have any questions!
