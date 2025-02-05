import streamlit as st
import datetime
import pandas as pd
import praw
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
REDDIT_POST_LIMIT = 1000  # Maximum posts retrievable per request
COMMENT_LIMIT = None  # None retrieves all comments

# ==============
# Type Definitions
# ==============
class RedditPostData:
    def __init__(self):
        self.data = []

# ==============
# Core Functions
# ==============
def add_footer() -> None:
    """Add persistent footer to all pages"""
    st.markdown("---")
    st.markdown("### **Gabriele Di Cicco, PhD in Social Psychology**")
    st.markdown("""
    [GitHub](https://github.com/gdc0000) | 
    [ORCID](https://orcid.org/0000-0002-1439-5790) | 
    [LinkedIn](https://www.linkedin.com/in/gabriele-di-cicco-124067b0/)
    """)

def handle_rate_limit(func):
    """Decorator for handling Reddit API rate limits"""
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
    """Initialize and return authenticated Reddit instance"""
    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=f"DigiPatch data collection (by /u/{username})",
            check_for_async=False
        )
        return reddit if not reddit.read_only else None
    except PRAWException as e:
        st.error(f"Authentication failed: {str(e)}")
        return None

def process_comment(comment: praw.models.Comment) -> List:
    """Extract relevant data from a comment"""
    return [
        str(comment.author),
        comment.score,
        comment.body,
        datetime.datetime.utcfromtimestamp(comment.created_utc)
    ] if not comment.body == "[deleted]" else [None]*4

@handle_rate_limit
def get_comments(post: praw.models.Submission, 
                comment_method: str, 
                comment_lim: Optional[int] = None,
                comment_range: Optional[tuple] = None) -> List[List]:
    """Retrieve and process comments based on selected method"""
    try:
        post.comments.replace_more(limit=COMMENT_LIMIT)
        comments = post.comments.list()
        
        if comment_method == "limit":
            return [process_comment(c) for c in comments[:comment_lim]]
        elif comment_method == "range":
            start = comment_range[0] - 1 if comment_range else 0
            end = comment_range[1] if comment_range else None
            return [process_comment(c) for c in comments[start:end]]
        return [process_comment(c) for c in comments]
    except APIException as e:
        st.error(f"Comment error: {str(e)}")
        return []

def process_post(post: praw.models.Submission, 
                 subreddit: str, 
                 sorting_method: str,
                 collect_comments: bool,
                 comment_method: str,
                 comment_params: dict) -> List[List]:
    """Process individual post and its comments"""
    base_data = [
        subreddit,
        post.id,
        post.title,
        str(post.author),
        post.score,
        post.num_comments,
        post.upvote_ratio,
        post.url,
        datetime.datetime.utcfromtimestamp(post.created_utc),
        sorting_method
    ]
    
    if collect_comments:
        comments = get_comments(post, comment_method, **comment_params)
        return [base_data + comment for comment in comments] if comments else [base_data + [None]*4]
    return [base_data + [None]*4]

def collect_reddit_data(reddit: praw.Reddit,
                       subreddits: List[str],
                       sorting_methods: List[str],
                       post_limit: int,
                       collect_comments: bool,
                       comment_method: str,
                       comment_params: dict) -> Generator:
    """Main data collection generator"""
    total_posts = len(subreddits) * len(sorting_methods) * post_limit
    progress_bar = st.progress(0)
    
    for i, subreddit in enumerate(subreddits):
        try:
            subreddit_obj = reddit.subreddit(subreddit)
            for method in sorting_methods:
                try:
                    posts = getattr(subreddit_obj, method)(limit=post_limit)
                    for post in posts:
                        yield process_post(post, subreddit, method, 
                                         collect_comments, comment_method,
                                         comment_params)
                        progress = (i + 1) / total_posts
                        progress_bar.progress(min(progress, 1.0))
                except PRAWException as e:
                    st.error(f"Error in {method} posts: {str(e)}")
        except prawcore.exceptions.NotFound:
            st.error(f"Subreddit '{subreddit}' not found. Skipping...")

# ==============
# UI Components
# ==============
def credential_inputs() -> dict:
    """Collect Reddit API credentials"""
    st.header("🔑 Reddit API Credentials")
    return {
        "client_id": st.text_input("Client ID"),
        "client_secret": st.text_input("Client Secret", type="password"),
        "username": st.text_input("Username"),
        "password": st.text_input("Password", type="password")
    }

def data_parameters() -> dict:
    """Collect data collection parameters"""
    st.header("📊 Data Parameters")
    params = {
        "subreddits": [s.strip() for s in 
                      st.text_input('Subreddits (comma-separated)', '').split(',') 
                      if s.strip()],
        "sorting_methods": st.multiselect(
            'Sorting Methods',
            ['hot', 'new', 'top', 'controversial', 'rising'],
            default=['hot']
        ),
        "post_limit": st.select_slider(
            "Post Limit", 
            options=[10, 50, 100, 500, 1000],
            value=100
        ),
        "collect_comments": st.checkbox('Collect Comments', value=False)
    }
    
    if params["collect_comments"]:
        params["comment_method"] = st.radio(
            "Comment Retrieval Method",
            ["Limit", "Range", "All"],
            horizontal=True
        )
        params["comment_params"] = {}
        
        if params["comment_method"] == "Limit":
            params["comment_params"]["comment_lim"] = st.number_input(
                "Comments per Post", min_value=1, value=10
            )
        elif params["comment_method"] == "Range":
            cols = st.columns(2)
            with cols[0]:
                params["comment_params"]["comment_range"] = (
                    st.number_input("Start Index", min_value=1, value=1),
                    st.number_input("End Index", min_value=1, value=10)
                )
    
    return params

# ==============
# Main App
# ==============
def main():
    # Initialize session state
    if "collection" not in st.session_state:
        st.session_state.collection = RedditPostData()
    
    # App Header
    st.image("DigiPatchLogo.png", width=700)
    st.title("WP4 DigiPatch: Reddit Data Collection")
    st.markdown("Collect Reddit data with resumable progress and smart rate limit handling.")
    
    # Input Sections
    creds = credential_inputs()
    params = data_parameters()
    
    # Data Collection Control
    if st.button("🚀 Start/Resume Collection"):
        if not all(creds.values()):
            st.error("Missing API credentials!")
            return
            
        reddit = initialize_reddit(**creds)
        if not reddit:
            return
            
        data_gen = collect_reddit_data(
            reddit=reddit,
            subreddits=params["subreddits"],
            sorting_methods=params["sorting_methods"],
            post_limit=params["post_limit"],
            collect_comments=params["collect_comments"],
            comment_method=params.get("comment_method", "").lower(),
            comment_params=params.get("comment_params", {})
        )
        
        with st.status("Collecting data...", expanded=True) as status:
            try:
                for batch in data_gen:
                    st.session_state.collection.data.extend(batch)
                    st.write(f"Collected {len(batch)} records")
            except Exception as e:
                st.error(f"Collection failed: {str(e)}")
            finally:
                status.update(label="Collection complete!", state="complete")
    
    # Data Management
    if st.session_state.collection.data:
        st.header("📦 Collected Data")
        df = pd.DataFrame(
            st.session_state.collection.data,
            columns=[
                "Subreddit", "Post ID", "Title", "Author", "Score", 
                "Comments", "Upvote Ratio", "URL", "Created", "Sort Method",
                "Comment Author", "Comment Score", "Comment", "Comment Time"
            ]
        )
        st.dataframe(df.head(), use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "💾 Download CSV",
            data=csv,
            file_name="reddit_data.csv",
            mime="text/csv"
        )
        
        if st.button("❌ Clear Data"):
            st.session_state.collection = RedditPostData()
            st.rerun()
    
    add_footer()

if __name__ == "__main__":
    main()
