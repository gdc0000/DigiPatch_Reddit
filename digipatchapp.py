import streamlit as st
import datetime
import pandas as pd
import praw
from praw.exceptions import APIException
from tqdm import tqdm

def add_footer():
    st.markdown("---")
    st.markdown("### **Gabriele Di Cicco, PhD in Social Psychology**")
    st.markdown("""
    [GitHub](https://github.com/gdc0000) | 
    [ORCID](https://orcid.org/0000-0002-1439-5790) | 
    [LinkedIn](https://www.linkedin.com/in/gabriele-di-cicco-124067b0/)
    """)

# Function to initialize Reddit instance
def initialize_reddit(client_id, client_secret, username, password):
    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            password=password,
            user_agent="web_app",
            username=username,
            check_for_async=False
        )
        if reddit.read_only:
            st.error("Authentication failed: Reddit is in read-only mode.")
        return reddit
    except Exception as e:
        st.error(f"Error initializing Reddit: {e}")
        return None

# Function to collect Reddit posts and (optionally) comments in one long-shaped dataset.
def collect_reddit_data(reddit, subreddit_name, sorting_methods, limit, collect_comments=False):
    try:
        subreddit = reddit.subreddit(subreddit_name)
        combined_data = []
        
        # For each sorting method (e.g., 'hot', 'new', etc.)
        for sorting_method in sorting_methods:
            st.write(f"Collecting posts sorted by **{sorting_method}**...")
            posts = getattr(subreddit, sorting_method)(limit=limit)
            
            for post in tqdm(posts, desc=f"Collecting posts ({sorting_method})"):
                # Collect post-level information
                post_id = post.id
                post_title = post.title
                post_author = str(post.author)
                post_score = post.score
                post_num_comments = post.num_comments
                post_upvote_ratio = post.upvote_ratio
                post_url = post.url
                post_timestamp = datetime.datetime.utcfromtimestamp(post.created_utc)
                
                if collect_comments:
                    try:
                        # Retrieve all comments; skip "MoreComments" objects
                        post.comments.replace_more(limit=0)
                        comment_list = post.comments.list()
                    except Exception as e:
                        st.error(f"Error collecting comments for post {post.id}: {e}")
                        comment_list = []
                    
                    # If comments exist, create one row per comment.
                    if comment_list:
                        for comment in comment_list:
                            comment_author = str(comment.author) if comment.author else None
                            comment_score = comment.score
                            comment_body = comment.body
                            comment_timestamp = datetime.datetime.utcfromtimestamp(comment.created_utc)
                            
                            row = [
                                post_id, post_title, post_author, post_score, post_num_comments,
                                post_upvote_ratio, post_url, post_timestamp, sorting_method,
                                comment_author, comment_score, comment_body, comment_timestamp
                            ]
                            combined_data.append(row)
                    else:
                        # No comments found: add a row with comment fields set to None.
                        row = [
                            post_id, post_title, post_author, post_score, post_num_comments,
                            post_upvote_ratio, post_url, post_timestamp, sorting_method,
                            None, None, None, None
                        ]
                        combined_data.append(row)
                else:
                    # Not collecting comments: add one row with comment fields set to None.
                    row = [
                        post_id, post_title, post_author, post_score, post_num_comments,
                        post_upvote_ratio, post_url, post_timestamp, sorting_method,
                        None, None, None, None
                    ]
                    combined_data.append(row)
                    
        return combined_data
    except APIException as e:
        st.error(f"Reddit API Exception: {e}")
        return []
    except Exception as e:
        st.error(f"Error collecting data: {e}")
        return []

# Streamlit app
def main():
    # Display the logo at the top
    st.image("DigiPatchLogo.png", width=700)  # Replace with your actual logo file path
    st.title("WP4 DigiPatch: Reddit Data Collection")
    st.markdown("This tool allows users to collect Reddit post and comment data for analysis.")
    st.markdown("https://digipatch.eu/")

    # User credentials input
    st.header("Reddit API Credentials")
    client_id = st.text_input("Client ID")
    client_secret = st.text_input("Client Secret")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    # User input for subreddit and data collection parameters
    st.header("Subreddit and Data Parameters")
    subreddit_name = st.text_input('Subreddit Name', '')
    sorting_methods = st.multiselect(
        'Sorting Methods',
        ['hot', 'new', 'top', 'controversial', 'rising'],
        default=['hot']
    )
    limit = st.number_input('Number of Posts', min_value=1, max_value=1000, value=10)
    
    # Option to collect comments as well
    collect_comments = st.checkbox('Collect Comments', value=False)

    if st.button('Collect Data'):
        if client_id and client_secret and username and password:
            if subreddit_name:
                reddit = initialize_reddit(client_id, client_secret, username, password)
                if reddit:
                    with st.spinner('Collecting data...'):
                        data = collect_reddit_data(reddit, subreddit_name, sorting_methods, limit, collect_comments)
                        if data:
                            columns = [
                                "Post ID", "Post Title", "Post Author", "Post Score", "Post Num Comments",
                                "Post Upvote Ratio", "Post URL", "Post Timestamp", "Sorting Method",
                                "Comment Author", "Comment Score", "Comment Body", "Comment Timestamp"
                            ]
                            df = pd.DataFrame(data, columns=columns)
                            
                            st.write(f"Data collected: **{df.shape[0]} records**")
                            st.write(df.head())
                            
                            # Download the unified CSV file
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(label='Download CSV', data=csv, file_name=f'{subreddit_name}_data.csv')
            else:
                st.error('Please enter a subreddit name')
        else:
            st.error('Please enter all Reddit API credentials')
    
    # Footer Section
    add_footer()

if __name__ == "__main__":
    main()
