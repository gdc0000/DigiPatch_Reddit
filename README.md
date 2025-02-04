# WP4 DigiPatch: Reddit Data Collection App

**WP4 DigiPatch: Reddit Data Collection** is a Streamlit-based application designed to collect Reddit posts and comments across multiple subreddits. This tool is built for researchers and analysts who need to harvest Reddit data with customizable collection parameters, adaptive rate limiting, and options for both post- and comment-level data retrieval.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [File Structure](#file-structure)
- [Development Container](#development-container)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

---

## Overview

This app leverages the [PRAW](https://praw.readthedocs.io/) library to interact with the Reddit API, allowing you to:
- Authenticate using your Reddit API credentials.
- Collect posts from multiple subreddits using various sorting methods (e.g., hot, new, top).
- Optionally collect comments from each post with flexible retrieval methods (Limit, Range, or Maximum).
- Manage API rate limiting using an adaptive sleep strategy.
- Store and resume data collection sessions with Streamlit's session state.
- Download the collected data as a CSV file for further analysis.

---

## Features

- **Reddit API Integration:**  
  Authenticate and interact with Reddit using client credentials.
  
- **Subreddit Data Collection:**  
  Specify one or multiple subreddits and choose sorting methods to control data collection.
  
- **Customizable Post & Comment Retrieval:**  
  - Set a limit on the number of posts per subreddit per sorting method.
  - Optionally collect comments with flexible options (limit, range, or maximum).
  
- **Adaptive Rate Limiting:**  
  Automatically handles rate-limit issues with an adaptive sleep function to retry API calls.
  
- **Session Persistence:**  
  Leverages Streamlit's session state to store collected data and allow resumption of interrupted sessions.
  
- **Downloadable Output:**  
  Download the resulting dataset as a CSV file for offline analysis.

- **Developer-Ready:**  
  Includes a [devcontainer](.devcontainer/devcontainer.json) configuration to help you quickly set up your development environment using Visual Studio Code or GitHub Codespaces.

---

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/digipatch-reddit-data-collection.git
   cd digipatch-reddit-data-collection
   ```

2. **(Optional) Create a Virtual Environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**

   All required packages are listed in the [`requirements.txt`](./requirements.txt) file. Install them using:

   ```bash
   pip install -r requirements.txt
   ```

---

## Usage

1. **Run the Streamlit App**

   Launch the application by running:

   ```bash
   streamlit run digipatchapp.py
   ```

2. **Enter Reddit API Credentials**

   - Provide your **Client ID**, **Client Secret**, **Username**, and **Password**.
   - The app will initialize a connection with Reddit using these credentials.

3. **Configure Data Collection Parameters**

   - **Subreddits:**  
     Enter one or more subreddit names (comma-separated).
     
   - **Sorting Methods:**  
     Select from available options (e.g., hot, new, top, controversial, rising).
     
   - **Post Limit:**  
     Choose whether to use a fixed limit or collect the maximum available posts per subreddit per sorting method.
     
   - **Comment Collection (Optional):**  
     Enable comment collection and select your preferred method (Limit, Range, or Maximum). Specify additional parameters as needed.
     
   - **Sleep Time:**  
     Set the number of seconds to wait between API calls to help manage rate limits.

4. **Start or Resume Data Collection**

   Click the **Start/Resume Data Collection** button to begin retrieving data.  
   - Progress is shown via a progress bar or textual feedback.
   - Collected data is stored in the session state so you can resume collection if needed.

5. **Download Your Data**

   Once the collection is complete, preview the data and download it as a CSV file.

6. **Clear Collected Data**

   Use the **Clear Collected Data** button to reset the session state if you need to start over.

---

## File Structure

```
.
├── digipatchapp.py              # Main Streamlit application for Reddit data collection
├── requirements.txt             # Required Python packages
└── .devcontainer
    └── devcontainer.json        # VS Code/Dev Container configuration for development environments
```

---

## Development Container

The repository includes a [devcontainer configuration](.devcontainer/devcontainer.json) that sets up a development environment with:
- A pre-configured Python 3.11 container.
- Essential VS Code extensions (Python and Pylance).
- Automatic package installation based on the `requirements.txt`.
- A post-attach command that automatically starts the Streamlit app.

This setup is ideal for using Visual Studio Code or GitHub Codespaces to ensure a consistent development environment.

---

## Contributing

Contributions are welcome! If you have suggestions, bug fixes, or improvements:
1. Fork the repository.
2. Create a new branch for your changes.
3. Commit and push your modifications.
4. Open a pull request with a detailed description of your changes.

---

## License

This project is open-source and available under the [MIT License](LICENSE).

---

## Contact

**Gabriele Di Cicco, PhD in Social Psychology**  
[GitHub](https://github.com/gdc0000) | [ORCID](https://orcid.org/0000-0002-1439-5790) | [LinkedIn](https://www.linkedin.com/in/gabriele-di-cicco-124067b0/)

---

Happy Data Collecting!
