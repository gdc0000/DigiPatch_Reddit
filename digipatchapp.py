import streamlit as st
import datetime
import pandas as pd
import praw
import re
from praw.exceptions import APIException, PRAWException
import prawcore
import time
from functools import wraps
from typing import List, Optional, Generator

# ======================
# Configuration Constants
# ======================
MAX_RETRIES = 5
BASE_SLEEP_MULTIPLIER = 5

# ==============
# Data Storage
# ==============
class RedditDataStore:
    def __init__(self):
        self.posts = []
        self.comments = []

    @property
    def all_data(self):
        """Merge posts and comments if comments exist.
           When comments are downloaded, remove duplicate comments per post based on 'Comment Body'."""
        if self.comments:
            df_posts = pd.DataFrame(self.posts, columns=[
                "Subreddit", "Post ID", "Title", "Author", "Score", 
                "Comments Count", "Upvote Ratio", "URL", "Created", "Sort Method"
            ])
            df_comments = pd.DataFrame(self.comments, columns=[
                "Post ID", "Comment Author", "Comment Score", 
                "Comment Body", "Comment Timestamp"
            ])
            # Normalize comment bodies by stripping extra whitespace
            df_comments["Comment Body"] = df_comments["Comment Body"].str.strip()
            # Remove duplicate comments for the same post
            df_comments = df_comments.drop_duplicates(subset=["Post ID", "Comment Body"])
            merged = pd.merge(df_posts, df_comments, on="Post ID", how="right")
            return merged
        else:
            return pd.DataFrame(self.posts, columns=[
                "Subreddit", "Post ID", "Title", "Author", "Score", 
                "Comments Count", "Upvote Ratio", "URL", "Created", "Sort Method"
            ])

# ======================
# Helper Functions
# ======================
def add_footer() -> None:
    """Add a persistent footer to all pages"""
    st.markdown("---")
    st.markdown("### **Gabriele Di Cicco, PhD in Social Psychology**")
    st.markdown("""
    [GitHub](https://github.com/gdc0000) | 
    [ORCID](https://orcid.org/0000-0002-1439-5790) | 
    [LinkedIn](https://www.linkedin.com/in/gabriele-di-cicco-124067b0/)
    """)

def handle_rate_limit(func):
    """Decorator for handling Reddit API rate limits."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        retries = 0
        while retries < MAX_RETRIES:
            try:
                return func(*args, **kwargs)
            except prawcore.exceptions.TooManyRequests as e:
                sleep_time = BASE_SLEEP_MULTIPLIER * (retries + 1)
                st.warning(f"Rate limited. Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
                retries += 1
        st.error("Max retries reached. Skipping this request.")
        return None
    return wrapper

@handle_rate_limit
def initialize_reddit(client_id: str, client_secret: str, 
                     username: str, password: str) -> Optional[praw.Reddit]:
    """Initialize and return an authenticated Reddit instance."""
    try:
        return praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=f"DigiPatch data collection (by /u/{username})",
            check_for_async=False
        )
    except PRAWException as e:
        st.error(f"Authentication failed: {str(e)}")
        return None

def process_post(post: praw.models.Submission, subreddit: str, sorting_method: str) -> dict:
    """Extract post metadata."""
    return {
        "Subreddit": subreddit,
        "Post ID": post.id,
        "Title": post.title,
        "Author": str(post.author),
        "Score": post.score,
        "Comments Count": post.num_comments,
        "Upvote Ratio": post.upvote_ratio,
        "URL": post.url,
        "Created": datetime.datetime.utcfromtimestamp(post.created_utc),
        "Sort Method": sorting_method
    }

def process_comment(comment: praw.models.Comment) -> dict:
    """Extract comment details."""
    return {
        "Post ID": comment.submission.id,
        "Comment Author": str(comment.author) if comment.author else None,
        "Comment Score": comment.score,
        "Comment Body": comment.body,
        "Comment Timestamp": datetime.datetime.utcfromtimestamp(comment.created_utc)
    }

@handle_rate_limit
def get_post_comments(post: praw.models.Submission, comment_lim: int) -> List[dict]:
    """Retrieve a limited number of comments for a post."""
    try:
        post.comments.replace_more(limit=None)
        all_comments = [c for c in post.comments.list() if isinstance(c, praw.models.Comment)]
        comments = all_comments[:comment_lim]
        return [process_comment(c) for c in comments if c.body not in ["[deleted]", "[removed]"]]
    except Exception as e:
        st.error(f"Error retrieving comments: {str(e)}")
        return []

def collect_reddit_data(reddit: praw.Reddit,
                        subreddit: str,
                        sorting_methods: List[str],
                        post_limit: int,
                        collect_comments: bool,
                        comment_lim: int) -> Generator:
    """Main data collection generator."""
    total_operations = len(sorting_methods) * post_limit
    processed = 0
    subreddit_obj = reddit.subreddit(subreddit)
    for method in sorting_methods:
        try:
            posts = getattr(subreddit_obj, method)(limit=post_limit)
            for post in posts:
                # Process and yield post data
                post_data = process_post(post, subreddit, method)
                yield ("post", post_data)
                if collect_comments:
                    comments = get_post_comments(post, comment_lim)
                    for comment in comments:
                        yield ("comment", comment)
                processed += 1
                progress = processed / total_operations
                yield ("progress", progress)
        except PRAWException as e:
            st.error(f"Error retrieving posts with method '{method}': {str(e)}")

# ======================
# UI Components
# ======================
def credential_inputs() -> dict:
    """Collect Reddit API credentials."""
    st.header("🔑 Reddit API Credentials")
    return {
        "client_id": st.text_input("Client ID"),
        "client_secret": st.text_input("Client Secret", type="password"),
        "username": st.text_input("Username"),
        "password": st.text_input("Password", type="password")
    }

def data_parameters() -> dict:
    """Collect data collection parameters."""
    st.header("📊 Data Parameters")
    params = {}
    # Single subreddit input
    params["subreddit"] = st.text_input("Subreddit name", value="python")
    # Multiple sorting methods allowed
    params["sorting_methods"] = st.multiselect(
        "Sorting Methods",
        ["hot", "new", "top", "controversial", "rising"],
        default=["hot"]
    )
    # Number of posts to download
    params["post_limit"] = st.number_input("Number of posts to download", min_value=1, value=100, step=1)
    # Ask whether to download comments
    params["collect_comments"] = st.checkbox("Download comments as well")
    if params["collect_comments"]:
        params["comment_lim"] = st.number_input("Number of comments per post", min_value=1, value=10, step=1)
    else:
        # If not downloading comments, allow removal of duplicate posts by Post ID.
        params["remove_duplicates"] = st.checkbox("Remove duplicate posts (by Post ID)", value=True)
    return params

def generate_filename(subreddit: str) -> str:
    """Generate a filename based on subreddit and timestamp."""
    clean_sub = re.sub(r'\W+', '', subreddit)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"reddit_data_{clean_sub}_{timestamp}.csv"

# ======================
# Main App
# ======================
def main():
    # Initialize session state for data storage.
    if "data_store" not in st.session_state:
        st.session_state.data_store = RedditDataStore()
    
    # App Header
    st.image("DigiPatchLogo.png", width=700)
    st.title("WP4 DigiPatch: Reddit Data Collection")
    st.markdown("Collect Reddit data with resumable progress and smart rate limit handling.")
    
    # Gather user inputs.
    creds = credential_inputs()
    params = data_parameters()
    
    # Start data collection when the button is pressed.
    if st.button("🚀 Start/Resume Collection"):
        if not all(creds.values()):
            st.error("Missing API credentials!")
            return
            
        reddit = initialize_reddit(**creds)
        if not reddit:
            return
            
        data_gen = collect_reddit_data(
            reddit=reddit,
            subreddit=params["subreddit"],
            sorting_methods=params["sorting_methods"],
            post_limit=params["post_limit"],
            collect_comments=params["collect_comments"],
            comment_lim=params.get("comment_lim", 0)
        )
        
        progress_bar = st.progress(0)
        with st.spinner("Collecting data..."):
            try:
                for record in data_gen:
                    record_type, data = record
                    if record_type == "post":
                        st.session_state.data_store.posts.append(data)
                    elif record_type == "comment":
                        st.session_state.data_store.comments.append(data)
                    elif record_type == "progress":
                        progress_bar.progress(min(data, 1.0))
            except Exception as e:
                st.error(f"Collection failed: {str(e)}")
        st.success("Collection complete!")
    
    # Data Management and Display
    if st.session_state.data_store.posts:
        st.header("📦 Collected Data")
        if params["collect_comments"]:
            df = st.session_state.data_store.all_data
        else:
            df = pd.DataFrame(st.session_state.data_store.posts, columns=[
                "Subreddit", "Post ID", "Title", "Author", "Score", 
                "Comments Count", "Upvote Ratio", "URL", "Created", "Sort Method"
            ])
            if params.get("remove_duplicates", False):
                df = df.drop_duplicates(subset=["Post ID"])
        st.markdown(f"""
        - Total posts collected: **{len(st.session_state.data_store.posts)}**
        - Total comments collected: **{len(st.session_state.data_store.comments)}**
        """)
        st.dataframe(df.head(10), use_container_width=True)
        
        # Generate filename and provide a CSV download button.
        filename = generate_filename(params["subreddit"])
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Download CSV", data=csv, file_name=filename, mime="text/csv")
        
        if st.button("❌ Clear Data"):
            st.session_state.data_store = RedditDataStore()
            st.experimental_rerun()
    
    add_footer()

if __name__ == "__main__":
    main()
