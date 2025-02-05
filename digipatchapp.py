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
REDDIT_POST_LIMIT = 1000
COMMENT_LIMIT = None

# ==============
# Type Definitions
# ==============
class RedditDataStore:
    def __init__(self):
        self.posts = []
        self.comments = []
        
    @property
    def all_data(self):
        """Merge posts and comments into long format"""
        df_posts = pd.DataFrame(self.posts, columns=[
            "Subreddit", "Post ID", "Title", "Author", "Score", 
            "Comments Count", "Upvote Ratio", "URL", "Created", "Sort Method"
        ])
        
        df_comments = pd.DataFrame(self.comments, columns=[
            "Post ID", "Comment Author", "Comment Score", 
            "Comment Body", "Comment Timestamp"
        ])
        
        return pd.merge(df_posts, df_comments, on="Post ID", how="left")

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

def process_post(post: praw.models.Submission, 
                subreddit: str, 
                sorting_method: str) -> dict:
    """Extract post metadata"""
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
    """Process individual comment"""
    return {
        "Post ID": comment.submission.id,
        "Comment Author": str(comment.author) if comment.author else None,
        "Comment Score": comment.score,
        "Comment Body": comment.body,
        "Comment Timestamp": datetime.datetime.utcfromtimestamp(comment.created_utc)
    }

@handle_rate_limit
def get_post_comments(post: praw.models.Submission, 
                     comment_method: str, 
                     comment_lim: Optional[int] = None,
                     comment_range: Optional[tuple] = None) -> List[dict]:
    """Retrieve and process comments based on selected method"""
    try:
        post.comments.replace_more(limit=COMMENT_LIMIT)
        all_comments = post.comments.list()
        
        if comment_method == "limit":
            comments = all_comments[:comment_lim]
        elif comment_method == "range":
            start = comment_range[0] - 1 if comment_range else 0
            end = comment_range[1] if comment_range else None
            comments = all_comments[start:end]
        else:
            comments = all_comments
            
        return [process_comment(c) for c in comments if not c.body == "[deleted]"]
    except APIException as e:
        st.error(f"Comment error: {str(e)}")
        return []

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
                    for post_idx, post in enumerate(posts):
                        # Always store post metadata
                        post_data = process_post(post, subreddit, method)
                        yield ("post", post_data)
                        
                        # Store comments if enabled
                        if collect_comments:
                            comments = get_post_comments(post, comment_method, **comment_params)
                            for comment in comments:
                                yield ("comment", comment)
                        
                        # Update progress
                        progress = ((i + 1) * (post_idx + 1)) / total_posts
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
    if "data_store" not in st.session_state:
        st.session_state.data_store = RedditDataStore()
    
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
                for record_type, data in data_gen:
                    if record_type == "post":
                        st.session_state.data_store.posts.append(data)
                    elif record_type == "comment":
                        st.session_state.data_store.comments.append(data)
                    st.write(f"Collected {record_type}: {data.get('Post ID', '')}")
            except Exception as e:
                st.error(f"Collection failed: {str(e)}")
            finally:
                status.update(label="Collection complete!", state="complete")
    
    # Data Management
    if st.session_state.data_store.posts:
        st.header("📦 Collected Data")
        df = st.session_state.data_store.all_data
        
        # Show post count with comment stats
        st.markdown(f"""
        - Total posts collected: **{len(st.session_state.data_store.posts)}**
        - Total comments collected: **{len(st.session_state.data_store.comments)}**
        - Posts without comments: **{df[df['Comment Body'].isna()].shape[0]}**
        """)
        
        st.dataframe(df.head(10), use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "💾 Download CSV",
            data=csv,
            file_name="reddit_data.csv",
            mime="text/csv"
        )
        
        if st.button("❌ Clear Data"):
            st.session_state.data_store = RedditDataStore()
            st.rerun()
    
    add_footer()

if __name__ == "__main__":
    main()
